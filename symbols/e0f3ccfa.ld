/* Addresses in main for build E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348 (v131072 / "1.1.1").
   Module base is taken as 0x80020000, the same base Hookshot uses, so f_XXXXXXXX names line up.
   main offset = address - 0x80020000.  IPS offset = main offset + 0x100.
   See docs/address-map.md for what each one is and how it was found. */

/* --- vtables (compare against [object]) --- */
VT_VIEW          = 0x84c18a88;  /* camera view: matrix +0x08, eye +0x60 (f64x3), target +0x78 (f64x3) */
VT_ACTOR         = 0x84b45e18;  /* physics actor handed to the movement update; pos +0x31c, rot 3x4 +0x328 */
VT_PLAYER        = 0x84b6c460;  /* player-type object; resource name at [[obj+0x10]+0x58] = "Player" */

/* --- globals --- */
CAMMGR_SLOT      = 0x84ca6bc0;  /* [[slot]] = camera manager; +0x20 count, +0x28 cameras; [cameras][0]+0x78 = gameplay view */

/* --- imports (PLT stubs) --- */
PLT_GETNPAD_JOYDUAL  = 0x83c627f0; /* nn::hid::GetNpadStates(NpadJoyDualState*, int, uint const&) */
PLT_GETNPAD_FULLKEY  = 0x83c62800; /* nn::hid::GetNpadStates(NpadFullKeyState*, int, uint const&) */
PLT_GETNPAD_HANDHELD = 0x83c62830; /* nn::hid::GetNpadStates(NpadHandheldState*, int, uint const&) */

/* --- hook sites used by mods in this repo (resume = site + 4) --- */
HOOK_VIEW        = 0x804e5068;  /* in f_804e48c0, right after the view matrix is written: ldr x8, [x19, #0x20] */
HOOK_VIEW_RET    = 0x804e506c;
HOOK_ACTOR       = 0x82c41720;  /* in f_82c415e0 (movement update), x19 = actor: add x23, x19, #0x328 */
HOOK_ACTOR_RET   = 0x82c41724;

/* --- free memory claimed by mods in this repo (see docs/memory-map.md) --- */
FP_STATE         = 0x84ebfc00;  /* 0x40 bytes of unused .bss (zeroed at boot) */
