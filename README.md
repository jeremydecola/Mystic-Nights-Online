# Mystic Nights (PS2) Multiplayer Private Server

Mystic Nights (미스틱 나이츠) is an obscure Korean-Exclusive survival horror Playstation 2 title.
It was developed by N-Log Corporation and published by Sony Computer Entertainment of Korea in 2005.
Although a North-American release was planned, Sony mysteriously pulled the plug.

This project's goal is to revive the Online Multiplayer functionality of the game by reverse-engineering the expected packet replies required from the server. This is achieved through examination of the client side packet parsing code through Ghidra decompilation (MIPS 5900 to C), analysis of values at target memory addresses in EE and IOP RAM (using PCSX2 Debugger) during different game states and some careful packet fuzzing.

In 2019, I released an English translation for Mystic Nights. It can be found here. 
https://github.com/jeremydecola/Mystic-Nights-Translation/tree/master

## Prerequisites

TBD

## Instructions

TBD

## *PROGRESS
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
