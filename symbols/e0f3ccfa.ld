/* Addresses in main for build E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348 (v131072 / "1.1.1").
   Module base is taken as 0x80020000, the same base Hookshot uses, so f_XXXXXXXX names line up.
   main offset = address - 0x80020000.  IPS offset = main offset + 0x100.
   See docs/address-map.md for what each one is and how it was found. */

/* --- vtables (compare against [object]) --- */
VT_VIEW          = 0x84c18a88;  /* camera view: matrix +0x08, eye +0x60 (f64x3), target +0x78 (f64x3) */
VT_ACTOR         = 0x84b45e18;  /* physics actor handed to the movement update; pos +0x31c, rot 3x4 +0x328 */
VT_PLAYER        = 0x84b6c460;  /* player-type object; resource name at [[obj+0x10]+0x58] = "Player" */
VT_CCT           = 0x84c54f10;  /* Link's physics character controller: [[[[[actor+0x270]+80]+32]+16]+8] */

/* --- functions --- */
CCT_CHANGE_POSITION = 0x806d2530; /* f_806d2530(controller, float pos[4]): moves a character controller (vtable slot +0xe8) */

/* --- globals --- */
CAMMGR_SLOT      = 0x84ca6bc0;  /* [[slot]] = camera manager; +0x20 count, +0x28 cameras; [cameras][0]+0x78 = gameplay view */

/* --- imports (PLT stubs: adrp x16 / ldr x17 / add x16 / br x17, 16 bytes each) --- */
PLT_GETNPAD_STYLESET = 0x83c627e0; /* nn::hid::GetNpadStyleSet(uint const&) (by its use in f_834893d0) */
PLT_GETNPAD_JOYDUAL  = 0x83c627f0; /* nn::hid::GetNpadStates(NpadJoyDualState*, int, uint const&) */
PLT_GETNPAD_FULLKEY  = 0x83c62800; /* nn::hid::GetNpadStates(NpadFullKeyState*, int, uint const&) */
PLT_GETNPAD_JOYLEFT  = 0x83c62810; /* nn::hid::GetNpadStates for style bit 3 (Joy-Con left, by its use) */
PLT_GETNPAD_JOYRIGHT = 0x83c62820; /* nn::hid::GetNpadStates for style bit 4 (Joy-Con right, by its use) */
PLT_GETNPAD_HANDHELD = 0x83c62830; /* nn::hid::GetNpadStates(NpadHandheldState*, int, uint const&) */
PLT_GETKEYBOARD      = 0x83c64810; /* nn::hid::GetKeyboardState(KeyboardState*): keys bitset at +0x10 */
PLT_GETMOUSESTATES   = 0x83c64800; /* nn::hid::GetMouseStates(MouseState*, int): returns the number written */
PLT_GETSIXAXIS       = 0x83c628a0; /* nn::hid::GetSixAxisSensorStates(SixAxisSensorState*, int, SixAxisSensorHandle const&) */
GAME_MOUSE_READ_RET  = 0x83b487b0; /* where the game's one GetMouseStates call returns (in f_83b48780) */

/* --- hook sites used by mods in this repo (resume = site + 4) --- */
HOOK_VIEW        = 0x804e5068;  /* in f_804e48c0, right after the view matrix is written: ldr x8, [x19, #0x20] */
HOOK_VIEW_RET    = 0x804e506c;
HOOK_ACTOR       = 0x82c41720;  /* in f_82c415e0 (movement update), x19 = actor: add x23, x19, #0x328 */
HOOK_ACTOR_RET   = 0x82c41724;
HOOK_VIEW2       = 0x804e506c;  /* in f_804e48c0, the instruction after HOOK_VIEW: cbz x8, 0x804e5b78 */
HOOK_VIEW2_RET   = 0x804e5070;
HOOK_VIEW2_TAKEN = 0x804e5b78;  /* where that cbz goes */
HOOK_MOVE        = 0x82c415e0;  /* f_82c415e0's first instruction: pacibsp; x0 = actor */
HOOK_MOVE_RET    = 0x82c415e4;
MOVE_SECOND_RET  = 0x82c415e8;  /* after the movement update's second instruction (str d10, [sp, #-0x80]!) */

/* --- free memory claimed by mods in this repo (see docs/memory-map.md) --- */
FP_STATE         = 0x84ebfc00;  /* 0x40 bytes of unused .bss (zeroed at boot) */
DRONE_STATE      = 0x84ebfd00;  /* 0x100 bytes, FPV drone */
PROBE_STATE      = 0x84ebfb00;  /* 0x100 bytes, mouse-grab's input probe (retired; Kaepora's hook slots now) */
KP_HOOK_SLOTS    = 0x84ebfb00;  /* Kaepora Core: one 8-byte function pointer per hook point, set by the module */
/* 0x84ebfe00..0x84ec0000 belongs to Lichii's built-in patches (Dynamic FPS state): keep out */
