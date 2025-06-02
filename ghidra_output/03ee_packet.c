//0x03ee packet

//PACKET ID 2 bytes ee03
//LENGTH 2 bytes XXXX
//LEADER Lobby Position 1 byte (00/01/02/03) - compared to Ram0025f4ec (client Lobby Position), 
//			 if clientLobbyPosition == leaderLobbyPosition then you have access to map select, kick player and game start (instead of game ready)

void FUN_0021e6c0(undefined4 *param_1,undefined8 param_2,undefined8 param_3,undefined8 param_4,
                 undefined8 param_5,undefined8 param_6,undefined8 param_7,undefined8 param_8)

{
  int iVar1;
  undefined8 uVar2;
  undefined8 uVar3;
  undefined8 uVar4;
  int iVar5;
  undefined4 *puVar6;
  int iVar7;
  
  uRam0039ecdc = 1;
  uRam0039ecda = (undefined2)*param_1; //sets leader lobby position
  FUN_0011f4b0((undefined1 *)0x39ecde,0x25d4d0,(long)(int)(param_1 + 1),param_4,param_5,param_6,
               param_7,param_8);
  FUN_0011f4b0((undefined1 *)0x39ecef,0x25d4d0,(long)((int)param_1 + 0x15),param_4,param_5,param_6,
               param_7,param_8);
  uVar4 = 0x70;
  FUN_0011cd30((undefined8 *)0x39ecfc,0,0x70,param_4,param_5);
  iVar7 = 0;
  iVar5 = 0x39eca0;
  puVar6 = param_1;
  //fill buffer for up to 4 players
  do {
    FUN_0011fab8((ulong *)(iVar5 + 0x5c),(undefined1 (*) [16])(puVar6 + 9));  //Handles Player ID - 0x39eca0 + 0x5c -> 0x39ecfc 
    iVar7 = iVar7 + 1;
    *(undefined1 *)(iVar5 + 0x69) = *(undefined1 *)((int)puVar6 + 0x31); //Handles Character Select Byte - 0x39eca0 + 0x69 -> 0x39ed09
    *(undefined1 *)(iVar5 + 0x6a) = *(undefined1 *)((int)puVar6 + 0x32); //Handles Status Byte - 0x39eca0 + 0x6a -> 0x39ed0a  
    *(undefined4 *)(iVar5 + 0x6c) = puVar6[0xd]; // UNKNOWN 4 bytes - 0x39eca0 + 0x6c -> 0x39ed0c
    *(undefined4 *)(iVar5 + 0x70) = puVar6[0xe]; // UNKNOWN 4 bytes - 0x39eca0 + 0x70 -> 0x39ed10
    *(undefined4 *)(iVar5 + 0x74) = puVar6[0xf]; //UNKNOWN 4 bytes - 0x39eca0 + 0x74 -> 0x39ed14 
    puVar6 = puVar6 + 7;
    iVar5 = iVar5 + 0x1c;
  } while (iVar7 < 4);
  iVar5 = 0;
  iVar7 = 0x39eca0;
  uRam0039ecd4 = (undefined2)param_1[0x25];// 0039ecd4 Seems to be tied to the map select logic. Value is initialized to 1 in init of NETROOM.
  uRam0039ecd8 = (undefined2)param_1[0x26];// Value is initialized to 1 in init of NETROOM.
  //Somehow associated to "모든 플레이어들이 아직 대기실로 들어오지 않았습니다." when 0039ecd8 = 4. Some other condition is also met when the value is set to 4... to investigate
  //Loop through each player
  do {
    uVar2 = FUN_00121480(0x399ade); //set uVar2 = localPlayerID (0x399ade holds the client player's ID)
    uVar3 = FUN_00121480((long)(iVar7 + 0x5c)); //set uVar3 = currentPlayerID
    iVar1 = FUN_0011f970(uVar2,(undefined1 (*) [16])uVar3,uVar4,param_4); //iVar1 = (localPlayerID == currentPlayerID)
    if (iVar1 == 0) {
      iRam0025f4ec = iVar5; //if true, set Ram0025f4ec to the current Lobby Position (marking the lobby position of the client player)
    }
    iVar5 = iVar5 + 1; //check next player
    iVar7 = iVar7 + 0x1c; //+28 bytes to point to the next player info block
  } while (iVar5 < 4);
  return;
}
