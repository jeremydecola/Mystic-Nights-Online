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

## *PROGRESS*
### 0.8.1
* Continued DB integration
  * Servers, Channels, Lobbies, Players tables, Lobby Join, Lobby Creation, Lobby Leave created.
  * Server List, Account Creation, Account Deletion, Login, Channel List, Channel Join, Lobby List, Lobby Kick, Map Select, Character Select working
  * To be done: 
    *Player Count accross all entities, Passing lobby owner to next player vs. deleting lobby, Channel Error handling, Lobby Error handling, Login Error handling

### 0.8.0
* Started DB integration
  * Servers, Channels, Lobbies, Players tables created.
  * Server List, Account Creation, Account Deletion, Login, Channel List, Channel Join, Lobby List working
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
