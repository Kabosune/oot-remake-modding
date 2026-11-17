/* Addresses in main for build 33FA6C2C23848282A77E8B88A0A93F4887C55920 (v65536 / "1.0.0").
   Module base is taken as 0x80020000, as in symbols/e0f3ccfa.ld. Same names as that file, for
   patches built against this build. Written from symbols/33fa6c2c.toml (17 November 2026);
   tests/test_kaegae_symbols.py checks that the two agree. */

/* --- vtables (compare against [object]) --- */
VT_VIEW                         = 0x84bb2e90; /* View */
VT_ACTOR                        = 0x84ae0e30; /* Actor */
VT_PLAYER                       = 0x84b07458; /* Player */
VT_CCT                          = 0x84bef308; /* Cct */

/* --- functions --- */
CCT_CHANGE_POSITION             = 0x806f7730; /* CctChangePosition */
POUCH_ADD_CONTENT               = 0x811578f0; /* PouchAddContent */
POUCH_GET_CONTENT_NUM           = 0x8049b950; /* PouchGetContentNum */
POUCH_INFO_FIND                 = 0x80493490; /* PouchInfoFind */
POUCH_CATEGORY_FROM_STRING      = 0x8049aaf0; /* PouchCategoryFromString */
POUCH_PUSH_PICKED_UP            = 0x82e54ef0; /* PouchPushPickedUp */
PICKUP_HANDLER                  = 0x82e554b0; /* PickupHandler */
DROP_READ_PARAMS                = 0x80bf89b0; /* DropReadParams */
QUERY_SET_GET_EVENT_REQUEST_ARG = 0x82aad700; /* QuerySetGetEventRequestArg */
EVFL_PROCESS_CONTEXT            = 0x81204220; /* EventFlowProcessContext */
EVFL_BUILD_CONTEXT              = 0x81205a80; /* EventFlowBuildContext */
EVFL_MARK_ENTRIES               = 0x812065c0; /* EventFlowMarkEntries */
EVFL_BIND_ACTION                = 0x80d86e60; /* EventFlowBindAction */
EVFL_BIND_QUERY                 = 0x81206e80; /* EventFlowBindQuery */
BANC_LOAD                       = 0x80c06dd0; /* BancLoad */
WINDOW_SET_MESSAGE              = 0x806a8740; /* WindowSetMessage */
DUNGEON_ADD_SMALL_KEY           = 0x83244110; /* DungeonAddSmallKey */
DUNGEON_SET_BOSS_KEY            = 0x832440e0; /* DungeonSetBossKey */
DUNGEON_SET_MAP                 = 0x83244080; /* DungeonSetMap */
DUNGEON_SET_COMPASS             = 0x832440b0; /* DungeonSetCompass */
BOOLEXP_EVALUATE                = 0x803b9d20; /* BoolExpEvaluate */
BOOLEXP_COMPARE_ENUM_ORDER      = 0x80a27490; /* BoolExpCompareEnumOrder */
SHOP_IS_SOLD_OUT                = 0x80ba8f30; /* ShopIsSoldOut */
GAMEDATA_FIND_STRUCT            = 0x80f1bc60; /* GameDataFindStruct */
GAMEDATA_GET_BOOL               = 0x805ba6c0; /* GameDataGetBool */
GAMEDATA_GET_INT                = 0x805bbb00; /* GameDataGetInt */
GAMEDATA_GET_ENUM               = 0x805bc6e0; /* GameDataGetEnum */
GAMEDATA_SET_BOOL               = 0x806fcfa0; /* GameDataSetBool */
GAMEDATA_SET_INT                = 0x80bce7d0; /* GameDataSetInt */
GAMEDATA_SET_BOOL_BY_HASH       = 0x806b1500; /* GameDataSetBoolByHash */
GAMEDATA_SET_ENUM_BY_HASH       = 0x803b7a20; /* GameDataSetEnumByHash */
EVENT_REQUEST_INIT              = 0x80d5c9a0; /* EventRequestInit */
EVENT_REQUEST                   = 0x80d5d2b0; /* EventRequest */
ACTOR_SET_POSITION              = 0x80964000; /* ActorSetPosition */
ACTOR_SET_TRANSFORM             = 0x80c55730; /* ActorSetTransform */
FRAMEWORK_FRAME                 = 0x83b11420; /* FrameworkFrame */

/* --- globals --- */
CAMMGR_SLOT                     = 0x84c40ed8; /* CameraManagerSlot */
POUCHMGR_PTR                    = 0x84e28a30; /* PouchMgrPtr */
GAMEDATAMGR_PTR                 = 0x84e33e48; /* GameDataMgrPtr */
EVENTMGR_PTR                    = 0x84e443e0; /* EventMgrPtr */

/* --- hook sites used by KaeGae Core (resume = site + 4) --- */
HOOK_VIEW        = 0x806841c8;  /* in the camera view function, right after the view matrix is written: ldr x8, [x19, #0x20] */
HOOK_VIEW_RET    = 0x806841cc;
HOOK_MOVE        = 0x82bed710;  /* the movement update's first instruction: pacibsp; x0 = actor */
HOOK_MOVE_RET    = 0x82bed714;
MOVE_SECOND_RET  = 0x82bed718;  /* after the movement update's second instruction (str d10, [sp, #-0x80]!) */

/* --- free memory claimed by KaeGae Core (registry/33fa6c2c.toml) --- */
KP_HOOK_SLOTS    = 0x84e4fb00;  /* KaeGae Core: one 8-byte function pointer per hook point, set by the module */
