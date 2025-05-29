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
### 0.6.3
* DNAS BYPASS (complete)
  *Bypass only works once. Must reset each time for bypass to work. Otherwise, hangs on DNAS screen.
* SERVER LIST PACKET (complete)
* ACCOUNT CREATE ACK PACKET (partially working)
  *Error logic missing
* ACCOUNT DELETE ACK PACKET (partially working)
  *Error logic missing
  *Despite triggering a succesful state change, the client continuously sends the deletion packet after ack. (something is wrong)
* LOGIN ACK PACKET
* CHANNEL LIST PACKET (complete)
* CHANNEL SELECT ACK PACKET (complete)
* LOBBY LIST PACKET (complete)
* LOBBY JOIN ACK PACKET (complete)
* LOBBY CREATE ACK PACKET (complete)
* NETROOM Logic (in work)

### 0.6.2
* DNAS BYPASS (complete)
  *Bypass only works once. Must reset each time for bypass to work. Otherwise, hangs on DNAS screen.
* SERVER LIST PACKET (complete)
* ACCOUNT CREATE ACK PACKET (partially working)
  *Error logic missing
* ACCOUNT DELETE ACK PACKET (partially working)
  *Error logic missing
  *Despite triggering a succesful state change, the client continuously sends the deletion packet after ack. (something is wrong)
* LOGIN ACK PACKET
* CHANNEL LIST PACKET (complete)
* CHANNEL SELECT ACK PACKET (complete)
* LOBBY LIST PACKET (complete)
* LOBBY SELECT ACK PACKET (in work)
  
### 0.6.1
* DNAS BYPASS (complete)
  *Bypass only works once. Must reset each time for bypass to work. Otherwise, hangs on DNAS screen.
* SERVER LIST PACKET (complete)
* ACCOUNT CREATE ACK PACKET (partially working)
  *Error logic missing
* ACCOUNT DELETE ACK PACKET (partially working)
  *Error logic missing
  *Despite triggering a succesful state change, the client continuously sends the deletion packet after ack. (something is wrong)
* LOGIN ACK PACKET
* CHANNEL LIST PACKET (complete)
* CHANNEL SELECT ACK PACKET (complete)
* LOBBY LIST PACKET (in work)
  *Done: Lobby Name, Current Players, Max Players, Lobby Status
  *To Do: Private/Public flag , Lobby Password


### 0.6.0
* DNAS BYPASS (complete)
  *Bypass only works once. Must reset each time for bypass to work. Otherwise, hangs on DNAS screen.
* SERVER LIST PACKET (complete)
* ACCOUNT CREATE ACK PACKET (partially working)
  *Error logic missing
* ACCOUNT DELETE ACK PACKET (partially working)
  *Error logic missing
  *Despite triggering a succesful state change, the client continuously sends the deletion packet after ack. (something is wrong)
* LOGIN ACK PACKET
* CHANNEL LIST PACKET (complete)
* CHANNEL SELECT ACK PACKET (complete)
* LOBBY LIST PACKET (in work)
  *Done: Lobby Name, Current Players, Max Players
  *To Do: Private/Public flag , Lobby Password and Lobby Status (Empty, In Queue, Started) 
