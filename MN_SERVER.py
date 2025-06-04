import threading
import time
import subprocess
import socket
import struct
from scapy.all import *

# Configuration
HOST = '211.233.10.5'
TCP_PORT = 18000
TCP_PORT_CHANNEL = 18001
#Canada
#MY_MAC = "00:ff:e5:67:d5:da"
#Korea - 00:04:1f:82:bf:b2
MY_MAC = "00:ff:22:cc:b2:bf"
IFACE = "OpenVPN TAP-Windows6"

previous_pkt_id = 0
pkt_cnt = 0
tcp_sessions = {}
accounts = [("BABA", "ABCABC")]  # Store tuples of (username, password)
allow_manual_send = False
latest_session = None
lobbies = {
    "TestRoom1": {
        'room_id': 0,
        'name': "TestRoom1",
        'password': "",
        'max_players': 4,
        'current_players': 0,
        'players': []
    },
    "TestRoom2": {
        'room_id': 1,
        'name': "TestRoom2",
        'password': "PW123",
        'max_players': 4,
        'current_players': 0,
        'players': []
    },
    "TestRoom3": {
        'room_id': 2,
        'name': "TestRoom3",
        'password': "CC999",
        'max_players': 4,
        'current_players': 0,
        'players': []
    }
}
lobby_counter = 4  # to assign new room_id (avoid collision with your existing test lobbies)

# Global lobby state
current_lobby_name = "TestRoom1"
current_lobby_players = [
    {"player_id": "BABA", "character": 0x01, "status": 0x00, "rank": 0x01},
    {"player_id": "JEREMY", "character": 0x06, "status": 0x00, "rank": 0x8d},
    {"player_id": "DJANGO", "character": 0x03, "status": 0x00, "rank": 0x34},
    {"player_id": "FANOUI", "character": 0x08, "status": 0x01, "rank": 0x0b}
]
current_lobby_map = 1  # Default map index
current_lobby_flag = 1
current_lobby_leader = 0

print("---------------------------------")
print("Mystic Nights Dummy Server v0.6.7")
print("---------------------------------")

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

def handle_arp(pkt):
    if ARP in pkt and pkt[ARP].op == 1 and pkt[ARP].pdst == HOST:
        print(f"[SCAPY] ARP request from {pkt[ARP].psrc}")
        ether = Ether(dst=pkt[ARP].hwsrc, src=MY_MAC)
        arp = ARP(op=2, psrc=HOST, pdst=pkt[ARP].psrc,
                  hwsrc=MY_MAC, hwdst=pkt[ARP].hwsrc)
        sendp(ether/arp, iface=IFACE, verbose=False)
        print(f"[SCAPY] Sent ARP reply for {HOST}")

def print_server_table(servers):
    print("-" * 60)
    print("{:<4} {:<16} {:<20} {:<10}".format("Idx", "Name", "IP (String)", "Status"))
    print("-" * 60)
    status_map = {
        -1: "알수없음",  # Unknown
         0: "적음",      # Few
         1: "보통",      # Normal
         2: "많음"       # Full
    }
    for idx, s in enumerate(servers):
        status_str = status_map.get(s.get('avail', -1), str(s.get('avail', -1)))
        print("{:<4} {:<16} {:<20} {:<10}".format(idx, s['name'], s['ip_str'], status_str))
    print("-" * 60)

def build_server_list_packet():
    import struct

# Each server entry (44 bytes):
# struct ServerEntry {
#     char name[16];       // EUC-KR string, padded with \x00
#     uint8_t reserved[5]; // unknown usage
#     char ip_ascii[16];   // "211.233.10.5\0" as ASCII
#     uint8_t reserved2[3];// trailing unknown padding
#     int32_t avail;       // server availability status
# };

    packet_id = 0x0bc7
    flag = 1
    unknown = b'\x00\x00\x00'

    # === Editable server list (up to 10) ===
    custom_servers = [
        {"name": "MN0", "ip_str": "211.233.10.5", "avail": 0},
        {"name": "MN1", "ip_str": "211.233.10.6", "avail": 1},
        {"name": "MN2", "ip_str": "211.233.10.7", "avail": 2},
        # Add more here
    ]

    servers = []

    for entry in custom_servers:
        name = entry['name'].encode('euc-kr').ljust(16, b'\x00')
        ip = entry['ip_str'].encode('ascii') + b'\x00'
        ip = ip.ljust(16, b'\x00')
        reserved1 = b'\x00' * 5
        reserved2 = b'\x00' * 3
        servers.append({
            'name': entry['name'],
            'ip_str': entry['ip_str'],
            'packed': struct.pack('<16s5s16s3si', name, reserved1, ip, reserved2, entry['avail'])
        })

    # Pad up to 10 entries
    while len(servers) < 10:
        idx = len(servers)
        name = f"MN{idx}".encode('euc-kr').ljust(16, b'\x00')
        ip = b'0.0.0.0\x00'.ljust(16, b'\x00')
        reserved1 = b'\x00' * 5
        reserved2 = b'\x00' * 3
        servers.append({
            'name': f"MN{idx}",
            'ip_str': "0.0.0.0",
            'packed': struct.pack('<16s5s16s3si', name, reserved1, ip, reserved2, -1)
        })

    print_server_table(servers)

    entries = b''.join(s['packed'] for s in servers)
    payload = struct.pack('<B3s', flag, unknown) + entries
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def parse_account_create(data):
    packet_id, payload_len = struct.unpack('<HH', data[:4])
    username = data[4:16].decode('ascii').rstrip('\x00')
    password = data[16:28].decode('ascii').rstrip('\x00')
    return packet_id, payload_len, username, password

def build_account_creation_result(success=True):
    # ba 0b 01 00 01  (success)
    # b9 0b 01 00 01/00 and ba 0b 01 00 00 also seem to work...
    # ?? ?? ?? ?? ??  (failure/duplicate) - ba 0b 01 00 00 THIS IS NOT THE FAILURE CONDITION
    # Struct: <H H B B B B  (packet_id, payload_len, 01, 00, 01/00)
    packet_id = 0x0bba
    payload = struct.pack('<B B B', 1 if success else 0, 0, 1 if success else 0)
    # Some clients expect the payload length to be 5 (from your successful case)
    header = struct.pack('<HH', packet_id, len(payload))
    reply = header + payload
    print(f"[DEBUG] Account Creation Result ({'success' if success else 'exists'}):", reply.hex())
    return reply

def build_account_creation_duplicate_id_error():
    packet_id = 0x0bb9
    payload = struct.pack('<BBB', 0x00, 0x00, 0x01)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_login_packet():
    packet_id = 0x0bb8
    payload = struct.pack('<BBB', 0x01, 0x00, 0x01)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_channel_list_packet():
    import struct

    # Packet ID for channel list
    packet_id = 0xbbb
    flag = 1
    unknown = b'\x00\x00\x00'  # Header just like server list

    # Define channels (each is a tuple: index, current_players, max_players)
    # Only 1 channel for testing, rest will be zero-filled.
    channels = [
        (0, 0, 80),  # Channel 1: 0/4 players
        (1, 0, 80),
        (2, 0, 80)
        # Add more tuples here if needed
    ]

    # Pad out to 12 channels
    while len(channels) < 12:
        channels.append((len(channels), 0, 80))

    # Build entries (12 bytes each: <III)
    entries = b''
    for idx, cur, maxp in channels:
        entries += struct.pack('<III', idx, cur, maxp)

    # Build payload: flag + unknown + channel entries
    payload = struct.pack('<B3s', flag, unknown) + entries

    # Build header (packet_id, payload length)
    header = struct.pack('<HH', packet_id, len(payload))

    # Return full packet
    return header + payload

def parse_channel_join_packet(data):
    # Expects a bytes object of at least 22 bytes (as in your example)
    packet_id, payload_len = struct.unpack('<HH', data[:4])
    username = data[4:12].decode('ascii').rstrip('\x00')
    channel = struct.unpack('<H', data[20:22])[0]
    channel_num = channel  # You can subtract 1 if zero-based elsewhere
    return {
        "packet_id": packet_id,
        "payload_len": payload_len,
        "username": username,
        "channel": channel_num
    }

def build_channel_join_ack(data):
    info = parse_channel_join_packet(data)
    print(info)
    """
    Builds a 0xbbc channel join ack packet.
    - val: 2-byte value, e.g., 1 or 2.
    Returns a bytes object ready to send.
    """
    val = 1
    packet_id = 0x0bbc
    flag = b'\x01\x00\x00\x00'  # 4 bytes
    payload = flag + struct.pack('<H', val)  # 4 + 2 = 6 bytes
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_lobby_list_packet():
    """
    Builds a multiplayer lobby list packet for transmission.
    Entry layout (44 bytes):
        0x00: uint32 room_id
        0x04: uint32 cur_players
        0x08: uint32 max_players
        0x0C: char[16] name (EUC-KR, padded with \x00) [Client only accepts 12 char entries]
        0x1C: uint8 pad1 (b'\x00')
        0x1D: char[12] password (EUC-KR, padded with \x00) [Client only accepts 8 char entries]l
                # NOTE: If password is empty, lobby is PUBLIC
                #       If password is non-empty, lobby is PRIVATE
        0x29: uint8 pad2 (b'\x00')
        0x2A: uint8 status (0=〈비어있음〉, 1=대기중, 2=시작됨)
        0x2B: uint8 pad3 (b'\x00')
    Note: name and password must only contain upper case letters and numbers
    """
    import struct

    packet_id = 0xbc8
    flag = 1
    unknown = b'\x00\x00\x00'

    entry_struct = '<III16s1s12s1sB1s'  # 44 bytes

    lobby_list = list(lobbies.values())
    lobbies_for_packet = []
    for entry in lobby_list:
        name = entry['name'].encode('euc-kr', errors='replace')[:16].ljust(16, b'\x00')
        pad1 = b'\x00'
        password = entry.get('password', '').encode('euc-kr', errors='replace')[:12].ljust(12, b'\x00')
        pad2 = b'\x00'
        status = int(entry.get('status', 1))
        pad3 = b'\x00'

        packed = struct.pack(
            entry_struct,
            entry['room_id'],
            entry['current_players'],
            entry['max_players'],
            name,
            pad1,
            password,
            pad2,
            status,
            pad3
        )
        lobbies_for_packet.append({'name': entry['name'], 'status': status, 'packed': packed})

    # Pad out to 20 entries (empty lobbies)
    while len(lobbies_for_packet) < 20:
        idx = len(lobbies_for_packet) + 1
        name = f"Lobby{idx}".encode('euc-kr')[:16].ljust(16, b'\x00')
        pad1 = b'\x00'
        password = b"".ljust(12, b'\x00')   # PUBLIC (no password)
        pad2 = b'\x00'
        status = 0
        pad3 = b'\x00'
        packed = struct.pack(
            entry_struct,
            idx,
            0,
            4,
            name,
            pad1,
            password,
            pad2,
            status,
            pad3
        )
        lobbies_for_packet.append({'name': f"Lobby{idx}", 'status': status, 'packed': packed})

    print_lobby_table(lobbies_for_packet)

    entries = b''.join(l['packed'] for l in lobbies_for_packet)
    payload = struct.pack('<B3s', flag, unknown) + entries
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def print_lobby_table(lobby_list=None):
    """
    Prints a summary table of lobbies.
    Status: 0=〈비어있음〉 (Empty), 1=대기중 (Waiting), 2=시작됨 (Started)
    """
    status_map = {0: '〈비어있음〉', 1: '대기중', 2: '시작됨'}
    print("Idx  Name           Status   Type    Players")
    print("="*60)
    # Use global lobbies if no argument
    if lobby_list is None:
        lobby_list = list(lobbies.values())
    for i, l in enumerate(lobby_list):
        status_text = status_map.get(l.get('status', 1), str(l.get('status', 1)))
        is_private = bool(l.get('password'))
        type_text = "Private" if is_private else "Public"
        players = ','.join(l.get('players', []))
        print(f"{i:2}   {l.get('name','')[:12]:12}   {status_text:6}  {type_text:7} {players}")


def parse_lobby_create_packet(data):
    # Sample incoming: d5 07 2b 00 41414141000000000000000000424142415858585858585858000000000041414141414141410000000000
    # Offsets found by hex inspection:
    # 0x04: 4 bytes: player_id
    # 0x0C: 12 bytes: lobby name
    # 0x1C: 8 bytes: password
    player_id = data[4:8].decode('ascii').rstrip('\x00')
    lobby_name = data[17:29].decode('ascii').rstrip('\x00')
    password = data[34:42].decode('ascii').rstrip('\x00')
    return player_id, lobby_name, password

def build_lobby_create_ack():
    return bytes.fromhex("bd0b010001")

def parse_lobby_join_packet(data):
    # Offsets found by hex inspection:
    # 0x04: 4 bytes: player_id
    # 0x18: 12 bytes: lobby name
    player_id = data[4:8].decode('ascii').rstrip('\x00')
    lobby_name = data[24:36].decode('ascii').rstrip('\x00')
    return player_id, lobby_name


def build_lobby_join_ack():
    """
    Builds a 0xbbf lobby join ack packet.
    - val: 2-byte value, e.g., 1 or 2.
    Returns a bytes object ready to send.
    """
    val = 0
    packet_id = 0x0bbe
    flag = b'\x01\x00\x00\x00'  # 4 bytes
    payload = flag + struct.pack('<H', val)  # 4 + 2 = 6 bytes
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_lobby_join_ack_2():
    """
    Builds a 0xbbf lobby join ack packet.
    - val: 2-byte value, e.g., 1 or 2.
    Returns a bytes object ready to send.
    """
    val = 0
    packet_id = 0x0bbf
    flag = b'\x01\x00\x00\x00'  # 4 bytes
    payload = flag + struct.pack('<H', val)  # 4 + 2 = 6 bytes
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def build_lobby_room_packet(lobby_name, players=None, map_idx=1, l_flag=1):

## Build a 0x03ee Lobby Room Info packet for Mystic Nights.
## 
## Total payload length: 0x9C (156 bytes)
## Total packet length:  0x9C + 4 header = 0xA0 (160 bytes)
## 
## Header (not part of payload layout):
##   [0x00–0x01] packet_id   (0x03EE, little endian)
##   [0x02–0x03] pkt_len     (total payload length = 0x9C)
## 
## Payload layout (offsets below start at 0x00, i.e., immediately after header):
##   [0x00]    lobby_leader     (1 byte: 00/01/02/03 based on position)
##   [0x01–0x03] padding        (3 bytes: 00 00 00)
##   [0x04–0x13] lobby_name     (16 bytes, EUC-KR, null-padded)
##   [0x14–0x23] unknown1       (16 bytes)
##   [0x24–0x93] player blocks  (4 blocks × 28 bytes = 112 bytes)
##       Player block layout (28 bytes each):
##         [0x00–0x07]  player_id   (8 bytes, ASCII, null-padded)
##         [0x08–0x0C]  reserved    (5 bytes, zero)
##         [0x0D]       character  (1 byte: character selection)
##                        - 01: Allen, 02: Henry, 03: Frank, 04: John
##                          05: Michael, 06: Luke, 07: Kelly, 08: Jane
##         [0x0E]       status     (1 byte: player status)
##                        - 00: Not Ready, 01: Ready
##         [0x0F]       padding    (1 byte: 00)
##         [0x10–0x13]  rank       (4 bytes: only 1st byte used)
##                        - E: [00–0A], D: [0B–1E], C: [1F–32], B: [33–5A],
##                          A: [5B–8C], S: [8D–9F], X: 0x9F01+
##         [0x14–0x17]  unknown2   (4 bytes)
##         [0x18–0x1B]  unknown3   (4 bytes)
##   [0x94–0x97] map_select      (4 bytes: 01/02/03/04/05 00 00 00)
##   [0x98–0x9B] lobby_flag      (4 bytes: 01/04 00 00 00)

    import struct

    packet_id = 0x03ee
    lobby_leader = b'\x00'               # Default to lobby leader position 0
    padding = b'\x00\x00\x00'            # 3-byte padding after leader
    name = lobby_name.encode('euc-kr', errors='replace')[:16].ljust(16, b'\x00')
    unknown1 = b'\x00' * 16              # Reserved 16-byte field

    if players is None:
        players = []

    player_structs = []
    for p in (players + [{}]*4)[:4]:
        pid = p.get("player_id", b'\x00' * 8)
        if isinstance(pid, str):
            pid = pid.encode('ascii', errors='replace')[:8].ljust(8, b'\x00')

        block = bytearray(28)
        block[0:8]   = pid                                # Player ID
        block[8:13]  = b'\x00' * 5                        # Reserved
        block[0x0D]  = p.get("character", 0)              # Character select
        block[0x0E]  = p.get("status", 0)                 # Player status
        block[0x0F]  = 0                                  # Padding
        block[0x10:0x14] = struct.pack('<I', p.get("rank", 0))        # Rank (only LSB used)
        block[0x14:0x18] = struct.pack('<I', p.get("unknown2", 0))    # Unknown field 2
        block[0x18:0x1C] = struct.pack('<I', p.get("unknown3", 0))    # Unknown field 3
        player_structs.append(bytes(block))

    # Final 8 bytes: map_select and lobby_flag (each 4 bytes, little-endian)
    map_select = struct.pack('<I', map_idx)  # Default value 0x01000000
    lobby_flag = struct.pack('<I', l_flag)  # Default value 0x01000000

    # Assemble full payload
    payload = (
        lobby_leader +
        padding +
        name +
        unknown1 +
        b''.join(player_structs) +
        map_select +
        lobby_flag
    )

    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload


def build_map_select_ack():
    """
    Builds a 0xbbf lobby join ack packet.
    - val: 2-byte value, e.g., 1 or 2.
    Returns a bytes object ready to send.
    """
    val = 1
    packet_id = 0x0bc6
    flag = b'\x01\x00\x00\x00'  # 4 bytes
    payload = flag + struct.pack('<H', val)  # 4 + 2 = 6 bytes
    packet_len = len(payload)
    header = struct.pack('<HH', packet_id, packet_len)
    return header + payload

def send_packet_to_client(session, payload):
    ether = Ether(dst=session["mac"], src=MY_MAC)
    ip_layer = IP(src=HOST, dst=session["ip"])
    tcp_layer = TCP(sport=session["sport"], dport=session["dport"], flags="PA",
                    seq=session["seq"] + 1, ack=session["ack"])
    sendp(ether/ip_layer/tcp_layer/Raw(load=payload), iface=IFACE, verbose=False)
    session["seq"] += len(payload)

def build_character_select_setup_packet(player):
    """
    Build a 0xbc4 packet for one player (32 bytes payload).
    """
    import struct
    packet_id = 0xbc4
    flag_and_unknown = b'\x01\x00\x00\x00'
    # Create the 28-byte player info block, just like 03ee
    pid = player.get("player_id", b'\x00' * 8)
    if isinstance(pid, str):
        pid = pid.encode('ascii', errors='replace')[:8].ljust(8, b'\x00')
    block = bytearray(28)
    block[0:8]   = pid
    block[8:13]  = b'\x00' * 5
    block[0x0D]  = player.get("character", 0)
    block[0x0E]  = player.get("status", 0)
    block[0x0F]  = 0
    block[0x10:0x14] = struct.pack('<I', player.get("rank", 0))
    block[0x14:0x18] = struct.pack('<I', player.get("unknown2", 0))
    block[0x18:0x1C] = struct.pack('<I', player.get("unknown3", 0))
    # Pad to 32 bytes for bc4
    data = bytes(block).ljust(32, b'\x00')
    header = struct.pack('<HH', packet_id, 36)
    return header + flag_and_unknown + data

def build_character_select_ack():
    """
    Build a 0xbc5 ACK packet (character select ACK).
    """
    import struct
    packet_id = 0xbc5
    flag = b'\x01\x00\x00\x00'
    val = 1
    payload = flag + struct.pack('<H', val)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_bc0_packet(data: bytes, param_3: int, param_4: int, param_5: int) -> bytes:
    """
    Build a 0xbc0 packet with standard header and 16 bytes data + 3 shorts.
    Header: <packet_id:2> <payload_len:2> 01 00 00 00
    """
    import struct
    packet_id = 0xbc0
    # 4 for flag+unknown, 16 for data, 2+2+2 for shorts
    payload_len = 4 + 16 + 2 + 2 + 2
    if len(data) != 16:
        raise ValueError("data for 0xbc0 packet must be exactly 16 bytes")
    header = struct.pack('<HH', packet_id, payload_len)
    flag_and_unknown = b'\x01\x00\x00\x00'
    payload = struct.pack('<16sHHh', data, param_3, param_4, param_5)
    return header + flag_and_unknown + payload

def build_kick_player_ack():
    """
    Build a 0xbc3 ACK packet (kick player ACK).
    """
    import struct
    packet_id = 0xbc3
    flag = b'\x01\x00\x00\x00'
    val = 1
    payload = flag + struct.pack('<H', val)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_lobby_leave_ack():
    """
    Build a 0xbc2 ACK packet (lobby leave ACK).
    """
    import struct
    packet_id = 0xbc2
    flag = b'\x01\x00\x00\x00'
    val = 1
    payload = flag + struct.pack('<H', val)
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

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
            send_packet_to_client(latest_session, pkt_bytes)
            print(f"[MANUAL SEND] {pkt_hex}")
        else:
            print("[ERROR] No session to send to.")

def handle_ip(pkt):
    global allow_manual_send, latest_session, previous_pkt_id, pkt_cnt, lobby_counter
    global current_lobby_name, current_lobby_players, current_lobby_map, current_lobby_flag, current_lobby_leader
    if not (pkt.haslayer(IP) and pkt.haslayer(TCP)):
        return

    ip = pkt[IP]
    tcp = pkt[TCP]
    key = (ip.src, tcp.sport)

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

        if pkt_id == 0x07d1:
            pid, plen, user, pwd = parse_account_create(client_data)
            print(f"[ACCOUNT CREATE REQ] User: {user} Pass: {pwd}")
            id_exists = any(acc[0] == user for acc in accounts)
            if not id_exists:
                accounts.append((user, pwd))
                response = build_account_creation_result(success=True)
                print(f"[SEND] Account creation OK to {ip.src}:{tcp.sport} ← {response.hex()}")
            else:
                response = build_account_creation_duplicate_id_error()
                print(f"[SEND] Account already exists to {ip.src}:{tcp.sport} ← {response.hex()}")
            if not allow_manual_send:
                allow_manual_send = True
                latest_session = session
                threading.Thread(target=manual_packet_sender, daemon=True).start()
            else:
                latest_session = session  # update session if new server list requested

        elif pkt_id == 0x07df:
            response = build_server_list_packet()
            print(f"[SEND] To {ip.src}:{tcp.sport} ← {response.hex()}")
            if not allow_manual_send:
                allow_manual_send = True
                latest_session = session
                threading.Thread(target=manual_packet_sender, daemon=True).start()
            else:
                latest_session = session  # update session if new server list requested

        elif pkt_id == 0x07d3:
            response = build_channel_list_packet()
            print(f"[SEND] To {ip.src}:{tcp.sport} ← {response.hex()}")
            if not allow_manual_send:
                allow_manual_send = True
                latest_session = session
                threading.Thread(target=manual_packet_sender, daemon=True).start()
            else:
                latest_session = session  # update session if new server list requested

        elif pkt_id == 0x07d0:
            response = build_login_packet()
            print(f"[SEND] To {ip.src}:{tcp.sport} ← {response.hex()}")
            if not allow_manual_send:
                allow_manual_send = True
                latest_session = session
                threading.Thread(target=manual_packet_sender, daemon=True).start()
            else:
                latest_session = session  # update session if new server list 

        elif pkt_id == 0x7d4:
            response = build_channel_join_ack(client_data)
            print(f"[SEND] To {ip.src}:{tcp.sport} ← {response.hex()}")
            if not allow_manual_send:
                allow_manual_send = True
                latest_session = session
                threading.Thread(target=manual_packet_sender, daemon=True).start()
            else:
                latest_session = session  # update session if new server list 
        
        elif pkt_id == 0x07d5:
            player_id, lobby_name, password = parse_lobby_create_packet(client_data)

            if lobby_name not in lobbies:
                lobbies[lobby_name] = {
                    'room_id': lobby_counter,
                    'name': lobby_name,
                    'password': password,
                    'max_players': 4,
                    'current_players': 1,
                    'players': [player_id]
                }
                lobby_counter += 1
                print(f"[LOBBY CREATE] '{lobby_name}' created by '{player_id}', password={password}{'(private)' if password else ' none (public)'}")

                #  Update global lobby state
                current_lobby_name = lobby_name
                current_lobby_players = [{
                    "player_id": player_id,
                    "character": 0x01,
                    "status": 0x00,
                    "rank": 0x01
                }]
                current_lobby_map = 1       # Default map
                current_lobby_flag = 1      # Default flag
                current_lobby_leader = 0    # Creator is lobby leader
            else:
                print(f"[LOBBY CREATE] Attempt to recreate existing lobby '{lobby_name}' ignored.")

            response = build_lobby_create_ack()
            print(f"[SEND] To {ip.src}:{tcp.sport} ← {response.hex()}")

            latest_session = session
            if not allow_manual_send:
                allow_manual_send = True
                threading.Thread(target=manual_packet_sender, daemon=True).start()

        elif pkt_id == 0x07d6:
            player_id, lobby_name = parse_lobby_join_packet(client_data)
            lobby = lobbies.get(lobby_name)

            # Fuzzy match fallback
            if not lobby:
                for name in lobbies:
                    if name.rstrip('\x00') == lobby_name.rstrip('\x00'):
                        lobby = lobbies[name]
                        lobby_name = name
                        break

            if lobby:
                if player_id not in lobby['players']:
                    if lobby['current_players'] < lobby['max_players']:
                        lobby['players'].append(player_id)
                        lobby['current_players'] += 1
                        print(f"[LOBBY JOIN] '{player_id}' joined lobby '{lobby_name}'")
                    else:
                        print(f"[LOBBY JOIN] '{lobby_name}' is full! '{player_id}' cannot join.")
                else:
                    print(f"[LOBBY JOIN] '{player_id}' is already in lobby '{lobby_name}'")

                # Update global lobby state
                current_lobby_name = lobby_name
                # Using the global fields as is for development and testing - to be completed later
                ### current_lobby_players = [
                ###     {
                ###         "player_id": pid,
                ###         "character": tbd
                ###         "status": 0x00,
                ###         "rank": getRank(pid)
                ###     }
                ###     for i, pid in enumerate(lobby["players"])
                ### ]
                current_lobby_players = current_lobby_players # leave unchanged
                current_lobby_map = current_lobby_map  # leave unchanged
                current_lobby_leader = current_lobby_leader # leave unchanged
                current_lobby_flag = 1
            else:
                print(f"[LOBBY JOIN] Lobby '{lobby_name}' does not exist.")

            # Response chain logic
            if previous_pkt_id == pkt_id and pkt_cnt == 2:
                response = build_lobby_room_packet(
                    current_lobby_name,
                    players=current_lobby_players,
                    map_idx=current_lobby_map,
                    l_flag=current_lobby_flag
                )
                pkt_cnt = 0
            elif previous_pkt_id == pkt_id and pkt_cnt == 1:
                response = build_lobby_join_ack_2()
                pkt_cnt = 2
            else:
                response = build_lobby_join_ack()
                pkt_cnt = 1

            print(f"[SEND] To {ip.src}:{tcp.sport} ← {response.hex()}")
            latest_session = session
            if not allow_manual_send:
                allow_manual_send = True
                threading.Thread(target=manual_packet_sender, daemon=True).start()

        
        elif pkt_id == 0x07e0:
            response = build_lobby_list_packet()
            print(f"[SEND] To {ip.src}:{tcp.sport} ← {response.hex()}")
            if not allow_manual_send:
                allow_manual_send = True
                latest_session = session
                threading.Thread(target=manual_packet_sender, daemon=True).start()
            else:
                latest_session = session  # update session if new server list requested
            
        elif pkt_id == 0x07da:
            # --- Parse player ID to leave (payload after header, 4+ bytes ASCII) ---
            if len(client_data) >= 8:
                player_id = client_data[4:8].decode('ascii').rstrip('\x00')
                print(f"[0x07da] Lobby leave request for player: {player_id}")

                # Send ACK (0xbc2)
                ack_packet = build_lobby_leave_ack()
                ether = Ether(dst=session["mac"], src=MY_MAC)
                ip_layer = IP(src=HOST, dst=ip.src)
                tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                                seq=session["seq"] + 1, ack=tcp.seq + len(client_data))
                sendp(ether/ip_layer/tcp_layer/Raw(load=ack_packet), iface=IFACE, verbose=False)
                session["seq"] += len(ack_packet)
                session["ack"] = tcp.seq + len(client_data)
                print(f"[SEND] Lobby Leave ACK (0xbc2) to {ip.src}:{tcp.sport} ← {ack_packet.hex()}")

                # Remove player from current lobby
                removed = False
                for i, p in enumerate(current_lobby_players):
                    pid = p.get("player_id", b"").decode() if isinstance(p.get("player_id"), bytes) else p.get("player_id")
                    if pid == player_id:
                        removed_player = current_lobby_players.pop(i)
                        print(f"[LEAVE] Removed player: {removed_player.get('player_id')}")
                        removed = True
                        break
                if not removed:
                    print(f"[WARN] Player {player_id} not found for 0x07da leave")
            else:
                print(f"[ERROR] 0x07da lobby leave packet too short")

            latest_session = session
            if not allow_manual_send:
                allow_manual_send = True
                threading.Thread(target=manual_packet_sender, daemon=True).start()

        elif pkt_id == 0x07db:
            # Parse the player index to be kicked (payload at offset 4, 4 bytes little-endian)
            if len(client_data) >= 8:
                kick_idx = struct.unpack('<I', client_data[4:8])[0]
                print(f"[0x07db] Kick request: remove player at index {kick_idx}")

                # ACK the kick with 0xbc3
                ack_packet = build_kick_player_ack()
                ether = Ether(dst=session["mac"], src=MY_MAC)
                ip_layer = IP(src=HOST, dst=ip.src)
                tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                                seq=session["seq"] + 1, ack=tcp.seq + len(client_data))
                sendp(ether/ip_layer/tcp_layer/Raw(load=ack_packet), iface=IFACE, verbose=False)
                session["seq"] += len(ack_packet)
                session["ack"] = tcp.seq + len(client_data)
                print(f"[SEND] Kick Player ACK (0xbc3) to {ip.src}:{tcp.sport} ← {ack_packet.hex()}")

                # Remove the player at that index from current_lobby_players
                if 0 <= kick_idx < len(current_lobby_players):
                    kicked = current_lobby_players.pop(kick_idx)
                    print(f"[KICK] Removed player: {kicked.get('player_id')}")
                else:
                    print(f"[WARN] Invalid kick index: {kick_idx}")

                # Send updated 0x03ee lobby packet
                room_packet = build_lobby_room_packet(
                    lobby_name=current_lobby_name,
                    players=current_lobby_players,
                    map_idx=current_lobby_map,
                    l_flag=current_lobby_flag
                )
                ether2 = Ether(dst=session["mac"], src=MY_MAC)
                tcp_layer2 = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                                 seq=session["seq"] + 1, ack=session["ack"])
                sendp(ether2/ip_layer/tcp_layer2/Raw(load=room_packet), iface=IFACE, verbose=False)
                session["seq"] += len(room_packet)
                print(f"[SEND] Updated Lobby Room Packet (0x03ee) after kick to {ip.src}:{tcp.sport}")

            else:
                print(f"[ERROR] Malformed 0x07db kick packet (len={len(client_data)})")

            latest_session = session
            if not allow_manual_send:
                allow_manual_send = True
                threading.Thread(target=manual_packet_sender, daemon=True).start()

        elif pkt_id == 0x07dc:
            # --- Extract player ID (first 4 bytes of payload after header) ---
            if len(client_data) >= 8:
                requested_id = client_data[4:8].decode('ascii').rstrip('\x00')
                print(f"[0x7dc] Requested player info for: {requested_id}")

                # Find the player in current lobby
                for p in current_lobby_players:
                    if p.get("player_id", b"").decode() if isinstance(p.get("player_id"), bytes) else p.get("player_id") == requested_id:
                        bc4_response = build_character_select_setup_packet(p)
                        # Save for later use in 0x07dd
                        session["last_7dc_player_id"] = requested_id
                        print(f"[SEND] To {ip.src}:{tcp.sport} ← {bc4_response.hex()}")
                        ether = Ether(dst=session["mac"], src=MY_MAC)
                        ip_layer = IP(src=HOST, dst=ip.src)
                        tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                                        seq=session["seq"] + 1, ack=tcp.seq + len(client_data))
                        sendp(ether/ip_layer/tcp_layer/Raw(load=bc4_response), iface=IFACE, verbose=False)
                        session["seq"] += len(bc4_response)
                        session["ack"] = tcp.seq + len(client_data)
                        break
                else:
                    print(f"[WARN] Player {requested_id} not found for 0x7dc")
            else:
                print(f"[ERROR] 0x07dc packet too short")
            latest_session = session
            if not allow_manual_send:
                allow_manual_send = True
                threading.Thread(target=manual_packet_sender, daemon=True).start()

        elif pkt_id == 0x07dd:
            # --- Parse the selected character byte from payload ---
            if len(client_data) >= 8:
                char_val = client_data[4]
                print(f"[0x7dd] Client selected character: {char_val}")

                # Find the last requested player from 0x7dc
                requested_id = session.get("last_7dc_player_id")
                updated = False
                if requested_id:
                    for p in current_lobby_players:
                        pid = p.get("player_id", b"").decode() if isinstance(p.get("player_id"), bytes) else p.get("player_id")
                        if pid == requested_id:
                            print(f"[0x7dd] Updating player {pid} character to {char_val}")
                            p["character"] = char_val
                            updated = True
                            break
                    if not updated:
                        print(f"[WARN] 0x07dd: player {requested_id} not found in current_lobby_players")

                # Send 0xbc5 ACK
                ack_packet = build_character_select_ack()
                ether = Ether(dst=session["mac"], src=MY_MAC)
                ip_layer = IP(src=HOST, dst=ip.src)
                tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                                seq=session["seq"] + 1, ack=tcp.seq + len(client_data))
                sendp(ether/ip_layer/tcp_layer/Raw(load=ack_packet), iface=IFACE, verbose=False)
                session["seq"] += len(ack_packet)
                session["ack"] = tcp.seq + len(client_data)
                print(f"[SEND] Character Select ACK (0xbc5) to {ip.src}:{tcp.sport} ← {ack_packet.hex()}")

                # Immediately follow with an updated 0x03ee packet
                room_packet = build_lobby_room_packet(
                    lobby_name=current_lobby_name,
                    players=current_lobby_players,
                    map_idx=current_lobby_map,
                    l_flag=current_lobby_flag
                )
                ether2 = Ether(dst=session["mac"], src=MY_MAC)
                tcp_layer2 = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                                 seq=session["seq"] + 1, ack=session["ack"])
                sendp(ether2/ip_layer/tcp_layer2/Raw(load=room_packet), iface=IFACE, verbose=False)
                session["seq"] += len(room_packet)
                print(f"[SEND] Updated Lobby Room Packet (0x03ee) after char select to {ip.src}:{tcp.sport}")
            else:
                print(f"[ERROR] Malformed 0x07dd packet (len={len(client_data)})")
            latest_session = session
            if not allow_manual_send:
                allow_manual_send = True
                threading.Thread(target=manual_packet_sender, daemon=True).start()

        elif pkt_id == 0x07de:
            if len(client_data) >= 8:
                desired_map = struct.unpack('<I', client_data[4:8])[0]
                print(f"[MAP SELECT] Client requested map index: {desired_map}")
                current_lobby_map = desired_map  # Update global state

                # First send ACK (0x0BC6)
                ack_packet = build_map_select_ack()
                ether = Ether(dst=session["mac"], src=MY_MAC)
                ip_layer = IP(src=HOST, dst=ip.src)
                tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                                seq=session["seq"] + 1, ack=tcp.seq + len(client_data))
                sendp(ether/ip_layer/tcp_layer/Raw(load=ack_packet), iface=IFACE, verbose=False)
                session["seq"] += len(ack_packet)
                session["ack"] = tcp.seq + len(client_data)
                print(f"[SEND] Map Select ACK to {ip.src}:{tcp.sport} ← {ack_packet.hex()}")

                # Then send updated 0x03ee lobby state
                room_packet = build_lobby_room_packet(
                    lobby_name=current_lobby_name,
                    players=current_lobby_players,
                    map_idx=current_lobby_map,
                    l_flag=current_lobby_flag
                )
                ether2 = Ether(dst=session["mac"], src=MY_MAC)
                tcp_layer2 = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                                 seq=session["seq"] + 1, ack=session["ack"])
                sendp(ether2/ip_layer/tcp_layer2/Raw(load=room_packet), iface=IFACE, verbose=False)
                session["seq"] += len(room_packet)
                print(f"[SEND] Lobby Room Packet (0x03ee) with map={desired_map} to {ip.src}:{tcp.sport}")
            else:
                print(f"[ERROR] Malformed 0x07de packet (len={len(client_data)})")
            latest_session = session
            if not allow_manual_send:
                allow_manual_send = True
                threading.Thread(target=manual_packet_sender, daemon=True).start()


        if response:
            ether = Ether(dst=session["mac"], src=MY_MAC)
            ip_layer = IP(src=HOST, dst=ip.src)
            tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                            seq=session["seq"] + 1, ack=tcp.seq + len(client_data))
            sendp(ether/ip_layer/tcp_layer/Raw(load=response), iface=IFACE, verbose=False)
            session["seq"] += len(response)
            session["ack"] = tcp.seq + len(client_data)
            latest_session = session  # Always set latest_session to most recent
        
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