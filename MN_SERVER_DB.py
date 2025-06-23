import threading
import time
import subprocess
import struct
import psycopg2
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
print("Mystic Nights Dummy Server v0.8.0")
print("---------------------------------")

class Player:
    def __init__(self, player_id, password, rank=0x01):
        self.player_id = player_id
        self.password = password
        self.rank = rank
        self.channel = None
        self.lobby = None
        self.character = 0
        self.status = 0

class Lobby:
    def __init__(self, name, room_id, password="", channel_id=0):
        self.name = name
        self.room_id = room_id
        self.password = password
        self.channel_id = channel_id  # <--- NEW
        self.max_players = 4
        self.current_players = 0
        self.players = []
        self.map = 1
        self.leader = None
        self.status = 1  # 1 = waiting, set to 2 when match in progress

    def add_player(self, player: 'Player', status=0):
        if player in self.players:
            print(f"[WARN] Player {player.player_id} already in lobby {self.name}")
            return
        if self.current_players >= self.max_players:
            print(f"[WARN] Lobby {self.name} is full")
            return
        # Assign next available character index
        taken = set(p.character for p in self.players if p.character)
        for i in range(1, 9):
            if i not in taken:
                player.character = i
                break
        else:
            player.character = 1  # fallback, shouldn't happen in 4p lobby
        player.lobby = self.name
        player.status = status
        self.players.append(player)
        self.current_players += 1
        if not self.leader:
            self.leader = player.player_id

    def remove_player(self, player_id):
        for p in self.players:
            if p.player_id == player_id:
                self.players.remove(p)
                self.current_players -= 1
                # Free up character index
                p.character = 0
                p.lobby = None
                if self.leader == p.player_id and self.players:
                    self.leader = self.players[0].player_id
                elif not self.players:
                    self.leader = None
                return

    def get_player(self, player_id):
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def kick_player_by_index(self, idx):
        if 0 <= idx < len(self.players):
            kicked = self.players.pop(idx)
            kicked.lobby = None
            kicked.character = 0  # Free up character index
            self.current_players -= 1
            if self.leader == kicked.player_id and self.players:
                self.leader = self.players[0].player_id
            elif not self.players:
                self.leader = None

class Channel:
    def __init__(self, id, server_id, channel_index, player_count=0):
        self.id = id  # Primary key from DB (1-120)
        self.server_id = server_id
        self.channel_index = channel_index
        self.player_count = player_count
        self.players = []  # In-memory only

    def add_player(self, player: Player):
        if player not in self.players:
            self.players.append(player)
            player.channel = self.channel_id

    def remove_player(self, player: Player):
        if player in self.players:
            self.players.remove(player)
            player.channel = None

class PlayerManager:
    players = {}

    @classmethod
    def get_player(cls, player_id):
        return cls.players.get(player_id)
    
    @classmethod
    def load_players(cls):
        cls.players = {}
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT player_id, password, rank FROM players;")
            for player_id, password, rank in cur.fetchall():
                cls.players[player_id] = Player(player_id, password, rank)
        print(f"Loaded {len(cls.players)} players.")

    @classmethod
    def load_player_from_db(cls, player_id):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT player_id, password, rank FROM players WHERE player_id = %s", (player_id,))
            row = cur.fetchone()
            if row:
                p = Player(row[0], row[1], row[2])
                cls.players[row[0]] = p
                return p
        return None

    @classmethod
    def create_player(cls, player_id, password, rank=0x01):
        # Try to insert into DB
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
            return None  # Already exists
        p = Player(player_id, password, rank)
        cls.players[player_id] = p
        return p

    @classmethod
    def remove_player(cls, player_id):
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM players WHERE player_id = %s", (player_id,))
            conn.commit()
        if player_id in cls.players:
            del cls.players[player_id]

class LobbyManager:
    lobbies = {}
    next_room_id = 0

    @classmethod
    def load_lobbies(cls):
        cls.lobbies = {}
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM lobbies;")
            for row in cur.fetchall():
                lobby = Lobby(
                    name=row[3],
                    room_id=row[0],
                    password=row[4],
                    channel_id=row[1]
                )
                lobby.status = row[6]
                lobby.map = row[7]
                lobby.leader = row[8]
                # Load up to 4 players
                for i in range(1, 5):
                    base_idx = 8 + (i - 1) * 3 + 1
                    pid = row[base_idx]
                    char = row[base_idx + 1]
                    stat = row[base_idx + 2]
                    if pid:
                        player = PlayerManager.get_player(pid)
                        if player:
                            player.character = char or 0
                            player.status = stat or 0
                            lobby.add_player(player, status=player.status)
                cls.lobbies[lobby.name] = lobby
        print(f"Loaded {len(cls.lobbies)} lobbies.")

    @classmethod
    def create_lobby(cls, name, password, channel_id=0):
        if name in cls.lobbies:
            return cls.lobbies[name]
        lobby = Lobby(name, cls.next_room_id, password, channel_id=channel_id)
        cls.lobbies[name] = lobby
        cls.next_room_id += 1
        return lobby

    @classmethod
    def get_lobby(cls, name):
        return cls.lobbies.get(name)

    @classmethod
    def get_lobby_by_player(cls, player_id):
        for l in cls.lobbies.values():
            for p in l.players:
                if p.player_id == player_id:
                    return l
        return None

    @classmethod
    def get_lobbies_for_channel(cls, channel_db_id):
        """
        Returns lobbies for the given DB channel id (not index!)
        """
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT idx_in_channel, player_count, name, password, status
                FROM lobbies
                WHERE channel_id = %s
                ORDER BY idx_in_channel ASC
            """, (channel_db_id,))
            return cur.fetchall()

    
    @classmethod
    def add_player_to_lobby_db(cls, server_id, channel_index, idx_in_channel, player_id):
        channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
        if not channel_db_id:
            print(f"[ERROR] No channel DB id for server_id={server_id}, channel_index={channel_index}")
            return False
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, player1_id, player2_id, player3_id, player4_id
                FROM lobbies
                WHERE channel_id = %s AND idx_in_channel = %s
            """, (channel_db_id, idx_in_channel))
            row = cur.fetchone()
            if not row:
                print(f"[ERROR] Lobby idx {idx_in_channel} in channel {channel_db_id} not found in DB.")
                return False
            lobby_id, p1, p2, p3, p4 = row
            slots = [p1, p2, p3, p4]
            for idx, slot in enumerate(slots, 1):
                if slot is None:
                    cur.execute(f"""
                        UPDATE lobbies SET player{idx}_id = %s WHERE id = %s
                    """, (player_id, lobby_id))
                    conn.commit()
                    print(f"[DB] Added player {player_id} to lobby {idx_in_channel} in channel {channel_db_id} (slot {idx}).")
                    return True
            print(f"[WARN] No empty player slot in lobby idx {idx_in_channel}, channel {channel_db_id}")
            return False
    
    @classmethod
    def print_lobby_table(cls, channel_id=None):
        """
        Prints a formatted table of all lobbies for the given channel_id (or all channels if None),
        using live DB data.
        """
        conn = get_db_conn()
        with conn.cursor() as cur:
            if channel_id is not None:
                cur.execute("""
                    SELECT idx_in_channel, name, player_count, password, status
                    FROM lobbies
                    WHERE channel_id = %s
                    ORDER BY idx_in_channel ASC
                """, (channel_id,))
            else:
                cur.execute("""
                    SELECT channel_id, idx_in_channel, name, player_count, password, status
                    FROM lobbies
                    ORDER BY channel_id ASC, idx_in_channel ASC
                """)
            rows = cur.fetchall()

        # Print table header
        print("ChID  Idx  Name            Players  Type     Status")
        print("=" * 60)
        status_map = {0: '〈비어있음〉', 1: '대기중', 2: '시작됨'}
        for row in rows:
            if channel_id is not None:
                idx, name, pc, pw, st = row
                ch = channel_id
            else:
                ch, idx, name, pc, pw, st = row
            is_private = bool(pw)
            type_txt = "Private" if is_private else "Public"
            print(f"{ch:<5} {idx:<4} {name[:12]:12} {pc:<7} {type_txt:7} {status_map.get(st, st):6}")
        print("=" * 60)

    @classmethod
    def remove_player_from_all_lobbies(cls, player_id):
        for l in cls.lobbies.values():
            l.remove_player(player_id)

class ChannelManager:
    # channels[(server_id, channel_index)] = Channel instance
    channels = {}

    @classmethod
    def load_channels(cls):
        cls.channels = {}
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, server_id, channel_index, player_count FROM channels;")
            for id, server_id, channel_index, player_count in cur.fetchall():
                ch = Channel(id, server_id, channel_index, player_count)
                cls.channels[(server_id, channel_index)] = ch
        print(f"Loaded {len(cls.channels)} channels.")

    @classmethod
    def get_channel(cls, server_id, channel_index):
        key = (server_id, channel_index)
        if key not in cls.channels:
            # Optionally, create it in-memory (not in DB)
            ch = Channel(None, server_id, channel_index, 0)
            cls.channels[key] = ch
        return cls.channels[key]
    
    @classmethod
    def get_channel_db_id(cls, server_id, channel_index):
        #Returns the primary key (id) in channels table for a given server_id and channel_index.
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
        return [ch for (sid, _), ch in cls.channels.items() if sid == server_id]

    @classmethod
    def print_channel_table(cls, server_id=None):
        print("-" * 50)
        print("{:<8} {:<8} {:<8} {:<12}".format("SrvID", "ChIdx", "ID", "Players"))
        print("-" * 50)
        channels = cls.channels.values() if server_id is None else cls.get_channels_for_server(server_id)
        for ch in sorted(channels, key=lambda c: (c.server_id, c.channel_index)):
            print("{:<8} {:<8} {:<8} {:<12}".format(ch.server_id, ch.channel_index, ch.id, ch.player_count))
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
class Server:
    def __init__(self, sid, name, ip_str, avail):
        self.sid = sid
        self.name = name
        self.ip_str = ip_str
        self.avail = avail

class ServerManager:
    servers = {}

    @classmethod
    def load_servers(cls):
        cls.servers = {}
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, ip_address, availability FROM servers;")
            for sid, name, ip_str, avail in cur.fetchall():
                cls.servers[name] = Server(sid, name, ip_str, avail)
        print(f"Loaded {len(cls.servers)} servers.")

    @classmethod
    def get_server_by_ip(cls, ip_address):
        # Allow lookup by IP (returns Server or None)
        for s in cls.servers.values():
            if s.ip_str == ip_address:
                return s
        return None

    @classmethod
    def get_server_id_by_ip(cls, ip_address):
        server = cls.get_server_by_ip(ip_address)
        if not server:
            print(f"[WARN] No server found for IP: {ip_address}")
            return None
        return server.sid if server else None

    @classmethod
    def get_servers(cls):
        return list(cls.servers.values())

    @classmethod
    def print_server_table(cls):
        cls.load_servers()  # Always get latest from DB
        print("-" * 60)
        print("{:<4} {:<16} {:<20} {:<10}".format("Idx", "Name", "IP (String)", "Status"))
        print("-" * 60)
        status_map = {-1: "알수없음", 0: "적음", 1: "보통", 2: "많음"}
        for idx, s in enumerate(cls.get_servers()):
            status_str = status_map.get(s.avail, str(s.avail))
            print("{:<4} {:<16} {:<20} {:<10}".format(idx, s.name, s.ip_str, status_str))
        print("-" * 60)

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
    # Same as before, just ensure you always pass server_id.
    packet_id = 0x0bbb
    flag = b'\x01\x00\x00\x00'
    entries = []
    for ch_idx in range(12):
        ch = ChannelManager.get_channel(server_id, ch_idx)
        cid = ch.channel_index
        cur_players = ch.player_count
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

def build_lobby_join_ack(lobby_idx):
    packet_id = 0x0bbe
    flag = b'\x01\x00\x00\x00'
    payload = flag + struct.pack('<H', lobby_idx)
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_lobby_join_ack_2(lobby_idx):
    packet_id = 0x0bbf
    flag = b'\x01\x00\x00\x00'
    payload = flag + struct.pack('<H', lobby_idx)
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
    """
    Builds a multiplayer lobby list packet for a specific server_id/channel_index.
    """
    packet_id = 0xbc8
    flag = b'\x01\x00\x00\x00'
    entry_struct = '<III16s1s12s1sB1s'
    lobbies = []

    channel_db_id = ChannelManager.get_channel_db_id(server_id, channel_index)
    # Query DB for up to 20 lobbies in this channel
    rows = []
    if channel_db_id is not None:
        rows = LobbyManager.get_lobbies_for_channel(channel_db_id)

    for row in rows:
        idx_in_channel, player_count, name, password, status = row
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
    for server in ServerManager.servers.values():
        name = server.name.encode('euc-kr').ljust(16, b'\x00')
        ip = server.ip_str.encode('ascii') + b'\x00'
        ip = ip.ljust(16, b'\x00')
        reserved1 = b'\x00' * 5
        reserved2 = b'\x00' * 3
        servers.append(struct.pack('<16s5s16s3si', name, reserved1, ip, reserved2, server.avail))
    # Pad to 10 entries...
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

def build_lobby_room_packet(lobby: Lobby):
    import struct
    packet_id = 0x03ee
    leader_idx = 0
    if lobby.leader:
        for i, p in enumerate(lobby.players):
            if p.player_id == lobby.leader:
                leader_idx = i
                break
    lobby_leader = struct.pack("B", leader_idx)
    padding = b'\x00\x00\x00'
    name = lobby.name.encode('euc-kr', errors='replace')[:16].ljust(16, b'\x00')
    unknown1 = b'\x00' * 16
    player_structs = []
    for p in (lobby.players + [Player("", "", 0)] * 4)[:4]:
        pid = p.player_id.encode('ascii')[:8].ljust(8, b'\x00')
        block = bytearray(28)
        block[0:8] = pid
        block[8:13] = b'\x00' * 5
        block[0x0D] = p.character
        block[0x0E] = p.status
        block[0x0F] = 0
        block[0x10:0x14] = struct.pack('<I', p.rank)
        block[0x14:0x18] = struct.pack('<I', 0)
        block[0x18:0x1C] = struct.pack('<I', 0)
        player_structs.append(bytes(block))
    map_select = struct.pack('<I', lobby.map)
    lobby_status = struct.pack('<I', lobby.status) #ACTUAL EXPECTED VALUE UNKNOWN, USING LOBBY STATUS FOR NOW
    payload = (
        lobby_leader +
        padding +
        name +
        unknown1 +
        b''.join(player_structs) +
        map_select +
        lobby_status #ACTUAL EXPECTED VALUE UNKNOWN, USING LOBBY STATUS FOR NOW
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
                    PlayerManager.remove_player(user)
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

            '''
            # Handle leaving the previous channel (if any)
            prev_channel = session.get('channel_index')
            if prev_channel:
                old_channel_index = prev_channel
                # Only decrement if leaving THIS server's channel
                # --- Update DB: Decrement player_count for this channel ---
                ChannelManager.decrement_player_count(old_channel_index)
                print(f"[CHANNEL LEAVE] Player {session.get('player_id')} left channel {old_channel_index} on server_id {server_id}")
                session['channel_index'] = None  # Clear channel tracking
            '''
            # Reload channels
            ChannelManager.load_channels()
            # Deduce server_id from destination IP
            server = ServerManager.get_server_by_ip(dest_ip)
            if server is None:
                print(f"[ERROR] Could not determine server for IP {dest_ip}")
                return
            server_id = server.sid
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
                pwd = client_data[17:28].decode('ascii', errors='replace').rstrip('\x00')
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
                # Optionally store server_id and channel_index in the Player object for reference
                player.server_id = server_id
                player.channel = channel_index
                
                '''
                # --- Update DB: Increment player_count for this channel ---
                ChannelManager.increment_player_count(server_id, channel_index)
                '''

                print(f"[CHANNEL JOIN] Player {player.player_id} joined channel {channel_index} on server_id {server_id}")
                session['player_id'] = player_id  # <-- Store player_id per session
                session['channel_index'] = channel_index # <-- Store current channel_index in session

            else:
                print(f"[ERROR] Channel join for unknown player: {player_id}")

            response = build_channel_join_ack(success=True)
            latest_session = session

        elif pkt_id == 0x07d5:  # Lobby create
            player_id, lobby_name, password = parse_lobby_create_packet(client_data)
            player = PlayerManager.load_player_from_db(player_id)
            ch_id = player.channel if player else 0
            lobby = LobbyManager.get_lobby(lobby_name)
            if lobby:
                # Lobby with this name already exists ERROR
                response = build_lobby_create_ack(success=False, val=0x10)
            else:
                lobby = LobbyManager.create_lobby(lobby_name, password, channel_id=ch_id)
                if player and lobby and player not in lobby.players:
                    lobby.add_player(player, status=0)
                    print(f"[LOBBY CREATE] '{lobby_name}' created by '{player_id}', password={password}")
                response = build_lobby_create_ack(success=True)
                send_packet_to_client(session, response, tcp=tcp, client_data=client_data)
                if lobby:
                    room_packet = build_lobby_room_packet(lobby)
                    send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
                response = None
                latest_session = session

        elif pkt_id == 0x07d6:  # Lobby join
            player_id, lobby_name = parse_lobby_join_packet(client_data)
            player = PlayerManager.load_player_from_db(player_id)
            lobby = LobbyManager.get_lobby(lobby_name)
            lobby_list = list(LobbyManager.lobbies.values())
            lobby_idx = lobby_list.index(lobby) if lobby in lobby_list else 0
            if player and lobby and player not in lobby.players:
                lobby.add_player(player, status=0)
                print(f"[LOBBY JOIN] Player {player_id} joined lobby {lobby_name}")

            session["join_cnt"] += 1
            
            response = build_lobby_join_ack(lobby_idx)
            send_packet_to_client(session, response, tcp=tcp, client_data=client_data)
            if lobby:
                room_packet = build_lobby_room_packet(lobby)
                send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
            
            response = None
            latest_session = session

        elif pkt_id == 0x07d8:  # Game start request
            if len(client_data) >= 8:
                player_id = client_data[4:8].decode('ascii').rstrip('\x00')
                print(f"[0x7d8] Game Start request by player: {player_id}")
                bc0_response = build_game_start_ack(player_id)
                send_packet_to_client(session, bc0_response, tcp=tcp, client_data=client_data)
                # Set lobby status to 'in progress'
                lobby = LobbyManager.get_lobby_by_player(player_id)
                if lobby:
                    lobby.status = 2
            else:
                print(f"[ERROR] Malformed 0x07d8 packet (len={len(client_data)})")
            latest_session = session

        elif pkt_id == 0x07d9:  # Game ready request
            if len(client_data) >= 8:
                player_id = client_data[4:8].decode('ascii').rstrip('\x00')
                player = PlayerManager.load_player_from_db(player_id)
                print(f"[0x7d9] Player Ready request by player: {player_id}")
                bc1_response = build_player_ready_ack(success=True)
                send_packet_to_client(session, bc1_response, tcp=tcp, client_data=client_data)
                # Toggle player status
                player.status = (player.status != 1) 
                for l in LobbyManager.lobbies.values():
                    if l.get_player(player_id):
                        room_packet = build_lobby_room_packet(l)
                        send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
            else:
                print(f"[ERROR] Malformed 0x07d9 packet (len={len(client_data)})")
                bc1_response = build_player_ready_ack(success=False, val=5)
                send_packet_to_client(session, bc1_response, tcp=tcp, client_data=client_data)
            latest_session = session

        elif pkt_id == 0x07da:  # Lobby leave
            if len(client_data) >= 8:
                player_id = client_data[4:8].decode('ascii').rstrip('\x00')
                player = PlayerManager.load_player_from_db(player_id)
                print(f"[0x07da] Lobby leave request for player: {player_id}")
                ack_packet = build_lobby_leave_ack()
                send_packet_to_client(session, ack_packet, tcp=tcp, client_data=client_data)
                lobby = LobbyManager.get_lobby_by_player(player_id)
                if lobby:
                    lobby.remove_player(player_id)
                    player.status = 0
                    print(f"[LEAVE] Removed player: {player_id} from {lobby.name}")
            latest_session = session

        elif pkt_id == 0x07db:  # Kick
            if len(client_data) >= 8:
                kick_idx = struct.unpack('<I', client_data[4:8])[0]
                print(f"[0x07db] Kick request: remove player at index {kick_idx}")
                ack_packet = build_kick_player_ack()
                send_packet_to_client(session, ack_packet, tcp=tcp, client_data=client_data)
                # Assume latest lobby
                for l in LobbyManager.lobbies.values():
                    if 0 <= kick_idx < len(l.players):
                        player = l.players[kick_idx]
                        kicked = player.player_id
                        l.kick_player_by_index(kick_idx)
                        player.status = 0
                        print(f"[KICK] Removed player: {kicked} from {l.name}")
                        room_packet = build_lobby_room_packet(l)
                        send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
                        break
            latest_session = session

        elif pkt_id == 0x07dc:  # Character info request
            if len(client_data) >= 8:
                requested_id = client_data[4:8].decode('ascii').rstrip('\x00')
                print(f"[0x7dc] Requested player info for: {requested_id}")
                for l in LobbyManager.lobbies.values():
                    p = l.get_player(requested_id)
                    if p:
                        bc4_response = build_character_select_setup_packet(p)
                        session["last_7dc_player_id"] = requested_id
                        send_packet_to_client(session, bc4_response, tcp=tcp, client_data=client_data)
                        break
            latest_session = session

        elif pkt_id == 0x07dd:  # Character select
            if len(client_data) >= 8:
                char_val = client_data[4]
                requested_id = session.get("last_7dc_player_id")
                if requested_id:
                    for l in LobbyManager.lobbies.values():
                        p = l.get_player(requested_id)
                        if p:
                            print(f"[0x7dd] Updating player {requested_id} character to {char_val}")
                            p.character = char_val
                            break
                ack_packet = build_character_select_ack()
                send_packet_to_client(session, ack_packet, tcp=tcp, client_data=client_data)
                for l in LobbyManager.lobbies.values():
                    if requested_id and l.get_player(requested_id):
                        room_packet = build_lobby_room_packet(l)
                        send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
                        break
            latest_session = session

        elif pkt_id == 0x07de:  # Map select
            if len(client_data) >= 8:
                desired_map = struct.unpack('<I', client_data[4:8])[0]
                print(f"[MAP SELECT] Client requested map index: {desired_map}")
                #player_id = ip_to_player.get(ip.src) #get player_id from IP addr
                player_id = session.get('player_id')
                if player_id:
                    lobby = LobbyManager.get_lobby_by_player(player_id)
                    if lobby:
                        lobby.map = desired_map
                        ack_packet = build_map_select_ack()
                        send_packet_to_client(session, ack_packet, tcp=tcp, client_data=client_data)
                        room_packet = build_lobby_room_packet(lobby)
                        send_packet_to_client(session, room_packet, tcp=tcp, client_data=client_data)
                else:
                    print("[ERROR] Map select received, but no player_id bound to session")
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
    ServerManager.load_servers()
    PlayerManager.load_players()
    ChannelManager.load_channels()
    LobbyManager.load_lobbies()
    print("All data loaded from the database.")
    print(f"Waiting for connection on {HOST}:{TCP_PORT}")
    threading.Thread(target=start_sniffer, daemon=True).start()
    while True:
        time.sleep(1)
