import asyncio
import struct
import logging
import uuid
import os
import re
import functools
import time
import asyncpg
import aiosqlite
import sqlite3
import random
import aioconsole

print("-----------------------------------")
print("Mystic Nights Private Server v0.9.9")
print("-----------------------------------")

# ========== CONFIG ==========

HOST = '211.233.10.5'
TCP_PORT = 18000
SERVER_PORT = 18001
CLIENT_GAMEPLAY_PORT = 3658
DB_POOL = None
DEBUG = 1
### ECHO WATCHER
WATCHER_SLEEP_TIME = 1
ECHO_TIMEOUT = 20
ECHO_RESPONSE_WAIT = 5
###

sessions = {}  # {addr: session}
lobby_echo_results = {}   # {(channel_db_id, lobby_name): {player_id: bool}}
last_packet_times = {}  # player_id -> timestamp
sessions_lock = asyncio.Lock()
lobby_echo_lock = asyncio.Lock()
last_packet_lock = asyncio.Lock()
lobby_ready_lock = asyncio.Lock()

dbtype = os.environ.get("DB_TYPE", "sqlite")   # "postgres" or "sqlite"

if DEBUG == 2:
    # Clear the trace log on each script run
    if os.path.exists("trace.log"):
        open("trace.log", "w").close()
    logging.basicConfig(filename="trace.log", level=logging.DEBUG)
    logging.getLogger("importlib").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

def get_postgres_dsn():
    # Fallback to sensible defaults if env vars are missing
    host = os.environ.get("PG_HOST", "localhost")
    dbname = os.environ.get("PG_DBNAME", "postgres")
    user = os.environ.get("PG_USER", "postgres")
    password = os.environ.get("PG_PASSWORD", "")
    #port = os.environ.get("PG_PORT", "5432")  # Add port if needed

    # asyncpg supports either a DSN string or keyword arguments
    # We'll use DSN for compatibility
    # ex: dsn = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    dsn = f"postgresql://{user}:{password}@{host}/{dbname}"
    return dsn

def trace_calls(func):
    if not DEBUG:
        return func

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        logging.debug(f"[CALL] {func.__name__} args={args} kwargs={kwargs}")
        result = func(*args, **kwargs)
        logging.debug(f"[RETURN] {func.__name__} result={result}")
        return result

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        logging.debug(f"[CALL] {func.__name__} args={args} kwargs={kwargs}")
        result = await func(*args, **kwargs)
        logging.debug(f"[RETURN] {func.__name__} result={result}")
        return result

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

# ========= CLASSES ==========

class DBBase:
    async def connect(self): pass
    async def fetch(self, query, *args): pass
    async def fetchrow(self, query, *args): pass
    async def execute(self, query, *args): pass
    async def close(self): pass

class PostgresDB(DBBase):
    def __init__(self, dsn): self.dsn = dsn; self.pool = None
    async def connect(self): self.pool = await asyncpg.create_pool(dsn=self.dsn)
    async def fetch(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    async def fetchrow(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    async def execute(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    async def close(self):
        if self.pool: await self.pool.close()

class SQLiteDB:
    def __init__(self, db_file="mysticnights.db", schema_file="mn_sqlite_schema.sql"):
        self.db_file = db_file
        self.schema_file = schema_file
        self.conn = None

    @staticmethod
    def _rewrite_query(query):
        """
        Rewrite $1, $2... to '?' for SQLite parameter substitution.
        """
        return re.sub(r'\$\d+', '?', query)

    async def connect(self):
        """
        Open the database connection. Should only be called once.
        """
        self.conn = await aiosqlite.connect(self.db_file)
        # Row factory gives dict-like rows for easier coding
        self.conn.row_factory = aiosqlite.Row
    
    async def fetch(self, query, *args):
        query = self._rewrite_query(query)
        async with self.conn.execute(query, (*args,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetchrow(self, query, *args):
        query = self._rewrite_query(query)
        async with self.conn.execute(query, (*args,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def execute(self, query, *args):
        query = self._rewrite_query(query)
        async with self.conn.execute(query, (*args,)) as cursor:
            await self.conn.commit()
            return cursor.rowcount

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    def create_db_if_missing(self):
        """
        Create the database and run schema SQL if the file doesn't exist.
        This is a synchronous operation and should be done before opening with aiosqlite.
        """
        if os.path.exists(self.db_file):
            return
        if not os.path.exists(self.schema_file):
            raise FileNotFoundError(f"Schema file not found: {self.schema_file}")
        with open(self.schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        with sqlite3.connect(self.db_file) as conn:
            conn.executescript(schema_sql)

    @classmethod
    async def init(cls, db_file="mysticnights.db", schema_file="mn_sqlite_schema.sql"):
        """
        Factory method to create and initialize the DB if needed.
        """
        self = cls(db_file, schema_file)
        self.create_db_if_missing()
        await self.connect()
        return self

class DBManager:
    _instance = None
    _backend = None

    @classmethod
    async def init(cls, dsn=None, dbtype="postgres", sqlite_file=None, schema_file="mn_sqlite_schema.sql"):
        if dbtype == "postgres":
            cls._backend = PostgresDB(dsn)
            await cls._backend.connect()
        elif dbtype == "sqlite":
            # Use SQLiteDB.init so schema gets created if missing
            cls._backend = await SQLiteDB.init(db_file=sqlite_file or "mysticnights.db", schema_file=schema_file)
        else:
            raise ValueError(f"Unknown dbtype: {dbtype}")
        cls._instance = cls._backend

    @classmethod
    def instance(cls):
        if not cls._instance: raise Exception("DBManager is not initialized.")
        return cls._instance

    @classmethod
    async def fetch(cls, query, *args):
        return await cls._instance.fetch(query, *args)
    @classmethod
    async def fetchrow(cls, query, *args):
        return await cls._instance.fetchrow(query, *args)
    @classmethod
    async def execute(cls, query, *args):
        return await cls._instance.execute(query, *args)
    @classmethod
    async def close(cls):
        await cls._instance.close()

class Server:
    def __init__(self, id, name, ip_address, player_count=0, availability=0):
        self.id = id
        self.name = name
        self.ip_address = ip_address
        self.player_count = player_count
        self.availability = availability

    @classmethod
    def from_row(cls, row):
        # Works for dict/Row/asyncpg.Record, else fallback to tuple
        try:
            return cls(
                row['id'],
                row['name'],
                row['ip_address'],
                row['player_count'],
                row['availability']
            )
        except (KeyError, TypeError):
            # fallback: tuple or list
            return cls(row[0], row[1], row[2], row[3], row[4])

class ServerManager:
    @classmethod
    async def get_server_by_ip(cls, ip_address):
        print("get_server_by_ip:", repr(ip_address), type(ip_address))
        row = await DBManager.fetchrow(
            "SELECT id, name, ip_address, player_count, availability FROM servers WHERE ip_address = $1",
            ip_address
        )
        return Server.from_row(row) if row else None

    @classmethod
    async def get_server_id_by_ip(cls, ip_address):
        server = await cls.get_server_by_ip(ip_address)
        return server.id if server else None

    @classmethod
    async def get_servers(cls):
        rows = await DBManager.fetch(
            "SELECT id, name, ip_address, player_count, availability FROM servers"
        )
        return [Server.from_row(row) for row in rows]

    @classmethod
    async def print_server_table(cls):
        servers = await cls.get_servers()
        print("-" * 60)
        print("{:<4} {:<16} {:<20} {:<10}".format("Idx", "Name", "IP (String)", "Status"))
        print("-" * 60)
        status_map = {-1: "알수없음", 0: "적음", 1: "보통", 2: "많음"}
        for idx, s in enumerate(servers):
            status_str = status_map.get(s.availability, str(s.availability))
            print("{:<4} {:<16} {:<20} {:<10}".format(idx, s.name, s.ip_address, status_str))
        print("-" * 60)

    @classmethod
    async def init_server(cls):
        # On initial startup, remove all lobbies whose name does NOT contain 'Test' (case-sensitive).
        result = await DBManager.execute("DELETE FROM lobbies WHERE name NOT LIKE $1", '%Test%')

        # Support both asyncpg ("DELETE N") and aiosqlite (int rowcount)
        if isinstance(result, int):
            deleted = result
        elif isinstance(result, str) and result.startswith("DELETE "):
            try:
                deleted = int(result.split(" ")[1])
            except Exception:
                deleted = '?'
        else:
            deleted = '?'
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
        # Accepts an asyncpg.Record or a dict
        return cls(
            id=row['id'],
            player_id=row['player_id'],
            password=row['password'],
            rank=row.get('rank', 1),
            created_at=row.get('created_at')
        )
    
class Channel:
    def __init__(self, id, server_id, channel_index, player_count=0):
        self.id = id
        self.server_id = server_id
        self.channel_index = channel_index
        self.player_count = player_count

    @classmethod
    def from_row(cls, row):
        # More robust for column order changes and missing columns
        return cls(
            id=row['id'],
            server_id=row['server_id'],
            channel_index=row['channel_index'],
            player_count=row.get('player_count', 0)
        )

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
        # robust: works even if column order changes
        return cls(
            id=row['id'],
            channel_id=row['channel_id'],
            idx_in_channel=row['idx_in_channel'],
            name=row['name'],
            password=row['password'],
            player_count=row.get('player_count', 0),
            status=row.get('status', 1),
            map=row.get('map', 1),
            leader=row.get('leader'),
            player1_id=row.get('player1_id'), player1_character=row.get('player1_character'), player1_status=row.get('player1_status'),
            player2_id=row.get('player2_id'), player2_character=row.get('player2_character'), player2_status=row.get('player2_status'),
            player3_id=row.get('player3_id'), player3_character=row.get('player3_character'), player3_status=row.get('player3_status'),
            player4_id=row.get('player4_id'), player4_character=row.get('player4_character'), player4_status=row.get('player4_status')
        )

    def as_short_tuple(self):
        """Used for lobby list: returns (idx_in_channel, player_count, name, password, status)"""
        return (self.idx_in_channel, self.player_count, self.name, self.password, self.status)


class PlayerManager:
    @classmethod
    async def load_player_from_db(cls, player_id):
        query = "SELECT id, player_id, password, rank, created_at FROM players WHERE player_id = $1"
        row = await DBManager.fetchrow(query, player_id)
        if row:
            return Player.from_row(row)
        return None

    @classmethod
    async def create_player(cls, player_id, password, rank=1):
        if dbtype == "postgres":
            query = """
                INSERT INTO players (player_id, password, rank) 
                VALUES ($1, $2, $3)
                RETURNING id, player_id, password, rank, created_at
            """
            row = await DBManager.fetchrow(query, player_id, password, rank)
        else:  # Assume SQLite
            insert_query = """
                INSERT INTO players (player_id, password, rank) 
                VALUES (?, ?, ?)
            """
            await DBManager.execute(insert_query, player_id, password, rank)
            # Now get the last inserted row (SQLite only)
            query = "SELECT id, player_id, password, rank, created_at FROM players WHERE player_id = ?"
            row = await DBManager.fetchrow(query, player_id)
        if row:
            return Player.from_row(row)
        return None

    @classmethod
    async def remove_player(cls, player_id):
        query = "DELETE FROM players WHERE player_id = $1"
        try:
            await DBManager.execute(query, player_id)
            return True
        except Exception as e:
            # Optionally log error here
            return False

    @classmethod
    async def add_rank_points(cls, player_id, points, max_rank=199):
        if dbtype == "postgres":
            query = """
                UPDATE players 
                SET rank = LEAST(rank + $1, $2)
                WHERE player_id = $3
            """
            await DBManager.execute(query, points, max_rank, player_id)
        else:  # SQLite
            query = """
                UPDATE players 
                SET rank = MIN(rank + ?, ?)
                WHERE player_id = ?
            """
            await DBManager.execute(query, points, max_rank, player_id)

class ChannelManager:
    @classmethod
    async def get_channel_db_id(cls, server_id, channel_index):
        """Returns the primary key (id) in channels table for a given server_id and channel_index."""
        row = await DBManager.fetchrow(
            "SELECT id FROM channels WHERE server_id = $1 AND channel_index = $2",
            server_id, channel_index
        )
        return row['id'] if row else None

    @classmethod
    async def get_channels_for_server(cls, server_id):
        """Return a list of Channel objects for this server_id."""
        rows = await DBManager.fetch(
            "SELECT id, server_id, channel_index, player_count FROM channels WHERE server_id = $1;",
            server_id
        )
        return [Channel.from_row(row) for row in rows]

    @classmethod
    async def get_channel(cls, server_id, channel_index):
        """Return Channel object for a given server_id and channel_index."""
        row = await DBManager.fetchrow(
            "SELECT id, server_id, channel_index, player_count FROM channels WHERE server_id = $1 AND channel_index = $2;",
            server_id, channel_index
        )
        return Channel.from_row(row) if row else None

    @classmethod
    async def print_channel_table(cls, server_id=None):
        """Prints all channels, or just those for a given server_id."""
        if server_id is None:
            rows = await DBManager.fetch("SELECT id, server_id, channel_index, player_count FROM channels;")
        else:
            rows = await DBManager.fetch(
                "SELECT id, server_id, channel_index, player_count FROM channels WHERE server_id = $1;",
                server_id
            )
        print("-" * 50)
        print("{:<8} {:<8} {:<8} {:<12}".format("SrvID", "ChIdx", "ID", "Players"))
        print("-" * 50)
        for row in sorted(rows, key=lambda c: (c['server_id'], c['channel_index'])):
            print("{:<8} {:<8} {:<8} {:<12}".format(
                row['server_id'], row['channel_index'], row['id'], row['player_count']
            ))
        print("-" * 50)

    @classmethod
    async def increment_player_count(cls, server_id, channel_index):
        await DBManager.execute(
            "UPDATE channels SET player_count = player_count + 1 WHERE server_id = $1 AND channel_index = $2;",
            server_id, channel_index
        )

    @classmethod
    async def decrement_player_count(cls, server_id, channel_index):
        if dbtype == "postgres":
            query = "UPDATE channels SET player_count = GREATEST(player_count - 1, 0) WHERE server_id = $1 AND channel_index = $2;"
        else:  # SQLite
            query = "UPDATE channels SET player_count = MAX(player_count - 1, 0) WHERE server_id = ? AND channel_index = ?;"
        await DBManager.execute(query, server_id, channel_index)


class LobbyManager:
    @classmethod
    async def get_lobbies_for_channel(cls, channel_db_id):
        rows = await DBManager.fetch("""
            SELECT id, channel_id, idx_in_channel, name, password, player_count, status, map, leader,
                   player1_id, player1_character, player1_status,
                   player2_id, player2_character, player2_status,
                   player3_id, player3_character, player3_status,
                   player4_id, player4_character, player4_status
            FROM lobbies
            WHERE channel_id = $1
            ORDER BY idx_in_channel ASC
        """, channel_db_id)
        return [Lobby.from_row(row) for row in rows]

    @classmethod
    async def get_lobby_by_name(cls, lobby_name, channel_db_id):
        row = await DBManager.fetchrow("""
            SELECT id, channel_id, idx_in_channel, name, password, player_count, status, map, leader,
                   player1_id, player1_character, player1_status,
                   player2_id, player2_character, player2_status,
                   player3_id, player3_character, player3_status,
                   player4_id, player4_character, player4_status
            FROM lobbies
            WHERE name = $1 AND channel_id = $2
        """, lobby_name, channel_db_id)
        return Lobby.from_row(row) if row else None

    @classmethod
    async def set_player_character(cls, channel_db_id, player_id, character):
        rows = await DBManager.fetch("""
            SELECT id, player1_id, player2_id, player3_id, player4_id
            FROM lobbies WHERE channel_id = $1
        """, channel_db_id)
        for row in rows:
            lobby_id = row['id']
            for idx, pid in enumerate([row['player1_id'], row['player2_id'], row['player3_id'], row['player4_id']], 1):
                if pid == player_id:
                    await DBManager.execute(
                        f"UPDATE lobbies SET player{idx}_character=$1 WHERE id=$2",
                        character, lobby_id
                    )
                    return True
        return False

    @classmethod
    async def set_lobby_map(cls, channel_db_id, lobby_name, map_id):
        await DBManager.execute(
            "UPDATE lobbies SET map=$1 WHERE channel_id=$2 AND name=$3",
            map_id, channel_db_id, lobby_name
        )

    @classmethod
    async def get_lobby_name_for_player(cls, channel_db_id, player_id):
        if dbtype == "postgres":
            row = await DBManager.fetchrow(
                """SELECT name FROM lobbies
                   WHERE channel_id=$1 AND
                   (player1_id=$2 OR player2_id=$2 OR player3_id=$2 OR player4_id=$2)""",
                channel_db_id, player_id
            )
        else: # sqlite
            row = await DBManager.fetchrow(
                """SELECT name FROM lobbies
                   WHERE channel_id=? AND
                   (player1_id=? OR player2_id=? OR player3_id=? OR player4_id=?)""",
                channel_db_id, player_id, player_id, player_id, player_id
            )
        return row['name'] if row else None

    @classmethod
    async def create_lobby_db(cls, lobby_name, password, channel_db_id, player_id):
        # Check if lobby exists or full
        rows = await cls.get_lobbies_for_channel(channel_db_id)
        if any(lobby.name == lobby_name for lobby in rows):
            print(f"[ERROR] Lobby '{lobby_name}' already exists in channel {channel_db_id}")
            return False
        used_indices = {lobby.idx_in_channel for lobby in rows}
        for idx_in_channel in range(20):
            if idx_in_channel not in used_indices:
                break
        else:
            print(f"[ERROR] No more lobby slots available in channel {channel_db_id}")
            return False

        await DBManager.execute(
            """INSERT INTO lobbies
               (channel_id, idx_in_channel, name, password, status, player1_id, player1_character, player1_status, player_count, leader, map)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 1, $9, 1)
            """, channel_db_id, idx_in_channel, lobby_name, password, 1, player_id, 1, 0, player_id
        )
        print(f"[DB] Created lobby '{lobby_name}' in channel {channel_db_id} idx {idx_in_channel}")
        return True

    @classmethod
    async def add_player_to_lobby_db(cls, lobby_name, channel_db_id, player_id):
        lobby = await cls.get_lobby_by_name(lobby_name, channel_db_id)
        if not lobby:
            print(f"[ERROR] Lobby '{lobby_name}' not found in DB for add_player.")
            return False
        player_slots = lobby.player_ids
        characters_taken = set(filter(None, lobby.player_characters))
        char_choices = {1,2,3,4,5,6,7,8} - characters_taken
        assigned_character = min(char_choices) if char_choices else 1
        assigned_status = 0  # "preparing"
        for idx, slot in enumerate(player_slots, 1):
            if slot is None:
                await DBManager.execute(
                    f"""UPDATE lobbies
                        SET player{idx}_id = $1,
                            player{idx}_character = $2,
                            player{idx}_status = $3,
                            player_count = player_count + 1
                        WHERE id = $4""",
                    player_id, assigned_character, assigned_status, lobby.id
                )
                print(f"[DB] Added player {player_id} to lobby '{lobby_name}' (slot {idx}, char {assigned_character}).")
                return True
        print(f"[WARN] No empty player slot in lobby '{lobby_name}'")
        return False

    @classmethod
    async def remove_player_from_lobby_db(cls, player_id, channel_db_id=None):
        if channel_db_id is not None:
            if dbtype == "postgres":
                row = await DBManager.fetchrow("""
                    SELECT id, idx_in_channel, player1_id, player2_id, player3_id, player4_id
                    FROM lobbies
                    WHERE channel_id = $1
                      AND ($2 = ANY(ARRAY[player1_id, player2_id, player3_id, player4_id]))
                """, channel_db_id, player_id)
            else:  # SQLite
                row = await DBManager.fetchrow("""
                    SELECT id, idx_in_channel, player1_id, player2_id, player3_id, player4_id
                    FROM lobbies
                    WHERE channel_id = ?
                      AND (player1_id = ? OR player2_id = ? OR player3_id = ? OR player4_id = ?)
                """, channel_db_id, player_id, player_id, player_id, player_id)
        else:
            # This query works on both backends since it doesn't use ANY/ARRAY
            row = await DBManager.fetchrow("""
                SELECT id, idx_in_channel, player1_id, player2_id, player3_id, player4_id
                FROM lobbies
                WHERE player1_id = $1 OR player2_id = $1 OR player3_id = $1 OR player4_id = $1
            """, player_id)
        if not row:
            print(f"[WARN] Player {player_id} not found in any lobby for removal.")
            return False
        lobby_id, idx_in_channel, p1, p2, p3, p4 = (
            row['id'], row['idx_in_channel'], row['player1_id'], row['player2_id'], row['player3_id'], row['player4_id']
        )
        for idx, slot in enumerate([p1, p2, p3, p4], 1):
            if slot == player_id:
                if dbtype == "postgres":
                    await DBManager.execute(
                        f"""UPDATE lobbies
                            SET player{idx}_id = NULL,
                                player{idx}_character = NULL,
                                player{idx}_status = NULL,
                                player_count = GREATEST(player_count - 1, 0)
                            WHERE id = $1
                        """, lobby_id
                    )
                else: # sqlite
                    await DBManager.execute(
                        f"""UPDATE lobbies
                            SET player{idx}_id = NULL,
                                player{idx}_character = NULL,
                                player{idx}_status = NULL,
                                player_count = MAX(player_count - 1, 0)
                            WHERE id = ?
                        """, lobby_id
                    )
                print(f"[DB] Removed player {player_id} from lobby (idx {idx_in_channel}).")
                return True
        return False

    @classmethod
    async def remove_player_and_update_leader(cls, player_id, channel_db_id):
        # NOTE: thread locking must be done outside this method for asyncio!
        if dbtype == "postgres":
            row = await DBManager.fetchrow("""
                SELECT id, name, leader,
                       player1_id, player2_id, player3_id, player4_id
                FROM lobbies
                WHERE channel_id = $1 AND ($2 = ANY(ARRAY[player1_id, player2_id, player3_id, player4_id]))
            """, channel_db_id, player_id)
        else: #sqlite
            row = await DBManager.fetchrow("""
                SELECT id, name, leader,
                       player1_id, player2_id, player3_id, player4_id
                FROM lobbies
                WHERE channel_id = ? AND
                    (? = player1_id OR ? = player2_id OR ? = player3_id OR ? = player4_id)
            """, channel_db_id, player_id, player_id, player_id, player_id)
        if not row:
            return (None, False)
        lobby_id, lobby_name, leader, p1, p2, p3, p4 = (
            row['id'], row['name'], row['leader'],
            row['player1_id'], row['player2_id'], row['player3_id'], row['player4_id']
        )
        player_slots = [p1, p2, p3, p4]
        cleared = False
        for idx, pid in enumerate(player_slots, 1):
            if pid == player_id:
                if dbtype == "postgres":
                    await DBManager.execute(
                        f"""UPDATE lobbies
                            SET player{idx}_id = NULL,
                                player{idx}_character = NULL,
                                player{idx}_status = NULL,
                                player_count = GREATEST(player_count - 1, 0)
                            WHERE id = $1
                        """, lobby_id
                    )
                else: # sqlite
                    await DBManager.execute(
                        f"""UPDATE lobbies
                            SET player{idx}_id = NULL,
                                player{idx}_character = NULL,
                                player{idx}_status = NULL,
                                player_count = MAX(player_count - 1, 0)
                            WHERE id = ?
                        """, lobby_id
                    )
                cleared = True
        if not cleared:
            return (None, False)
        # Reload updated slots and leader
        row2 = await DBManager.fetchrow(
            "SELECT leader, player1_id, player2_id, player3_id, player4_id FROM lobbies WHERE id=$1", lobby_id
        )
        leader, p1, p2, p3, p4 = row2['leader'], row2['player1_id'], row2['player2_id'], row2['player3_id'], row2['player4_id']
        slots = [(1, p1), (2, p2), (3, p3), (4, p4)]
        non_empty = [(i, pid) for i, pid in slots if pid]
        # If leader was removed or is now None, assign to lowest index remaining
        if (leader == player_id) or (not leader) or (leader not in [pid for _, pid in non_empty]):
            new_leader = non_empty[0][1] if non_empty else None
            await DBManager.execute(
                "UPDATE lobbies SET leader=$1 WHERE id=$2", new_leader, lobby_id
            )
        # If lobby is now empty, delete it
        if not non_empty:
            await DBManager.execute("DELETE FROM lobbies WHERE id=$1", lobby_id)
            print(f"[LOBBY DELETED] Lobby '{lobby_name}' deleted (was empty after player leave/disconnect).")
            return (lobby_name, True)
        return (lobby_name, False)

    @classmethod
    async def is_player_in_lobby_db(cls, lobby_name, channel_db_id, player_id):
        row = await DBManager.fetchrow("""
            SELECT player1_id, player2_id, player3_id, player4_id
            FROM lobbies
            WHERE name = $1 AND channel_id = $2
        """, lobby_name, channel_db_id)
        if not row:
            return False
        return player_id in [row['player1_id'], row['player2_id'], row['player3_id'], row['player4_id']]

    @classmethod
    async def toggle_player_ready_in_lobby(cls, channel_db_id, lobby_name, player_id):
        row = await DBManager.fetchrow("""
            SELECT player1_id, player2_id, player3_id, player4_id,
                   player1_status, player2_status, player3_status, player4_status
            FROM lobbies WHERE name = $1 AND channel_id = $2
        """, lobby_name, channel_db_id)
        if not row:
            return None
        ids = [row['player1_id'], row['player2_id'], row['player3_id'], row['player4_id']]
        statuses = [row['player1_status'], row['player2_status'], row['player3_status'], row['player4_status']]
        for idx, pid in enumerate(ids):
            if pid == player_id:
                new_status = 0 if (statuses[idx] or 0) == 1 else 1
                await DBManager.execute(
                    f"UPDATE lobbies SET player{idx+1}_status = $1 WHERE name = $2 AND channel_id = $3",
                    new_status, lobby_name, channel_db_id
                )
                return new_status
        return None

    @classmethod
    async def set_player_not_ready(cls, player_id, channel_db_id, lobby_name):
        if dbtype == "postgres":
            await DBManager.execute("""
                UPDATE lobbies
                SET player1_status = CASE WHEN player1_id=$1 THEN 0 ELSE player1_status END,
                    player2_status = CASE WHEN player2_id=$1 THEN 0 ELSE player2_status END,
                    player3_status = CASE WHEN player3_id=$1 THEN 0 ELSE player3_status END,
                    player4_status = CASE WHEN player4_id=$1 THEN 0 ELSE player4_status END
                WHERE name = $2 AND channel_id = $3
            """, player_id, lobby_name, channel_db_id)
        else: #sqlite
            await DBManager.execute("""
                UPDATE lobbies
                SET player1_status = CASE WHEN player1_id = ? THEN 0 ELSE player1_status END,
                    player2_status = CASE WHEN player2_id = ? THEN 0 ELSE player2_status END,
                    player3_status = CASE WHEN player3_id = ? THEN 0 ELSE player3_status END,
                    player4_status = CASE WHEN player4_id = ? THEN 0 ELSE player4_status END
                WHERE name = ? AND channel_id = ?
            """, player_id, player_id, player_id, player_id, lobby_name, channel_db_id)

    @classmethod
    async def set_lobby_status(cls, channel_db_id, lobby_name, status):
        await DBManager.execute(
            "UPDATE lobbies SET status=$1 WHERE name=$2 AND channel_id=$3",
            status, lobby_name, channel_db_id
        )

    @classmethod
    async def get_lobby_status(cls, channel_db_id, lobby_name):
        row = await DBManager.fetchrow(
            "SELECT status FROM lobbies WHERE name = $1 AND channel_id = $2",
            lobby_name, channel_db_id
        )
        return row['status'] if row else None

    @classmethod
    async def get_player_character_from_slot_id(cls, lobby_name, channel_db_id, slot_id):
        lobby = await cls.get_lobby_by_name(lobby_name, channel_db_id)
        if lobby and 0 <= slot_id <= 3:
            return lobby.player_characters[slot_id] or 0
        return 0  # Return 0 (default) if not found or invalid slot

    @classmethod
    async def print_lobby_table(cls, channel_id=None):
        if channel_id is not None:
            rows = await DBManager.fetch("""
                SELECT id, channel_id, idx_in_channel, name, password, player_count, status, map, leader,
                       player1_id, player1_character, player1_status,
                       player2_id, player2_character, player2_status,
                       player3_id, player3_character, player3_status,
                       player4_id, player4_character, player4_status
                FROM lobbies
                WHERE channel_id = $1
                ORDER BY idx_in_channel ASC
            """, channel_id)
        else:
            rows = await DBManager.fetch("""
                SELECT id, channel_id, idx_in_channel, name, password, player_count, status, map, leader,
                       player1_id, player1_character, player1_status,
                       player2_id, player2_character, player2_status,
                       player3_id, player3_character, player3_status,
                       player4_id, player4_character, player4_status
                FROM lobbies
                ORDER BY channel_id ASC, idx_in_channel ASC
            """)
        lobbies = [Lobby.from_row(row) for row in rows]
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

async def build_channel_list_packet(server_id):
    packet_id = 0x0bbb
    flag = b'\x01\x00\x00\x00'
    entries = []

    # Get all channels for this server from DB (async)
    channels_list = await ChannelManager.get_channels_for_server(server_id)
    channels = {ch.channel_index: ch for ch in channels_list}

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
    if DEBUG:
        await ChannelManager.print_channel_table(server_id)
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
def build_lobby_quick_join_ack(success=True, val=1):
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

async def build_lobby_list_packet(server_id, channel_index):
    packet_id = 0xbc8
    flag = b'\x01\x00\x00\x00'
    entry_struct = '<III16s1s12s1sB1s'
    max_lobbies = 20
    entries = [None] * max_lobbies

    channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
    rows = []
    if channel_db_id is not None:
        rows = await LobbyManager.get_lobbies_for_channel(channel_db_id)

    for lobby in rows:
        idx = lobby.idx_in_channel
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
        packed = struct.pack(entry_struct, idx, player_count, max_players, name_enc, pad1, pw_enc, pad2, status, pad3)
        if 0 <= idx < max_lobbies:
            entries[idx] = packed

    # Fill unused slots
    for idx in range(max_lobbies):
        if entries[idx] is None:
            name = f"Lobby{idx+1}".encode('euc-kr')[:16].ljust(16, b'\x00')
            pad1 = b'\x00'
            pw_enc = b"".ljust(12, b'\x00')
            pad2 = b'\x00'
            status = 0
            pad3 = b'\x00'
            packed = struct.pack(entry_struct, idx, 0, 4, name, pad1, pw_enc, pad2, status, pad3)
            entries[idx] = packed

    payload = flag + b''.join(entries)
    header = struct.pack('<HH', packet_id, len(payload))
    if DEBUG:
        await LobbyManager.print_lobby_table(channel_db_id)
    return header + payload

async def build_server_list_packet():
    packet_id = 0x0bc7
    flag = b'\x01\x00\x00\x00'
    servers = []
    server_list = await ServerManager.get_servers()
    for server in server_list:
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
    if DEBUG:
        await ServerManager.print_server_table()
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

async def build_game_start_ack(lobby_name, channel_db_id, success= True, val=1, player_count=4):
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
        vampire_character = await LobbyManager.get_player_character_from_slot_id(lobby_name, channel_db_id, vampire_id)
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

async def build_lobby_room_packet(lobby_name, channel_db_id):
    lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
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
            player = await PlayerManager.load_player_from_db(pid_str)
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
    Build the 0x03f4 Player DC packet.
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

async def send_echo_challenge(session, payload=None, broadcast=False):
    packet_id = 0x03e9
    payload = payload or b'\x01\x00\x00\x00'
    header = struct.pack('<HH', packet_id, len(payload))
    packet = header + payload[:4]
    if broadcast:
        player_id = session.get('player_id')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        await broadcast_to_lobby(lobby_name, channel_db_id, packet, note="[ECHO CHALLENGE 0x03e9]")
    else:
        await send_packet_to_client(session, packet, note="[ECHO CHALLENGE 0x03e9]")

async def run_echo_challenge(session, purpose, payload=None, timeout=10, interval=1, on_result=None):
    """
    Sends echo challenges at `interval` seconds until reply or `timeout` seconds passed.
    Calls `on_result(success:bool)` with True if reply, False if timeout.
    """
    token = uuid.uuid4().hex
    if 'echo' not in session:
        session['echo'] = {}
    if purpose not in session['echo']:
        session['echo'][purpose] = {}
    session['echo'][purpose]['token'] = token
    session['echo'][purpose]['reply'] = False
    session['echo'][purpose]['in_progress'] = True

    for i in range(timeout):
        if session['echo'][purpose]['reply']:
            print(f"[ECHO {purpose.upper()}] {session.get('player_id')} replied in {i+1}s.")
            if on_result:
                await on_result(True)
            session['echo'][purpose]['in_progress'] = False
            return
        await send_echo_challenge(session)
        await asyncio.sleep(interval)

    print(f"[ECHO {purpose.upper()}] {session.get('player_id')} timed out.")
    if on_result:
        await on_result(False)
    session['echo'][purpose]['in_progress'] = False


async def send_packet_to_client(session, payload, note=""):
    try:
        writer = session['writer']  # should be an asyncio.StreamWriter
        writer.write(payload)
        await writer.drain()
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

async def broadcast_to_lobby(lobby_name, channel_db_id, payload, note="", cur_session=None, to_self=True):
    lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
    if not lobby:
        print(f"[BROADCAST ERROR] Lobby '{lobby_name}' not found in channel {channel_db_id}")
        return

    target_ids = {pid for pid in lobby.player_ids if pid}

    async with sessions_lock:
        targets = [
            s for s in sessions.values()
            if s.get("player_id") in target_ids and s['addr'][1] == CLIENT_GAMEPLAY_PORT
        ]

    # Use asyncio.gather to send to all clients concurrently
    await asyncio.gather(*[
        send_packet_to_client(s, payload, note=f"[BROADCAST] {lobby_name}] {note}")
        for s in targets
        if not s.get('removed') and (to_self or s is not cur_session)
    ])

async def handle_client_packet(session, data):
    # The session is now a dict: {'socket': sock, 'addr': addr, ...}
    # All DB and network calls are async!
    pkt_id, payload_len = parse_packet_header(data)
    if pkt_id is None:
        print(f"[ERROR] Packet too short from {session['addr']}")
        return

    response = None
    await update_last_packet_time(session) 

    # --- Login ---
    if pkt_id == 0x07d0:
        print("[DEBUG] Handling 0x07d0 LOGIN packet")
        print(f"[DEBUG] Raw client_data: {data.hex()}")
        if len(data) >= 30:
            player_id = data[4:16].decode('ascii', errors='replace').rstrip('\x00')
            pwd = data[17:29].decode('ascii', errors='replace').rstrip('\x00')
            print(f"[DEBUG] Parsed player_id: '{player_id}' (raw: {data[4:16].hex()})")
            print(f"[DEBUG] Parsed password: '{pwd}' (raw: {data[17:29].hex()})")
            player = await PlayerManager.load_player_from_db(player_id)
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
        await send_packet_to_client(session, response, note="[LOGIN REPLY]")

    # --- Account Create ---
    elif pkt_id == 0x07d1:
        pid, plen, user, pwd = parse_account(data)
        print(f"[ACCOUNT CREATE REQ] User: {user} Pass: {pwd}")
        # Try to load first in case it exists
        player = await PlayerManager.load_player_from_db(user)
        if player:
            response = build_account_creation_result(success=False, val=9)  # ID exists
            print("Account already exists.")
        else:
            await PlayerManager.create_player(user, pwd)
            response = build_account_creation_result(success=True)
            print("Account succesfully created.")
        await send_packet_to_client(session, response, note="[ACCOUNT CREATE]")

    # --- Account Delete ---
    elif pkt_id == 0x07d2:
        pid, plen, user, pwd = parse_account(data)
        print(f"[ACCOUNT DELETE REQ] User: {user} Pass: {pwd}")
        # Always check DB for player
        player = await PlayerManager.load_player_from_db(user)
        if player:
            if player.password == pwd:
                result = await PlayerManager.remove_player(user)
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
        await send_packet_to_client(session, response, note="[ACCOUNT DELETE]")
    
    # --- Channel List ---
    elif pkt_id == 0x07d3:
        # The server is now tracked in session['server'] or session['server_id']
        server_id = session.get('server_id')
        if not server_id:
            print(f"[ERROR] Could not determine server for session {session['addr']}")
            return
        response = await build_channel_list_packet(server_id)
        await send_packet_to_client(session, response, note="[CHANNEL LIST]")

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
            await send_packet_to_client(session, response, note="[CHANNEL JOIN FAIL]")
            return

        player = await PlayerManager.load_player_from_db(player_id)
        if player:
            # ChannelManager.increment_player_count(server_id, channel_index)  # Uncomment if wanted
            print(f"[CHANNEL JOIN] Player {player.player_id} joined channel {channel_index} on server_id {server_id}")
        else:
            print(f"[ERROR] Channel join for unknown player: {player_id}")

        # Save per-session state for later packets
        session['player_id'] = player_id
        session['channel_index'] = channel_index

        response = build_channel_join_ack(success=True)
        await send_packet_to_client(session, response, note="[CHANNEL JOIN]")

    # --- Lobby Create ---
    elif pkt_id == 0x07d5:
        player_id, lobby_name, password = parse_lobby_create_packet(data)
        player = await PlayerManager.load_player_from_db(player_id)
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
        print(f"[LOBBY CREATE] Player '{player_id}' requests lobby '{lobby_name}' (channel_db_id={channel_db_id})")

        response = None

        if channel_db_id is None or player is None:
            print(f"[ERROR] Missing channel or player for lobby create. channel_db_id={channel_db_id}, player={player_id}")
            response = build_lobby_create_ack(success=False, val=5)
        else:
            success = await LobbyManager.create_lobby_db(lobby_name, password, channel_db_id, player_id)
            if not success:
                # Already exists or full
                lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
                if lobby is not None:
                    print(f"[ERROR] Lobby '{lobby_name}' already exists in channel {channel_db_id}")
                    response = build_lobby_create_ack(success=False, val=0x10)  # Already exists
                else:
                    print(f"[ERROR] No more lobby slots available in channel {channel_db_id}")
                    response = build_lobby_create_ack(success=False, val=0x0d)  # Full
            else:
                print(f"[LOBBY CREATE] Lobby '{lobby_name}' successfully created in channel {channel_db_id}")
                response = build_lobby_create_ack(success=True)
                await send_packet_to_client(session, response, note="[LOBBY CREATE OK]")
                room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
                await send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")
                response = None  # Prevent sending response again below

        if response:
            await send_packet_to_client(session, response, note="[LOBBY CREATE ERR]")

    # --- Lobby Join ---
    elif pkt_id == 0x07d6:
        player_id, lobby_name = parse_lobby_join_packet(data)
        player = await PlayerManager.load_player_from_db(player_id)
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)

        success = False
        val = 1  # Default (idx)

        # --- QUICK JOIN HANDLING ---
        if session.pop('quick_join_pending', False):
            print(f"[LOBBY JOIN][QUICK JOIN] Ignoring FIRST 0x07d6 after quick join for {player_id}")
            return

        if channel_db_id is None or player is None:
            print(f"[ERROR] Invalid channel or player missing. server_id={server_id}, channel_index={channel_index}, player={player_id}")
            val = 0x05  # Invalid parameter
            lobby = None
        else:
            lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
            status = await LobbyManager.get_lobby_status(channel_db_id, lobby_name)
            if not lobby:
                print(f"[ERROR] Lobby '{lobby_name}' not found in channel {channel_db_id}")
                val = 0x0f  # Lobby does not exist
            else:
                if status == 1:
                    player_in_lobby = await LobbyManager.is_player_in_lobby_db(lobby_name, channel_db_id, player_id)
                    if player_in_lobby:
                        print(f"[LOBBY JOIN] (repeat) Player {player_id} already in lobby '{lobby_name}' (idx {lobby.idx_in_channel})")
                        success = True
                        val = lobby.idx_in_channel
                    else:
                        add_success = await LobbyManager.add_player_to_lobby_db(lobby_name, channel_db_id, player_id)
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
        await send_packet_to_client(session, response, note="[LOBBY JOIN]")

        if success and channel_db_id is not None and lobby is not None:
            # Store the player_index in the session
            updated_lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
            if updated_lobby and player_id in updated_lobby.player_ids:
                session['player_index'] = updated_lobby.player_ids.index(player_id)
            else:
                print(f"[WARNING] Could not cache player_index for {player_id} in lobby {lobby_name}")
            room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
            await broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
            #send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")

    # --- Quick Join ---
    elif pkt_id == 0x07d7:
        if len(data) < 13:
            print("[QUICK JOIN] Malformed 0x07d7 packet (too short)")
            response = build_lobby_quick_join_ack(success=False, val=1)
            await send_packet_to_client(session, response, note="[QUICK JOIN FAIL]")
            return
        
        session['quick_join_pending'] = True # Session flag for subsequent lobby join
        player_id = data[4:12].decode('ascii').rstrip('\x00')
        print(f"[QUICK JOIN] Request from player_id={player_id}")

        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        if server_id is None or channel_index is None:
            print("[QUICK JOIN] Missing server or channel info in session.")
            response = build_lobby_quick_join_ack(success=False, val=5)
            await send_packet_to_client(session, response, note="[QUICK JOIN FAIL]")
            return

        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
        if channel_db_id is None:
            print("[QUICK JOIN] Invalid channel_db_id.")
            response = build_lobby_quick_join_ack(success=False, val=5)
            await send_packet_to_client(session, response, note="[QUICK JOIN FAIL]")
            return

        # Get all lobbies in the channel
        lobbies = await LobbyManager.get_lobbies_for_channel(channel_db_id)
        # Filter: public, not full, status == 1 (waiting)
        available = [
            lobby for lobby in lobbies
            if not lobby.password  # public
            and lobby.player_count < 4
            and lobby.status == 1  # waiting for players
        ]
        print(f"[QUICK JOIN] {len(available)} public, not full lobbies found.")

        if not available:
            # No lobbies available
            response = build_lobby_quick_join_ack(success=False, val=0x0d)
            await send_packet_to_client(session, response, note="[QUICK JOIN NO LOBBY]")
            return

        # Pick a random lobby
        lobby = random.choice(available)
        lobby_name = lobby.name

        print(f"[QUICK JOIN] Player {player_id} request to join lobby '{lobby_name}' (idx {lobby.idx_in_channel})")
        response = build_lobby_quick_join_ack(success=True, val=lobby.idx_in_channel)
        await send_packet_to_client(session, response, note="[QUICK JOIN SUCCESS]")

    # --- Game Start Request ---
    elif pkt_id == 0x07d8:
        if len(data) >= 8:
            session['countdown_in_progress'] = True  
            player_id = data[4:12].decode('ascii').rstrip('\x00')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
            lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
            print(f"[0x7d8] Game Start request by {player_id} in lobby {lobby_name}")

            if channel_db_id is not None and lobby_name:
                await LobbyManager.set_lobby_status(channel_db_id, lobby_name, 2)  # 2 = started/in progress

                bc0_response = await build_game_start_ack(lobby_name, channel_db_id)
                await broadcast_to_lobby(lobby_name, channel_db_id, bc0_response, note="[GAME START ACK]")
                
        else:
            print(f"[ERROR] Malformed 0x07d8 packet (len={len(data)})")
            # lobby_name/channel_db_id may not be defined here, so guard against that
            lobby_name = session.get('lobby_name', None)
            channel_db_id = session.get('channel_db_id', None)
            bc0_response = await build_game_start_ack(lobby_name, channel_db_id, success=False, val=1)
            await send_packet_to_client(session, bc0_response, note="[GAME START ACK]")

    # --- Game Ready Request ---
    elif pkt_id == 0x07d9:
        if len(data) >= 8:
            session['countdown_in_progress'] = True 
            player_id = data[4:12].decode('ascii').rstrip('\x00')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
            lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
            if channel_db_id is not None and lobby_name:
                new_status = await LobbyManager.toggle_player_ready_in_lobby(channel_db_id, lobby_name, player_id)
                print(f"[0x7d9] Player Ready request by {player_id}, new status: {new_status}")
                bc1_response = build_player_ready_ack(success=True)
                await send_packet_to_client(session, bc1_response, note="[PLAYER READY ACK]")
                room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
                await broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
                # await send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")
            else:
                print(f"[0x7d9] Player Ready failed: missing lobby or channel info.")
                bc1_response = build_player_ready_ack(success=False, val=5)
                await send_packet_to_client(session, bc1_response, note="[PLAYER READY FAIL]")
        else:
            print(f"[ERROR] Malformed 0x07d9 packet (len={len(data)})")
            bc1_response = build_player_ready_ack(success=False, val=1)
            await send_packet_to_client(session, bc1_response, note="[PLAYER READY FAIL]")

    # --- Lobby Leave ---
    elif pkt_id == 0x07da:  # Lobby leave
        if len(data) >= 8:
            player_id = data[4:12].decode('ascii').rstrip('\x00')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
            if channel_db_id is None:
                print(f"[ERROR] No channel DB id for server_id={server_id}, channel_index={channel_index}")
                ack_packet = build_lobby_leave_ack()
            removed_lobby, lobby_deleted = await LobbyManager.remove_player_and_update_leader(player_id, channel_db_id)
            ack_packet = build_lobby_leave_ack()
            await send_packet_to_client(session, ack_packet, note="[LOBBY LEAVE ACK]")
            if not lobby_deleted:
                # Update remaining players
                room_packet = await build_lobby_room_packet(removed_lobby, channel_db_id)
                await broadcast_to_lobby(removed_lobby, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
            else:
                print(f"[LEAVE] Lobby '{removed_lobby}' deleted after last player left.")

        else:
            print(f"[ERROR] Malformed 0x07da packet (len={len(data)})")
            ack_packet = build_lobby_leave_ack(success=False, val=1)
            await send_packet_to_client(session, ack_packet, note="[LOBBY LEAVE FAIL]")

# --- Lobby Kick ---
    elif pkt_id == 0x07db:
        if len(data) >= 8:
            kick_idx = struct.unpack('<I', data[4:8])[0]
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            player_id = session.get('player_id')
            channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
            lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
            print(f"[0x07db] Kick request: remove player at index {kick_idx} (channel_db_id={channel_db_id})")
            kick_packet = build_kick_player_ack()
            # Find the session for the player being kicked
            if lobby_name:
                lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
                if lobby and 0 <= kick_idx < 4:
                    kicked_player_id = lobby.player_ids[kick_idx]
                    if kicked_player_id:
                        # Send kick to the player being kicked and to lobby leader (this session) to ack the 
                        async with sessions_lock:
                            targets = [
                                s for s in sessions.values()
                                if s.get("player_id") == kicked_player_id and s['addr'][1] == CLIENT_GAMEPLAY_PORT
                            ]
                        # Release lock before any awaits

                        for s in targets:
                            await send_packet_to_client(s, kick_packet, note=f"[PLAYER KICKED index={kick_idx}]")
                            await send_packet_to_client(session, kick_packet, note=f"[SUCCESFULLY KICKED index={kick_idx}]")
                            break

                        removed = await LobbyManager.remove_player_from_lobby_db(kicked_player_id, channel_db_id)
                        if removed:
                            print(f"[KICK] Removed player: {kicked_player_id} from {lobby_name} (idx {kick_idx})")
                        else:
                            print(f"[KICK] Could not remove player: {kicked_player_id} from {lobby_name}")
                    else:
                        print(f"[KICK] No player in slot {kick_idx} of {lobby_name}")
                else:
                    print(f"[KICK] Invalid kick index {kick_idx} for lobby {lobby_name}")
                room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
                await broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
                # await send_packet_to_client(session, room_packet, note="[LOBBY ROOM INFO]")
        else:
            print(f"[ERROR] Malformed 0x07db packet (len={len(data)})")
            ack_packet = build_kick_player_ack(success=False, val=1)
            await send_packet_to_client(session, ack_packet, note="[KICK FAIL]")

    # --- Character Info Request ---
    elif pkt_id == 0x07dc:
        if len(data) >= 8:
            requested_id = data[4:12].decode('ascii').rstrip('\x00')
            print(f"[0x7dc] Requested player info for: {requested_id}")
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
            if channel_db_id is not None:
                lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, requested_id)
                character, status = 0, 0
                if lobby_name:
                    lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
                    if lobby and requested_id in lobby.player_ids:
                        slot_idx = lobby.player_ids.index(requested_id)
                        character = lobby.player_characters[slot_idx] or 0
                        status = lobby.player_statuses[slot_idx] or 0
                player = await PlayerManager.load_player_from_db(requested_id)
                if player:
                    player.character = character
                    player.status = status
                    bc4_response = build_character_select_setup_packet(player)
                    await send_packet_to_client(session, bc4_response, note="[CHAR INFO]")
        else:
            print(f"[ERROR] Malformed 0x07dc packet (len={len(data)})")

    # --- Character Select Request ---
    elif pkt_id == 0x07dd:
        if len(data) >= 8:
            char_val = data[4]
            requested_id = session.get('player_id')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
            if requested_id and channel_db_id is not None:
                # Update the player's character in the DB
                await LobbyManager.set_player_character(channel_db_id, requested_id, char_val)
                ack_packet = build_character_select_ack()
                await send_packet_to_client(session, ack_packet, note="[CHAR SELECT ACK]")
                lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, requested_id)
                room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
                await broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
        else:
            print(f"[ERROR] Malformed 0x07dd packet (len={len(data)})")

    # --- Map Select Request ---
    elif pkt_id == 0x07de:  # Map select
        if len(data) >= 8:
            desired_map = struct.unpack('<I', data[4:12])[0]
            player_id = session.get('player_id')
            server_id = session.get('server_id')
            channel_index = session.get('channel_index')
            channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
            if player_id and channel_db_id is not None:
                lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
                if lobby_name:
                    await LobbyManager.set_lobby_map(channel_db_id, lobby_name, desired_map)
                    ack_packet = build_map_select_ack()
                    await send_packet_to_client(session, ack_packet, note="[MAP SELECT ACK]")
                    room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
                    await broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="LOBBY ROOM UPDATE")
        else:
            print(f"[ERROR] Malformed 0x07de packet (len={len(data)})")

    # --- Server List ---
    elif pkt_id == 0x07df: 
        response = await build_server_list_packet()
        await send_packet_to_client(session, response, note="[SERVER LIST]")

    # --- Lobby List ---
    elif pkt_id == 0x07e0:
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')  # Set on Channel Join
        print(f"server_id is: '{server_id}', channel_index is: '{channel_index}'")
        if server_id is not None and channel_index is not None:
            response = await build_lobby_list_packet(server_id, channel_index)
            await send_packet_to_client(session, response, note="[LOBBY LIST]")
        else:
            print("[ERROR] Missing server_id or channel_index in session.")

    # --- Game Ready Check ---
    elif pkt_id == 0x03f0:
        player_id = session.get('player_id')
        player_index = session.get('player_index')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
        if not lobby:
            print("[READY] Could not find lobby for player.")
            return

        key = (channel_db_id, lobby_name)
        # You may want to use an asyncio.Lock() here for echo state if needed

        async def after_echo(success):
            # Mark this player’s echo result
            d = lobby_echo_results.setdefault(key, {})
            d[player_id] = success
            print(f"[READY] Echo reply for '{player_id}' is {'READY' if success else 'DC'}")

            # Check and mark DCs for all other slots (not self)
            async with sessions_lock:
                sessions_snapshot = list(sessions.values())
            # Now operate on snapshot outside lock
            for idx, pid in enumerate(lobby.player_ids):
                if not pid or pid == player_id:
                    continue
                active = any(
                    s.get("player_id") == pid and s['addr'][1] == CLIENT_GAMEPLAY_PORT
                    for s in sessions_snapshot
                )
                d = lobby_echo_results.setdefault(key, {})
                if not active and pid not in d:
                    d[pid] = False  # Mark as DC
                    dc_packet = build_dc_packet(idx)
                    await broadcast_to_lobby(lobby_name, channel_db_id, dc_packet, note=f"[PLAYER DC {idx}]")
                    print(f"[READY] {pid} has no active session, marked as DC, slot {idx}")

            # Check if ALL 4 slots are resolved for non-empty player_ids
            non_empty_ids = [pid for pid in lobby.player_ids if pid]
            resolved = [pid for pid in non_empty_ids if pid in lobby_echo_results[key]]
            num_dc = sum(1 for pid in non_empty_ids if lobby_echo_results[key].get(pid) is False)
            print(f"[READY] Resolved: {resolved} / {non_empty_ids}")
            if len(resolved) == len(non_empty_ids):
                print(f"[COUNTDOWN] All players resolved ({len(non_empty_ids)} slots, {num_dc} DC). Starting countdown.")

                # === SEND DC PACKET TO EACH PLAYER WITH THEIR OWN INDEX, AS AN EXPERIMENT ===
                # Do this *before* countdown.
                tasks = []
                for idx, pid in enumerate(lobby.player_ids):
                    if not pid:
                        continue
                    for s in sessions_snapshot:
                        if s.get("player_id") == pid and s['addr'][1] == CLIENT_GAMEPLAY_PORT:
                            dc_packet = build_dc_packet(idx)
                            tasks.append(send_packet_to_client(s, dc_packet, note=f"[EXPERIMENTAL DC SELF {idx}]"))
                            break
                await asyncio.gather(*tasks)

                # === LAUNCH COUNTDOWN ===
                async def countdown_coroutine():
                    await asyncio.sleep(1)
                    for x in range(4, 0, -1):
                        packet = build_countdown(x)
                        await broadcast_to_lobby(lobby_name, channel_db_id, packet, note=f"[COUNTDOWN {x}]")
                        await asyncio.sleep(1)
                    final_packet = build_countdown(0)
                    await broadcast_to_lobby(lobby_name, channel_db_id, final_packet, note="[COUNTDOWN GO]")
                    lobby_echo_results[key] = {}
                    async with sessions_lock:
                        session_list = list(sessions.values())
                    for s in session_list:
                        s['countdown_in_progress'] = False

                asyncio.create_task(countdown_coroutine())

        # Launch echo only for THIS player, callback does the rest
        asyncio.create_task(
            run_echo_challenge(
                session,
                'readycheck',
                payload=player_index,
                timeout=10,
                on_result=after_echo
            )
        )

    # --- Disconnect  ---
    elif pkt_id == 0x03f1: 
        player_id = session.get('player_id')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = None
        if channel_db_id is not None and player_id:
            lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        
        # Broadcast to players in the lobby
        if lobby_name and channel_db_id is not None:
            await broadcast_to_lobby(lobby_name, channel_db_id, data, note=f"[DISCONNECT BROADCAST {pkt_id}]")
            # Remove player, update leader, and delete lobby if empty
            removed_lobby, lobby_deleted = await LobbyManager.remove_player_and_update_leader(player_id, channel_db_id)
            if not lobby_deleted:
                # Broadcast updated room info to remaining players
                room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
                await broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="[DISCONNECT ROOM UPDATE]")
            else:
                print(f"[DISCONNECT] Lobby '{lobby_name}' deleted after last player left/disconnected.")

        else:
            print(f"[{pkt_id}] WARNING: Could not find lobby/channel for broadcast for {player_id}")

    # --- Game Over ---
        """
        Update the player's status and broadcast lobby room info
        """            
    elif pkt_id == 0x03f2:
        player_id = data[4:12].decode('ascii').rstrip('\x00')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        if not lobby_name:
            print(f"[0x3f2] Could not find lobby for {player_id}")
            return
        # -- set lobby status to 1 (In Queue)
        await LobbyManager.set_lobby_status(channel_db_id, lobby_name, 1)
        # -- set Player status to 1 (Not Ready)
        await LobbyManager.set_player_not_ready(player_id, channel_db_id, lobby_name)
        room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
        await broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="[LOBBY ROOM INFO]")
    
    # --- Game Result / Update Rank ---
    elif pkt_id == 0x03f3:
        """
        If player wins, increment RANK score by 5 points
        If player loses, increment RANK score by 2 points
        """    
        player_id = data[4:12].decode('ascii').rstrip('\x00')
        victory_flag = data[20:24]
        is_victory = struct.unpack('<I', victory_flag)[0] == 1
        points = 5 if is_victory else 2
        print(f"[GAME END] Player {player_id} {'VICTORY' if is_victory else 'DEFEAT'}, +{points} pts")
        await PlayerManager.add_rank_points(player_id, points)

    # --- Echo Reply ---
    elif pkt_id == 0x03ea:
        # The payload is always the last 4 bytes after the 4-byte header
        if len(data) >= 8:
            payload = data[-4:]
            print(f"[ECHO REPLY 0x03ea] Payload: {payload.hex()}")
            # No lock needed for single-threaded asyncio
            echo = session.get('echo', {})
            # Prioritize readycheck reply if in progress
            if echo.get('readycheck', {}).get('in_progress'):
                echo['readycheck']['reply'] = True
            elif echo.get('keepalive', {}).get('in_progress'):
                echo['keepalive']['reply'] = True
            session['echo'] = echo  # If you’re storing a copy, but not needed if it's a ref
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
            channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
            lobby_name = None
            if channel_db_id is not None and player_id:
                lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)

            print(f"[1388] Movement from {player_id}: x={parsed['x_pos']:.3f} y={parsed['y_pos']:.3f} "
                  f"player_heading={parsed['player_heading']:.3f} cam={parsed['cam_heading']:.3f} "
                  f"LR={parsed['left_right']:02x} UD={parsed['up_down']:02x} "
                  f"unk1={parsed['unknown1'].hex()} player_idx={parsed['player_idx'].hex()}")

            # Broadcast to other players in the same lobby
            if lobby_name and channel_db_id is not None:
                await broadcast_to_lobby(lobby_name, channel_db_id, data, note=f"[MOVE BROADCAST 0x1388]")
            else:
                print(f"[1388] WARNING: Could not find lobby/channel for movement broadcast for {player_id}")

        except Exception as e:
            print(f"[ERROR][1388] Failed to parse or broadcast movement packet: {e}")

    # --- All other Gameplay ---
    elif pkt_id >> 8 == 0x13: # check high byte - if packet_id is 0x13XX
        player_id = session.get('player_id')
        server_id = session.get('server_id')
        channel_index = session.get('channel_index')
        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)
        lobby_name = None
        if channel_db_id is not None and player_id:
            lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)
        
        # Broadcast to all players in the lobby
        if lobby_name and channel_db_id is not None:
            if pkt_id == 0x139c: # Don't self-broadcast Incident Proximity Detection
                await broadcast_to_lobby(lobby_name, channel_db_id, data, note=f"[DETECTION EVENT {pkt_id:04x}]", cur_session=session, to_self = False)                
            else:
                await broadcast_to_lobby(lobby_name, channel_db_id, data, note=f"[GAMEPLAY BROADCAST {pkt_id:04x}]")
        else:
            print(f"[{pkt_id:04x}] WARNING: Could not find lobby/channel for broadcast for {player_id}")

    # --- Unhandled Packet ---
    else:
        print(f"[WARN] Unhandled packet ID: 0x{pkt_id:04x} from {session['addr']}")

### END OF PACKET HANDLERS ###

async def handle_client(reader, writer, server_port):
    addr = writer.get_extra_info('peername')
    host = writer.get_extra_info('sockname')[0]

    # Look up server by host (or whatever key you use)
    server = await ServerManager.get_server_by_ip(host)
    session = {
        'reader': reader,
        'writer': writer,
        'addr': addr,
        'server': server if server_port == SERVER_PORT else None,
        'server_id': server.id if server else None,
        'player_id': None,
        'channel_index': None,
        'player_index': None,
        'echo': {
            'keepalive': {'token': None, 'reply': False, 'in_progress': False},
            'readycheck': {'token': None, 'reply': False, 'in_progress': False}
        },
        'countdown_in_progress': False,
    }
    # Add to global sessions
    async with sessions_lock:
        sessions[addr] = session
        print(f"[CONNECT] New connection from {addr}")

    try:
        while True:
            header = await reader.readexactly(4)
            pkt_id, payload_len = struct.unpack('<HH', header)
            payload = await reader.readexactly(payload_len)
            data = header + payload
            print(f"[RECV] From {addr}: {data.hex()} (pkt_id={pkt_id:04x}, {payload_len} bytes)")
            await handle_client_packet(session, data)
    except asyncio.IncompleteReadError:
        print(f"[DISCONNECT] {addr} disconnected.")
    except Exception as e:
        print(f"[CLIENT ERROR] {addr}: {e}")
    finally:
        await full_disconnect(session)

async def start_server(host, listen_port):
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, listen_port),
        host, listen_port
    )
    print(f"[SERVER] LISTENING on {host}:{listen_port}")
    return server

async def full_disconnect(session):
    if session.get('removed'):
        return

    addr = session.get('addr')
    player_id = session.get('player_id')
    server_id = session.get('server_id')
    channel_index = session.get('channel_index')
    player_index = session.get('player_index')

    channel_db_id = None
    if server_id is not None and channel_index is not None:
        channel_db_id = await ChannelManager.get_channel_db_id(server_id, channel_index)

    lobby_name = None
    if channel_db_id is not None and player_id:
        lobby_name = await LobbyManager.get_lobby_name_for_player(channel_db_id, player_id)

    lobby = None
    if lobby_name and channel_db_id is not None:
        lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)

    # Mark as removed and remove from sessions
    session['removed'] = True
    async with sessions_lock:
        sessions.pop(addr, None)

    # Close writer if not already closed
    writer = session.get('writer')
    if writer and not writer.is_closing():
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"[DISCONNECT] Writer close error for {addr}: {e}")
    else:
        print(f"[DISCONNECT] No writer found or already closed for {addr}")

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

        removed_lobby, lobby_deleted = await LobbyManager.remove_player_and_update_leader(player_id, channel_db_id)
        if not lobby_deleted:
            lobby = await LobbyManager.get_lobby_by_name(lobby_name, channel_db_id)
            if lobby:
                status = await LobbyManager.get_lobby_status(channel_db_id, lobby_name)
                if status == 1:
                    room_packet = await build_lobby_room_packet(lobby_name, channel_db_id)
                    await broadcast_to_lobby(lobby_name, channel_db_id, room_packet, note="[DISCONNECT ROOM UPDATE]")
                elif status == 2:
                    dc_packet = build_dc_packet(player_index)
                    await broadcast_to_lobby(lobby_name, channel_db_id, dc_packet, note=f"[DISCONNECT DC {player_index}]")
                else:
                    print(f"Unknown Lobby Status: {status}")
        else:
            print(f"[DISCONNECT] Lobby '{lobby_name}' deleted after last player left.")

async def admin_command_loop():
    print("Admin console ready. Type 'help' for commands.")
    while True:
        try:
            cmd = (await aioconsole.ainput("ADMIN> ")).strip()
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
                # Await the async broadcast function
                await broadcast_manual_packet(payload, note="ADMIN TERMINAL")
                print(f"[ADMIN] Sent {len(payload)} bytes to all clients.")
            else:
                print("Unknown command. Type 'help' for help.")
        except EOFError:
            break
        except KeyboardInterrupt:
            break


async def echo_watcher():
    while True:
        now = time.time()
        # snapshot all current sessions
        async with sessions_lock:
            active_sessions = list(sessions.values())
        for session in active_sessions:
            player_id = session.get('player_id')
            if not player_id:
                continue
            # Only send echo to gameplay clients
            if session['addr'][1] != CLIENT_GAMEPLAY_PORT:
                continue
            if session.get('countdown_in_progress', False):
                continue

            # Use a simple global last_packet_times dict, you may want an asyncio.Lock for atomic access
            last_time = last_packet_times.get(player_id, 0)
            if now - last_time <= ECHO_TIMEOUT:
                continue
            if session['echo']['keepalive']['in_progress']:
                continue

            # Use an async function to check if session is alive if possible, or just leave it sync
            if not is_session_socket_alive(session):
                print(f"[ECHO CHECK] Socket dead for {player_id}, immediate kick.")
                await full_disconnect(session)
                continue

            session['echo']['keepalive']['in_progress'] = True
            session['echo']['keepalive']['token'] = uuid.uuid4().hex
            session['echo']['keepalive']['reply'] = False
            echo_token = session['echo']['keepalive']['token']

            print(f"[ECHO CHECK] {player_id} idle for {int(now - last_time)}s, sending echo challenge...")

            # Launch an echo challenge (one per session)
            asyncio.create_task(
                echo_per_session(session, player_id, echo_token)
            )
        await asyncio.sleep(WATCHER_SLEEP_TIME)

async def echo_per_session(session, player_id, echo_token):
    try:
        for i in range(ECHO_RESPONSE_WAIT):
            if not is_session_socket_alive(session):
                print(f"[ECHO THREAD] Socket dead for {player_id}, kicking immediately from echo thread.")
                await on_echo_result(False, session, player_id, echo_token)
                return
            if session['echo']['keepalive']['token'] != echo_token:
                print(f"[ECHO THREAD] Token changed for {player_id}, another echo thread is running or session replaced. Abort.")
                return
            try:
                await send_echo_challenge(session)
            except Exception as e:
                print(f"[ECHO ERROR] Failed to send echo to {player_id}: {e}")
                await on_echo_result(False, session, player_id, echo_token)
                return
            await asyncio.sleep(1)
            if session['echo']['keepalive']['reply']:
                print(f"[ECHO REPLY] {player_id} replied on attempt {i+1}.")
                await on_echo_result(True, session, player_id, echo_token)
                return
        await on_echo_result(False, session, player_id, echo_token)
    finally:
        session['echo']['keepalive']['in_progress'] = False

async def broadcast_manual_packet(payload: bytes, note="MANUAL BROADCAST"):
    """
    Broadcast a manual packet to all currently connected sessions (asyncio version).
    `payload` should be a complete packet (header + payload), e.g. from struct.pack or a hex string.
    """
    # If you keep sessions in a global dict:
    async with sessions_lock:
        sessions_list = list(sessions.values())  # snapshot for iteration
    for session in sessions_list:
        try:
            await send_packet_to_client(session, payload, note=note)
        except Exception as e:
            print(f"[MANUAL BROADCAST ERROR] {session.get('addr')}: {e}")


async def on_echo_result(success, session, player_id, token):
    # Only handle if the token matches (no overlap from replaced/old sessions)
    if session['echo']['keepalive']['token'] != token:
        print(f"[ECHO ABORT] Echo token mismatch for {player_id}, aborting kick.")
        return
    if success:
        print(f"[ECHO SUCCESS] {player_id} replied successfully, no action needed.")
        return
    print(f"[ECHO FAIL] {player_id} did not reply, disconnecting.")
    await full_disconnect(session)

async def update_last_packet_time(session):
    player_id = session.get('player_id')
    if player_id:
        async with last_packet_lock:
            last_packet_times[player_id] = time.time()

def is_session_socket_alive(session):
    writer = session.get('writer')
    if not writer:
        return False
    transport = writer.transport
    return not transport.is_closing()

async def main():
    # Init DB
    if dbtype == "postgres":
        dsn = get_postgres_dsn()
        await DBManager.init(dsn=dsn, dbtype="postgres")
    else:
        sqlite_file = os.environ.get("SQLITE_FILE", "mysticnights.db")
        schema_file = os.environ.get("SQLITE_SCHEMA", "mn_sqlite_schema.sql")
        await DBManager.init(dbtype="sqlite", sqlite_file=sqlite_file, schema_file=schema_file)
    # Clear orphaned lobbies (async now!)
    await ServerManager.init_server()
    # Start both servers
    manager_server = await start_server(HOST, TCP_PORT)
    gameplay_server = await start_server(HOST, SERVER_PORT)    
    # Manager/Admin
    asyncio.create_task(manager_server.serve_forever())
    # Gameplay/Server
    asyncio.create_task(gameplay_server.serve_forever())
    # Echo Watcher
    asyncio.create_task(echo_watcher())
    # Optionally start admin command loop
    asyncio.create_task(admin_command_loop())
    # Wait forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())