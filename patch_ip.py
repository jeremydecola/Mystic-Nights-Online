import os
import ipaddress

def patch_ip_in_iso(iso_path, ip_offset, new_ip):
    # Enforce max 15-character ASCII IP string for patching
    new_ip_bytes = new_ip.encode("ascii").ljust(15, b'\x00')
    with open(iso_path, "r+b") as f:
        f.seek(ip_offset)
        f.write(new_ip_bytes)
    print(f"Patched IP address {new_ip} at offset {hex(ip_offset)} in {iso_path}.")

def main():
    iso_path = input("Enter ISO file path: ").strip()
    if not os.path.exists(iso_path):
        print("File not found!")
        return

    while True:
        new_ip = input("Enter new IP address (e.g., 192.168.1.100): ").strip()
        try:
            # Validate IP address format
            ipaddress.IPv4Address(new_ip)
            break
        except ipaddress.AddressValueError:
            print("Invalid IPv4 address. Please try again.")

    #offset on original game is 0x64ffb1e8
    ip_offset = 0x64ffb9e8
    patch_ip_in_iso(iso_path, ip_offset, new_ip)

if __name__ == "__main__":
    main()
