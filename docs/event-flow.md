# Event flows: cutscenes and dialogue scripts

What is known from reading the game's data (1.1.1). Nothing here has been tried in game, and the
code that runs these scripts has not been read.

## Where they are

- `Event/EventFlow/*.bfevfl.zs`: 914 scripts, zstd-compressed (dictionary ID 1, `zs`) BFEVFL files
  (magic `BFEVFL`, the Nintendo event-flow format; BOM `FF FE`, sections `DIC `, `EVFL`, `STR `,
  `RELT`). Total about 8 MB uncompressed. Smallest ~90 bytes (`Meet_GreatFairy`), largest
  `SageOfSpirit_FocusOnGimmick` (43 KB), `MiniGame_Fishing` (38 KB), `Npc_Hylia_Dampe_001` (37 KB).
- Names: `Dm_<Place>_<number>` (demo cutscenes, plus `_Effect` companions), `Npc_<Name>_<number>`
  (townspeople), `SubEvent_*` (quests and item hand-overs, e.g. `SubEvent_GetSwordBigGoron`,
  `SubEvent_GetFireArrow`, `SubEvent_GetIceArrow`, `SubEvent_GetEponaSong`), `MiniGame_*`,
  `Meet_*`, `AllSage`, `DungeonHint_CommonModule`.
- Around them in `Event/`: `EventSetting/EventSettingComponent/*` (200 `GameEventBaseSetting`, 33
  `ExceptionalActorSetting`, 11 `GameFunctionSetting`, 7 `EventPlayEnvSetting`, others) and
  `EventSettingComponentList` (109), `GameEventEffectSetting` (8), `GameEventSoundSetting` (11),
  `Movie` (26), `ResidentEventList` (1).
- The spoken lines are separate: `Voice/Resource/Stream/<Lang>_EventFlowMsg-_<Dm_Name>--..._Text_N_b.bwav`,
  one per message per language; the message texts are the MSBT files (see `docs/romfs.md`, Text).

## What a script can do

Counting the action and query names in the string tables of all 914 files (a count of files that
mention the name, not of uses):

| Name | Files | Meaning (from the name) |
|---|---|---|
| `EventTriggerSetGameDataBool` | 397 | set a story flag |
| `EventQueryIsGameDataBool` | 353 | branch on a flag (`...BoolExp`: 179, a flag expression) |
| `EventTriggerSetGameDataInt` / `EventQueryIsGameDataInt` | 54 / 61 | counters |
| `EventPlayerPlayASForFlowchart` | 323 | make Link play an animation |
| `EventMoveToTargetPosCamera` | 298 | camera moves |
| `EventTriggerParticipateEvent` | 230 | an actor joins the event |
| `EventWarpToTargetPosAndRot` / `EventPlayerWarpToTargetPosAndRot` | 209 / 149 | move an actor / Link inside the scene |
| `EventQueryPlayerIsEquipArmor`, `...IsEquipMask`, `...IsChild` | 202 / 74 / 78 | react to Link's gear and age |
| `EventQueryTalkChoice2` / `3` | 149 / 71 | dialogue choices |
| `EventQueryTimeDivision` | 52 | time of day |
| `EventQueryIsExistInPouch` | 56 | has an item |
| `EventTriggerStartBgmSimple`, `...StopInGameBgm` | 80 / 84 | music |

657 distinct `Event*` names exist in total. Almost every script also lists the same set of
parameter names (`ActorName`, `InstanceName`, `MessageId`, `ChoiceLabel1..4`, `ASName`, `Event0..N`
entry points), which are the argument names of those actions and queries.

## Story flags (`docs/data/story-flags.tsv`, `tools/evflags.py`)

A standard BFEVFL reader (the `evfl` Python package) reads all 914 scripts without error: 74,631 events in
all. `tools/evflags.py` lists the flags they set (`EventTriggerSetGameDataBool` / `...Int`) and check
(`...IsGameDataBool` / `...Int`): 2,423 names, of which 1,329 are both set and checked by scripts, 533 only set
and 561 only checked (those are set or read by code or by other data, not by a script). The table gives
each flag with the scripts that set it and those that check it.

Flag names are grouped by place or person (`HaveTalked*` 404, `Npc*` 361, `MiniGame*` 197, `KakarikoVillage*`
110, `NaviHint*` 100, `KokiriForest*` 68, `SubEvent*` 62, `GerudoFortress*` 61, `Market*` 53,
`GetSwordBigGoron*` 43 ...). A few entries are not real names but placeholders a script passes on from its
caller (`GameDataName`, `FlavorTalk_GameDataName`, `SimpleShop_Price`); the real names are in the scripts that
call it. Checks written as expressions (`...BoolExp`) are not in the table. Which flag means what in play is not
checked, except where the name says it.

## What it means for mods

- A story flag is set by an action in a script and its name is in the script, so the table above says
  where to look for a flag. How the game stores the flags (the save data side) is in code and not read.
- Dialogue text changes need no script change (see Text in `docs/romfs.md`); changing what a
  script does means rewriting its BFEVFL, which no tool here does yet.
- Not known: how the code runs the scripts, the exact binary layout beyond the section names, and
  whether the game accepts an edited script from a mod.
