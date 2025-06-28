
Currently my server is receiving this packet from the game client:
[RECV] From ('211.233.10.22', 3658): f0030d0043434343000000000000000000 (pkt_id=03f0, 13 bytes)
[WARN] Unhandled packet ID: 0x03f0 from ('211.233.10.22', 3658)

FUN_00208480 sends packet 0x03f0
which is called by FUN_0020e370

State machine variable is sRam002c4050 = 3

which puts us in case 3 , in function FUN_00159af0
    case 3:
      FUN_00159af0(lVar1,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
      break;
	  

this string is what i currently see on screen:
"다른 플레이어들을 기다리고 있습니다. 잠시만 대기해 주십시오."
"Waiting for other players. Please wait a moment."
s_HANGUL#._._0025b090

this string is called from void FUN_0020e100 inside our function FUN_00159af0. How do i progress past this... I am just stuck on this screen. 

Checked in PCSX2 Debug EERAM Memory Viewer
sRam002c4056 = 01
sRam002c4054 = FF
sRam002c4058 = 00
sRam0025f4e0 = 00
sRam0025f464 = 00
sRam0025f4e4 = 00
cRam0025f454 = 01
cRam002a330e = 00
cRam002a34b5 = 00
cRam002a330c = 01
iRam0025f338 = 00
iRam0025f33c = 00
cRam0025f370 = 00
uRam002c4052 = 11
sRam0025f374 = 00
sRam002a3310 = FFFF
cRam002a330d = 00
cRam002a3304 = 00
iRam0025f21c = D0 (0025f21d and 0025f21e are 94 and 26)
sRam0025f484 = 00
cRam002c4070 = 00 (002c4071 is 01)
sRam002a2c8c = 00
iRam002a021c = D0 (0025f21d and 0025f21e are 94 and 26)
sRam0025f330 = 00
iRam0025f220 = 00
uRam0039eb58 = 00
sRam002a34bc = 00
iRam0025f4ec = 00
uRam002a0000 = 00
uRam002a0008 = 00
uRam002a0200 = 00
fRam002a0010 = D8 0F 49 40

void FUN_00159af0(undefined8 param_1,long param_2,long param_3,long param_4,ulong param_5,
                 ulong param_6,long param_7,long param_8)

{
  int iVar1;
  bool bVar2;
  short sVar3;
  ushort uVar4;
  undefined8 uVar5;
  long lVar6;
  undefined8 uVar7;
  long lVar8;
  int iVar9;
  int iVar10;
  ulong auStack_d0 [26];
  
  if (sRam002c4056 == 2) {
    FUN_00127a20(0,0,0,1);
    FUN_00127a20(0,1,0,1);
    if (sRam002c4058 != 1) {
      FUN_00162320(0);
      FUN_00152d90();
      FUN_0013e8b0();
      if (sRam002c4054 == 3) {
        FUN_0012e260(0);
      }
      else {
        FUN_0012e260(1);
        if (cRam0025f370 == '\0') {
          iVar9 = 0;
          iVar10 = 0x2694d0;
          do {
            FUN_001fce90(iVar10);
            iVar9 = iVar9 + 1;
            iVar10 = iVar10 + 0x430;
          } while (iVar9 < 4);
        }
      }
    }
    uRam002c4052 = sRam002c4050;
    sRam002c4050 = sRam002c4054;
    sRam002c4054 = 0xffff;
    sRam002c4056 = 0;
    return;
  }
  if (sRam002c4056 != 1) {
    if (sRam002c4056 != 0) {
      return;
    }
    FUN_00152d70();
    FUN_0013e9f0();
    FUN_00131ec0();
    FUN_001325b0(1,2,param_3,param_4,param_5,param_6,param_7,param_8);
    if (cRam0025f454 != '\0') {
      iRam0025f21c = iRam0025f4ec * 0x430 + 0x2694d0;
    }
    lVar8 = (long)iRam0025f21c;
    uVar7 = 0x2a0000;
    iRam002a021c = iRam0025f21c;
    uRam002a0000 = *(undefined4 *)(iRam0025f21c + 0x3a0);
    uRam002a0008 = *(undefined4 *)(iRam0025f21c + 0x3a8);
    uRam002a0200 = *(undefined4 *)(iRam0025f21c + 0x5c);
    fRam002a0010 = *(float *)(iRam0025f21c + 0x3b4);
    if (0.0 < fRam002a0010) {
      fRam002a0010 = fRam002a0010 - 3.141592;
    }
    else {
      fRam002a0010 = fRam002a0010 + 3.141592;
    }
    uVar5 = 0x2a0000;
    FUN_00168600((float *)0x2a0000);
    if (sRam0025f374 != 0) {
      FUN_0016b870(uVar5,uVar7,lVar8,param_4);
    }
    FUN_001ed0e0(uVar5,uVar7,lVar8,param_4,param_5,param_6,param_7,param_8);
    iVar9 = 0x2a0000;
    iVar10 = 0;
    do {
      iVar1 = *(int *)(iVar9 + 0x34d0);
      if ((((long)iVar1 != 0) && (sVar3 = *(short *)(*(int *)(iVar1 + 0x414) + 10), 0 < sVar3)) &&
         (*(char *)(sVar3 + 0x2da800) != '\0')) {
        FUN_0012db00((long)iVar1);
      }
      iVar10 = iVar10 + 1;
      iVar9 = iVar9 + 4;
    } while (iVar10 < 200);
    lVar6 = (long)iRam0025f21c;
    uVar7 = 0;
    FUN_001fbe10(iRam0025f21c,0);
    sRam002c4056 = 1;
    FUN_0014de10(lVar6,uVar7,lVar8,param_4,param_5);
    FUN_00152e70(iRam0025f21c,uVar7,lVar8,param_4,param_5);
    if (cRam0025f454 != '\0') {
      FUN_0020d830();
      FUN_0011cd30((undefined8 *)0x2a52b0,0,0x14,param_4,param_5);
      sRam0025f330 = (short)iRam0025f4ec;
      FUN_0020e370();
      sRam0025f464 = 0;
      sRam0025f4e4 = 0;
      sRam0025f4e0 = 0;
      FUN_00128530((long *)0x39d310);
    }
    FUN_0015c2a0(0x40400000,'\x01',0);
    FUN_00162320((int)sRam002a34bc);
    FUN_001626b0(*(int **)(*(int *)(iRam0025f21c + 0x5c) + 0x48));
    iRam0025f338 = 0;
    iRam0025f33c = 0;
    return;
  }
  if (cRam0025f454 == '\0') {
    uVar4 = FUN_001279d0(0,8);
    if ((((uVar4 != 0) && (uVar4 = FUN_001279d0(0,2), uVar4 != 0)) &&
        ((uVar4 = FUN_001279d0(0,4), uVar4 != 0 &&
         ((uVar4 = FUN_001279d0(0,1), uVar4 != 0 && (uVar4 = FUN_001279d0(0,0x800), uVar4 != 0))))))
       && (uVar4 = FUN_001279d0(0,0x100), uVar4 != 0)) {
      sRam002c4058 = 0;
      sRam002c4056 = 2;
      sRam0025f374 = 0;
      FUN_0014c160();
      FUN_0014bf40();
      sRam002c4054 = 0;
      return;
    }
    if (cRam002a330e == '\x01') {
      FUN_0014d080(0);
      iVar9 = FUN_0014b240();
      if ((iVar9 == 0x67) || (iVar9 == 0x66)) {
        FUN_0015c2a0(0x40400000,'\0',0);
        cRam002a330e = '\x02';
        FUN_001278b0(0,0x20);
        FUN_001278b0(0,0x40);
      }
    }
    lVar8 = 0x2a3495;
    param_2 = 0x250938;
    iVar9 = FUN_0011f970(0x2a3495,(undefined1 (*) [16])&DAT_00250938,param_3,param_4);
    if (iVar9 != 0) {
      FUN_0013c4e0(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    }
    if (cRam002a34b5 != '\0') {
      FUN_0013c580(lVar8,param_2,param_3,param_4);
    }
    goto LAB_00159f40;
  }
  lVar8 = 0;
  FUN_0014d080(0);
  bVar2 = FUN_0020e310();
  if (bVar2) {
    cRam002a330c = '\x01';
    FUN_00208b40(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    bVar2 = FUN_0020e300();
    if (bVar2) {
      cRam002a330c = '\0';
      FUN_0020e060();
    }
  }
  if ((sRam0025f464 == 0) && (sVar3 = FUN_0014ac40(), sVar3 == 0)) {
    param_2 = 3000;
    lVar8 = 0x39d310;
    param_3 = 1;
    iVar9 = FUN_001284a0((ulong *)0x39d310,3000,1);
    if ((iVar9 != 0) && (iVar9 = FUN_0020ac80(), iVar9 < 1)) {
      sRam0025f464 = 1;
      FUN_0020c860();
      lVar8 = 2;
      param_2 = 0x250e20;
      FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#._._00250e20);
      if (cRam002a330c == '\0') {
        iVar10 = 0;
        iVar9 = 0x2694d0;
        do {
          lVar6 = (long)iVar9;
          if (-1 < **(short **)(iVar9 + 0x414)) {
            param_2 = 1;
            FUN_001f6d90(iVar9,1,param_3,(int)param_4);
            lVar8 = lVar6;
          }
          iVar10 = iVar10 + 1;
          iVar9 = iVar9 + 0x430;
        } while (iVar10 < 4);
        FUN_0020d390();
      }
    }
  }
  if (((sRam0025f4e4 == 0) && (sVar3 = FUN_0014ac40(), sVar3 == 0)) &&
     (iVar9 = FUN_002198d0(), iVar9 < 1)) {
    sRam0025f4e4 = 1;
    FUN_0020c860();
    if (iVar9 == 0) {
      lVar8 = 2;
      param_2 = 0x250e50;
      FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#._._00250e50);
    }
    else {
      lVar8 = 2;
      param_2 = 0x250e80;
      FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#_00250e80);
    }
    if (cRam002a330c == '\0') {
      iVar9 = 0;
      iVar10 = 0x2694d0;
      do {
        lVar6 = (long)iVar10;
        if (-1 < **(short **)(iVar10 + 0x414)) {
          param_2 = 1;
          FUN_001f6d90(iVar10,1,param_3,(int)param_4);
          lVar8 = lVar6;
        }
        iVar9 = iVar9 + 1;
        iVar10 = iVar10 + 0x430;
      } while (iVar9 < 4);
      FUN_0020d390();
    }
  }
  if ((cRam002a330c == '\0') && (sVar3 = FUN_0014ac40(), sVar3 == 0)) {
    lVar8 = 0;
    param_2 = 0x800;
    uVar4 = FUN_001279d0(0,0x800);
    if (uVar4 != 0) {
      FUN_0020c860();
      lVar8 = 1;
      param_2 = 0x250da0;
      FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#?_00250da0);
      cRam002a330e = '\x01';
      iRam0025f338 = 1;
    }
  }
  sVar3 = FUN_0014ac40();
  if (sVar3 != 0) {
    lVar8 = (long)(int)auStack_d0;
    FUN_0014ac00(auStack_d0,param_2,param_3,param_4,param_5);
    iVar9 = FUN_0014b240();
    if (iVar9 == 0x65) {
      iVar9 = FUN_0011f970(0x250eb0,(undefined1 (*) [16])auStack_d0,param_3,param_4);
      if (((iVar9 != 0) &&
          (iVar9 = FUN_0011f970(0x250f00,(undefined1 (*) [16])auStack_d0,param_3,param_4),
          iVar9 != 0)) &&
         (iVar9 = FUN_0011f970(0x250f50,(undefined1 (*) [16])auStack_d0,param_3,param_4), iVar9 != 0
         )) {
        param_2 = (long)(int)auStack_d0;
        lVar8 = 0x250fa0;
        iVar9 = FUN_0011f970(0x250fa0,(undefined1 (*) [16])auStack_d0,param_3,param_4);
        if (iVar9 != 0) goto LAB_00159dac;
      }
      param_2 = 1000;
      lVar8 = 0x39eb50;
      param_3 = 1;
      FUN_001284a0((ulong *)0x39eb50,1000,1);
      if (4 < uRam0039eb58) {
        uVar5 = 0x250938;
        FUN_0014b3c0(0,(undefined1 (*) [16])&DAT_00250938);
        uVar7 = 0;
        FUN_0015c310(0);
        FUN_0020b9f0(uVar7,uVar5,param_3,param_4,param_5,param_6,param_7,param_8);
        iRam0025f33c = 1;
        FUN_0015c2a0(0x40400000,'\0',0);
        cRam002a330e = 2;
        return;
      }
    }
    else if (iVar9 == 0x66) {
      iVar9 = FUN_0011f970(0x250da0,(undefined1 (*) [16])auStack_d0,param_3,param_4);
      if (iVar9 == 0) {
        if (*(char *)(*(int *)(iRam0025f21c + 0x414) + 0x858) == '\0') {
          cRam002a330e = '\0';
        }
        else {
          FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#L3_._00250ff0);
        }
      }
      else {
        iVar9 = FUN_0011f970(0x250ff0,(undefined1 (*) [16])auStack_d0,param_3,param_4);
        if (iVar9 != 0) {
          iVar9 = FUN_0011f970(0x250e20,(undefined1 (*) [16])auStack_d0,param_3,param_4);
          if (iVar9 == 0) {
            sRam0025f4e0 = 1;
            cRam002a3304 = 0;
            return;
          }
          iVar9 = FUN_0011f970(0x250e50,(undefined1 (*) [16])auStack_d0,param_3,param_4);
          if (iVar9 == 0) {
            sRam0025f4e0 = 1;
            cRam002a3304 = 0;
            return;
          }
          lVar8 = (long)(int)auStack_d0;
          uVar7 = 0x250e80;
          iVar9 = FUN_0011f970(0x250e80,(undefined1 (*) [16])auStack_d0,param_3,param_4);
          if (iVar9 == 0) {
            sRam0025f4e0 = 1;
            cRam002a3304 = 0;
            return;
          }
          FUN_0020b9f0(uVar7,lVar8,param_3,param_4,param_5,param_6,param_7,param_8);
          iRam0025f33c = 1;
          FUN_0015c2a0(0x40400000,'\0',0);
          cRam002a330e = 2;
          return;
        }
        cRam002a330e = '\x03';
      }
      FUN_001278b0(0,0x20);
      lVar8 = 0;
      param_2 = 0x40;
      FUN_001278b0(0,0x40);
    }
    else if (iVar9 == 0x67) {
      param_2 = (long)(int)auStack_d0;
      lVar8 = 0x250da0;
      iVar9 = FUN_0011f970(0x250da0,(undefined1 (*) [16])auStack_d0,param_3,param_4);
      if (iVar9 == 0) {
        FUN_0015c2a0(0x40400000,'\0',0);
        cRam002a330e = '\x02';
        FUN_001278b0(0,0x20);
        param_2 = 0x40;
        FUN_001278b0(0,0x40);
        FUN_00207e70((int)*(char *)(*(int *)(iRam0025f21c + 0x414) + 0x858),param_2,param_3,param_4,
                     param_5,param_6,param_7,param_8);
        lVar8 = (long)iRam0025f220;
        cRam002a330c = '\x01';
        iRam0025f220 = iRam0025f220 + 1;
      }
    }
  }
LAB_00159dac:
  if (cRam002a330e == '\x03') {
    lVar8 = 0;
    param_2 = 0x200;
    uVar4 = FUN_00127950(0,0x200);
    if (uVar4 != 0) {
      param_3 = 0;
      iVar9 = sRam0025f330 + 1;
      sRam0025f330 = (short)iVar9;
      do {
        sVar3 = (short)iVar9;
        if (3 < sVar3) {
          sRam0025f330 = 0;
          sVar3 = 0;
        }
        if (-1 < **(short **)((sVar3 * 0x42 + (int)sVar3) * 0x10 + 0x2698e4)) break;
        param_3 = (long)((int)param_3 + 1);
        iVar9 = sVar3 + 1;
        sRam0025f330 = (short)iVar9;
        sVar3 = sRam0025f330;
      } while (param_3 < 4);
      param_2 = (long)sVar3;
      iRam002a021c = (sVar3 * 0x42 + (int)sVar3) * 0x10;
      lVar8 = (long)iRam002a021c;
      iRam002a021c = iRam002a021c + 0x2694d0;
    }
  }
LAB_00159f40:
  if ((sRam0025f4e0 == 0) ||
     (iVar9 = FUN_00219b90(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8),
     iVar9 == 0)) {
    if (cRam002a330c == '\0') {
      if ((((cRam0025f454 != '\0') && (sRam0025f464 == 0)) && (sRam0025f4e4 == 0)) &&
         (FUN_00208cc0(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8),
         sRam0025f484 == 0)) {
        iVar9 = 0;
        iVar10 = 0x2694d0;
        do {
          FUN_001fb4e0(iVar10,param_2,param_3,param_4);
          iVar9 = iVar9 + 1;
          iVar10 = iVar10 + 0x430;
        } while (iVar9 < 4);
        iVar9 = FUN_0020d030();
        if (iVar9 != 0) {
          iVar9 = 0;
          iVar10 = 0x2694d0;
          do {
            if (-1 < **(short **)(iVar10 + 0x414)) {
              param_2 = 1;
              FUN_001f6d90(iVar10,1,param_3,(int)param_4);
            }
            iVar9 = iVar9 + 1;
            iVar10 = iVar10 + 0x430;
          } while (iVar9 < 4);
        }
      }
      FUN_001fb670(iRam0025f21c,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
      lVar8 = (long)iRam0025f338;
      FUN_001529f0(lVar8,param_2,param_3,param_4,param_5);
      iRam0025f338 = 0;
      FUN_0013d930(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    }
    if ((cRam0025f454 == '\0') && (iVar9 = FUN_0012a590((long)iRam0025f21c), iVar9 == 0)) {
      cRam002a3304 = '\0';
    }
    if (cRam002a330d == '\0') {
      FUN_0013d2b0();
    }
    if (cRam0025f454 == '\0') {
      lVar8 = (long)iRam0025f21c;
      iVar9 = FUN_0012a590(lVar8);
      if (((iVar9 == 0) && (cRam002a330e != '\x02')) &&
         (iRam0025f338 = 1, *(char *)(*(int *)(iRam0025f21c + 0x414) + 0x858) != '\0')) {
        lVar8 = 0;
        param_2 = 0;
        FUN_0015c2a0(0x40400000,'\0',0);
        cRam002a330e = '\x02';
      }
      if (cRam002a330e == '\x04') {
        FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#!_..._00250dc0);
        lVar8 = (long)iRam0025f21c;
        param_2 = 1;
        cRam002a330e = '\x01';
        FUN_001f6d90(iRam0025f21c,1,param_3,(int)param_4);
        iRam0025f338 = 1;
      }
      if (((cRam002a330e == '\x02') && (sRam0025f4e0 == 0)) && (cRam002c4070 == '\0')) {
        sRam0025f374 = 0;
        sRam002c4056 = 2;
        sRam002c4058 = 0;
        FUN_0014c160();
        FUN_0014bf40();
        sRam002c4054 = 5;
        return;
      }
    }
    else {
      lVar8 = (long)iRam0025f21c;
      bVar2 = FUN_00210590(iRam0025f21c);
      if (bVar2) {
        lVar8 = (long)iRam0025f21c;
        iVar9 = FUN_0020f9e0(iRam0025f21c);
        if (((iVar9 != 0) && (0 < *(short *)(*(int *)(iRam0025f21c + 0x414) + 0x12))) &&
           (lVar6 = 0, 0 < sRam002a2c8c)) {
          iVar9 = 0x2a0000;
          do {
            iVar10 = *(int *)(iVar9 + 0x2c90);
            lVar8 = (long)iVar10;
            if ((*(short *)(iVar10 + 2) == 100) &&
               ((int)*(char *)(*(int *)(iVar10 + 0x414) + 0x8a6) - 2U < 2)) {
              FUN_0020f9b0();
            }
            lVar6 = (long)((int)lVar6 + 1);
            iVar9 = iVar9 + 4;
          } while (lVar6 < sRam002a2c8c);
        }
      }
      FUN_0020e100(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
      if ((cRam002a330e == '\x02') && (cRam002c4070 == '\0')) {
        FUN_0014b3c0(0,(undefined1 (*) [16])&DAT_00250938);
        if (iRam0025f33c != 0) {
          sRam002c4058 = 0;
          sRam002c4056 = 2;
          sRam0025f374 = 0;
          FUN_0014c160();
          FUN_0014bf40();
          sRam002c4054 = 0x13;
          return;
        }
        sRam002c4058 = 0;
        sRam002c4056 = 2;
        sRam0025f374 = 0;
        FUN_0014c160();
        FUN_0014bf40();
        sRam002c4054 = 0xf;
        return;
      }
      sVar3 = FUN_0014ac40();
      if (sVar3 == 0) {
        if (((*(char *)(*(int *)(iRam0025f21c + 0x414) + 0x858) != '\0') && (cRam002a330e == '\0'))
           && (sRam0025f484 == 0)) {
          lVar8 = 1;
          param_2 = 0x250da0;
          FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#?_00250da0);
          cRam002a330e = '\x01';
          iRam0025f338 = 1;
          FUN_0020c860();
        }
      }
      else {
        FUN_0014ac00(auStack_d0,param_2,param_3,param_4,param_5);
        param_2 = (long)(int)auStack_d0;
        lVar8 = 0x250e20;
        iVar9 = FUN_0011f970(0x250e20,(undefined1 (*) [16])auStack_d0,param_3,param_4);
        if (iVar9 != 0) {
          param_2 = (long)(int)auStack_d0;
          lVar8 = 0x250e50;
          iVar9 = FUN_0011f970(0x250e50,(undefined1 (*) [16])auStack_d0,param_3,param_4);
          if (iVar9 != 0) {
            param_2 = (long)(int)auStack_d0;
            lVar8 = 0x250e80;
            iVar9 = FUN_0011f970(0x250e80,(undefined1 (*) [16])auStack_d0,param_3,param_4);
            if ((((iVar9 != 0) && (*(char *)(*(int *)(iRam0025f21c + 0x414) + 0x858) != '\0')) &&
                (cRam002a330e == '\0')) && (sRam0025f484 == 0)) {
              lVar8 = 1;
              param_2 = 0x250da0;
              FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#?_00250da0);
              cRam002a330e = '\x01';
              iRam0025f338 = 1;
              FUN_0020c860();
            }
          }
        }
      }
    }
    if (sRam0025f4e0 == 0) {
      if ((cRam0025f454 != '\0') && (cRam002a330c == '\0')) {
        FUN_0020bf20(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
      }
      FUN_00151b80();
    }
    if ((cRam002a330d == '\0') && (cRam002a3304 != '\0')) {
      FUN_0013cd40(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    }
    if (-1 < sRam002a3310) {
      lVar8 = 0x2a3495;
      param_2 = 0x250938;
      iVar9 = FUN_0011f970(0x2a3495,(undefined1 (*) [16])&DAT_00250938,param_3,param_4);
      if ((iVar9 == 0) && (lVar8 = (long)(sRam002a3310 * 0xf0 + 0x35ee40), lVar8 != 0)) {
        FUN_001597f0(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
      }
    }
    FUN_0014c000(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    FUN_0014bba0(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    if ((cRam0025f454 == '\0') || (sRam0025f4e0 != 0)) {
      lVar8 = 0;
      FUN_0014ac50(0,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    }
    else {
      lVar8 = 5;
      FUN_0014ac50(5,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    }
    if (sRam0025f4e0 != 0) {
      FUN_0014aad0(0x1e,0x17c,1,0x250e00,param_5,param_6,param_7,param_8);
      sVar3 = FUN_00155840();
      lVar8 = (long)(sVar3 + 10);
      sVar3 = FUN_00155830();
      param_2 = (long)sVar3;
      param_7 = 1;
      param_3 = 0xc;
      param_4 = 0x12;
      param_5 = 6;
      param_6 = 2;
      param_8 = param_7;
      FUN_0014c5e0(lVar8,param_2,0xc,0x12,6,2,1,1);
    }
    FUN_0015c190(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    FUN_00127630(lVar8,param_2,param_3,param_4,param_5,param_6,param_7,param_8);
    FUN_001631f0();
  }
  else {
    sRam002c4058 = 0;
    sRam002c4056 = 2;
    sRam0025f374 = 0;
    FUN_0014c160();
    FUN_0014bf40();
    sRam002c4054 = 0x15;
  }
  return;
}

