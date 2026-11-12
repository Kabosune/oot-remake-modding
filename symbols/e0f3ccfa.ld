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
POUCH_ADD_CONTENT               = 0x8112d570; /* adds a content (an item, ammo, rupees and so on) to the pouch */
POUCH_GET_CONTENT_NUM           = 0x805b63e0; /* returns how many of a content the pouch holds, by the content's actor name */
POUCH_INFO_FIND                 = 0x805aed10; /* finds a content's pouch info by its actor name */
POUCH_CATEGORY_FROM_STRING      = 0x8015fdd0; /* converts a pouch category name to its number: bool (u32* out, const char** name) */
POUCH_PUSH_PICKED_UP            = 0x80c8f620; /* pushes a picked-up item's content into the pouch */
PICKUP_HANDLER                  = 0x82eaa1e0; /* handles an item pickup */
DROP_READ_PARAMS                = 0x80bf1c00; /* reads a placed actor's drop parameters (Drop__DropActor) */
QUERY_SET_GET_EVENT_REQUEST_ARG = 0x82b00750; /* QuerySetGetEventRequestArg(node, request) */
EVFL_PROCESS_CONTEXT            = 0x81248840; /* processes an EventFlow flowchart context: runs its actions, queries and subflows */
EVFL_BUILD_CONTEXT              = 0x8124a0a0; /* builds an EventFlow context */
EVFL_MARK_ENTRIES               = 0x8124abe0; /* marks the entries reachable from one EventFlow entry: bool (err*, flowcharts*, bitsets*, u32 flowchart, u64 entry) */
EVFL_BIND_ACTION                = 0x80d5c9a0; /* adds an action handler to an EventFlow binding, by the action's name */
EVFL_BIND_QUERY                 = 0x8124b4a0; /* adds a query handler to an EventFlow binding, by the query's name */
BANC_LOAD                       = 0x80c1ba50; /* loads a Banc (an area's placements) */
WINDOW_SET_MESSAGE              = 0x80a8c460; /* sets a talk window's message from a message file and label */
DUNGEON_ADD_SMALL_KEY           = 0x832a3160; /* adds small keys: (dungeon manager, int count) */
DUNGEON_SET_BOSS_KEY            = 0x832a30e0; /* sets the boss key: (dungeon manager, bool) */
DUNGEON_SET_MAP                 = 0x832a2fe0; /* sets the map: (dungeon manager, bool) */
DUNGEON_SET_COMPASS             = 0x832a3060; /* sets the compass: (dungeon manager, bool) */
BOOLEXP_EVALUATE                = 0x804029e0; /* evaluates a GameData BoolExp (a condition expression) */
BOOLEXP_COMPARE_ENUM_ORDER      = 0x804248f0; /* compares the order of two enum values for the BoolExp evaluators */
SHOP_IS_SOLD_OUT                = 0x80bb88d0; /* checks whether a shop's goods slot is sold out: (owner link, index, ...) */
GAMEDATA_FIND_STRUCT            = 0x809d3eb0; /* finds a GameData struct: (manager, Key* out, u32 struct hash) */
GAMEDATA_GET_BOOL               = 0x80199f70; /* gets a GameData bool: (manager, bool* out, Key*, u32 member hash) */
GAMEDATA_GET_INT                = 0x8019b3b0; /* gets a GameData int: (manager, int* out, Key*, u32 member hash) */
GAMEDATA_GET_ENUM               = 0x8019bf90; /* gets a GameData enum: (manager, u32* out, Key*, u32 member hash) */
GAMEDATA_SET_BOOL               = 0x80628a10; /* sets a GameData bool: (manager, bool value, Key*, u32 member hash) */
GAMEDATA_SET_INT                = 0x809d39e0; /* sets a GameData int: (manager, int value, Key*, u32 member hash) */
GAMEDATA_SET_BOOL_BY_HASH       = 0x806a2b20; /* sets a GameData bool by its hash: (manager, bool value, u32 hash) */
GAMEDATA_SET_ENUM_BY_HASH       = 0x80400980; /* sets a GameData enum by its hash: (manager, u32 value, u32 hash) */
EVENT_REQUEST_INIT              = 0x80d99f10; /* constructs an EventRequest */
EVENT_REQUEST                   = 0x80d9a820; /* requests an event: bool (EventMgr*, EventRequest*) */
ACTOR_SET_POSITION              = 0x80964e70; /* sets an actor's position: (Actor*, const float pos[3], bool) */
ACTOR_SET_TRANSFORM             = 0x80c8fd60; /* sets an actor's transform: (Actor*, const float mtx[12], bool) */
FRAMEWORK_FRAME                 = 0x83b6ea90; /* runs one frame of the game framework (slot 28 of the vtable at 0x84c83f80) */

/* --- globals --- */
CAMMGR_SLOT      = 0x84ca6bc0;  /* [[slot]] = camera manager; +0x20 count, +0x28 cameras; [cameras][0]+0x78 = gameplay view */
POUCHMGR_PTR                    = 0x84e98e28; /* the PouchMgr pointer variable */
GAMEDATAMGR_PTR                 = 0x84ea42a8; /* the GameDataMgr pointer variable */
EVENTMGR_PTR                    = 0x84eb4840; /* the EventMgr pointer variable */

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
PROBE_STATE      = 0x84ebfb00;  /* 0x100 bytes, mouse-grab's input probe (retired; KaeGae's hook slots now) */
KP_HOOK_SLOTS    = 0x84ebfb00;  /* KaeGae Core: one 8-byte function pointer per hook point, set by the module */
/* 0x84ebfe00..0x84ec0000 belongs to Lichii's built-in patches (Dynamic FPS state): keep out */
