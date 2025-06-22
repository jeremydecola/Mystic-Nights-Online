
bool FUN_0021ade0(undefined2 *param_1,undefined8 param_2,long param_3,ulong param_4,ulong param_5,
                 ulong param_6,long param_7,long param_8)

{
  short sVar1;
  int iVar2;
  long lVar3;
  undefined8 uVar4;
  undefined8 uVar5;
  ulong uVar6;
  ulong uVar7;
  undefined1 auStack_270 [208];
  ulong auStack_1a0 [26];
  undefined1 auStack_d0 [208];
  
  uVar4 = 1;
  uVar5 = param_2;
  FUN_0014d080(1);
  if (*(short *)param_2 != 0) {
    iVar2 = FUN_00219b90(uVar4,uVar5,param_3,param_4,param_5,param_6,param_7,param_8);
    return iVar2 == 0;
  }
  if ((((sRam0025f464 == 0) && (sVar1 = FUN_0014ac40(), sVar1 == 0)) &&
      (iVar2 = FUN_001284a0((ulong *)0x39d310,3000,1), iVar2 != 0)) &&
     (iVar2 = FUN_0020ac80(), iVar2 < 1)) {
    sRam0025f464 = 1;
    FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#._._0025cdb0); //"The network cable is disconnected. You will now be logged out."
  }
  if (((sRam0025f4e4 == 0) && (sVar1 = FUN_0014ac40(), sVar1 == 0)) &&
     (iVar2 = FUN_002198d0(), iVar2 < 1)) {
    sRam0025f4e4 = 1;
    if (iVar2 == 0) {
      FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#._._0025cc60); //"The connection to the server was lost. You will now be logged out."
    }
    else {
      FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#._._0025cc90); //"A network error has occurred. You will now be logged out."
    }
  }
  sVar1 = FUN_0014ac40();
  if (sVar1 != 0) {
    sRam0039eb0a = 1;
  }
  uVar7 = 4;
  uVar6 = (ulong)sRam0039eb02;
  if (uVar6 == 4) {
    if (sRam0039eb0a == 0) {
      iVar2 = FUN_0011f970(0x39eb18,(undefined1 (*) [16])&DAT_0025ccc0,4,param_4);
      if (iVar2 == 0) {
        uVar6 = 0x25ccd0;
        FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#ID_._._0025ccd0); // "Invalid ID. Please re-enter."
      }
      else {
        iVar2 = FUN_0011f970(0x39eb25,(undefined1 (*) [16])0x39eb32,uVar7,param_4);
        if (iVar2 == 0) {
          uVar6 = 0x25ccc0;
          iVar2 = FUN_0011f970(0x39eb25,(undefined1 (*) [16])&DAT_0025ccc0,uVar7,param_4);
          if (iVar2 != 0) {
            if (sRam0039eb0e == 0) {
              if (sRam0039eb08 == 0) {
                uVar6 = 0x25cd50;
                FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#?_0025cd50); // "Are you sure you want to delete your account?"
              }
              else {
                uVar6 = 0x25cd30;
                FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#?_0025cd30); // "Would you like to create an account?"
              }
            }
            else {
              if (sRam0039eb14 == 0) {
                if (sRam0039eb08 == 0) {
                  lVar3 = FUN_00218db0(0x7d2,uVar6,uVar7,param_4,param_5,param_6,param_7,param_8); //send account delete request
                }
                else {
                  lVar3 = FUN_00218db0(0x7d1,uVar6,uVar7,param_4,param_5,param_6,param_7,param_8); //send account create request
                }
                sRam0039eb14 = 0;
                if (0 < lVar3) {
                  sRam0039eb14 = 1;
                }
              }
              if (sRam0039eb0c != 0) {
                if (sRam0039eb08 == 0) {
                  *param_1 = 1;
                  return false;
                }
                uVar6 = 0x25ce80;
                uRam0025f500 = 0;
                FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#(PS2)_?_0025ce80); //"Would you like to save the settings to the memory card (PS2)?"
                FUN_0014b370(1);
              }
            }
            goto LAB_0021b35c;
          }
        }
        uVar6 = 0x25cd00;
        FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#._._0025cd00); // "Incorrect password. Please re-enter it."
      }
    }
  }
  else if (uVar6 == 3) {
    if (sRam0039eb0a == 0) {
      if (sRam002a52b0 == 1) {
        FUN_0015c310(2);
        sRam0039eb06 = sRam0039eb06 + -1;
        uRam0025f4fc = 0;
        if (sRam0039eb06 < 0) {
          sRam0039eb06 = 0x24;
        }
      }
      if (sRam002a52b0 == 2) {
        FUN_0015c310(2);
        sRam0039eb06 = sRam0039eb06 + 1;
        uRam0025f4fc = 0;
        if (0x24 < sRam0039eb06) {
          sRam0039eb06 = 0;
        }
      }
      if (cRam002a52b2 == '\0') {
        if (cRam002a52b3 == '\0') {
          if ((cRam002a52b4 == '\0') || (sRam0039eb44 < 1)) {
            if (cRam002a52b7 != '\0') {
              FUN_0015c310(2);
              uRam0025f4fc = 0;
              sRam0039eb06 = 0x24;
            }
          }
          else {
            FUN_0015c310(3);
            cRam002a52b4 = '\0';
            uVar6 = (ulong)(sRam0039eb44 + -1);
            sRam0039eb44 = (short)(sRam0039eb44 + -1);
            *(undefined1 *)(sRam0039eb44 + 0x39eb32) = 0;
          }
        }
        else {
          FUN_0015c310(1);
          cRam002a52b3 = '\0';
          sRam0039eb44 = 0;
          uVar6 = 0;
          uVar7 = 0xd;
          FUN_0011cd30((undefined8 *)0x39eb32,0,0xd,param_4,param_5);
          uRam0025f4fc = 0;
          sRam0039eb02 = 0;
          uRam0025f4f8 = 0;
          sRam0039eb06 = 0;
        }
      }
      else {
        FUN_0015c310(0);
        uRam0025f4fc = 0;
        cRam002a52b2 = '\0';
        uRam0025f4f8 = 0;
        if (sRam0039eb06 < 0x1a) {
          uVar6 = (ulong)sRam0039eb44;
          iVar2 = sRam0039eb06 + 0x41;
          uVar7 = (ulong)iVar2;
          *(char *)(sRam0039eb44 + 0x39eb32) = (char)iVar2;
          sRam0039eb44 = sRam0039eb44 + 1;
        }
        else if (sRam0039eb06 < 0x24) {
          uVar6 = (ulong)sRam0039eb44;
          iVar2 = sRam0039eb06 + 0x16;
          uVar7 = (ulong)iVar2;
          *(char *)(sRam0039eb44 + 0x39eb32) = (char)iVar2;
          sRam0039eb44 = sRam0039eb44 + 1;
        }
        else if (sRam0039eb44 < 4) {
          uVar6 = 0x25cde0;
          FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#ID_4_._0025cde0); //"ID and password must be at least 4 characters long."
        }
        else {
          iVar2 = FUN_0011f970(0x39eb25,(undefined1 (*) [16])0x39eb32,uVar7,param_4);
          if (iVar2 == 0) {
            uVar7 = 0xc;
            sRam0025f504 = sRam0039eb44;
            FUN_001200f0(0x39ea30,(undefined1 (*) [16])0x39eb32,0xc,param_4,param_5,param_6,param_7)
            ;
            uVar6 = (ulong)sRam0039eb44;
            *(undefined1 *)(sRam0039eb44 + 0x39eb32) = 0;
            sRam0039eb02 = 0;
            sRam0039eb06 = 0;
          }
          else {
            uVar6 = 0x25ce50;
            FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#._._0025ce50); // "The passwords you entered don't match. Please try again."
          }
        }
        if (8 < sRam0039eb44) {
          sRam0039eb44 = sRam0039eb44 + -1;
          uVar6 = 0x25ce20;
          *(undefined1 *)(sRam0039eb44 + 0x39eb32) = 0;
          FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#ID_8_._0025ce20); // "ID and password must be within 8 characters."
        }
      }
    }
  }
  else if (uVar6 == 2) {
    if (sRam0039eb0a == 0) {
      if (sRam002a52b0 == 1) {
        FUN_0015c310(2);
        sRam0039eb06 = sRam0039eb06 + -1;
        uRam0025f4fc = 0;
        if (sRam0039eb06 < 0) {
          sRam0039eb06 = 0x24;
        }
      }
      if (sRam002a52b0 == 2) {
        FUN_0015c310(2);
        sRam0039eb06 = sRam0039eb06 + 1;
        uRam0025f4fc = 0;
        if (0x24 < sRam0039eb06) {
          sRam0039eb06 = 0;
        }
      }
      if (cRam002a52b2 == '\0') {
        if (cRam002a52b3 == '\0') {
          if ((cRam002a52b4 == '\0') || (sRam0039eb42 < 1)) {
            if (cRam002a52b7 != '\0') {
              FUN_0015c310(2);
              uRam0025f4fc = 0;
              sRam0039eb06 = 0x24;
            }
          }
          else {
            FUN_0015c310(3);
            cRam002a52b4 = '\0';
            uVar6 = (ulong)(sRam0039eb42 + -1);
            sRam0039eb42 = (short)(sRam0039eb42 + -1);
            *(undefined1 *)(sRam0039eb42 + 0x39eb25) = 0;
          }
        }
        else {
          FUN_0015c310(1);
          cRam002a52b3 = '\0';
          uVar6 = 0x39ea70;
          uVar7 = 0xc;
          sRam0039eb42 = sRam0025f508;
          FUN_001200f0(0x39eb25,(undefined1 (*) [16])0x39ea70,0xc,param_4,param_5,param_6,param_7);
          uRam0025f4fc = 0;
          sRam0039eb02 = 0;
          uRam0025f4f8 = 0;
          sRam0039eb06 = 0;
        }
      }
      else {
        FUN_0015c310(0);
        uRam0025f4fc = 0;
        cRam002a52b2 = '\0';
        uRam0025f4f8 = 0;
        if (sRam0039eb06 < 0x1a) {
          uVar6 = (ulong)sRam0039eb42;
          iVar2 = sRam0039eb06 + 0x41;
          uVar7 = (ulong)iVar2;
          *(char *)(sRam0039eb42 + 0x39eb25) = (char)iVar2;
          sRam0039eb42 = sRam0039eb42 + 1;
        }
        else if (sRam0039eb06 < 0x24) {
          uVar6 = (ulong)sRam0039eb42;
          iVar2 = sRam0039eb06 + 0x16;
          uVar7 = (ulong)iVar2;
          *(char *)(sRam0039eb42 + 0x39eb25) = (char)iVar2;
          sRam0039eb42 = sRam0039eb42 + 1;
        }
        else if (sRam0039eb42 < 4) {
          uVar6 = 0x25cde0;
          FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#ID_4_._0025cde0); // "ID and password must be at least 4 characters long."
        }
        else {
          sRam0025f508 = sRam0039eb42;
          uVar7 = 0xc;
          FUN_001200f0(0x39ea70,(undefined1 (*) [16])0x39eb25,0xc,param_4,param_5,param_6,param_7);
          uVar6 = (ulong)sRam0039eb42;
          *(undefined1 *)(sRam0039eb42 + 0x39eb25) = 0;
          sRam0039eb02 = 0;
          sRam0039eb06 = 0;
        }
        if (8 < sRam0039eb42) {
          sRam0039eb42 = sRam0039eb42 + -1;
          uVar6 = 0x25ce20;
          *(undefined1 *)(sRam0039eb42 + 0x39eb25) = 0;
          FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#ID_8_._0025ce20); // "ID and password must be within 8 characters."
        }
      }
    }
  }
  else if (uVar6 == 1) {
    if (sRam0039eb0a == 0) {
      if (sRam002a52b0 == 1) {
        FUN_0015c310(2);
        sRam0039eb06 = sRam0039eb06 + -1;
        uRam0025f4fc = 0;
        if (sRam0039eb06 < 0) {
          sRam0039eb06 = 0x24;
        }
      }
      if (sRam002a52b0 == 2) {
        FUN_0015c310(2);
        sRam0039eb06 = sRam0039eb06 + 1;
        uRam0025f4fc = 0;
        if (0x24 < sRam0039eb06) {
          sRam0039eb06 = 0;
        }
      }
      if (cRam002a52b2 == '\0') {
        if (cRam002a52b3 == '\0') {
          if ((cRam002a52b4 == '\0') || (sRam0039eb40 < 1)) {
            if (cRam002a52b7 != '\0') {
              FUN_0015c310(2);
              uRam0025f4fc = 0;
              sRam0039eb06 = 0x24;
            }
          }
          else {
            FUN_0015c310(3);
            cRam002a52b4 = '\0';
            uVar6 = (ulong)(sRam0039eb40 + -1);
            sRam0039eb40 = (short)(sRam0039eb40 + -1);
            *(undefined1 *)(sRam0039eb40 + 0x39eb18) = 0;
          }
        }
        else {
          cRam002a52b3 = '\0';
          FUN_0015c310(1);
          uVar6 = 0x39eab0;
          uVar7 = 0xc;
          sRam0039eb40 = sRam0025f50c;
          FUN_001200f0(0x39eb18,(undefined1 (*) [16])0x39eab0,0xc,param_4,param_5,param_6,param_7);
          uRam0025f4fc = 0;
          sRam0039eb02 = 0;
          uRam0025f4f8 = 0;
          sRam0039eb06 = 0;
        }
      }
      else {
        FUN_0015c310(0);
        uRam0025f4fc = 0;
        cRam002a52b2 = '\0';
        uRam0025f4f8 = 0;
        if (sRam0039eb06 < 0x1a) {
          uVar6 = (ulong)sRam0039eb40;
          iVar2 = sRam0039eb06 + 0x41;
          uVar7 = (ulong)iVar2;
          *(char *)(sRam0039eb40 + 0x39eb18) = (char)iVar2;
          sRam0039eb40 = sRam0039eb40 + 1;
        }
        else if (sRam0039eb06 < 0x24) {
          uVar6 = (ulong)sRam0039eb40;
          iVar2 = sRam0039eb06 + 0x16;
          uVar7 = (ulong)iVar2;
          *(char *)(sRam0039eb40 + 0x39eb18) = (char)iVar2;
          sRam0039eb40 = sRam0039eb40 + 1;
        }
        else if (sRam0039eb40 < 4) {
          uVar6 = 0x25cde0;
          FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#ID_4_._0025cde0); // "ID and password must be at least 4 characters long."
        }
        else {
          sRam0025f50c = sRam0039eb40;
          uVar7 = 0xc;
          FUN_001200f0(0x39eab0,(undefined1 (*) [16])0x39eb18,0xc,param_4,param_5,param_6,param_7);
          uVar6 = (ulong)sRam0039eb40;
          *(undefined1 *)(sRam0039eb40 + 0x39eb18) = 0;
          sRam0039eb02 = 0;
          sRam0039eb06 = 0;
        }
        if (8 < sRam0039eb40) {
          sRam0039eb40 = sRam0039eb40 + -1;
          uVar6 = 0x25ce20;
          *(undefined1 *)(sRam0039eb40 + 0x39eb18) = 0;
          FUN_0014b3c0(2,(undefined1 (*) [16])s_HANGUL#ID_8_._0025ce20); // "ID and password must be within 8 characters."
        }
      }
    }
  }
  else if (uVar6 == 0) {
    uVar6 = (ulong)sRam002a52b0;
    param_4 = uVar7;
    FUN_0015c790(psRam0039eaf8,(int)sRam002a52b0,4,4);
    sRam0039eb00 = psRam0039eaf8[0x1b] + 1;
    if (cRam002a52b2 == '\0') {
      if (cRam002a52b3 != '\0') {
        cRam002a52b3 = 0;
        FUN_0015c310(1);
        *param_1 = 1;
        return false;
      }
    }
    else {
      cRam002a52b2 = '\0';
      FUN_0015c310(0);
      uRam0025f4fc = 0;
      sRam0039eb14 = 0;
      sRam0039eb02 = sRam0039eb00;
    }
  }
LAB_0021b35c:
  if ((sRam0039eb16 != 0) && (sRam0039eb0a == 0)) {
    if (sRam0039eb10 == 0) {
      uVar6 = 1;
      param_4 = 0;
      uVar7 = uVar6;
      iVar2 = FUN_0014a900((int)sRam0039eb12,1,1,0,param_5,param_6,param_7,param_8);
      if (iVar2 != 0) {
        uVar6 = 5;
        uVar7 = 1;
        iVar2 = FUN_00164370((int)sRam0039eb12,5,1,param_4,param_5,param_6,param_7,param_8);
        if (iVar2 != 0) {
          uVar7 = (ulong)(sRam0039eb12 + 1);
          FUN_0011f4b0(auStack_d0,0x25ceb0,uVar7,param_4,param_5,param_6,param_7,param_8);
          uVar6 = (ulong)(int)auStack_d0;
          FUN_0014b3c0(2,(undefined1 (*) [16])auStack_d0);
        }
      }
    }
    else {
      if ((sRam002a52b0 == 1) && (sRam0039eb12 == 1)) {
        FUN_0015c310(2);
        sRam0039eb12 = 0;
      }
      if ((sRam002a52b0 == 2) && (sRam0039eb12 == 0)) {
        FUN_0015c310(2);
        sRam0039eb12 = 1;
      }
      if (cRam002a52b2 != '\0') {
        FUN_0015c310(0);
        cRam002a52b2 = '\0';
        sRam0039eb10 = 0;
      }
      if (cRam002a52b3 != '\0') {
        cRam002a52b3 = 0;
        FUN_0015c310(1);
        FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#(PS2)_,_?_0025cd70); // "End the memory card (PS2) save operation and start the game"
        FUN_0014b370(1);
        *param_1 = 1;
        return false;
      }
    }
  }
  if (sRam0039eb0a != 0) {
    FUN_0014ac00(auStack_1a0,uVar6,uVar7,param_4,param_5);
    iVar2 = FUN_0014b240();
    if (iVar2 == 0x67) {
      sRam0039eb0a = 0;
      if (sRam0039eb16 == 0) {
        if ((sRam0039eb08 == 0) || (sRam0039eb0c == 0)) {
          sRam0039eb0e = 1;
        }
        else {
          sRam0039eb0c = 0;
          sRam0039eb16 = 1;
          sRam0039eb10 = 1;
        }
      }
      else {
        uVar7 = (ulong)(sRam0039eb12 + 1);
        FUN_0011f4b0(auStack_270,0x25cf20,uVar7,param_4,param_5,param_6,param_7,param_8);
        iVar2 = FUN_0011f970((long)(int)auStack_1a0,(undefined1 (*) [16])auStack_270,uVar7,param_4);
        if (iVar2 == 0) {
          uVar7 = 0;
          iVar2 = FUN_00165650((int)sRam0039eb12,5,0,param_4,param_5,param_6,param_7,param_8);
          if (iVar2 != 0) {
            sRam0039eb10 = 0;
            return true;
          }
        }
        //"Would you like to save the settings to the memory card (PS2)?"
        iVar2 = FUN_0011f970((long)(int)auStack_1a0,(undefined1 (*) [16])s_HANGUL#(PS2)_?_0025ce80,
                             uVar7,param_4);
        if (iVar2 == 0) {
          sRam0039eb10 = 1;
          sRam0039eb12 = 0;
        }
        else {
          // "End the memory card (PS2) save operation and start the game"
          iVar2 = FUN_0011f970((long)(int)auStack_1a0,
                               (undefined1 (*) [16])s_HANGUL#(PS2)_,_?_0025cd70,uVar7,param_4);
          if (iVar2 == 0) {
            *param_1 = 1;
            return false;
          }
        }
      }
    }
    else if (iVar2 == 0x66) {
      sRam0039eb0a = 0;
      if (sRam0039eb16 == 0) {
        if (sRam0039eb02 == 1) {
          sRam0039eb0a = 0;
          return true;
        }
        if (sRam0039eb02 == 2) {
          sRam0039eb0a = 0;
          return true;
        }
        if (sRam0039eb02 == 3) {
          sRam0039eb0a = 0;
          return true;
        }
        if (sRam0039eb0c != 0) {
          *param_1 = 1;
          return false;
        }
        sRam0039eb0e = 0;
        sRam0039eb0a = 0;
        sRam0039eb14 = 0;
        sRam0039eb02 = 0;
      }
      else {
        sRam0039eb10 = 0;
        uVar7 = (ulong)(sRam0039eb12 + 1);
        FUN_0011f4b0(auStack_270,0x25ceb0,uVar7,param_4,param_5,param_6,param_7,param_8);
        iVar2 = FUN_0011f970((long)(int)auStack_1a0,(undefined1 (*) [16])auStack_270,uVar7,param_4);
        if (iVar2 == 0) {
          *param_1 = 1;
          return false;
        }
        // "Would you like to save the settings to the memory card (PS2)?"
        iVar2 = FUN_0011f970((long)(int)auStack_1a0,(undefined1 (*) [16])s_HANGUL#(PS2)_?_0025ce80,
                             uVar7,param_4);
        if (iVar2 == 0) {
          *param_1 = 1;
          return false;
        }
        // "End the memory card (PS2) save operation and start the game"
        iVar2 = FUN_0011f970((long)(int)auStack_1a0,(undefined1 (*) [16])s_HANGUL#(PS2)_,_?_0025cd70
                             ,uVar7,param_4);
        if (iVar2 == 0) {
          // "Would you like to save the settings to the memory card (PS2)?"
          FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#(PS2)_?_0025ce80);
          FUN_0014b370(1);
          return true;
        }
        // "End the memory card (PS2) save operation and start the game"
        FUN_0014b3c0(1,(undefined1 (*) [16])s_HANGUL#(PS2)_,_?_0025cd70);
        FUN_0014b370(1);
      }
      iVar2 = FUN_0011f970(0x25cdb0,(undefined1 (*) [16])auStack_1a0,uVar7,param_4);
      if (((iVar2 == 0) ||
          (iVar2 = FUN_0011f970(0x25cc60,(undefined1 (*) [16])auStack_1a0,uVar7,param_4), iVar2 == 0
          )) || (iVar2 = FUN_0011f970(0x25cc90,(undefined1 (*) [16])auStack_1a0,uVar7,param_4),
                iVar2 == 0)) {
        *(short *)param_2 = 1;
      }
    }
  }
  return true;
}

