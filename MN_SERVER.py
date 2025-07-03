import socket
import threading
import struct
import psycopg2
import os
import time
import uuid
import logging
import sys
import functools
import random

# ========== NETWORKING AND SERVER ==========

HOST = '211.233.10.5'  # Listen on all, or use your real public/local IP
TCP_PORT = 18000
SERVER = '211.233.10.5' 
SERVER_PORT = 18001
CLIENT_GAMEPLAY_PORT = 3658
DEBUG = True

# Global registry for sessions
sessions = {}
sessions_lock = threading.Lock()
lobby_ready_counts = {}
lobby_ready_lock = threading.Lock()
lobby_echo_results = {}   # key: (channel_db_id, lobby_name) -> dict of pid: True/False (ready/dc)
lobby_echo_lock = threading.Lock()
# Dict of last-packet times: key = player_id, value = timestamp
last_packet_times = {}
last_packet_lock = threading.Lock()

# POSTGRES DATABASE CONNECTION
DB_CONN = None

def get_db_conn():
    global DB_CONN
    if DB_CONN is None:
        DB_CONN = psycopg2.connect(
            host=os.environ.get("PG_HOST"),
            dbname=os.environ.get("PG_DBNAME"),
            user=os.environ.get("PG_USER"),
            password=os.environ.get("PG_PASSWORD")
        )
    return DB_CONN

if DEBUG:
    # Clear the trace log on each script run
    if os.path.exists("trace.log"):
        open("trace.log", "w").close()
    logging.basicConfig(filename="trace.log", level=logging.DEBUG)
    logging.getLogger("importlib").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

def trace_calls(func):
    if not DEBUG:
        return func  # Return the original function unwrapped
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logging.debug(f"[CALL] {func.__name__} args={args} kwargs={kwargs}")
        result = func(*args, **kwargs)
        logging.debug(f"[RETURN] {func.__name__} result={result}")
        return result
    return wrapper

print("-----------------------------------")
print("Mystic Nights Private Server v0.9.5")
print("-----------------------------------")

class Server:
    def __init__(self, id, name, ip_address, player_count=0, availability=0):
        self.id = id
        self.name = name
        self.ip_address = ip_address
        self.player_count = player_count
        self.availability = availability

    @classmethod
    def from_row(cls, row):
        return cls(*row)

class ServerManager:

    @classmethod
    def get_server_by_ip(cls, ip_address):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, ip_address, player_count, availability FROM servers WHERE ip_address = %s", (ip_address,))
            row = cur.fetchone()
            return Server.from_row(row) if row else None

    @classmethod
    def get_server_id_by_ip(cls, ip_address):
        server = cls.get_server_by_ip(ip_address)
        return server.id if server else None

    @classmethod
    def get_servers(cls):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, ip_address, player_count, availability FROM servers;")
            return [Server.from_row(row) for row in cur.fetchall()]

    @classmethod
    def print_server_table(cls):
        servers = cls.get_servers()
        print("-" * 60)
        print("{:<4} {:<16} {:<20} {:<10}".format("Idx", "Name", "IP (String)", "Status"))
        print("-" * 60)
        status_map = {-1: "알수없음", 0: "적음", 1: "보통", 2: "많음"}
        for idx, s in enumerate(servers):
            status_str = status_map.get(s.availability, str(s.availability))
            print("{:<4} {:<16} {:<20} {:<10}".format(idx, s.name, s.ip_address, status_str))
        print("-" * 60)

    @classmethod
    def init_server(cls):
        #On initial startup, remove all lobbies whose name does NOT contain 'TestRoom' (case-sensitive).
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM lobbies WHERE name NOT LIKE %s", ('%TestRoom%',))
            deleted = cur.rowcount
            conn.commit()
            print(f"[INIT] Cleared {deleted} non-TestRoom lobbies from database.")

class Player:
    def __init__(self, id, player_id, password, rank=1, created_at=None):
        self.id = id
        self.player_id = player_id
        self.password = password
        self.rank = rank
        self.created_at = created_at

    @classmethod
    def from_row(cls, row):
        return cls(*row)

class Channel:
    def __init__(self, id, server_id, channel_index, player_count=0):
        self.id = id
        self.server_id = server_id
        self.channel_index = channel_index
        self.player_count = player_count

    @classmethod
    def from_row(cls, row):
        return cls(*row)

class Lobby:
    def __init__(
        self, id, channel_id, idx_in_channel, name, password, player_count=0, status=1, map=1, leader=None,
        player1_id=None, player1_character=None, player1_status=None,
        player2_id=None, player2_character=None, player2_status=None,
        player3_id=None, player3_character=None, player3_status=None,
        player4_id=None, player4_character=None, player4_status=None
    ):
        self.id = id
        self.channel_id = channel_id
        self.idx_in_channel = idx_in_channel
        self.name = name
        self.password = password
        self.player_count = player_count
        self.status = status
        self.map = map
        self.leader = leader
        self.player_ids = [player1_id, player2_id, player3_id, player4_id]
        self.player_characters = [player1_character, player2_character, player3_character, player4_character]
        self.player_statuses = [player1_status, player2_status, player3_status, player4_status]

    @classmethod
    def from_row(cls, row):
        # row: (id, channel_id, idx_in_channel, name, password, player_count, status, map, leader, 
        # player1_id, player1_character, player1_status, ... player4_id, player4_character, player4_status)
        return cls(
            id=row[0],
            channel_id=row[1],
            idx_in_channel=row[2],
            name=row[3],
            password=row[4],
            player_count=row[5],
            status=row[6],
            map=row[7],
            leader=row[8],
            player1_id=row[9], player1_character=row[10], player1_status=row[11],
            player2_id=row[12], player2_character=row[13], player2_status=row[14],
            player3_id=row[15], player3_character=row[16], player3_status=row[17],
            player4_id=row[18], player4_character=row[19], player4_status=row[20]
        )
    
    @classmethod
    def as_short_tuple(self):
        """Used for lobby list: returns (idx_in_channel, player_count, name, password, status)"""
        return (self.idx_in_channel, self.player_count, self.name, self.password, self.status)

class PlayerManager:

    @classmethod
    def load_player_from_db(cls, player_id):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, player_id, password, rank FROM players WHERE player_id = %s", (player_id,))
            row = cur.fetchone()
            if row:
                return Player(*row)
        return None

    @classmethod
    def create_player(cls, player_id, password, rank=0x01):
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO players (player_id, password, rank) VALUES (%s, %s, %s)",
                    (player_id, password, rank)
                )
                conn.commit()
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return None
        return Player(player_id, password, rank)

    @classmethod
    def remove_player(cls, player_id):
        conn = get_db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM players WHERE player_id = %s", (player_id,))
                conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] General DB error during player deletion: {e}")
            return False
        
    @classmethod
    def add_rank_points(cls, player_id, points, max_rank=199):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE players SET rank = LEAST(rank + %s, %s) WHERE player_id = %s",
                (points, max_rank, player_id)
            )
            conn.commit()

class ChannelManager:
    @classmethod
    def get_channel_db_id(cls, server_id, channel_index):
        """Returns the primary key (id) in channels table for a given server_id and channel_index."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM channels WHERE server_id = %s AND channel_index = %s",
                (server_id, channel_index)
            )
            row = cur.fetchone()
            return row[0] if row else None

    @classmethod
    def get_channels_for_server(cls, server_id):
        """Return a list of Channel objects for this server_id."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, server_id, channel_index, player_count FROM channels WHERE server_id = %s;", (server_id,))
            return [Channel.from_row(row) for row in cur.fetchall()]

    @classmethod
    def get_channel(cls, server_id, channel_index):
        """Return Channel object for a given server_id and channel_index."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, server_id, channel_index, player_count FROM channels WHERE server_id = %s AND channel_index = %s;",
                        (server_id, channel_index))
            row = cur.fetchone()
            return Channel.from_row(row) if row else None

    @classmethod
    def print_channel_table(cls, server_id=None):
        """Prints all channels, or just those for a given server_id."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            if server_id is None:
                cur.execute("SELECT id, server_id, channel_index, player_count FROM channels;")
            else:
                cur.execute("SELECT id, server_id, channel_index, player_count FROM channels WHERE server_id = %s;", (server_id,))
            rows = cur.fetchall()
        print("-" * 50)
        print("{:<8} {:<8} {:<8} {:<12}".format("SrvID", "ChIdx", "ID", "Players"))
        print("-" * 50)
        for row in sorted(rows, key=lambda c: (c[1], c[2])):  # Sort by server_id, channel_index
            _, srv_id, ch_idx, pc = row
            print("{:<8} {:<8} {:<8} {:<12}".format(srv_id, ch_idx, row[0], pc))
        print("-" * 50)

    @classmethod
    def increment_player_count(cls, server_id, channel_index):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE channels SET player_count = player_count + 1 "
                "WHERE server_id = %s AND channel_index = %s;",
                (server_id, channel_index)
            )
            conn.commit()

    @classmethod
    def decrement_player_count(cls, server_id, channel_index):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE channels SET player_count = GREATEST(player_count - 1, 0) "
                "WHERE server_id = %s AND channel_index = %s;",
                (server_id, channel_index)
            )
            conn.commit()

class LobbyManager:
    @classmethod
    def get_lobbies_for_channel(cls, channel_db_id):
        """Returns list of Lobby objects for given channel DB id."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, channel_id, idx_in_channel, name, password, player_count, status, map, leader,
                       player1_id, player1_character, player1_status,
                       player2_id, player2_character, player2_status,
                       player3_id, player3_character, player3_status,
                       player4_id, player4_character, player4_status
                FROM lobbies
                WHERE channel_id = %s
                ORDER BY idx_in_channel ASC
            """, (channel_db_id,))
            return [Lobby.from_row(row) for row in cur.fetchall()]

    @classmethod
    def get_lobby_by_name(cls, lobby_name, channel_db_id):
        """Return Lobby object matching name+channel."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, channel_id, idx_in_channel, name, password, player_count, status, map, leader,
                       player1_id, player1_character, player1_status,
                       player2_id, player2_character, player2_status,
                       player3_id, player3_character, player3_status,
                       player4_id, player4_character, player4_status
                FROM lobbies
                WHERE name = %s AND channel_id = %s
            """, (lobby_name, channel_db_id))
            row = cur.fetchone()
            return Lobby.from_row(row) if row else None

    @classmethod
    def set_player_character(cls, channel_db_id, player_id, character):
        """Set the character field for the specified player in their lobby."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, player1_id, player2_id, player3_id, player4_id
                   FROM lobbies WHERE channel_id = %s""",
                (channel_db_id,)
            )
            for row in cur.fetchall():
                lobby_id = row[0]
                for idx, pid in enumerate(row[1:5], 1):
                    if pid == player_id:
                        cur.execute(
                            f"""UPDATE lobbies
                                SET player{idx}_character=%s
                                WHERE id=%s""",
                            (character, lobby_id)
                        )
                        conn.commit()
                        return True
        return False

    @classmethod
    def set_lobby_map(cls, channel_db_id, lobby_name, map_id):
        """Set the selected map for the lobby."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE lobbies SET map=%s WHERE channel_id=%s AND name=%s",
                (map_id, channel_db_id, lobby_name)
            )
            conn.commit()

    @classmethod
    def get_lobby_name_for_player(cls, channel_db_id, player_id):
        """Return the lobby name in this channel that contains the player, or None."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT name FROM lobbies
                   WHERE channel_id=%s AND
                         (player1_id=%s OR player2_id=%s OR player3_id=%s OR player4_id=%s)""",
                (channel_db_id, player_id, player_id, player_id, player_id)
            )
            row = cur.fetchone()
            return row[0] if row else None

    @classmethod
    def create_lobby_db(cls, lobby_name, password, channel_db_id, player_id):
        """Creates a lobby in the database, returns True if successful, False if full or exists."""
        # Check if lobby already exists in channel
        rows = cls.get_lobbies_for_channel(channel_db_id)
        for lobby in rows:
            if lobby.name == lobby_name:
                print(f"[ERROR] Lobby '{lobby_name}' already exists in channel {channel_db_id}")
                return False
        # Find next available idx_in_channel
        used_indices = {lobby.idx_in_channel for lobby in rows}
        for idx_in_channel in range(20):
            if idx_in_channel not in used_indices:
                break
        else:
            print(f"[ERROR] No more lobby slots available in channel {channel_db_id}")
            return False

        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO lobbies
                   (channel_id, idx_in_channel, name, password, status, player1_id, player1_character, player1_status, player_count, leader, map)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, 1)
                """,
                (channel_db_id, idx_in_channel, lobby_name, password, 1, player_id, 1, 0, player_id)
            )
            conn.commit()
        print(f"[DB] Created lobby '{lobby_name}' in channel {channel_db_id} idx {idx_in_channel}")
        return True

    @classmethod
    def add_player_to_lobby_db(cls, lobby_name, channel_db_id, player_id):
        """
        Add player to lobby (DB), assign lowest available character 1-8, status=0.
        Returns True if success, False if lobby full or not found.
        """
        lobby = cls.get_lobby_by_name(lobby_name, channel_db_id)
        if not lobby:
            print(f"[ERROR] Lobby '{lobby_name}' not found in DB for add_player.")
            return False
        conn = get_db_conn()
        player_slots = lobby.player_ids
        characters_taken = set(filter(None, lobby.player_characters))
        char_choices = {1,2,3,4,5,6,7,8} - characters_taken
        assigned_character = min(char_choices) if char_choices else 1
        assigned_status = 0  # "preparing"
        with conn.cursor() as cur:
            for idx, slot in enumerate(player_slots, 1):
                if slot is None:
                    cur.execute(f"""
                        UPDATE lobbies
                        SET player{idx}_id = %s,
                            player{idx}_character = %s,
                            player{idx}_status = %s,
                            player_count = player_count + 1
                        WHERE id = %s
                    """, (player_id, assigned_character, assigned_status, lobby.id))
                    conn.commit()
                    print(f"[DB] Added player {player_id} to lobby '{lobby_name}' (slot {idx}, char {assigned_character}).")
                    return True
        print(f"[WARN] No empty player slot in lobby '{lobby_name}'")
        return False

    @classmethod
    def remove_player_from_lobby_db(cls, player_id, channel_db_id=None):
        """
        Remove player from first lobby (in channel if specified) where they are present.
        Returns True if removed, False otherwise.
        """
        conn = get_db_conn()
        with conn.cursor() as cur:
            if channel_db_id is not None:
                cur.execute("""
                    SELECT id, idx_in_channel, player1_id, player2_id, player3_id, player4_id
                    FROM lobbies
                    WHERE channel_id = %s AND (player1_id = %s OR player2_id = %s OR player3_id = %s OR player4_id = %s)
                """, (channel_db_id, player_id, player_id, player_id, player_id))
            else:
                cur.execute("""
                    SELECT id, idx_in_channel, player1_id, player2_id, player3_id, player4_id
                    FROM lobbies
                    WHERE player1_id = %s OR player2_id = %s OR player3_id = %s OR player4_id = %s
                """, (player_id, player_id, player_id, player_id))
            row = cur.fetchone()
            if not row:
                print(f"[WARN] Player {player_id} not found in any lobby for removal.")
                return False
            lobby_id, idx_in_channel, p1, p2, p3, p4 = row
            for idx, slot in enumerate([p1, p2, p3, p4], 1):
                if slot == player_id:
                    cur.execute(f"""
                        UPDATE lobbies
                        SET player{idx}_id = NULL,
                            player{idx}_character = NULL,
                            player{idx}_status = NULL,
                            player_count = GREATEST(player_count - 1, 0)
                        WHERE id = %s
                    """, (lobby_id,))
                    conn.commit()
                    print(f"[DB] Removed player {player_id} from lobby (idx {idx_in_channel}).")
                    return True
        return False

    @classmethod
    def remove_player_and_update_leader(cls, player_id, channel_db_id):
        """
        Thread-safe removal of a player from their lobby.
        Updates leader, and deletes lobby if empty.
        Returns (lobby_name, lobby_deleted: bool)
        """
        print(f"[DEBUG] Attempting to remove {player_id} from lobby in channel {channel_db_id}")

        with sessions_lock:  # Lock added for thread-safety
            conn = get_db_conn()
            with conn.cursor() as cur:
                # Find the lobby where player is present
                cur.execute("""
                    SELECT id, name, leader,
                           player1_id, player2_id, player3_id, player4_id
                    FROM lobbies
                    WHERE channel_id = %s AND (%s = ANY(ARRAY[player1_id, player2_id, player3_id, player4_id]))
                    """, (channel_db_id, player_id))
                row = cur.fetchone()
                if not row:
                    return (None, False)

                lobby_id, lobby_name, leader, p1, p2, p3, p4 = row
                player_slots = [p1, p2, p3, p4]

                # Find which slot to clear
                cleared = False
                for idx, pid in enumerate(player_slots, 1):
                    if pid == player_id:
                        cur.execute(f"""
                            UPDATE lobbies
                            SET player{idx}_id = NULL,
                                player{idx}_character = NULL,
                                player{idx}_status = NULL,
                                player_count = GREATEST(player_count - 1, 0)
                            WHERE id = %s
                        """, (lobby_id,))
                        cleared = True
                conn.commit()
                if not cleared:
                    return (None, False)

                # Reload updated slots and leader
                cur.execute("SELECT leader, player1_id, player2_id, player3_id, player4_id FROM lobbies WHERE id=%s", (lobby_id,))
                leader, p1, p2, p3, p4 = cur.fetchone()
                slots = [(1, p1), (2, p2), (3, p3), (4, p4)]
                non_empty = [(i, pid) for i, pid in slots if pid]
                # If leader was removed or is now None, assign to lowest index remaining
                if (leader == player_id) or (not leader) or (leader not in [pid for _, pid in non_empty]):
                    new_leader = non_empty[0][1] if non_empty else None
                    cur.execute("UPDATE lobbies SET leader=%s WHERE id=%s", (new_leader, lobby_id))
                    conn.commit()

                # If lobby is now empty, delete it
                if not non_empty:
                    cur.execute("DELETE FROM lobbies WHERE id=%s", (lobby_id,))
                    conn.commit()
                    print(f"[LOBBY DELETED] Lobby '{lobby_name}' deleted (was empty after player leave/disconnect).")
                    return (lobby_name, True)

                return (lobby_name, False)

    @classmethod
    def safe_remove_player_from_lobby(cls, session):
        player_id = session.get('player_id')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        if not (player_id and server_id is not None and channel_index is not None):
            return
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
        if channel_db_id is None:
            return
        lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        if not lobby_name:
            return
        LobbyManager.remove_player_and_update_leader(player_id, channel_db_id)
        room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
        broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="[ECHO DC CLEANUP]")

    @classmethod
    def is_player_in_lobby_db(cls, lobby_name, channel_db_id, player_id):
        """Return True if the player is in the named lobby in this channel."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT player1_id, player2_id, player3_id, player4_id
                FROM lobbies
                WHERE name = %s AND channel_id = %s
            """, (lobby_name, channel_db_id))
            row = cur.fetchone()
            if not row:
                return False
            return player_id in row

    @classmethod
    def toggle_player_ready_in_lobby(cls, channel_db_id, lobby_name, player_id):
        """
        Toggle the ready status of the player in the lobby in the DB,
        returns new status (0 or 1), or None if not found.
        """
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """SELECT player1_id, player2_id, player3_id, player4_id,
                          player1_status, player2_status, player3_status, player4_status
                   FROM lobbies WHERE name = %s AND channel_id = %s""",
                (lobby_name, channel_db_id)
            )
            row = cur.fetchone()
            if not row:
                return None
            ids = row[:4]
            statuses = row[4:8]
            for idx, pid in enumerate(ids):
                if pid == player_id:
                    new_status = 0 if (statuses[idx] or 0) == 1 else 1
                    cur.execute(
                        f"UPDATE lobbies SET player{idx+1}_status = %s WHERE name = %s AND channel_id = %s",
                        (new_status, lobby_name, channel_db_id)
                    )
                    conn.commit()
                    return new_status
        return None

    @classmethod
    def set_player_not_ready(cls, player_id, channel_db_id, lobby_name):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE lobbies
                SET player1_status = CASE WHEN player1_id=%s THEN 0 ELSE player1_status END,
                    player2_status = CASE WHEN player2_id=%s THEN 0 ELSE player2_status END,
                    player3_status = CASE WHEN player3_id=%s THEN 0 ELSE player3_status END,
                    player4_status = CASE WHEN player4_id=%s THEN 0 ELSE player4_status END
                WHERE name = %s AND channel_id = %s
                """, (player_id, player_id, player_id, player_id, lobby_name, channel_db_id)
            )
            conn.commit()

    @classmethod
    def set_lobby_status(cls, channel_db_id, lobby_name, status):
        """Set the lobby's status field in the DB (1=waiting, 2=started)."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE lobbies SET status=%s WHERE name=%s AND channel_id=%s",
                (status, lobby_name, channel_db_id)
            )
            conn.commit()

    @classmethod
    def get_lobby_status(cls, channel_db_id, lobby_name):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM lobbies WHERE name = %s AND channel_id = %s",
                (lobby_name, channel_db_id)
            )
            row = cur.fetchone()
            return row[0] if row else None

    @classmethod
    def get_player_character_from_slot_id(cls, lobby_name, channel_db_id, slot_id):
        """
        Returns the playerX_character integer for the given slot_id (0-3) in the lobby.
        """
        lobby = cls.get_lobby_by_name(lobby_name, channel_db_id)
        if lobby and 0 <= slot_id <= 3:
            return lobby.player_characters[slot_id] or 0
        return 0  # Return 0 (default) if not found or invalid slot
    
    @classmethod
    def print_lobby_table(cls, channel_id=None):
        """Prints a formatted table of all lobbies for the given channel_id (or all channels if None), using live DB data."""
        conn = get_db_conn()
        with conn.cursor() as cur:
            if channel_id is not None:
                cur.execute("""
                    SELECT id, channel_id, idx_in_channel, name, password, player_count, status, map, leader,
                           player1_id, player1_character, player1_status,
                           player2_id, player2_character, player2_status,
                           player3_id, player3_character, player3_status,
                           player4_id, player4_character, player4_status
                    FROM lobbies
                    WHERE channel_id = %s
                    ORDER BY idx_in_channel ASC
                """, (channel_id,))
            else:
                cur.execute("""
                    SELECT id, channel_id, idx_in_channel, name, password, player_count, status, map, leader,
                           player1_id, player1_character, player1_status,
                           player2_id, player2_character, player2_status,
                           player3_id, player3_character, player3_status,
                           player4_id, player4_character, player4_status
                    FROM lobbies
                    ORDER BY channel_id ASC, idx_in_channel ASC
                """)
            lobbies = [Lobby.from_row(row) for row in cur.fetchall()]

        # Print table header
        print("ChID  Idx  Name            Players  Type     Status")
        print("=" * 60)
        status_map = {0: '〈비어있음〉', 1: '대기중', 2: '시작됨'}
        for lobby in lobbies:
            is_private = bool(lobby.password)
            type_txt = "Private" if is_private else "Public"
            print(f"{lobby.channel_id:<5} {lobby.idx_in_channel:<4} {lobby.name[:12]:12} {lobby.player_count:<7} {type_txt:7} {status_map.get(lobby.status, lobby.status):6}")
        print("=" * 60)

### END OF CLASS DEFINITIONS ###

def build_account_creation_result(success=True, val=1):
    packet_id = 0x0bba
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val) 
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_account_deletion_result(success=True, val=1):
    packet_id = 0x0bb9
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_channel_list_packet(server_id):
    packet_id = 0x0bbb
    flag = b'\x01\x00\x00\x00'
    entries = []

    # Get all channels for this server from DB
    channels = {ch.channel_index: ch for ch in ChannelManager.get_channels_for_server(server_id)}
    for ch_idx in range(12):
        ch = channels.get(ch_idx)
        if ch:
            cid = ch.channel_index
            cur_players = ch.player_count
        else:
            cid = ch_idx
            cur_players = 0
        max_players = 80
        entries.append(struct.pack('<III', cid, cur_players, max_players))
    payload = flag + b''.join(entries)
    header = struct.pack('<HH', packet_id, len(payload))
    ChannelManager.print_channel_table(server_id)
    return header + payload

def build_channel_join_ack(success=True, val=1):
    packet_id = 0x0bbc
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_lobby_create_ack(success=True, val=1):
    packet_id = 0x0bbd
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

# where val = lobby idx_in_channel if success
def build_lobby_join_ack(success=True, val=1):
    packet_id = 0x0bbe
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

# where val = lobby idx_in_channel if success
def build_lobby_join_ack_2(success=True, val=1):
    packet_id = 0x0bbf
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_login_packet(success=True, val=1):
    packet_id = 0x0bb8
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_lobby_list_packet(server_id, channel_index):
    packet_id = 0xbc8
    flag = b'\x01\x00\x00\x00'
    entry_struct = '<III16s1s12s1sB1s'
    lobbies = []

    channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
    rows = []
    if channel_db_id is not None:
        rows = LobbyManager.get_lobbies_for_channel(channel_db_id)

    for lobby in rows:
        idx_in_channel = lobby.idx_in_channel
        player_count = lobby.player_count
        name = lobby.name
        password = lobby.password
        status = lobby.status
        max_players = 4
        name_enc = name.encode('euc-kr', errors='replace')[:16].ljust(16, b'\x00')
        pad1 = b'\x00'
        pw_enc = (password or '').encode('euc-kr', errors='replace')[:12].ljust(12, b'\x00')
        pad2 = b'\x00'
        pad3 = b'\x00'
        packed = struct.pack(entry_struct, idx_in_channel, player_count, max_players, name_enc, pad1, pw_enc, pad2, status, pad3)
        lobbies.append(packed)

    # Pad to 20 entries if needed
    while len(lobbies) < 20:
        idx = len(lobbies)
        name = f"Lobby{idx+1}".encode('euc-kr')[:16].ljust(16, b'\x00')
        pad1 = b'\x00'
        pw_enc = b"".ljust(12, b'\x00')
        pad2 = b'\x00'
        status = 0
        pad3 = b'\x00'
        packed = struct.pack(entry_struct, idx, 0, 4, name, pad1, pw_enc, pad2, status, pad3)
        lobbies.append(packed)

    payload = flag + b''.join(lobbies)
    header = struct.pack('<HH', packet_id, len(payload))
    LobbyManager.print_lobby_table(channel_db_id)
    return header + payload

def build_server_list_packet():
    packet_id = 0x0bc7
    flag = b'\x01\x00\x00\x00'
    servers = []
    for server in ServerManager.get_servers():
        name = server.name.encode('euc-kr').ljust(16, b'\x00')
        ip = server.ip_address.encode('ascii') + b'\x00'
        ip = ip.ljust(16, b'\x00')
        reserved1 = b'\x00' * 5
        reserved2 = b'\x00' * 3
        servers.append(struct.pack('<16s5s16s3si', name, reserved1, ip, reserved2, server.availability))
    while len(servers) < 10:
        idx = len(servers)
        name = f"MN{idx}".encode('euc-kr').ljust(16, b'\x00')
        ip = b'0.0.0.0\x00'.ljust(16, b'\x00')
        reserved1 = b'\x00' * 5
        reserved2 = b'\x00' * 3
        servers.append(struct.pack('<16s5s16s3si', name, reserved1, ip, reserved2, -1))
    entries = b''.join(servers)
    payload = flag + entries
    header = struct.pack('<HH', packet_id, len(payload))
    ServerManager.print_server_table()
    return header + payload

def build_map_select_ack(success=True, val=1):
    packet_id = 0x0bc6
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_character_select_ack(success=True, val=1):
    packet_id = 0xbc5
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_character_select_setup_packet(player):
    packet_id = 0xbc4
    flag_and_unknown = b'\x01\x00\x00\x00'
    pid = player.player_id.encode('ascii')[:8].ljust(8, b'\x00')
    block = bytearray(28)
    block[0:8]   = pid
    block[8:13]  = b'\x00' * 5
    block[0x0D]  = player.character
    block[0x0E]  = player.status
    block[0x0F]  = 0
    block[0x10:0x14] = struct.pack('<I', player.rank)
    block[0x14:0x18] = struct.pack('<I', 0)
    block[0x18:0x1C] = struct.pack('<I', 0)
    data = bytes(block).ljust(32, b'\x00')
    header = struct.pack('<HH', packet_id, 36)
    return header + flag_and_unknown + data

def build_kick_player_ack(success=True, val=1):
    packet_id = 0xbc3
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_lobby_leave_ack(success=True, val=1):
    packet_id = 0xbc2
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_player_ready_ack(success=True, val=1):
    packet_id = 0xbc1
    if success:
        flag = b'\x01\x00\x00\x00'
    else:
        flag = b'\x00'
    payload = flag + struct.pack('<H', val)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_game_start_ack(lobby_name, channel_db_id, success= True, val=1, player_count=4):
    """
    Build the Game Start Ack packet (0xbc0).
    - 16-byte field: 4 unique random start positions (0..11), each as 1 byte + 3 zero bytes.
    - vampire_id: random 0..3
    - vampire_gender: 0: female, 1: male
    - map_id: random 1..4
    """
    packet_id = 0xbc0
    if success:
        flag = b'\x01\x00\x00\x00'
        pad = b'\x00\x00'
        g_logic = False
        # Generate unique random positions for each player (0..11)
        start_positions = random.sample(range(12), k=player_count)
        positions = b''.join(struct.pack('<B3x', pos) for pos in start_positions)
        vampire_id = random.randint(0, 3)
        vampire_character = LobbyManager.get_player_character_from_slot_id(lobby_name, channel_db_id, vampire_id)
        # Assign gender based on gender of character
        if (g_logic):
            if(vampire_character > 6): # if Kelly or Jane
                vampire_gender = 0
            else:
                vampire_gender = 1
        # Assign gender randomly (likely the intended design - otherwise vampire identity is too obvious)
        else:
            vampire_gender = random.randint(0, 1)

        map_id = random.randint(1, 4) # If RANDOM map was selected, this value will be used
        print(f"Start Positions:{start_positions}, Map:{map_id}, Vampire:{vampire_id}, Gender:{vampire_gender}")

        payload = (
            flag
            + positions
            + struct.pack('<H', vampire_id)
            + pad
            + struct.pack('<H', vampire_gender)
            + pad
            + struct.pack('<H', map_id)
        )
        header = struct.pack('<HH', packet_id, len(payload))
    else:
        flag = b'\x00'
        payload = flag + struct.pack('<H', val)
        header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_lobby_room_packet(lobby_name, channel_db_id):
    lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
    if not lobby:
        print(f"[ERROR] Could not fetch lobby {lobby_name} for channel {channel_db_id}")
        return b''

    packet_id = 0x03ee

    # Determine leader index (0 if not found)
    leader_idx = 0
    for i, pid in enumerate(lobby.player_ids):
        if pid == lobby.leader:
            leader_idx = i
            break
    lobby_leader = struct.pack("B", leader_idx)
    padding = b'\x00\x00\x00'
    name = lobby.name.encode('euc-kr', errors='replace')[:16].ljust(16, b'\x00')
    unknown1 = b'\x00' * 16

    player_structs = []
    for i in range(4):
        pid_str = lobby.player_ids[i]
        pid = (pid_str or '').encode('ascii')[:8].ljust(8, b'\x00')
        block = bytearray(28)
        block[0:8] = pid
        block[8:13] = b'\x00' * 5
        block[0x0D] = lobby.player_characters[i] or 0
        block[0x0E] = lobby.player_statuses[i] or 0
        block[0x0F] = 0
        # Look up each player's rank from the database 
        if pid_str:
            player = PlayerManager.load_player_from_db(pid_str)
            player_rank = player.rank if player else 1
        else:
            player_rank = 1
        block[0x10:0x14] = struct.pack('<I', player_rank)
        block[0x14:0x18] = struct.pack('<I', 0)
        block[0x18:0x1C] = struct.pack('<I', 0)
        player_structs.append(bytes(block))

    map_select = struct.pack('<I', lobby.map or 1)
    lobby_status = struct.pack('<I', lobby.status or 1)
    payload = (
        lobby_leader +
        padding +
        name +
        unknown1 +
        b''.join(player_structs) +
        map_select +
        lobby_status
    )
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def parse_account(data):
    packet_id, payload_len = struct.unpack('<HH', data[:4])
    username = data[4:12].decode('ascii').rstrip('\x00')
    password = data[17:29].decode('ascii').rstrip('\x00')
    return packet_id, payload_len, username, password

def parse_channel_join_packet(data):
    packet_id, payload_len = struct.unpack('<HH', data[:4])
    player_id = data[4:12].decode('ascii').rstrip('\x00')
    channel_index = struct.unpack('<H', data[20:22])[0]
    return {
        "packet_id": packet_id,
        "payload_len": payload_len,
        "player_id": player_id,
        "channel_index": channel_index
    }

def parse_lobby_create_packet(data):
    player_id = data[4:12].decode('ascii').rstrip('\x00')
    lobby_name = data[17:29].decode('ascii').rstrip('\x00')
    password = data[34:42].decode('ascii').rstrip('\x00')
    return player_id, lobby_name, password

def parse_lobby_join_packet(data):
    player_id = data[4:12].decode('ascii').rstrip('\x00')
    lobby_name = data[24:36].decode('ascii').rstrip('\x00')
    return player_id, lobby_name

def parse_move_packet(data):
    """
    Parse player movement/position update (0x1388) packet.
    Assumes 'data' includes header (4 bytes) + payload (24 bytes).
    Returns a dict of all parsed fields.
    """
    if len(data) < 28:
        raise ValueError("Packet too short for 0x1388 movement update")

    pkt_id, pkt_len = struct.unpack('<HH', data[:4])
    y_pos      = struct.unpack('<f', data[4:8])[0]
    x_pos      = struct.unpack('<f', data[8:12])[0]
    player_heading    = struct.unpack('<f', data[12:16])[0]
    cam_heading= struct.unpack('<f', data[16:20])[0]
    unknown1   = data[20:22]           # 2 bytes
    left_right = data[22]              # 1 byte
    up_down    = data[23]              # 1 byte
    player_idx   = data[24:28]           # 4 bytes (character index [0,3])

    return {
        "pkt_id": pkt_id,
        "pkt_len": pkt_len,
        "x_pos": x_pos,
        "y_pos": y_pos,
        "player_heading": player_heading,
        "cam_heading": cam_heading,
        "unknown1": unknown1,
        "left_right": left_right,
        "up_down": up_down,
        "player_idx": player_idx,
    }

def build_dc_packet(player_index):
    """
    Build the 0x03f4 Ready Ack packet.
    Example: player_index 3 -> f4 03 04 00 03 00 00 00
    """
    packet_id = 0x03f4
    payload_len = 4
    payload = struct.pack('<B3x', player_index)
    header = struct.pack('<HH', packet_id, payload_len)
    return header + payload

def build_countdown(number):
    """
    Build the 0x03ef Countdown packet (ef03 0100 XX).
    Example: number=3 -> ef 03 01 00 03
    """
    packet_id = 0x03ef
    payload_len = 1
    header = struct.pack('<HH', packet_id, payload_len)
    payload = struct.pack('<B', number)
    return header + payload
@trace_calls
def send_echo_challenge(session, payload=None, broadcast=False):
    """
    Send a 0x03e9 echo challenge packet to a client.
    Payload should be 4 bytes (default = b'\x01\x00\x00\x00').
    """
    packet_id = 0x03e9
    payload = payload or b'\x01\x00\x00\x00'
    header = struct.pack('<HH', packet_id, len(payload))
    packet = header + payload[:4]
    if broadcast:
        player_id = session.get('player_id')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        broadcast_to_lobby(lobby_name, channel_db_id, packet, note="[ECHO CHALLENGE 0x03e9]")
    else:
        send_packet_to_client(session, packet, note="[ECHO CHALLENGE 0x03e9]")

@trace_calls
def run_echo_challenge(session, purpose, payload=None, timeout=10, interval=1, on_result=None):
    """
    Sends echo challenges at `interval` seconds until reply or `timeout` seconds passed.
    Calls `on_result(success:bool)` with True if reply, False if timeout.
    """

    # Clear previous reply state
    with sessions_lock:
        token = uuid.uuid4().hex
        session['echo'][purpose]['token'] = token
        session['echo'][purpose]['reply'] = False
        session['echo'][purpose]['in_progress'] = True

    @trace_calls
    def challenge_loop():
        try:
            for i in range(timeout):
                if session['echo'][purpose]['reply']:
                    print(f"[ECHO {purpose.upper()}] {session.get('player_id')} replied in {i+1}s.")
                    if on_result:
                        on_result(True)
                    return
                send_echo_challenge(session)
                time.sleep(interval)
            print(f"[ECHO {purpose.upper()}] {session.get('player_id')} timed out.")
            if on_result:
                on_result(False)
        finally:
            session['echo'][purpose]['in_progress'] = False

    threading.Thread(target=challenge_loop, daemon=True).start()

# def kill_process_using_port(port):
#     print(f"Killing processes that may be using port {port}...")
#     try:
#         result = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True)
#         for line in result.splitlines():
#             parts = line.split()
#             if len(parts) >= 5:
#                 pid = parts[-1]
#                 if int(pid) > 10:
#                     print(f"Port {port} is being used by PID: {pid}.")
#                     print(f"Attempting to terminate PID {pid}...")
#                     subprocess.run(f"taskkill /F /PID {pid}", shell=True)
#                     print(f"Successfully terminated process {pid}.")
#     except subprocess.CalledProcessError:
#         print(f"No process found using port {port}.")

# kill_process_using_port(TCP_PORT)
# kill_process_using_port(TCP_PORT_CHANNEL)

def send_packet_to_client(session, payload, note=""):
    """Send a TCP packet to a single client."""
    try:
        session['socket'].sendall(payload)
        if note:
            print(f"[SEND] {note} To {session['addr']}: {payload.hex()}")
        else:
            print(f"[SEND] To {session['addr']}: {payload.hex()}")
    except Exception as e:
        print(f"[SEND ERROR] {session['addr']}: {e}")

def parse_packet_header(data):
    if len(data) < 4:
        return None, None
    packet_id, payload_len = struct.unpack('<HH', data[:4])
    return packet_id, payload_len

def broadcast_to_lobby(lobby_name, channel_db_id, payload, note="", cur_session=None, to_self=True):
    """
    Broadcast a packet to all gameplay clients (port 3658) in the specified lobby.
    Avoids sending to `cur_session` if `to_self` is False.
    """
    lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
    if not lobby:
        print(f"[BROADCAST ERROR] Lobby '{lobby_name}' not found in channel {channel_db_id}")
        return

    target_ids = {pid for pid in lobby.player_ids if pid}

    with sessions_lock:
        targets = [
            s for s in sessions.values()
            if s.get("player_id") in target_ids and s['addr'][1] == CLIENT_GAMEPLAY_PORT
        ]

    for s in targets:
        time.sleep(0.02)
        if s.get('removed') or not is_session_socket_alive(s):
            continue
        if not to_self and s is cur_session:
            continue
        try:
            send_packet_to_client(s, payload, note=f"[BROADCAST] {lobby_name}] {note}")
        except Exception as e:
            print(f"[BROADCAST ERROR] {s['addr']}: {e}")

@trace_calls
def handle_client_packet(session, data):

    # The session is now a dict: {'socket': sock, 'addr': addr, ...}
    # Instead of raw/ether/IP/TCP, just use TCP socket: data is the full packet.

    # Example minimal pattern (fill out as needed):
    pkt_id, payload_len = parse_packet_header(data)
    if pkt_id is None:
        print(f"[ERROR] Packet too short from {session['addr']}")
        return

    response = None
    update_last_packet_time(session)

    # --- Login ---
    if pkt_id == 0x07d0:
        print("[DEBUG] Handling 0x07d0 LOGIN packet")
        print(f"[DEBUG] Raw client_data: {data.hex()}")
        if len(data) >= 30:
            player_id = data[4:16].decode('ascii', errors='replace').rstrip('\x00')
            pwd = data[17:29].decode('ascii', errors='replace').rstrip('\x00')
            print(f"[DEBUG] Parsed player_id: '{player_id}' (raw: {data[4:16].hex()})")
            print(f"[DEBUG] Parsed password: '{pwd}' (raw: {data[17:29].hex()})")
            player = PlayerManager.load_player_from_db(player_id)
            if player:
                print(f"[DEBUG] Player found in DB: '{player.player_id}', expected password: '{player.password}'")
                if player.password == pwd:
                    print(f"[LOGIN] Login OK for player '{player_id}'")
                    response = build_login_packet(success=True)
                    # Save to session for later use
                    session['player_id'] = player_id
                else:
                    print(f"[LOGIN] Login failed for player '{player_id}'. Received password: '{pwd}' != Expected password: '{player.password}'")
                    response = build_login_packet(success=False, val=7)
            else:
                print(f"[LOGIN] Player '{player_id}' not found in DB")
                response = build_login_packet(success=False, val=8)
        else:
            print("[LOGIN] Malformed login request. Payload too short.")
            print(f"[DEBUG] Received length: {len(data)} bytes, expected >= 30 bytes")
            response = build_login_packet(success=False, val=5)
        send_packet_to_client(session, response, note="[LOGIN REPLY]")
    
    # --- Account Create ---
    elif pkt_id == 0x07d1:
        pid, plen, user, pwd = parse_account(data)
        print(f"[ACCOUNT CREATE REQ] User: {user} Pass: {pwd}")
        # Try to load first in case it exists
        player = PlayerManager.load_player_from_db(user)
        if player:
            response = build_account_creation_result(success=False, val=9)  # ID exists
            print("Account already exists.")
        else:
            PlayerManager.create_player(user, pwd)
            response = build_account_creation_result(success=True)
            print("Account succesfully created.")
        send_packet_to_client(session, response, note="[ACCOUNT CREATE]")

    # --- Account Delete ---
    elif pkt_id == 0x07d2:
        pid, plen, user, pwd = parse_account(data)
        print(f"[ACCOUNT DELETE REQ] User: {user} Pass: {pwd}")
        # Always check DB for player
        player = PlayerManager.load_player_from_db(user)
        if player:
            if player.password == pwd:
                result = PlayerManager.remove_player(user)
                if not result:
                    response = build_account_deletion_result(success=False, val=4) # Database Error
                else:
                    response = build_account_deletion_result(success=True)
                    print("Account deletion OK.")
            else:
                response = build_account_deletion_result(success=False, val=7)
                print("Account deletion failed. Incorrect Password.")
        else:
            response = build_account_deletion_result(success=False, val=8)
            print("Account deletion failed. No such Player ID.")
        send_packet_to_client(session, response, note="[ACCOUNT DELETE]")
    
    # --- Channel List ---
    elif pkt_id == 0x07d3:
        # The server is now tracked in session['server'] or session['server_id']
        server_id = session.get('server_id')
        if not server_id:
            print(f"[ERROR] Could not determine server for session {session['addr']}")
            return
        response = build_channel_list_packet(server_id)
        send_packet_to_client(session, response, note="[CHANNEL LIST]")

    # --- Channel Join ---
    elif pkt_id == 0x07d4:
        info = parse_channel_join_packet(data)
        player_id = info["player_id"]
        channel_index = info["channel_index"]

        # Use server_id from session (set on connection or earlier packet)
        server_id = session.get('server_id')
        if server_id is None:
            print(f"[ERROR] Channel join for unknown server_id in session {session['addr']}")
            response = build_channel_join_ack(success=False, val=5)
            send_packet_to_client(session, response, note="[CHANNEL JOIN FAIL]")
            return

        player = PlayerManager.load_player_from_db(player_id)
        if player:
            # ChannelManager.increment_player_count(server_id, channel_index)  # Uncomment if wanted
            print(f"[CHANNEL JOIN] Player {player.player_id} joined channel {channel_index} on server_id {server_id}")
        else:
            print(f"[ERROR] Channel join for unknown player: {player_id}")

        # Save per-session state for later packets
        session['player_id'] = player_id
        session['channel_index'] = channel_index

        response = build_channel_join_ack(success=True)
        send_packet_to_client(session, response, note="[CHANNEL JOIN]")

    # --- Lobby Create ---
    elif pkt_id == 0x07d5:
        player_id, lobby_name, password = parse_lobby_create_packet(data)
        player = PlayerManager.load_player_from_db(player_id)
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
        print(f"[LOBBY CREATE] Player '{player_id}' requests lobby '{lobby_name}' (channel_db_id={channel_db_id})")
    
        if channel_db_id is None or player is None:
            print(f"[ERROR] Missing channel or player for lobby create. channel_db_id={channel_db_id}, player={player_id}")
            response = build_lobby_create_ack(success=False, val=5)
        elif not LobbyManager.create_lobby_db(lobby_name, password, channel_db_id, player_id):
            # Already exists or full
            lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
            if lobby is not None:
                print(f"[ERROR] Lobby '{lobby_name}' already exists in channel {channel_db_id}")
                response = build_lobby_create_ack(success=False, val=0x10)  # Already exists
            else:
                print(f"[ERROR] No more lobby slots available in channel {channel_db_id}")
                response = build_lobby_create_ack(success=False, val=0x0d)  # Full
        else:
            print(f"[LOBBY CREATE] Lobby '{lobby_name}' successfully created in channel {channel_db_id}")
            response = build_lobby_create_ack(success=True)
            send_packet_to_client(session, response, note="[LOBBY CREATE OK]")
            room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
            send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")
            response = None  # Don't send response again below
    
        if response:
            send_packet_to_client(session, response, note="[LOBBY CREATE ERR]")

    # --- Lobby Join ---
    elif pkt_id == 0x07d6:
        player_id, lobby_name = parse_lobby_join_packet(data)
        player = PlayerManager.load_player_from_db(player_id)
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)

        success = False
        val = 1  # Default (idx)

        if channel_db_id is None or player is None:
            print(f"[ERROR] Invalid channel or player missing. server_id={server_id}, channel_index={channel_index}, player={player_id}")
            val = 0x05  # Invalid parameter
            lobby = None
        else:
            lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
            status = LobbyManager.get_lobby_status(channel_db_id, lobby_name)
            if not lobby:
                print(f"[ERROR] Lobby '{lobby_name}' not found in channel {channel_db_id}")
                val = 0x0f  # Lobby does not exist
            else:
                if status == 1:
                    if LobbyManager.is_player_in_lobby_db(lobby_name, channel_db_id, player_id):
                        print(f"[LOBBY JOIN] (repeat) Player {player_id} already in lobby '{lobby_name}' (idx {lobby.idx_in_channel})")
                        success = True
                        val = lobby.idx_in_channel
                    else:
                        add_success = LobbyManager.add_player_to_lobby_db(lobby_name, channel_db_id, player_id)
                        if add_success:
                            print(f"[LOBBY JOIN] Player {player_id} joined lobby '{lobby_name}' (idx {lobby.idx_in_channel}) in channel {channel_db_id}")
                            success = True
                            val = lobby.idx_in_channel
                        else:
                            print(f"[ERROR] Lobby '{lobby_name}' is full or cannot add player {player_id}")
                            val = 0x0a  # Lobby full
                elif status == 2:
                    print(f"[LOBBY JOIN] A game has already started in lobby {lobby_name}. {player_id} join denied.")
                    val = 0x0e # Game has already Started
                else:
                    print(f"[LOBBY JOIN] Uknown lobby status {status}. Join failed.")
                    val = 0x04 # Database error

        response = build_lobby_join_ack(success=success, val=val)
        send_packet_to_client(session, response, note="[LOBBY JOIN]")

        if success and channel_db_id is not None and lobby is not None:
            # Store the player_index in the session
            updated_lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
            if updated_lobby and player_id in updated_lobby.player_ids:
                session['player_index'] = updated_lobby.player_ids.index(player_id)
            else:
                print(f"[WARNING] Could not cache player_index for {player_id} in lobby {lobby_name}")
            room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
            broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
            #send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")

    # --- Game Start Request ---
    elif pkt_id == 0x07d8:
        if len(data) >= 8:
            with sessions_lock:
                session['countdown_in_progress'] = True
            player_id = data[4:12].decode('ascii').rstrip('\x00')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
            lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
            print(f"[0x7d8] Game Start request by {player_id} in lobby {lobby_name}")
            if channel_db_id is not None and lobby_name:
                LobbyManager.set_lobby_status(channel_db_id, lobby_name, 2)  # 2 = started/in progress
                with lobby_ready_lock:
                    key = (channel_db_id, lobby_name)
                    lobby_ready_counts[key] = 0 # RESET READY COUNT AS FAILSAFE
            bc0_response = build_game_start_ack(lobby_name, channel_db_id)
            broadcast_to_lobby(lobby_name, channel_db_id, bc0_response, note="[GAME START ACK]")
            # send updated lobby room packet:
            room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
            broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
        else:
            print(f"[ERROR] Malformed 0x07d8 packet (len={len(data)})")
            bc0_response = build_game_start_ack(lobby_name, channel_db_id, success=False, val=1)
            send_packet_to_client(session, bc0_response, note="[GAME START ACK]")

    # --- Game Ready Request ---
    elif pkt_id == 0x07d9:
        if len(data) >= 8:
            with sessions_lock:
                session['countdown_in_progress'] = True
            player_id = data[4:12].decode('ascii').rstrip('\x00')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
            lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
            if channel_db_id is not None and lobby_name:
                new_status = LobbyManager.toggle_player_ready_in_lobby(channel_db_id, lobby_name, player_id)
                print(f"[0x7d9] Player Ready request by {player_id}, new status: {new_status}")
                bc1_response = build_player_ready_ack(success=True)
                send_packet_to_client(session, bc1_response, note="[PLAYER READY ACK]")
                room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
                #send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")
            else:
                print(f"[0x7d9] Player Ready failed: missing lobby or channel info.")
                bc1_response = build_player_ready_ack(success=False, val=5)
                send_packet_to_client(session, bc1_response, note="[PLAYER READY FAIL]")
        else:
            print(f"[ERROR] Malformed 0x07d9 packet (len={len(data)})")
            bc1_response = build_player_ready_ack(success=False, val=1)
            send_packet_to_client(session, bc1_response, note="[PLAYER READY FAIL]")

    # --- Lobby Leave ---
    elif pkt_id == 0x07da:  # Lobby leave
        if len(data) >= 8:
            player_id = data[4:12].decode('ascii').rstrip('\x00')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
            if channel_db_id is None:
                print(f"[ERROR] No channel DB id for server_id={server_id}, channel_index={channel_index}")
                ack_packet = build_lobby_leave_ack()
            removed_lobby, lobby_deleted = LobbyManager.remove_player_and_update_leader(player_id, channel_db_id)
            ack_packet = build_lobby_leave_ack()
            send_packet_to_client(session, ack_packet, note="[LOBBY LEAVE ACK]")
            if not lobby_deleted:
                # Update remaining players
                room_packet = build_lobby_room_packet(removed_lobby, channel_db_id)
                broadcast_to_lobby(removed_lobby, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
            else:
                print(f"[LEAVE] Lobby '{removed_lobby}' deleted after last player left.")

        else:
            print(f"[ERROR] Malformed 0x07da packet (len={len(data)})")
            ack_packet = build_lobby_leave_ack(success=False, val=1)
            send_packet_to_client(session, ack_packet, note="[LOBBY LEAVE FAIL]")

    # --- Lobby Kick ---
    elif pkt_id == 0x07db:
        if len(data) >= 8:
            kick_idx = struct.unpack('<I', data[4:12])[0]
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            player_id = session.get('player_id')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
            lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
            print(f"[0x07db] Kick request: remove player at index {kick_idx} (channel_db_id={channel_db_id})")
            kick_packet = build_kick_player_ack()
            # Find the session for the player being kicked
            if lobby_name:
                lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
                if lobby and 0 <= kick_idx < 4:
                    kicked_player_id = lobby.player_ids[kick_idx]
                    if kicked_player_id:
                        with sessions_lock:
                            for s in sessions.values():
                                # Send kick to player getting kicked and to lobby leader to ack the kick
                                if (
                                    s.get("player_id") == (kicked_player_id) and 
                                    s['addr'][1] == CLIENT_GAMEPLAY_PORT
                                ):
                                    send_packet_to_client(s, kick_packet, note=f"[PLAYER KICKED index={kick_idx}]")
                                    send_packet_to_client(session, kick_packet, note=f"[SUCCESFULLY KICKED index={kick_idx}]")
                                    break

                        removed = LobbyManager.remove_player_from_lobby_db(kicked_player_id, channel_db_id)
                        if removed:
                            print(f"[KICK] Removed player: {kicked_player_id} from {lobby_name} (idx {kick_idx})")
                        else:
                            print(f"[KICK] Could not remove player: {kicked_player_id} from {lobby_name}")
                    else:
                        print(f"[KICK] No player in slot {kick_idx} of {lobby_name}")
                else:
                    print(f"[KICK] Invalid kick index {kick_idx} for lobby {lobby_name}")
                room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
                #send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")
        else:
            print(f"[ERROR] Malformed 0x07db packet (len={len(data)})")
            #ack_packet = LOGIC TO BE IMPLEMENTED
            #send_packet_to_client(session, ack_packet, note="[KICK FAIL]")

    # --- Character Info Request ---
    elif pkt_id == 0x07dc:
        if len(data) >= 8:
            requested_id = data[4:12].decode('ascii').rstrip('\x00')
            print(f"[0x7dc] Requested player info for: {requested_id}")
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
            if channel_db_id is not None:
                lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, requested_id)
                character, status = 0, 0
                if lobby_name:
                    lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
                    if lobby and requested_id in lobby.player_ids:
                        slot_idx = lobby.player_ids.index(requested_id)
                        character = lobby.player_characters[slot_idx] or 0
                        status = lobby.player_statuses[slot_idx] or 0
                player = PlayerManager.load_player_from_db(requested_id)
                if player:
                    player.character = character
                    player.status = status
                    bc4_response = build_character_select_setup_packet(player)
                    send_packet_to_client(session, bc4_response, note="[CHAR INFO]")
        else:
            print(f"[ERROR] Malformed 0x07dc packet (len={len(data)})")

    # --- Character Select Request ---
    elif pkt_id == 0x07dd:
        if len(data) >= 8:
            char_val = data[4]
            requested_id = session.get('player_id')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
            if requested_id and channel_db_id is not None:
                # Update the player's character in the DB
                LobbyManager.set_player_character(channel_db_id, requested_id, char_val)
                ack_packet = build_character_select_ack()
                send_packet_to_client(session, ack_packet, note="[CHAR SELECT ACK]")
                lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, requested_id)
                room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
                #send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")
        else:
            print(f"[ERROR] Malformed 0x07dd packet (len={len(data)})")

    # --- Map Select Request ---
    elif pkt_id == 0x07de:  # Map select
        if len(data) >= 8:
            desired_map = struct.unpack('<I', data[4:12])[0]
            player_id = session.get('player_id')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
            if player_id and channel_db_id is not None:
                lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
                if lobby_name:
                    LobbyManager.set_lobby_map(channel_db_id, lobby_name, desired_map)
                    ack_packet = build_map_select_ack()
                    send_packet_to_client(session, ack_packet, note="[MAP SELECT ACK]")
                    room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                    broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
                    #send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")
        else:
            print(f"[ERROR] Malformed 0x07de packet (len={len(data)})")

    # --- Server List ---
    elif pkt_id == 0x07df: 
        response = build_server_list_packet()
        send_packet_to_client(session, response, note="[SERVER LIST]")

    # --- Lobby List ---
    elif pkt_id == 0x07e0:
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')  # Set on Channel Join
        print(f"server_id is: '{server_id}', channel_index is: '{channel_index}'")
        if server_id is not None and channel_index is not None:
            response = build_lobby_list_packet(server_id, channel_index)
            send_packet_to_client(session, response, note="[LOBBY LIST]")
        else:
            print("[ERROR] Missing server_id or channel_index in session.")
    
    # --- Game Ready Check ---
    elif pkt_id == 0x03f0:
        player_id = session.get('player_id')
        player_index = session.get('player_index')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
        if not lobby:
            print("[READY] Could not find lobby for player.")
            return
    
        key = (channel_db_id, lobby_name)
    
        def after_echo(success):
            # Mark this player’s echo result
            with lobby_echo_lock:
                d = lobby_echo_results.setdefault(key, {})
                d[player_id] = success
                print(f"[READY] Echo reply for '{player_id}' is {'READY' if success else 'DC'}")
    
            # Check and mark DCs for all other slots (not self)
            for idx, pid in enumerate(lobby.player_ids):
                if not pid or pid == player_id:
                    continue
                # If not already resolved, check for active session
                with sessions_lock:
                    active = any(
                        s.get("player_id") == pid and s['addr'][1] == CLIENT_GAMEPLAY_PORT
                        for s in sessions.values()
                    )
                with lobby_echo_lock:
                    d = lobby_echo_results.setdefault(key, {})
                    if not active and pid not in d:
                        d[pid] = False  # Mark as DC
                        dc_packet = build_dc_packet(idx)
                        broadcast_to_lobby(lobby_name, channel_db_id, dc_packet, note=f"[PLAYER DC {idx}]")
                        print(f"[READY] {pid} has no active session, marked as DC, slot {idx}")
    
            # Check if ALL 4 slots are resolved for non-empty player_ids
            with lobby_echo_lock:
                non_empty_ids = [pid for pid in lobby.player_ids if pid]
                resolved = [pid for pid in non_empty_ids if pid in lobby_echo_results[key]]
                num_dc = sum(1 for pid in non_empty_ids if lobby_echo_results[key].get(pid) is False)
                print(f"[READY] Resolved: {resolved} / {non_empty_ids}")
                if len(resolved) == len(non_empty_ids):
                    print(f"[COUNTDOWN] All players resolved ({len(non_empty_ids)} slots, {num_dc} DC). Starting countdown.")
                    def countdown_thread():
                        time.sleep(1)
                        for x in range(4, 0, -1):
                            packet = build_countdown(x)
                            #for _ in range(2): # add double send redundancy for transmission issues
                            #    time.sleep(0.02)
                            broadcast_to_lobby(lobby_name, channel_db_id, packet, note=f"[COUNTDOWN {x}]")
                            time.sleep(1)
                        final_packet = build_countdown(0)
                        #for _ in range(2): # add double send redundancy for transmission issues
                        #    time.sleep(0.02)
                        broadcast_to_lobby(lobby_name, channel_db_id, final_packet, note="[COUNTDOWN GO]")
                        with lobby_echo_lock:
                            lobby_echo_results[key] = {}
                        with sessions_lock:
                            for s in sessions.values():
                                s['countdown_in_progress'] = False
                    threading.Thread(target=countdown_thread, daemon=True).start()
    
        # Launch echo only for THIS player, callback does the rest
        threading.Thread(
            target=run_echo_challenge,
            args=(session, 'readycheck'),
            kwargs={'timeout': 10, 'payload': player_index, 'on_result': after_echo},
            daemon=True
        ).start()

    # --- Disconnect  ---
    elif pkt_id == 0x03f1: 
        player_id = session.get('player_id')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = None
        if channel_db_id is not None and player_id:
            lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        
        # Broadcast to players in the lobby
        if lobby_name and channel_db_id is not None:
            broadcast_to_lobby(lobby_name, channel_db_id, data, note=f"[DISCONNECT BROADCAST {pkt_id}]")
            # Remove player, update leader, and delete lobby if empty
            removed_lobby, lobby_deleted = LobbyManager.remove_player_and_update_leader(player_id, channel_db_id)
            if not lobby_deleted:
                # Broadcast updated room info to remaining players
                room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="[DISCONNECT ROOM UPDATE]")
            else:
                print(f"[DISCONNECT] Lobby '{lobby_name}' deleted after last player left/disconnected.")

        else:
            print(f"[{pkt_id}] WARNING: Could not find lobby/channel for broadcast for {player_id}")

    # --- Game Result / Update Rank ---
    elif pkt_id == 0x03f3:
        """
        If player wins, increment RANK score by 5 points
        If player loses, increment RANK score by 2 points
        """    
        player_id = data[4:12].decode('ascii').rstrip('\x00')
        victory_flag = data[16:20]
        is_victory = victory_flag == b'\x01\x00\x00\x00'
        points = 5 if is_victory else 2
        print(f"[GAME END] Player {player_id} {'VICTORY' if is_victory else 'DEFEAT'}, +{points} pts")
        PlayerManager.add_rank_points(player_id, points)

    # --- Game Over ---
        """
        Update the player's status and broadcast lobby room info
        """            
    elif pkt_id == 0x03f2:
        player_id = data[4:12].decode('ascii').rstrip('\x00')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        if not lobby_name:
            print(f"[0x3f2] Could not find lobby for {player_id}")
            return
        # -- set lobby status to 1 (In Queue)
        LobbyManager.set_lobby_status(channel_db_id, lobby_name, 1)
        # -- set Player status to 1 (Not Ready)
        LobbyManager.set_player_not_ready(player_id, channel_db_id, lobby_name)
        room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
        broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="[LOBBY ROOM INFO]")
    
    # --- Echo Reply ---
    elif pkt_id == 0x03ea:
        # The payload is always the last 4 bytes after the 4-byte header
        if len(data) >= 8:
            payload = data[-4:]
            print(f"[ECHO REPLY 0x03ea] Payload: {payload.hex()}")
            with sessions_lock:
                # Prioritize readycheck reply if in progress
                if session['echo']['readycheck']['in_progress']:
                    session['echo']['readycheck']['reply'] = True
                else:
                    session['echo']['keepalive']['reply'] = True
        else:
            print(f"[ECHO REPLY 0x03ea] Packet too short: {data.hex()}")

# --- Gameplay Loop ---

    # --- Player Movement ---
    elif pkt_id == 0x1388:
        try:
            parsed = parse_move_packet(data)
            # Store state for session
            session['y'] = parsed['y_pos']
            session['x'] = parsed['x_pos']
            session['player_heading'] = parsed['player_heading']
            session['cam_heading'] = parsed['cam_heading']
            session['move_lr'] = parsed['left_right']
            session['move_ud'] = parsed['up_down']
            session['move_unknown1'] = parsed['unknown1']
            session['player_idx'] = parsed['player_idx']

            # Figure out lobby as before
            player_id = session.get('player_id')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
            lobby_name = None
            if channel_db_id is not None and player_id:
                lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)

            print(f"[1388] Movement from {player_id}: x={parsed['x_pos']:.3f} y={parsed['y_pos']:.3f} "
                  f"player_heading={parsed['player_heading']:.3f} cam={parsed['cam_heading']:.3f} "
                  f"LR={parsed['left_right']:02x} UD={parsed['up_down']:02x} "
                  f"unk1={parsed['unknown1'].hex()} player_idx={parsed['player_idx'].hex()}")

            # Broadcast to other players in the same lobby
            if lobby_name and channel_db_id is not None:
                broadcast_to_lobby(lobby_name, channel_db_id, data, note=f"[MOVE BROADCAST 0x1388]")
            else:
                print(f"[1388] WARNING: Could not find lobby/channel for movement broadcast for {player_id}")

        except Exception as e:
            print(f"[ERROR][1388] Failed to parse or broadcast movement packet: {e}")

    # --- All other Gameplay ---
    elif pkt_id >> 8 == 0x13: # check high byte - if packet_id is 0x13XX
        player_id = session.get('player_id')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = None
        if channel_db_id is not None and player_id:
            lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        
        # Broadcast to other players in the same lobby
        if lobby_name and channel_db_id is not None:
            # with sessions_lock:
            #     for s in sessions.values():
            #         if s is session:
            #             continue  # don't echo to sender
            #         if s['addr'][1] == CLIENT_GAMEPLAY_PORT:
            #             if s.get('player_id') and LobbyManager.get_lobby_name_for_player(channel_db_id, s.get('player_id')) == lobby_name:
            #                 send_packet_to_client(s, data, note=f"[GAMEPLAY BROADCAST {pkt_id:04x}]")
            #broadcast_to_lobby(lobby_name, channel_db_id, data, note=f"[GAMEPLAY BROADCAST {pkt_id:04x}]", cur_session=session, to_self=False)
            broadcast_to_lobby(lobby_name, channel_db_id, data, note=f"[GAMEPLAY BROADCAST {pkt_id:04x}]")
        else:
            print(f"[{pkt_id:04x}] WARNING: Could not find lobby/channel for broadcast for {player_id}")

    # --- Unhandled Packet ---
    else:
        print(f"[WARN] Unhandled packet ID: 0x{pkt_id:04x} from {session['addr']}")

# --- Client Thread ---
@trace_calls
def client_thread(session):
    sock = session['socket']
    addr = session['addr']
    print(f"[CONNECT] New connection from {addr}")

    # Add to sessions registry
    with sessions_lock:
        sessions[addr] = session

    try:
        while True:
            # Protocol: read header to get payload length
            header = b''
            while len(header) < 4:
                chunk = sock.recv(4 - len(header))
                if not chunk:
                    raise ConnectionResetError
                header += chunk
            pkt_id, payload_len = struct.unpack('<HH', header)

            # Now read the payload
            payload = b''
            while len(payload) < payload_len:
                chunk = sock.recv(payload_len - len(payload))
                if not chunk:
                    raise ConnectionResetError
                payload += chunk

            data = header + payload
            print(f"[RECV] From {addr}: {data.hex()} (pkt_id={pkt_id:04x}, {payload_len} bytes)")
            handle_client_packet(session, data)

    except (ConnectionResetError, BrokenPipeError):
        print(f"[DISCONNECT] {addr} disconnected.")
    except Exception as e:
            print(f"[CLIENT ERROR] {addr}: {e}")
    finally:
        full_disconnect(session)

# --- Main TCP server loop ---

def start_server(host,listen_port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, listen_port))
    srv.listen(64)
    print(f"[SERVER] LISTENING on {host}:{listen_port} \n")
    while True:
        try:
            client_sock, addr = srv.accept()
            # On connect, look up the Server object by port or bound IP (as needed)
            server = ServerManager.get_server_by_ip(host)
            session = {
                'socket': client_sock,
                'addr': addr,
                'server': server if listen_port == SERVER_PORT else None,  # Store the server object if conn from SERVER_PORT
                'server_id': server.id if server else None,
                'player_id': None,
                'channel_index': None,
                'player_index': None,
                'echo': {
                    'keepalive': {'token': None, 'reply': False, 'in_progress': False},
                    'readycheck': {'token': None, 'reply': False, 'in_progress': False}
                },
                'countdown_in_progress': False
                # other per-session state
            }
            threading.Thread(target=client_thread, args=(session,), daemon=True).start()
        except Exception as e:
            print(f"[ACCEPT ERROR] {e}")

def start_manager(host,listen_port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, listen_port))
    srv.listen(64)
    print(f"[MANAGER] LISTENING on {host}:{listen_port} \n")
    while True:
        try:
            client_sock, addr = srv.accept()
            session = {
                'socket': client_sock,
                'addr': addr
                # other per-session state
            }
            threading.Thread(target=client_thread, args=(session,), daemon=True).start()
        except Exception as e:
            print(f"[ACCEPT ERROR] {e}")

def admin_command_loop():
    print("Admin console ready. Type 'help' for commands.")
    while True:
        try:
            cmd = input("ADMIN> ").strip()
            if not cmd:
                continue
            if cmd.lower() in ("quit", "exit"):
                print("Exiting admin console (server still runs)...")
                break
            elif cmd.lower() == "help":
                print("Commands:")
                print("  sendhex HEXSTRING     # Send raw hex packet to all clients")
                print("  quit                  # Exit admin console")
            elif cmd.lower().startswith("sendhex "):
                hex_str = cmd.split(" ", 1)[1]
                try:
                    payload = bytes.fromhex(hex_str.replace(' ', ''))
                except Exception as e:
                    print(f"Invalid hex: {e}")
                    continue
                broadcast_manual_packet(payload, note="ADMIN TERMINAL")
                print(f"[ADMIN] Sent {len(payload)} bytes to all clients.")
            else:
                print("Unknown command. Type 'help' for help.")
        except EOFError:
            break
        except KeyboardInterrupt:
            break

@trace_calls
def is_session_socket_alive(session):
    sock = session.get('socket')
    if not sock:
        return False
    try:
        sock.send(b'')  # Zero-byte send for socket health check
        return True
    except OSError:
        return 
    
@trace_calls
def full_disconnect(session):
    # avoid closure of socket that is already closed
    if session.get('removed'):
        return

    addr = session.get('addr')
    player_id = session.get('player_id')
    server_id = session.get('server_id')
    channel_index = session.get('channel_index')
    player_index = session.get('player_index')

    channel_db_id = None
    if server_id is not None and channel_index is not None:
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
    
    lobby_name = None
    if channel_db_id is not None and player_id:
        lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
    
    lobby = None
    if lobby_name and channel_db_id is not None:
        lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)

    with sessions_lock:
        session['removed'] = True
        sessions.pop(addr, None)

    sock = session.get('socket')
    if sock and not session.get("removed"): # ensuring socket not already closed (redundancy)
        try:
            sock.setblocking(False)
            sock.send(b'')
            sock.setblocking(True)
            sock.shutdown(socket.SHUT_RDWR)
        except OSError as e:
            print(f"[DISCONNECT] Socket shutdown error for {addr}: {e}")
        finally:
            try:
                sock.close()
            except Exception as e:
                print(f"[DISCONNECT] Socket close error for {addr}: {e}")
    else:
        print(f"[DISCONNECT] No socket found for {addr}")

    print(f"[FORCED DISCONNECT] Closed session for {addr}")

    # Kick from lobby if needed
    if lobby_name and channel_db_id is not None:
        if player_index is None:
            print(f"[DISCONNECT WARNING] No cached player_index for {player_id}, falling back to DB lookup.")
            if lobby and player_id in lobby.player_ids:
                player_index = lobby.player_ids.index(player_id)
            else:
                print(f"Couldn't find lobby player index for player {player_id}.")
                player_index = -1

        removed_lobby, lobby_deleted = LobbyManager.remove_player_and_update_leader(player_id, channel_db_id)
        if not lobby_deleted:
            lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
            if lobby:
                status = LobbyManager.get_lobby_status(channel_db_id, lobby_name)
                if status == 1:
                    room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                    broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="[DISCONNECT ROOM UPDATE]")
                elif status == 2:
                    dc_packet = build_dc_packet(player_index)
                    broadcast_to_lobby(lobby_name, channel_db_id, dc_packet, note=f"[DISCONNECT DC {player_index}]")
                else:
                    print(f"Unknown Lobby Status: {status}")
        else:
            print(f"[DISCONNECT] Lobby '{lobby_name}' deleted after last player left.")


# Background thread for periodic echo checks
"""
NOTE: Player and session cleanup is performed in both the client handler's 'finally' block (for immediate/clean disconnect)
and in the echo watcher (for zombie/half-open sockets not reported as closed). This double layer is intentional for 
reliability, to handle both explicit disconnects and network-level failures.
"""

@trace_calls
def echo_watcher():
    WATCHER_SLEEP_TIME = 1
    ECHO_TIMEOUT = 20
    ECHO_RESPONSE_WAIT = 5

    while True:
        now = time.time()
        with sessions_lock:
            active_sessions = list(sessions.values())

        for session in active_sessions:
            player_id = session.get('player_id')
            if not player_id:
                continue

            # Only send echo to port 3658 sessions
            if session['addr'][1] != CLIENT_GAMEPLAY_PORT:
                continue
            
            # Only proceed if a countdown is not in progress
            if session.get('countdown_in_progress', False):
                continue

            # Check last-packet time for all sessions (even non-3658)
            with last_packet_lock:
                last_time = last_packet_times.get(player_id, 0)

            # Skip if not idle
            if now - last_time <= ECHO_TIMEOUT:
                continue

            # Skip if echo already in progress
            if session['echo']['keepalive']['in_progress']:
                continue

            # Check socket health before echoing
            if not is_session_socket_alive(session):
                print(f"[ECHO CHECK] Socket dead for {player_id}, immediate kick.")
                try:
                    full_disconnect(session)
                except Exception as e:
                    print(f"[DISCONNECT ERROR] Exception during full_disconnect [is_session_socket_alive]: {e}")
                continue

            #  Mark echo in progress and start 
            with sessions_lock:
                session['echo']['keepalive']['in_progress'] = True
                session['echo']['keepalive']['token'] = uuid.uuid4().hex
                session['echo']['keepalive']['reply'] = False
                echo_token = session['echo']['keepalive']['token']

            print(f"[ECHO CHECK] {player_id} idle for {int(now - last_time)}s, sending echo challenge...")

            @trace_calls
            def on_result(success, s=session, pid=player_id, token=None):
                with sessions_lock:
                    if s['echo']['keepalive']['token'] != token:
                        print(f"[ECHO ABORT] Echo token mismatch for {pid}, aborting kick.")
                        return
                    if success:
                        print(f"[ECHO SUCCESS] {pid} replied successfully, no action needed.")
                        return

                print(f"[ECHO FAIL] {pid} did not reply, disconnecting.")
                try:
                    full_disconnect(s)
                except Exception as e:
                    print(f"[DISCONNECT ERROR] Exception during full_disconnect for {pid}: {e}")
            
            @trace_calls
            def resend_echo_and_wait(s, pid, token):
                try:
                    for i in range(ECHO_RESPONSE_WAIT):
                        if not is_session_socket_alive(s):
                            print(f"[ECHO THREAD] Socket dead for {pid}, kicking immediately from echo thread.")
                            on_result(False,s, pid, token)
                            return
                        if s['echo']['keepalive']['token'] != token:
                            print(f"[ECHO THREAD] Token changed for {pid}, another echo thread is running or session replaced. Abort.")
                            return
                        try:
                            send_echo_challenge(s)
                        except Exception as e:
                            print(f"[ECHO ERROR] Failed to send echo to {pid}: {e}")
                            on_result(False, s, pid, token)
                            return
                        time.sleep(1)
                        if s['echo']['keepalive']['reply'] :
                            print(f"[ECHO REPLY] {pid} replied on attempt {i+1}.")
                            on_result(True, s, pid, token)
                            return
                    on_result(False,s, pid, token)
                finally:
                     s['echo']['keepalive']['in_progress'] = False
            
            threading.Thread(
                target=resend_echo_and_wait,
                args=(session, player_id, echo_token),
                daemon=True
            ).start()

        time.sleep(WATCHER_SLEEP_TIME)

@trace_calls
def update_last_packet_time(session):
    player_id = session.get('player_id')
    if player_id:
        with last_packet_lock:
            last_packet_times[player_id] = time.time()

def broadcast_manual_packet(payload: bytes, note="MANUAL BROADCAST"):
    """
    Broadcast a manual packet to all currently connected sessions.
    `payload` should be a complete packet (header + payload), e.g. from struct.pack or a hex string.
    """
    with sessions_lock:
        for session in sessions.values():
            try:
                send_packet_to_client(session, payload, note=note)
            except Exception as e:
                print(f"[MANUAL BROADCAST ERROR] {session['addr']}: {e}")

if __name__ == "__main__":
    # Clear latched lobbies in DB in case Server crashed
    ServerManager.init_server()
    # Start both servers (Manager and Server)
    threading.Thread(target=start_manager, args=(HOST,TCP_PORT,), daemon=True).start()
    threading.Thread(target=start_server, args=(SERVER,SERVER_PORT,), daemon=True).start()
    threading.Thread(target=echo_watcher, daemon=True).start()
    # Start admin console in main thread (so Ctrl+C works as expected)
    time.sleep(1)
    admin_command_loop()
    print("Admin console closed. Server still running in background threads.")
    while True:
        time.sleep(1)