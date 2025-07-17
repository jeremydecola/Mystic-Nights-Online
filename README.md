# Mystic Nights (PS2) Multiplayer Private Server

Mystic Nights (미스틱 나이츠) is an obscure Korean-Exclusive survival horror Playstation 2 title.
It was developed by N-LOG Soft and published by Sony Computer Entertainment Korea in 2005.
Although a North-American release was planned, the game was never localized.

This project's goal is to revive the Online Multiplayer functionality of the game by reverse-engineering the expected packet replies required from the server. This is achieved through examination of the client side packet parsing code through Ghidra decompilation (MIPS 5900 to C), analysis of values at target memory addresses in EE and IOP RAM (using PCSX2 Debugger) during different game states and some careful packet fuzzing.

If you like my work, feel free to show your support: https://ko-fi.com/jeremydecola

I'm hosting my server for a limited time!

For more information check out : https://jeremydecola.github.io/Mystic-Nights-Archive/multiplayer.html

# Connect to an Existing server

Patch the Mystic Nights iso with my latest English Translation patch:
https://github.com/jeremydecola/Mystic-Nights-Translation/tree/master

## 1. PCSX2/DEV9 Setup (for Online Play)

- **PCSX2** emulator ([PCSX2.net](https://pcsx2.net/)) with **DEV9** network plugin.
- Open the "Network & HDD" menu in PCSX2. Make sure Ethernet is enabled. Select Ethernet Device Type: Sockets or PCAP Bridged. Then, select the name of the adapter you use to access the internet. (Something like "Ethernet"). 

## 2. Patch the Mystic Nights ISO so that it connects to the Private Server
1. Find the IP address of the server you want to connect to.
2. **Patch Mystic Nights ISO** with server IP address (use the provided patch_ip.py).
- IMPORTANT: The patch_ip.py tool doesn't work with the original untranslated Mystic Nights iso. If you would like to use that one, you will have to hex edit the IP address manually.
- Note: My latest v1.2 translation patch already patches the IP address to the PUBLIC IP of my server.

## 3. Set up Network Configuration on PS2 Memory Card.
1. Boot up Mystic Nights in PCSX2 and Navigate to NETWORK GAME from the main menu.
2. Follow the guide on the Mystic Nights Archive website: https://jeremydecola.github.io/Mystic-Nights-Archive/multiplayer.html

# Host the server yourself

## Prerequisites

Patch the Mystic Nights iso with my latest English Translation patch:
https://github.com/jeremydecola/Mystic-Nights-Translation/tree/master

### 1. Python Environment

- **Python 3.9+**\
  [Download Python](https://www.python.org/downloads/)

### 2. Database (Choose One)

- **SQLite 3** (Default — easy, local, no setup required)
- **PostgreSQL 13+** (Advanced/production, optional)

### 3. Python Libraries

Install required Python packages:

```sh
pip install asyncpg aiosqlite aioconsole
```

Or using `requirements.txt`:

```sh
pip install -r requirements.txt
```

**Contents of requirements.txt:**

```
asyncpg
aiosqlite
aioconsole
```

### 4.1 PCSX2/DEV9 Setup (for Online Play)

- **PCSX2** emulator ([PCSX2.net](https://pcsx2.net/)) with **DEV9** network plugin.
- Open the "Network & HDD" menu in PCSX2. Make sure Ethernet is enabled. Select Ethernet Device Type: Sockets or PCAP Bridged. Then, select the name of the adapter you use to access the internet. (Something like "Ethernet"). 

### 4.2 PCSX2/DEV9 Setup (for Local Play)

- **PCSX2** emulator ([PCSX2.net](https://pcsx2.net/)) with **DEV9** network plugin.
- Create a **TAP** network adapter: 
  - **Windows:** Install [OpenVPN](https://openvpn.net/) or [TAP-Windows driver](https://swupdate.openvpn.org/community/releases/tap-windows-9.24.2.exe)
  - **Linux:** `sudo apt install uml-utilities` and create a tap device using `tunctl` or `ip tuntap`
- See [PCSX2 DEV9 Setup Guide](https://pcsx2.net/docs/) for bridging instructions.
- Open the "Network & HDD" menu in PCSX2. Make sure Ethernet is enabled. Select Ethernet Device Type: TAP. Then, select the TAP adapter that you created. 

---

## Instructions (Windows & Linux)

### A. Server Setup

#### 1. Clone or Download the Project

```sh
git clone https://github.com/jeremydecola/Mystic-Nights-Private-Server.git
cd Mystic-Nights-Private-Server
```

#### 2. Database Configuration

**SQLite (Default, easiest):**

- No manual setup needed.
- On first launch, `mysticnights.db` is created automatically and schema loaded from `mn_sqlite_schema.sql`.
- *(Optional)* To specify a custom database file, set the `SQLITE_FILE` environment variable.

**PostgreSQL (Advanced/Production):**

1. Create a PostgreSQL database and user.
2. Import the schema:
   ```sh
   psql -U youruser -d yourdb -f mn_postgres_schema.sql
   ```
3. Set environment variables as described below.

**SUPER IMPORTANT**

**The DATABASE contains a SERVERS table which holds the IP address of the 10 servers that are available to connect to. When you chose the first server in the list and try to log on, it then tries to establish a TCP session with the IP address associated to server 1. You must update the ip_address in the database to match your HOST (Server) IP.**

#### 3. Environment Variables

Set these before running the server (SQLite):

| Variable        | Description                | Example                              |
| --------------- | -------------------------- | ------------------------------------ |
| `DB_TYPE`       | `"sqlite"` or `"postgres"` | `DB_TYPE=sqlite`                     |
| `SQLITE_FILE`   | SQLite DB file name (opt)  | `SQLITE_FILE=mysticnights.db`        |
| `SQLITE_SCHEMA` | SQLite schema file (opt)   | `SQLITE_SCHEMA=mn_sqlite_schema.sql` |

Set these before running the server (PostgreSQL):

| Variable        | Description                | Example                              |
| --------------- | -------------------------- | ------------------------------------ |
| `DB_TYPE`       | `"sqlite"` or `"postgres"` | `DB_TYPE=postgres`                   |
| `PG_HOST`       | Postgres host              | `PG_HOST=localhost`                  |
| `PG_DBNAME`     | Postgres DB name           | `PG_DBNAME=mysticnights`             |
| `PG_USER`       | Postgres username          | `PG_USER=postgres`                   |
| `PG_PASSWORD`   | Postgres password          | `PG_PASSWORD=secret`                 |


**On Windows:**\
Set variables in Command Prompt for the current session:

```cmd
set DB_TYPE=sqlite
set SQLITE_FILE=mysticnights.db
```

**On Linux/macOS:**

```sh
export DB_TYPE=sqlite
export SQLITE_FILE=mysticnights.db
```

#### 4. Run the Server

```sh
python mn_server.py
```

- By default, the server listens on ports `18000` and `18001` (change in source if needed).
- Admin commands are available from the console after launch.
- The DEBUG variable can be used to print logs for troubleshooting purposes. Set the global variable DEBUG = 1 in the code. In production DEBUG should be set back to 0 as printing can be quite ressource intensive when we have multiple concurrent client connections.
- If you plan to host a server, you should probably run this as a service instead.

#### 5. Connecting from PCSX2 (Gameplay)

1. **Patch Mystic Nights ISO** with server IP address (use the provided patch_ip.py).
2. **Configure DEV9 plugin** in PCSX2:
   - **Exactly 1 PCSX2 client:** Set up a TAP adapter and bind DEV9 to it in the "Network & HDD" menu of PCSX2. Modify the properties of the TAP adapter so that the IP address corresponds to the IP of the server that your games are trying to connect to (the IP that is hardcoded in the HOST global variable in the server code and the same IP that you patched in with patch_ip.py). 
   - **More than 1 PCSX2 client:** Set up a unique TAP adapter for each PCSX2 instance you wish to run - bind each DEV9 of each PCSX2 instance to a different TAP adapter in the "Network & HDD" menu. Then, bridge your TAP adapters together. Example in Windows using Microsoft "Network Bridge". All of the TAP adapters can't have their IPv4 addresses changed once they're part of the "Network Bridge". Modify the properties of the "Network Bridge" so that the IP address corresponds to the IP of the server that your games are trying to connect to (the IP that is hardcoded in the HOST global variable in the server code and the same IP that you patched in with patch_ip.py). 
3. **Connect in-game**: Use the Multiplayer/Online menu in Mystic Nights.

#### 6. Server Usage

- Player registration, login, lobby creation/join, and game synchronization are all handled by the server.
- Disconnects, lobbies, and player stats (rank/score) are auto-managed in real-time.
- The admin console allows sending raw packets and shutting down gracefully.

---

## Troubleshooting
- **Do your IP addresses match everywhere?**
  - The IP set in MN_SERVER.py - HOST global variable
  - The server IP in the .iso (run patch_ip.py)
  - ip_adress field in the database SERVERS table
- **Firewall Issues:**
  - Ensure inbound TCP traffic to ports 18000 and 18001 is allowed.
  - On Windows, **allow PCSX2 and Python through your firewall**.
  - On Linux, use `ufw allow 18000:18001/tcp` or equivalent.
- **DEV9/TAP Adapter Not Working:**
  - Ensure TAP adapter is enabled and bridged to your main connection.
  - Check PCSX2 logs for network plugin errors.
- **Database Problems:**
  - For SQLite: Ensure the folder is writable and `mn_sqlite_schema.sql` exists.
  - For PostgreSQL: Verify credentials and connectivity. Use `psql` to test login.
- **Other Issues:**
  - Run Python with elevated permissions if necessary (Windows: Run as Administrator; Linux: use `sudo` only if needed).
  - Set `DEBUG=1` for verbose output (edit the `mn_server.py` source).

---

## License & Credits

- **Reverse engineering, code, and server:** Jeremy De Cola
- **Translation patch:** Jeremy De Cola
- **Mystic Nights** © N-Log Corporation, SCE Korea, 2005
- This project is non-commercial, for preservation/educational use only.

---

## Contact & Community

For questions, bug reports, or to join the project, open an [issue](https://github.com/jeremydecola/Mystic-Nights-Private-Server/issues) or contact jeremydecola on GitHub.

## *PROGRESS

### 1.0.0
Public release.
* Fixed 18000 session cleanup regression.
* Cleanup and improved README

### 0.9.12
* The server used a flag to blindly skip the first lobby join packet after a Quick Join, leading to unreliable behavior under high latency or packet reordering (sometimes skipping too many or too few join attempts).
  * When a player uses Quick Join, the randomly selected lobby index is now stored in the session.
  * The server will only accept lobby join packets matching the stored lobby index. All others are ignored while Quick Join is pending.
  * Once the correct join is processed, the pending state is cleared.
  * If no matching join arrives within 5 seconds, the server sends an explicit error packet to the client and clears the Quick Join state.
  * A new background coroutine (quick_join_timeout_watcher) handles these timeouts efficiently.
  * Even if Quick Join fails, we block/ignore lobby joins for 1 second since client attempts to blindly join lobby 0.
* Overriding print() function to return immediately if not DEBUG
  * Print statements are ressource intensive and are a bottleneck when trying to scale to hundreds of concurrent client connections.
* Removed CLIENT_GAMEPLAY_PORT from conditional checks for lobby broadcasts.
  * The client port is NOT always 3658. It varies greatly. 
* Disconnecting other sessions with same player_id (targeting Connection Manager 18000 session) on Channel Join
  * Echo Watcher would cause disconnects on session with port 18000 and would incorrectly remove associated player from the lobby causing a bunch of regressions. (following removal of CLIENT_GAMEPLAY_PORT check logic)

### 0.9.11
* No longer self-broadcasting Player/Enemy Attack packets
  * Fixes bug where double the ammo/mags are consumed
* Only incrementing player count of server after joining a channel at least one time.

### 0.9.10
* Implemented Channel and Server player count tracking
  * Server player count decrementing not working if client disconnects/resets before joining a Channel.
* Now assigning leader on lobby join if no leader is set (abnormal edge case)
* Now using ORDER ASC in SQL querries to avoid Servers and Channels unpredictably changing order (occured on Server player count increment)

### 0.9.9
* Implemented SQLite support (now supports both POSTGRESQL and SQLite backends)
* Patched MACRO character limit to 42 instead of 20 characters.
  * Monitor for regressions...
  * 001175A8 (00217528) 0x15 (21) changed to 0x2B (43)

### 0.9.8
* Not broadcasting 0x139c to self to avoid duplicate Player X Detected Near Incident events causing an extra increase in suspicion meter.
* No longer sending lobby room update at the end of Game Start packet handler
* Moved quick_join_pending flag to fix subsequent Lobby Join after Quick Join error causing an erroneous error.
* Modified start_server and main() so that Listening on Port X... messages print before the ADMIN console.

### 0.9.7
* Implemented 0x7d7 Lobby Quick Join packet handler
  * Using session flag to ignore first 0x7d6 packet received after Quick Join ack to avoid joining the wrong lobby/errors
* Corrected Lobby List packet so that we actually use the static idx_in_channel of each lobby to index them

### 0.9.6
* Refactored all code for asyncio singlethreaded design
* Fixed byte position of victory_flag for 0x3f3 packet
* Potentially fixed major issue with countdown/game start not working half the time
  * Sending a self-DC (0x3f4) packet before countdown seems to have greatly enhanced success rate.
* Found bug with lobby indexing after lobby deletion. I think we might be accidentally reindexing lobbies. 

### 0.9.5
* Solved regression with countdown and game start not working at all (still inconsistent)
  * Segmented pre-countdown echo challenges from echo watcher. 
  * Now pausing echo watcher during ready check and countdown.
* Added more lobby error handling.
* Fixed Lobby Kick logic (regression)
* On init, we now clear all lobbies unless TestRoom is in their name.
* MAJOR ISSUE: Despite my best attempts, 50% of the time, the client fails to react to the countdown/start packets. I tried:
  * Staggered broadcast
  * Increasing delay between packets.
  * 2x, 3x send for redundancy. 
* I will attempt to refactor the code into a singlethreaded design for simplicity's sake. I'll leave the multithreaded version semi-functional with this bug for those who are curious.
  
### 0.9.4
* Implemented watcher for disconnected player handling and implemented lobby HOST reassigment and lobby deletion conditions
* When a player disconnects while in game with  0x03f1 packet , the server removes that player from the lobby. 
  * If they were the "leader" in that lobby, the leader should become the lowest player index in the remaining players. 
* When a player leaves a lobby while in queue with a 0x07da packet  the server removes that player from the lobby. 
  * If they were the "leader" in that lobby, the leader should become the lowest player index in the remaining players. 
* If a player leaves a lobby and there are no more players to transfer leadership (leader) to , then the lobby is deleted from the database and that idx_in_channel becomes free to claim by the next created lobby
* When a Game Over 0x03f2 packet is received, we now set the lobby's status to 1 (In Queue) instead of 2 (Started)
* The server's main loop periodically sends an echo challenge on all player's that have joined a lobby and whose session we have not received a packet from in over 30 seconds. 
  * If they fail the echo challenge, they are removed from the lobby. 
  * If they were the "leader" in that lobby, the leader becomes the lowest player index in the remaining players. 

### 0.9.3
* Implemented all remaining necessary packet handlers
* Assigning gender randomly (likely the intended design - otherwise vampire identity is too obvious)
  * Leaving the ability to toggle back to Vampire Gender = Character Gender
* Added 0x3f1 packet handling. (Player Disconnect broadcast).
* Investigated no BGM > likely intended. Abandonning further investigation on missing BGM.
* When the HOST (player1) disconnects, the enemy AI stop reacting to other players.
  * It seems like the next player (player2) becomes the HOST. (To be confirmed) That would explain the behaviour, since I had no player2)
* Added echo challenge before game counter starts.(tx: 0x3e9, rx: 0x3ea.
* Added DC check on all lobby players based on session+player_id pair lookup.
* Implemented Game Over (0x3f2) and Rank Update (0x3f3) packet handlers.
* Observation: If the vampire player is marked as DC, the vampire is controlled by AI.

### 0.9.2
* Reverse engineered last remaining field in Game Start packet
  * Discovered Gender field in Game Start bc0 packet which must be set to either 0 or 1.
    * Fixes issue with strange sounds looping on player movement in vampire mode. 

### 0.9.1
* Fixed player starting positions logic and gameplay packet broadcasting
  * Discovered player starting positions logic in bc0 game start packet
  * Implemented vampire and map ID randomization in bc0 packet
  * Reverted to full lobby broadcast for all 0x13XX packets. Resolved many issues such as enemy models not doing a death animation and despawning, items not dropping, kill count not incrementing, etc. 
  * Each time the active vampire transforms, it currently loops a sound indefinitely. To be investigated. Potentially due to packet broadcasting change?
  * No music plays during gameplay. Perhaps this is intended? 
  
### 0.9.0
* Started implementing gameplay packet handling
  * We are now able to reach the actual game world.
    * Solved an issue where the screen would stay black and only the UI overlay would load. (Modified 0xbc0 packet reply)
  * Added ability to exclude the sender's session from a packet broadcast.
  * Broadcasting all received 0x13XX packets directly back to all other players.
  * Now Broadcasting Game Start to all players. (this fixes non-leader players not transitioning from lobby to game)
  * Discovered logic for reply to 0x3f0. Each player sends a Ready Ack. When all Acks are received, we send packets to perform a coutdown. 
  * ENEMY DEATH, PLAYER DEATH, ENEMY KILL COUNT logic has still not been discovered. A lot of error handling left to do. RANDOM map select is now hardcoded. Need to add randomization.
  
### 0.8.3
* Migrated from Scapy-based raw packet handling to threaded TCP socket server
  * TCP socket implementation REQUIRES firewall modification to allow TCP on ports 18000 and 18001 - adding powershell script
  * Replaced Scapy sniffing/packet injection with standard Python socket server implementation
  * Implemented threaded client handling for simultaneous connections
  * Improved session management and code structure for maintainability
  * Prepares server for production-like multiplayer support and real-world PS2 network compatibility
  
### 0.8.2
* Removed all reliance on local in favor of DB lookups
* Refactoring of code done. Classes now reflect DB schema. Removed redundant functions. 
  * To be done: 
    *Player Count accross all entities, Passing lobby owner to next player vs. deleting lobby, Channel Error handling, Lobby Error handling, Login Error handling, Add try-except statements to all DB operations to be able to notify client of DB Errors. 

### 0.8.1
* Continued DB integration
  * Servers, Channels, Lobbies, Players tables, Lobby Join, Lobby Creation, Lobby Leave created.
  * Server List, Account Creation, Account Deletion, Login, Channel List, Channel Join, Lobby List, Lobby Kick, Map Select, Character Select working.
  * To be done: 
    *Player Count accross all entities, Passing lobby owner to next player vs. deleting lobby, Channel Error handling, Lobby Error handling, Login Error handling

### 0.8.0
* Started DB integration
  * Servers, Channels, Lobbies, Players tables created.
  * Server List, Account Creation, Account Deletion, Login, Channel List, Channel Join, Lobby List working.
  * To be done: 
    * Lobby Join, Lobby Creation, Lobby Leave, Lobby Kick, Map Select, Character Select, Player Count accross all entities, Passing lobby owner to next player vs. deleting lobby, Channel Error handling, Lobby Error handling, Login Error handling
  
### 0.7.3
* Implemented error handling for duplicate Lobby name

### 0.7.2
* Implemented error handling for Account Creation/Deletion and Login

### 0.7.1
* Added session player_id tracking
  * Fixes incorrect Map Select behavior on Lobbies other than Lobby at index 1
* Fixed incorrect player password length parsing for account creation/deletion and login
* (regression fix) Added back packet reply for account deletion request

### 0.7.0
* Overhaul of code for future DB integration
* NETROOM Logic (in work)
  * Implemented Player Ready (Game Ready) logic 
    * We now reply to 0x7d9 Game/Player Ready request packets with a 0xbc1 packet. 
	* We are able to press the "O" button again to toggle player ready status. While "Ready", the client is unresponsive to all button presses except "O".

### 0.6.8
* NETROOM Logic (in work)
  * Implemented rudementary Game Start logic (most likely incorrect)
    * We now reply to 0x7d8 Game Start request packets with a 0xbc0 packet. 
	* The 0xbc0 packet causes a copy of 0x10 bytes of its payload to memory location 0x39ed6c. It is unclear what data is required at this memory location but it seems to be used in a validation check later on. To be investigated...  

### 0.6.7
* NETROOM Logic (in work)
  * Implemented Player Kick logic
    * We now reply to 0x7db Player Kick packets with a 0xbc3 ACK and a follow-up lobby info update that removes the player at the index number parsed from 0x7db.
  * Implemented Lobby Leave logic
    * We now reply to 0x7da Lobby Leave packets with a 0xbc2 ACK and remove the player from the Lobby (server side) - no follow-up packet necessary. 
	
### 0.6.6
* NETROOM Logic (in work)
  * Implemented Map Select logic
    * We now reply to 0x7de Map Select packets with a 0xbc6 ACK and a follow-up lobby info update that sets the lobby's Map field to match the requested map index number parsed from 0x7de.
  * Discovered and Implemented Character Select logic 
    * Client first sends 0x7dc packet with player ID.
	* We reply with a 0xbc4 packet which allows the client to transition into sending a 0x7dd packet. The required contents of the 0x20 of data that is copied from the payload of the 0xbc4 reply to memory location 0x39ed7c remains unclear - for now we are sending the requested player's information. The 0x7dd packet contains the select character index in its payload.
	* We now reply to 0x7dd Character Select packets with a 0xbc5 ACK and a follow-up lobby info update that sets the active player's character field to match the requested character index number parsed from 0x7dd. 
  
### 0.6.5
* NETROOM Logic (in work)
  * Discovered value range for E,D,C,B,A,S RANK values.
  * Discovered position of Map Select Index and most other 0x03ee fields  

### 0.6.4
* NETROOM Logic (in work)
  * Established preliminary partial packet structure and fields for 0x03ee

### 0.6.3
* LOBBY JOIN ACK PACKET (complete)
* LOBBY CREATE ACK PACKET (complete)
* NETROOM Logic (in work)

### 0.6.2
* LOBBY LIST PACKET (complete)
* LOBBY SELECT ACK PACKET (in work)
  
### 0.6.1
* LOBBY LIST PACKET (in work)
* Done: Lobby Name, Current Players, Max Players, Lobby Status
  * To Do: Private/Public flag , Lobby Password


### 0.6.0
* DNAS BYPASS (complete)
  * Bypass only works once. Must reset each time for bypass to work. Otherwise, hangs on DNAS screen.
* SERVER LIST PACKET (complete)
* ACCOUNT CREATE ACK PACKET (partially working)
  * Error logic missing
* ACCOUNT DELETE ACK PACKET (partially working)
  * Error logic missing
  * Despite triggering a succesful state change, the client continuously sends the deletion packet after ack. (something is wrong)
* LOGIN ACK PACKET
* CHANNEL LIST PACKET (complete)
* CHANNEL SELECT ACK PACKET (complete)
* LOBBY LIST PACKET (in work)
  * Done: Lobby Name, Current Players, Max Players
  * To Do: Private/Public flag , Lobby Password and Lobby Status (Empty, In Queue, Started) 
