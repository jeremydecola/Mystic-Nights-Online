I have decompiled C code from a Playstation 2 game client. The full decompilation can be found in the file mysticnights_elf.c
I am trying to emulate the server side commmunication purely by reverse engineering how the client parses and handles different packets.
Currently, I am in FUN_00156fe0 called from state machine function FUN_0012e480 when sRam002c4050 = 0x11.
FUN_00156fe0 handles the lobby room logic. Populates the lobby name and selected map and also a list of all players in the lobby (up to 4), with relevant data (player ID, selected character, their Rank, their status (ready/not ready)). There are menus accessible from this UI that trigger interactible pop-ups. One such menu allows the selection of the map.
There are 5 maps (01,02,03,04,05) which can be set through a buffer write to 39ecd3 from the injection of a 0x03ee server packet. When you select a map from the client UI (ex: map 5), the client sends a map select request 0x7de packet to the server (de07040005000000). The 05000000 is little endian 5 (4 bytes) and is parsed and then the server. The server must first ACK the map select request with a 0xbc6 packet (c60b0600010000000100) and then it can update the UI accordingly by sending a follow-up 0x03ee packet with map select flag set to 5. 
I am trying to achieve a similar result with character select request packet but the behavior is a little bit different:
The character select request 0x7dc packet is sent after I select a character from the UI menu. There are eight characters (01,02,03,04,05,06,07,08). 
It loops and keeps sending packet dc070d0042414241000000000000000000 with the UI becoming unresponsive until a valid packet is received and parsed by function FUN_00219310.
The selected character can also be updated through a 0x03ee packet by setting the player's selected character field to one of these 8 values.
It seems that, similarly to the map select request, we must first ACK the request with a 0xbc5 packet (c50b0600010000000100) - I am not sure about this though...
The problem is that the 0x7dc (unlike the 0x7de packet) doesn't specify the selected character chosen in the UI. That means, I don't know what to send in the follow-up 0x03ee packet.
The packet is always dc070d0042414241000000000000000000 no matter which character I chose. Note that the presence of "42414241" is due to my player ID being "BABA".
This is just the ASCII or EUC-KR encoding of "BABA". I am trying to understand if something was perhaps not initialized properly or if I'm missing a step in the handshake.
Let's analyze what is happening in FUN_00156fe0. 

FUN_00219310 is the function that parses incoming packets from the server.
Before AND After I select a character from the character sub-menu:
sRam002c4056 is = 1
sRam0025f318 is = 0
sRam0025f31c is = 0