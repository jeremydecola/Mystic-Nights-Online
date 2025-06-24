import threading
import time
import subprocess
import struct
import psycopg2
import os
from scapy.all import *


# Canada MAC: "00:ff:e5:67:d5:da"
# Korea  MAC: "00:ff:22:cc:b2:bf"
HOST = '211.233.10.5'
TCP_PORT = 18000
TCP_PORT_CHANNEL = 18001
MY_MAC = "00:ff:e5:67:d5:da"
IFACE = "OpenVPN TAP-Windows6"

previous_pkt_id = 0
pkt_cnt = 0
tcp_sessions = {}
#ip_to_player = {}
allow_manual_send = False
latest_session = None

#POSTGRES DATABASE CONNECTION
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

print("---------------------------------")
print("Mystic Nights Dummy Server v0.8.2")
print("---------------------------------")

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
        # See your DB query order!
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

###  END OF CLASS DEFINITIONS ###

def manual_packet_sender():
    global latest_session
    print("[INFO] Manual packet sending ENABLED. Type hex bytes (e.g. 0bc700...):")
    while True:
        pkt_hex = input("[SEND HEX]> ").strip()
        if not pkt_hex:
            continue
        try:
            pkt_bytes = bytes.fromhex(pkt_hex)
        except Exception as e:
            print(f"Invalid hex: {e}")
            continue
        if latest_session:
            send_packet_to_client(latest_session, pkt_bytes, note="[MANUAL SEND]")
        else:
            print("[ERROR] No session to send to.")

def send_packet_to_client(session, payload, tcp=None, client_data=None, note=""):
    ether = Ether(dst=session["mac"], src=MY_MAC)
    ip_layer = IP(src=HOST, dst=session["ip"])

    # If we have the last received TCP/Raw, set seq/ack exactly as in the legacy code
    if tcp is not None and client_data is not None:
        seq = session["seq"] + 1
        ack = tcp.seq + len(client_data)
        tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA", seq=seq, ack=ack)
        # Update the session state for next time
        session["seq"] += len(payload)
        session["ack"] = ack
    else:
        # fallback to just incrementing, NOT recommended unless for manual/incomplete sending
        tcp_layer = TCP(sport=session["sport"], dport=session["dport"], flags="PA", seq=session["seq"] + 1, ack=session["ack"])
        session["seq"] += len(payload)
        # session["ack"] should probably not change in this branch

    sendp(ether/ip_layer/tcp_layer/Raw(load=payload), iface=IFACE, verbose=False)
    msg = "[SEND]"
    if note:
        msg += f" {note}"
    print(f"{msg} To {session['ip']}:{session['dport']} ← {payload.hex()}")

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
    flag = b'\x01\x00\x00\x00'
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

def build_map_select_ack():
    val = 1
    packet_id = 0x0bc6
    flag = b'\x01\x00\x00\x00'
    payload = flag + struct.pack('<H', val)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_character_select_ack():
    packet_id = 0xbc5
    flag = b'\x01\x00\x00\x00'
    val = 1
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

def build_kick_player_ack():
    packet_id = 0xbc3
    flag = b'\x01\x00\x00\x00'
    val = 1
    payload = flag + struct.pack('<H', val)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_lobby_leave_ack():
    packet_id = 0xbc2
    flag = b'\x01\x00\x00\x00'
    val = 1
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

def build_game_start_ack(player_id):
    packet_id = 0xbc0
    flag = b'\x01\x00\x00\x00'
    pid = player_id.encode('ascii')[:16].ljust(16, b'\x00')
    param3, param4, param5 = 0, 0, 0
    payload = flag + pid + struct.pack('<HHh', param3, param4, param5)
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
    username = data[4:16].decode('ascii').rstrip('\x00')
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
    player_id = data[4:8].decode('ascii').rstrip('\x00')
    lobby_name = data[17:29].decode('ascii').rstrip('\x00')
    password = data[34:42].decode('ascii').rstrip('\x00')
    return player_id, lobby_name, password

def parse_lobby_join_packet(data):
    player_id = data[4:8].decode('ascii').rstrip('\x00')
    lobby_name = data[24:36].decode('ascii').rstrip('\x00')
    return player_id, lobby_name

def kill_process_using_port(port):
    print(f"Killing processes that may be using port {port}...")
    try:
        result = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True)
        for line in result.splitlines():
            parts = line.split()
            if len(parts) >= 5:
                pid = parts[-1]
                if int(pid) > 10:
                    print(f"Port {port} is being used by PID: {pid}.")
                    print(f"Attempting to terminate PID {pid}...")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True)
                    print(f"Successfully terminated process {pid}.")
    except subprocess.CalledProcessError:
        print(f"No process found using port {port}.")

kill_process_using_port(TCP_PORT)
kill_process_using_port(TCP_PORT_CHANNEL)

def enable_manual_packet_sender():
    global allow_manual_send
    if not allow_manual_send:
        allow_manual_send = True
        print("[MANUAL PACKET SENDER ENABLED]")
        threading.Thread(target=manual_packet_sender, daemon=True).start()

def handle_arp(pkt):
    if ARP in pkt and pkt[ARP].op == 1 and pkt[ARP].pdst == HOST:
        print(f"[SCAPY] ARP request from {pkt[ARP].psrc}")
        ether = Ether(dst=pkt[ARP].hwsrc, src=MY_MAC)
        arp = ARP(op=2, psrc=HOST, pdst=pkt[ARP].psrc, hwsrc=MY_MAC, hwdst=pkt[ARP].hwsrc)
        sendp(ether/arp, iface=IFACE, verbose=False)
        print(f"[SCAPY] Sent ARP reply for {HOST}")

def handle_ip(pkt):
    global allow_manual_send, latest_session, previous_pkt_id, pkt_cnt
    if not (pkt.haslayer(IP) and pkt.haslayer(TCP)):
        return
    
    ip = pkt[IP]
    tcp = pkt[TCP]
    key = (ip.src, tcp.sport)

    # Get the IP the packet was sent to (server IP)
    dest_ip = ip.dst

    #print(f"[DEBUG] handle_ip: {ip.src}:{tcp.sport}->{ip.dst}:{tcp.dport}, flags={tcp.flags}, seq={tcp.seq}, ack={tcp.ack}, payload={len(tcp.payload)} bytes")
    #if Raw in pkt:
        #print(f"[DEBUG] Raw payload: {pkt[Raw].load.hex()}")

    if ip.dst == HOST and tcp.dport in (18000, 18001) and tcp.flags == "S":
        if key in tcp_sessions:
            return
        print(f"[SCAPY] TCP SYN from {ip.src}:{tcp.sport} to port {tcp.dport}")
        seq_num = 1000
        ack_num = tcp.seq + 1
        ether = Ether(dst=pkt[Ether].src, src=MY_MAC)
        ip_layer = IP(src=ip.dst, dst=ip.src)
        tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="SA", seq=seq_num, ack=ack_num)
        sendp(ether/ip_layer/tcp_layer, iface=IFACE, verbose=False)
        tcp_sessions[key] = {
            "seq": seq_num,
            "ack": ack_num,
            "mac": pkt[Ether].src,
            "ip": ip.src,
            "sport": tcp.dport,
            "dport": tcp.sport,
            "is_channel": tcp.dport == 18001
        }
        print(f"[SCAPY] Sent SYN-ACK to {ip.src}:{tcp.sport} on port {tcp.dport}")

    elif tcp.flags == "PA" and key in tcp_sessions and Raw in pkt:
        session = tcp_sessions[key]
        client_data = pkt[Raw].load
        print(f"[RECV] From {ip.src}:{tcp.sport} on port {tcp.dport} → {client_data.hex()}")
        response = b''
        pkt_id = struct.unpack('<H', client_data[:2])[0] if len(client_data) >= 2 else None

        handled = True
        #join_cnt used for lobby join/create packet reply count
        if "join_cnt" not in session:
            session["join_cnt"] = 0

        if pkt_id == 0x07d1:  # Account create
            pid, plen, user, pwd = parse_account(client_data)
            print(f"[ACCOUNT CREATE REQ] User: {user} Pass: {pwd}")
            # Try to load first in case it exists
            player = PlayerManager.load_player_from_db(user)
            if player:
                response = build_account_creation_result(success=False, val=9)  # ID exists
                print(f"[SEND] Account already exists to {ip.src}:{tcp.sport} ← {response.hex()}")
            else:
                PlayerManager.create_player(user, pwd)
                response = build_account_creation_result(success=True)
                print(f"[SEND] Account creation OK to {ip.src}:{tcp.sport} ← {response.hex()}")
            latest_session = session

        elif pkt_id == 0x07d2:  # Account delete
            pid, plen, user, pwd = parse_account(client_data)
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
                        print(f"[SEND] Account deletion OK to {ip.src}:{tcp.sport} ← {response.hex()}")
                else:
                    response = build_account_deletion_result(success=False, val=7)
                    print(f"[SEND] Account deletion failed (wrong pw) to {ip.src}:{tcp.sport} ← {response.hex()}")
            else:
                response = build_account_deletion_result(success=False, val=8)
                print(f"[SEND] No such account to {ip.src}:{tcp.sport} ← {response.hex()}")
            latest_session = session

        elif pkt_id == 0x07df: # Server List
            response = build_server_list_packet()
            latest_session = session

        elif pkt_id == 0x07d3: # Channel List
            # Deduce server_id from destination IP
            server = ServerManager.get_server_by_ip(dest_ip)
            if server is None:
                print(f"[ERROR] Could not determine server for IP {dest_ip}")
                return
            server_id = server.id
            # Build channel list for this server
            response = build_channel_list_packet(server_id)
            latest_session = session

        elif pkt_id == 0x07e0: # Lobby List
            server_id = ServerManager.get_server_id_by_ip(dest_ip)
            channel_index = session.get('channel_index')
            print(f"server_id is: '{server_id}', channel_index is: '{channel_index}'")
            if server_id is not None and channel_index is not None:
                response = build_lobby_list_packet(server_id, channel_index)
            latest_session = session

        elif pkt_id == 0x07d0: # Login
            print("[DEBUG] Handling 0x07d0 LOGIN packet")
            print(f"[DEBUG] Raw client_data: {client_data.hex()}")
            if len(client_data) >= 30:
                player_id = client_data[4:16].decode('ascii', errors='replace').rstrip('\x00')
                pwd = client_data[17:29].decode('ascii', errors='replace').rstrip('\x00')
                print(f"[DEBUG] Parsed player_id: '{player_id}' (raw: {client_data[4:16].hex()})")
                print(f"[DEBUG] Parsed password: '{pwd}' (raw: {client_data[17:29].hex()})")
                player = PlayerManager.load_player_from_db(player_id)
                if player:
                    print(f"[DEBUG] Player found in DB: '{player.player_id}', expected password: '{player.password}'")
                    if player.password == pwd:
                        print(f"[LOGIN] Login OK for player '{player_id}'")
                        response = build_login_packet(success=True)
                    else:
                        print(f"[LOGIN] Login failed for player '{player_id}'. Received password: '{pwd}' != Expected password: '{player.password}")
                        response = build_login_packet(success=False, val=7)
                else:
                    print(f"[LOGIN] Player '{player_id}' not found in DB")
                    response = build_login_packet(success=False, val=8)
            else:
                print("[LOGIN] Malformed login request. Payload too short.")
                print(f"[DEBUG] Received length: {len(client_data)} bytes, expected >= 30 bytes")
                response = build_login_packet(success=False, val=5)
                
            latest_session = session

        elif pkt_id == 0x07d4:  # Channel join
            info = parse_channel_join_packet(client_data)
            player_id = info["player_id"]
            channel_index = info["channel_index"]

            # Determine which server based on packet's destination IP
            dest_ip = ip.dst  # from the sniffed packet
            server_id = ServerManager.get_server_id_by_ip(dest_ip)
            if server_id is None:
                print(f"[ERROR] Channel join for unknown server IP: {dest_ip}")
                response = build_channel_join_ack(success=False, val=5)
                send_packet_to_client(session, response, tcp=tcp, client_data=client_data)
                latest_session = session
                return

            # Get player from DB
            player = PlayerManager.load_player_from_db(player_id)
            if player:
                '''
                # --- Update DB: Increment player_count for this channel ---
                ChannelManager.increment_player_count(server_id, channel_index)
                '''
                print(f"[CHANNEL JOIN] Player {player.player_id} joined channel {channel_index} on server_id {server_id}")

            else:
                print(f"[ERROR] Channel join for unknown player: {player_id}")
            
            session['player_id'] = player_id  # <-- Store player_id per session
            session['channel_index'] = channel_index # <-- Store current channel_index in session
            response = build_channel_join_ack(success=True)
            latest_session = session

        elif pkt_id == 0x07d5:  # Lobby create
            player_id, lobby_name, password = parse_lobby_create_packet(client_data)
            player = PlayerManager.load_player_from_db(player_id)
            server_id = ServerManager.get_server_id_by_ip(dest_ip)
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)

            if channel_db_id is None or player is None:
                response = build_lobby_create_ack(success=False, val=5)
            elif not LobbyManager.create_lobby_db(lobby_name, password, channel_db_id, player_id):
                # Already exists or full
                lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
                if lobby is not None:
                    response = build_lobby_create_ack(success=False, val=0x10)  # Already exists
                else:
                    response = build_lobby_create_ack(success=False, val=0x0d)  # Full
            else:
                response = build_lobby_create_ack(success=True)
                send_packet_to_client(session, response, tcp=tcp, client_data=client_data)
                room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
                response = None
            if response:
                send_packet_to_client(session, response, tcp=tcp, client_data=client_data)
            latest_session = session

        elif pkt_id == 0x07d6:  # Lobby join
            player_id, lobby_name = parse_lobby_join_packet(client_data)
            player = PlayerManager.load_player_from_db(player_id)
            server_id = ServerManager.get_server_id_by_ip(dest_ip)
            channel_index = session.get('channel_index')
            channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)

            success = False
            val = 1  # Default

            if channel_db_id is None or player is None:
                print(f"[ERROR] Invalid channel or player missing. server_id={server_id}, channel_index={channel_index}, player={player_id}")
                val = 0x05  # Invalid parameter
            else:
                lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
                if not lobby:
                    print(f"[ERROR] Lobby '{lobby_name}' not found in channel {channel_db_id}")
                    val = 0x0f  # Lobby does not exist
                else:
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

            response = build_lobby_join_ack(success=success, val=val)
            send_packet_to_client(session, response, tcp=tcp, client_data=client_data)

            if success and channel_db_id is not None and lobby is not None:
                room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)

            latest_session = session

        elif pkt_id == 0x07d8:  # Game start request
            if len(client_data) >= 8:
                player_id = client_data[4:8].decode('ascii').rstrip('\x00')
                server_id = ServerManager.get_server_id_by_ip(dest_ip)
                channel_index = session.get('channel_index')
                channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
                lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
                print(f"[0x7d8] Game Start request by {player_id} in lobby {lobby_name}")
                if channel_db_id is not None and lobby_name:
                    LobbyManager.set_lobby_status(channel_db_id, lobby_name, 2)  # 2 = started/in progress
                bc0_response = build_game_start_ack(player_id)
                send_packet_to_client(session, bc0_response, tcp=tcp, client_data=client_data)
                # Optionally send updated lobby room packet:
                room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
            else:
                print(f"[ERROR] Malformed 0x07d8 packet (len={len(client_data)})")
            latest_session = session

        elif pkt_id == 0x07d9:  # Game ready request
            if len(client_data) >= 8:
                player_id = client_data[4:8].decode('ascii').rstrip('\x00')
                server_id = ServerManager.get_server_id_by_ip(dest_ip)
                channel_index = session.get('channel_index')
                channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
                lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
                if channel_db_id is not None and lobby_name:
                    new_status = LobbyManager.toggle_player_ready_in_lobby(channel_db_id, lobby_name, player_id)
                    print(f"[0x7d9] Player Ready request by {player_id}, new status: {new_status}")
                    bc1_response = build_player_ready_ack(success=True)
                    send_packet_to_client(session, bc1_response, tcp=tcp, client_data=client_data)
                    room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                    send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
                else:
                    print(f"[0x7d9] Player Ready failed: missing lobby or channel info.")
                    bc1_response = build_player_ready_ack(success=False, val=5)
                    send_packet_to_client(session, bc1_response, tcp=tcp, client_data=client_data)
            else:
                print(f"[ERROR] Malformed 0x07d9 packet (len={len(client_data)})")
                bc1_response = build_player_ready_ack(success=False, val=5)
                send_packet_to_client(session, bc1_response, tcp=tcp, client_data=client_data)
            latest_session = session

        elif pkt_id == 0x07da:  # Lobby leave
            if len(client_data) >= 8:
                player_id = client_data[4:8].decode('ascii').rstrip('\x00')
                server_id = ServerManager.get_server_id_by_ip(dest_ip)
                channel_index = session.get('channel_index')
                channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
                if channel_db_id is None:
                    print(f"[ERROR] No channel DB id for server_id={server_id}, channel_index={channel_index}")
                    ack_packet = build_lobby_leave_ack()
                elif not LobbyManager.remove_player_from_lobby_db(player_id, channel_db_id):
                    print(f"[WARN] Could not remove player {player_id} from lobby in channel {channel_db_id}")
                    ack_packet = build_lobby_leave_ack()
                else:
                    print(f"[LEAVE] Removed player: {player_id} from channel {channel_db_id}")
                    ack_packet = build_lobby_leave_ack()
                send_packet_to_client(session, ack_packet, tcp=tcp, client_data=client_data)
            latest_session = session

        elif pkt_id == 0x07db:  # Kick
            if len(client_data) >= 8:
                kick_idx = struct.unpack('<I', client_data[4:8])[0]
                server_id = ServerManager.get_server_id_by_ip(dest_ip)
                channel_index = session.get('channel_index')
                channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)

                print(f"[0x07db] Kick request: remove player at index {kick_idx} (channel_db_id={channel_db_id})")

                ack_packet = build_kick_player_ack()
                send_packet_to_client(session, ack_packet, tcp=tcp, client_data=client_data)

                player_id = session.get('player_id')
                lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
                if lobby_name:
                    lobby = LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
                    if lobby and 0 <= kick_idx < 4:
                        kicked_player_id = lobby.player_ids[kick_idx]
                        if kicked_player_id:
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
                    send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
            latest_session = session

        elif pkt_id == 0x07dc:  # Character info request
            if len(client_data) >= 8:
                requested_id = client_data[4:8].decode('ascii').rstrip('\x00')
                print(f"[0x7dc] Requested player info for: {requested_id}")

                server_id = ServerManager.get_server_id_by_ip(dest_ip)
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
                        send_packet_to_client(session, bc4_response, tcp=tcp, client_data=client_data)
            latest_session = session

        elif pkt_id == 0x07dd:  # Character select
            if len(client_data) >= 8:
                char_val = client_data[4]
                requested_id = session.get('player_id')
                server_id = ServerManager.get_server_id_by_ip(dest_ip)
                channel_index = session.get('channel_index')
                channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
                if requested_id and channel_db_id is not None:
                    # Update the player's character in the DB
                    LobbyManager.set_player_character(channel_db_id, requested_id, char_val)
                    ack_packet = build_character_select_ack()
                    send_packet_to_client(session, ack_packet, tcp=tcp, client_data=client_data)
                    lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, requested_id)
                    room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                    send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
            latest_session = session

        elif pkt_id == 0x07de:  # Map select
            if len(client_data) >= 8:
                desired_map = struct.unpack('<I', client_data[4:8])[0]
                player_id = session.get('player_id')
                server_id = ServerManager.get_server_id_by_ip(dest_ip)
                channel_index = session.get('channel_index')
                channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
                if player_id and channel_db_id is not None:
                    lobby_name = LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
                    if lobby_name:
                        LobbyManager.set_lobby_map(channel_db_id, lobby_name, desired_map)
                        ack_packet = build_map_select_ack()
                        send_packet_to_client(session, ack_packet, tcp=tcp, client_data=client_data)
                        room_packet = build_lobby_room_packet(lobby_name, channel_db_id)
                        send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
            latest_session = session

        else: #Unhandled packet_id
            handled = False
        
        if not handled:
            print(f"[WARN] Unhandled packet ID: 0x{pkt_id:04x}")
            enable_manual_packet_sender()

        if response:
            send_packet_to_client(session, response, tcp=tcp, client_data=client_data)
            latest_session = session

        previous_pkt_id = pkt_id

def packet_handler(pkt):
    if pkt.haslayer(ARP):
        handle_arp(pkt)
    elif pkt.haslayer(TCP):
        handle_ip(pkt)

def start_sniffer():
    sniff(filter=f"arp or (tcp port {TCP_PORT} or tcp port {TCP_PORT_CHANNEL})", prn=packet_handler, iface=IFACE, store=0)

if __name__ == "__main__":
    print(f"Waiting for connection on {HOST}:{TCP_PORT}")
    threading.Thread(target=start_sniffer, daemon=True).start()
    while True:
        time.sleep(1)
