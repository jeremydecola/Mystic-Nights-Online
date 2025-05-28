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
MY_MAC = "00:ff:e5:67:d5:da"
IFACE = "OpenVPN TAP-Windows6"

tcp_sessions = {}
accounts = [("AAAA", "AAAA")]  # Store tuples of (username, password)
allow_manual_send = False
latest_session = None

print("-------------------------------")
print("Mystic Nights Dummy Server v0.6")
print("-------------------------------")

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
        (0, 1, 4),  # Channel 1: 0/4 players
        (1, 0, 4),
        (2, 3, 4)
        # Add more tuples here if needed
    ]

    # Pad out to 12 channels
    while len(channels) < 12:
        channels.append((len(channels), 0, 4))

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
    packet_id = 0xbbc
    payload = b'\x01'
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_lobby_list_packet_old():
    import struct

    packet_id = 0xbc8
    flag = 1
    unknown = b'\x00\x00\x00'

    lobbies = [
        {"name": "TestRoom", "status": 0, "cur": 1, "max": 4, "public": 1},
        # Add more as needed
    ]

    max_lobbies = 10
    while len(lobbies) < max_lobbies:
        lobbies.append({
            "name": "<Empty Lobby Slot>",  # filler entry
            "status": 0,
            "cur": 0,
            "max": 4,
            "public": 1
        })

    entries = b''
    for lobby in lobbies:
        unknown = b'\x00' * 12
        name = lobby['name'].encode('euc-kr')[:28].ljust(28, b'\x00')
        status = lobby['status']
        cur = lobby['cur']
        maxp = lobby['max']
        public = lobby['public']
        entries += struct.pack('<12s28sBBBB', unknown, name, status, cur, maxp, public)

    payload = struct.pack('<B3s', flag, unknown) + entries
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload

def build_lobby_list_packet():
    import struct

    packet_id = 0xbc8
    flag = 1
    unknown = b'\x00\x00\x00'  # same header format

    # Example lobbies: adjust/add more as needed.
    lobbies = [
        {
            'room_id': 1,
            'cur_players': 0,
            'max_players': 4,
            'name': "Test Room",     # shown in lobby list
            'sub': "Public",         # could be anything, not shown
            'status': 1,             # 0=open, 1=closed/locked?
        },
        # Add more lobbies here!
    ]

    # Pad up to 20 lobbies
    while len(lobbies) < 20:
        lobbies.append({
            'room_id': 2,
            'cur_players': 0,
            'max_players': 4,
            'name': "test",
            'sub': "Public",
            'status': 0,
        })

    entries = b""
    for entry in lobbies:
        name = entry['name'].encode('euc-kr', errors='replace')[:16].ljust(16, b'\x00')
        sub = entry['sub'].encode('euc-kr', errors='replace')[:12].ljust(12, b'\x11')
        packed = struct.pack(
            '<III16s12s2sB B',
            entry['room_id'],
            entry['cur_players'],
            entry['max_players'],
            name,
            sub,
            b'\x00\x00',        # pad
            entry['status'],
            0                   # pad2
        )
        entries += packed

    payload = struct.pack('<B3s', flag, unknown) + entries
    header = struct.pack('<HH', packet_id, len(payload))
    return header + payload


def send_packet_to_client(session, payload):
    ether = Ether(dst=session["mac"], src=MY_MAC)
    ip_layer = IP(src=HOST, dst=session["ip"])
    tcp_layer = TCP(sport=session["sport"], dport=session["dport"], flags="PA",
                    seq=session["seq"] + 1, ack=session["ack"])
    sendp(ether/ip_layer/tcp_layer/Raw(load=payload), iface=IFACE, verbose=False)
    session["seq"] += len(payload)

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
    global allow_manual_send, latest_session
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
        
        elif pkt_id == 0x07e0:
            response = build_lobby_list_packet()
            print(f"[SEND] To {ip.src}:{tcp.sport} ← {response.hex()}")
            if not allow_manual_send:
                allow_manual_send = True
                latest_session = session
                threading.Thread(target=manual_packet_sender, daemon=True).start()
            else:
                latest_session = session  # update session if new server list requested
    

        else:
            print(f"[WARN] Unhandled packet ID: {pkt_id}")

        if response:
            ether = Ether(dst=session["mac"], src=MY_MAC)
            ip_layer = IP(src=HOST, dst=ip.src)
            tcp_layer = TCP(sport=tcp.dport, dport=tcp.sport, flags="PA",
                            seq=session["seq"] + 1, ack=tcp.seq + len(client_data))
            sendp(ether/ip_layer/tcp_layer/Raw(load=response), iface=IFACE, verbose=False)
            session["seq"] += len(response)
            session["ack"] = tcp.seq + len(client_data)
            latest_session = session  # Always set latest_session to most recent

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