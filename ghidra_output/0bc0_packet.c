c00b4c00010000004343434300000000000000000000000001230000010000000100
xPIDxLENxFLAG___xLOCAL40C_0x10_BYTES____________x3f8____x3f4____xMAP

sendhex c00b4c00030303030800000000000000000000000000000001000000010000000100
		c00b4c00010000000800000300000000000000000000000001000000010000000100

void entry(void)

  uVar2 = 0x100000;
  uVar3 = 0x25f580;
  uVar4 = 0x100220;
  
  FUN_0012e480((long)iRam0025f580,0x25f584,uVar2,uVar3,uVar4,uVar5,uVar6,lVar7);

  param_2 is 0x25f584
  param_3 is 0x100000
  param_4 is 0x25f580
  param_5 is 0x100220

      else if (local_410[0] == 0xbc0) {
        if ((char)local_40c == '\x01') {
          param_3 = (ulong)local_3f8;
          param_4 = (long)local_3f4;
          param_5 = (long)local_3f0;
          FUN_0021e5f0(1,local_408,(short)local_3f8,(short)local_3f4,(short)local_3f0);
        }
        else {
          FUN_00218b40((long)local_40c._1_1_,10,param_3,param_4,param_5);
        }
      }
	  
	  undefined8 *FUN_0021e5f0(long param_1,undefined8 *param_2,undefined2 param_3,undefined2 param_4,short param_5)

		{
		undefined8 *puVar1;
		
		if (param_1 == 0) { //param_1 = 1 so ignore this conditional...
			uRam0039ecb8 = 0;
			puVar1 = FUN_0011cb78((undefined8 *)0x39ed6c,(undefined8 *)0x0,0x10);
		}
		else {
			uRam0039ecb8 = 2;
			puVar1 = FUN_0011cb78((undefined8 *)0x39ed6c,param_2,0x10);
			uRam0039ecba = param_3; //(short)local_3f8 (this is definitely the player index of the IMPOSTER/VAMPIRE)
			uRam0039ecbc = param_4; //(short)local_3f4 (2 bytes? - don't know what this does)
			sRam0039ecd6 = param_5; //(short)local_3f0 (this is definitely the MAP ID!)
			if (sRam0039ecd4 != 5) { //if MAP ID is not RANDOM (between 1 and 4) then overwrite MAP ID with the one from UI. 
			sRam0039ecd6 = sRam0039ecd4;
			}
		}
		uRam0039ecc6 = 2;
		return puVar1;
		}
		
		
undefined4 FUN_0021e8c0(int param_1,int param_2)

{
  undefined4 uVar1;
  
  if ((*(char *)(param_1 * 0x1c + 0x39ed09) == '\0') ||
     (*(int *)(param_1 * 4 + 0x39ed6c) != param_2)) {
    uVar1 = 0;
  }
  else {
    uVar1 = 1;
  }
  return uVar1;
}

FUN_0021e8c0 is the only HARDCODED OBVIOUS function where 0x39ed09 which we set from the 16 bytes in param_2 of game start ack is used. I doubt that we only need to pass the player_id. I actually doubt we need to pass the player_id at all... That was just a guess on my part. the player_id is only a maximum of 8 bytes, why would it require 16 bytes then? that's silly.
I set a breakpoint in pcsx2 debug and we see register values :
a0 = 0, a1 = 8 

here is the MIPS assembly too:

                             **************************************************************
                             *                          FUNCTION                          *
                             **************************************************************
                             undefined4 __stdcall FUN_0021e8c0(int param_1, int param
                               assume gp = 0x267170
             undefined4        v0_lo:4        <RETURN>
             int               a0_lo:4        param_1
             int               a1_lo:4        param_2
                             FUN_0021e8c0                                    XREF[1]:     FUN_0013da90:0013e714(c)  
        0021e8c0 c0 10 04 00     sll        v0,param_1,0x3
             assume gp = <UNKNOWN>
        0021e8c4 23 18 44 00     subu       v1,v0,param_1
        0021e8c8 3a 00 02 3c     lui        v0,0x3a
        0021e8cc 80 18 03 00     sll        v1,v1,0x2
        0021e8d0 09 ed 42 24     addiu      v0,v0,-0x12f7
        0021e8d4 21 10 43 00     addu       v0,v0,v1
        0021e8d8 00 00 42 80     lb         v0,0x0(v0)
        0021e8dc 2b 10 02 00     sltu       v0,zero,v0
        0021e8e0 0a 00 40 10     beq        v0,zero,LAB_0021e90c
        0021e8e4 00 00 00 00     _nop
        0021e8e8 3a 00 02 3c     lui        v0,0x3a
        0021e8ec 80 18 04 00     sll        v1,param_1,0x2
        0021e8f0 6c ed 42 24     addiu      v0,v0,-0x1294
        0021e8f4 21 10 43 00     addu       v0,v0,v1
        0021e8f8 00 00 42 8c     lw         v0,0x0(v0)
        0021e8fc 03 00 45 14     bne        v0,param_2,LAB_0021e90c
        0021e900 00 00 00 00     _nop
        0021e904 02 00 00 10     b          LAB_0021e910
        0021e908 01 00 02 24     _li        v0,0x1
                             LAB_0021e90c                                    XREF[2]:     0021e8e0(j), 0021e8fc(j)  
        0021e90c 2d 10 00 00     move       v0,zero
                             LAB_0021e910                                    XREF[1]:     0021e904(j)  
        0021e910 08 00 e0 03     jr         ra
        0021e914 00 00 00 00     _nop
        0021e918 00 00 00 00     nop
        0021e91c 00 00 00 00     nop

i overwrote 0x39ed6c with an 8 and i got rendering!
It seems that the value can be between 0 and 0b (11).
There are 16 bytes total for param_2 -> 4 bytes for each player, 1st byte of each 4 bytes should be a number between 0 and 11 which indicates the starting position of that player. 