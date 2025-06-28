c00b4c00010000004343434300000000000000000000000001230000010000000100
xPIDxLENxFLAG___xLOCAL40C_0x10_BYTES____________x3f8____x3f4____xMAP

sendhex c00b4c00010000004343434300000000000000000000000001230000010000000100
43434343000000000000000000000000
16 bytes =

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
			uRam0039ecba = param_3; //(short)local_3f8 (2 bytes?)
			uRam0039ecbc = param_4; //(short)local_3f4 (2 bytes?)
			sRam0039ecd6 = param_5; //(short)local_3f0 (this is definitely the MAP ID!)
			if (sRam0039ecd4 != 5) { //if MAP ID is not RANDOM (between 1 and 4) then overwrite MAP ID with the one from UI. 
			sRam0039ecd6 = sRam0039ecd4;
			}
		}
		uRam0039ecc6 = 2;
		return puVar1;
		}