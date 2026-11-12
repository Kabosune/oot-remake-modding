# What sloperinaGZ found (and what we can use)

[sloperinaGZ](https://github.com/PracticeROM/sloperina) is PracticeROM's gz-style practice menu for
this game. Its [`docs/FINDINGS.md`](https://github.com/PracticeROM/sloperina/blob/master/docs/FINDINGS.md)
is a long, careful record of how the game's data works, on the same build as this repo (E0F3CCFA).
This page is our summary of the parts that matter for mods here, read from their repository at
commit `cad5995` (9 November 2026, release 0.0.3), with later sections for 0.0.4, 0.0.4.1 and
0.0.4.2.

- **Everything below is their finding, not ours**, unless the "Checked here" column says otherwise.
  Go to their document for the detail, the method and what they tried that didn't work.
- Their code is GPL-3.0 and this repository is MIT. Use the facts, don't copy their code into a mod here.
- Addresses are rewritten to this repo's form: `address = their main+offset + 0x80020000`.

"Matches ours" means the address or offset agrees with something found here independently
(the address map, the structures page or the script-command table).

## Functions

| Address | What | Checked here |
|---|---|---|
| `f_806d2530` | Physics controller ChangePosition (vtable `0x84c54f10` slot `+0xe8`): keeps the rotation, sets the translation, then updates attached bodies through slot `+0x250` (`0x806d23a0`) | Matches ours (`CCT_CHANGE_POSITION`) |
| `0x82920120` | `OneShotPhysicsCctChangePosition` execute, follows the controller chain below | Matches our command table |
| `f_80178d40` | `(body, bool)`: switch a controller body's collision off / on (the game's ForceNoHit). Locks the body and queues the filter change. State: body `+0x70` bit 11 | |
| `0x8297f0d0` | `OneshotChangeForceNoHitMode` execute, which calls it | |
| `f_8014dbe0` | Set a controller body's linear velocity `(body, vec)`: locks the body and queues it. Current velocity is at body `+0xe0` | |
| `0x82acba20` | `QueryPhysicsCctIsOnGround`: property `+0x48`, result pointer at `+0x40 + 8 × [+0x58]`, on ground when result `+0x10` is 0 | Matches our command table |
| `f_80183d20` | GameData GetInt `(mgr, &out, hash)` | |
| `f_80183b70` | GameData SetInt `(mgr, value, hash)` | |
| `f_8112d570` | AddPouch (give an item), called the way `OneShotAddOrRemovePouchContent` does | |
| `f_833c4fa0` | Remove from pouch `(pouch mgr, &name, count, 0, 0, 0)` | |
| `f_82e16c80` | Create one equipment slot on Link `(equipment component, slot)`; reads `PlayerStatus.Equip*` | |
| `f_80f401b0` | Re-apply all of Link's gear `(owner, 0)` | |
| `f_80a97ff0` | HUD screen "refresh contents" (virtual method 98). Every UI screen has one at vtable `+0x310` | |
| `f_80857240` | UI manager: screen by hash `(ui mgr, hash)`; HUD = `0x5c7f1c3c` | |
| `f_80b1b980`, `f_80b1ba70` | Pause manager: request / release a pause type (arguments not traced by them) | |
| `0x832fb1a0` | `SeqOneShotRequestEvent` execute: how their warp asks for `Dm_SY_BancChangeGo` | Matches our command table |
| `0x827f3e60` | `ExecutePlayerDebugMove` slot 29: not an empty stub; calls `f_80953270` with request `0xF` on a player component. Untried | Matches our command table |
| `0x83b700a4` | Runs every frame: locks GameData, applies its command queue (`f_80bb9980`), tail-calls the unlock at `0x83b700dc`. **sloperinaGZ hooks that tail call** | Their IPS patches it ([memory map](memory-map.md)) |

## Globals

| Address | What | Checked here |
|---|---|---|
| `0x84c9e180` | GameData manager slot | Matches ours |
| `0x84c9e098` | UI manager slot: screen count `+8`, screen array `+0x10` | |
| `0x84eb8068` | `[[this]+0x68]` = the gameplay camera: `+0x38` position, `+0x44` look-at, `+0x130` vertical FOV in radians (0.8727 = 50°), `+0x134 / +0x138 / +0x13c` sin / cos / tan of half of it, `+0x140` aspect, projection scales at `+0x9c` and `+0xb0` | Eye / target offsets match our camera view; the path and the FOV fields are new to us |
| `0x84ea4ba0` | Frame counter. Keeps running in the game's own menus | |
| `0x84eb7e38` | Pause manager slot | |
| `0x84eb0d90` | Actor manager slot | |
| `0x84eb7648` | Scene manager slot: `[[this]+0x1f0]` = current scene | |
| `0x84eb7e60` | RomConfig instance | |

## Objects

**Link's physics controller.** `property = [[[[[actor+0x270]+0x50]+0x20]+0x10]+8]` (vtable
`0x84c54f10`, "CharacterProperty"), `body = [property+0x20]` (vtable `0x84c54658`). The chain matches
ours. The body is what `f_80178d40` and `f_8014dbe0` take.

**Link's position is copied in several places**, and most copies are rewritten by the game every
frame, so writing them does nothing lasting. The velocity on the actor (`+0x388..+0x390`) is output
only. Use the controller's ChangePosition.

**Fall damage.** The game tracks where a fall started: player component `+0x18e0` is the peak height,
and the base component's `+0x189c` is the fall distance, `max(origin y − actor y, 0)`, computed at
`0x804a4a10`. Resetting those while Link is being moved, plus zeroing the body's downward velocity,
gave them a gentle landing with no damage after a levitate (confirmed in game by their user).

**The component at `[[actor+0x270]+0x2b8]` is the generic Life component** (vtable `0x84b6c460`, its
name string is "ライフ"): current life object at `+0x1c10`, max at `+0x1c18`, value s32 at `+8`.
Enemies have it too. Our structures page calls that vtable the "player-type actor" and reaches Link
through it; their reading says it is not Link-specific, which fits our note that others share it.

**Actors.** The live actors are a red-black tree at `[mgr+0x38]` under the mutex at `mgr+0`. Per
actor: name `char*` at `+0x20` (`"Enemy_Gibdo"`), state at `+0x2c` (below 2 = not live; 6 or 3 =
waiting to appear, 4 or 5 = appeared; 7 to 11 = dying or gone), position at `+0x31c` and rotation from
`+0x328` (both match ours).

**Pause manager.** A pause is a request count above 0 on one of 20 named pause types (0x20 bytes
each, count at `+0x1c`, ID = MurmurHash3 of the name). Raising a count from outside behaved like the
game's own request in their tests:

- `EventDisableController` (`0xd468c7d1`): Link ignores the controller while the world keeps running.
- `GamePause` (`0xba597383`): everything stops and the game keeps drawing, but some objects vanish.
- `DebugPause`, `ClickPause`: look like developer leftovers, untried.

The `Sequence_*Pause*` GameData values only keep count for the sequence graphs; writing them does
nothing useful.

**Scene managers.** The current scene holds 41 named components at `[scene+0x58]`, among them
`WarpMgr`, `DungeonMgr`, `OcarinaMgr`, `NaviMgr`, `NpcMgr`, `TimerMgr`, `StaticCompoundBodyMgr`.
`NaviMgr` keeps a per-frame copy of Link's transform (rotation `+0x894`, feet `+0x8b8`, velocity
`+0x8dc`): read-only, but a stable way to read where Link is.

## GameData (save fields)

- Every saved value is a GameData field keyed by MurmurHash3_32 (seed 0) of its name. The full list
  of about 15,000 fields with types and defaults is in `GameData/GameDataList.Product.110.byml.zs`.
  They have recovered names for 7,161 of them (`data/` in their repository).
- Field objects by type: Int / Float 0x28 bytes with the value at `+0x1c` **and a copy at `+0x20`**
  (write both); Bool 0x18 bytes, value `+0x16`, copy `+0x17`; Enum 0x38 bytes, value = hash of the
  choice name. Header: reset bits at `+0x08`, save file index at `+0x10` (−1 = not saved).
- Name patterns: `PouchData.<item>.StockNum` and `IsGet.<item>` (an item needs both to show),
  `PlayerStatus.EquipWeapon / EquipShield / EquipArmor / EquipBoot / EquipOcarina`,
  `HavePlayedEvent.<event>`, `Step_<quest>`, `DungeonInfo.<Dungeon>.IsGetMap / IsGetCompass / IsGetBossKey`.
- Pouch data and `PlayerStatus.Equip*` are only data. What Link holds is a separate object made by
  `f_82e16c80`; upgrades are pouch items (`Item_Wallet_Medium`, ...), not just numbers.
- Save files: `progress.sav` is `(hash, value)` pairs from offset 0x20, no checksum.

## Changing maps

An exit is a `FieldAndDungeonEntranceEventRequestActor` that requests the event `Dm_SY_BancChangeGo`
with `NextBanc`, `NextStartPos` and an arrival event. That only writes GameData
(`Sequence_ReservedNextBanc`, `...NextStartPosName`, `...BootEventName`, `...EventStarterName`), and
the Event sequence turns it into the map change. Warp-song pads have no exit actor: they arrive with
an empty starter and `OcarinaWarp_Arrive`.

## Debug leftovers

- Scene selector: almost certainly compiled out (the config build is hard-coded to `Product`).
- `ExecuteDebugDraw*` commands: names kept, bodies are a bare `ret`. The renderer's debug shaders
  and layers are still listed.
- Player debug move: the one lead that may still work (see the function table).

## New in 0.0.4 and 0.0.4.1 (read 10 November 2026)

0.0.4 draws its menu the way the game draws its own UI; 0.0.4.1 adds a dive test. Their write-up is
`docs/NATIVE_UI.md`, plus sections 5.21 and 9.6 of `docs/FINDINGS.md`. The facts below are theirs,
retold; their code is GPL-3.0, so it is read for understanding and not copied here. None of this
has been checked by us.

**Drawing with the game's own parts.** They draw on the GPU just before the game presents a frame
(the same `nvnBootstrapLoader` hook KaeGae Core uses for its rectangles), with the game's UI
shader, fonts and pictures read from the player's own RomFS at start. Nothing needs a game address,
so one build serves 1.0.0 and 1.1.1, and it keeps drawing while the game is paused. They looked at
driving the game's UI library (Layout2) and set it aside: no symbols, an address per version for
every function, and it only draws inside the game's frame.

| What | File in RomFS | Notes |
|---|---|---|
| UI font | `Font2/Scalable/ClarimoUDPE-Regular.Nin_Ounce_NVN2.bfotf.zs` (also `-DemiBold`, `-Light`) | OpenType (CFF) behind a scramble |
| Button glyphs | `Font2/Scalable/External.Nin_Ounce_NVN2.bfotf.zs` | private use area: A to ZR are `U+E040` to `U+E047`, + `E04B`, - `E04C`, sticks `E050` to `E05F`, D-pad `E060` to `E065` |
| UI shader | `Layout2Shader/MergeShader.Product.100.Nin_Ounce_NVN2.bfsha.zs` | BFSHA 9.1.1; 121 programs picked by 55 options; attributes `_p0`, `_u0` |
| UI pictures | `UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.bntx.zs` | 878 textures, 65 MB packed, 244 MB unpacked, no dictionary |
| Item icons | `UI/Tex/Icon/<name>.bntx.zs` | one ASTC 4x4 texture each, about 13 MB in all |
| UI layouts | `UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.blarc.zs` | SARC of `.buil` files (`BFFH`), no public tools |

- Font scramble: the file is `u32 magic, u32 size, font`, every big-endian word XORed with one key.
  The key is word 1 XOR (file size - 8); for this game's fonts it is `0xA6018502`.
- A BNTX texture record (`BRTI`): format `+0x1c`, size `+0x24`, packaged layout `+0x34`, channel
  sources `+0x58`, name `+0x60`, level offsets `+0x70`. The data is block-linear, and the Switch 2
  ("Ounc") orders the sectors inside a block differently from the Switch 1.
- Memory is the limit. The game's heap gave them one block of about 10 MB and refused 15 MB, so big
  pictures are decoded a piece at a time and shrunk into a small atlas.

**The scene's depth (found on 1.0.0).** A Depth32F texture at the render resolution, a new texture
object every frame or two. Right after its depth pre-pass the game copies it with
`nvnCommandBufferCopyTextureToTexture`; that call is the place to read it, because HUD targets
reuse its memory later in the frame. The camera's projection is at camera `+0x90` (near `+0x128` =
0.1, far `+0x12C` = 25000, vertical FOV `+0x130`, aspect `+0x140`). They use it to hide health bars
and collision lines behind the scenery and behind Link.

**What writes Link's position (1.1.1).** A position written from outside doesn't hold because the
game stores it again afterwards: the collision resolver at `main+0x18D2C18` and `+0x18D2C20`, and
the body at `main+0x180EA24` (X and Y) and `+0x180EA2C` (Z). Link's body centre sits 0.585 above
his drawn position. Their lock X / Y / Z options patch those four stores.

**1.0.0.** Data slots they compared (frame counter, camera pointer, actor manager) sit `0x70460`
lower than in 1.1.1, and the actor fields we use (`+0x270`, position at `+0x31C`) are the same in
both versions. Useful when a symbol pack for 1.0.0 is made.

**Dive test (0.0.4.1, their measurements on 1.1.1).** Gravity about 28 units/s², falling speed
tops out at 60 units/s.

What this means for KaeGae: text and pictures in Core (the Mods menu, Mouse Grab's fairy cursor)
can follow the same route, a font read from the game's own files and blended quads drawn at
present time, written from scratch. Whether to use the game's UI shader or a small shader of our
own is still to decide.

## New in 0.0.4.2 (read 11 November 2026)

Release [v0.0.4.2](https://github.com/PracticeROM/sloperina/releases/tag/v0.0.4.2), commit `0cc9c8f`,
compared against 0.0.4.1. Their IPS patches didn't change, so **no new game addresses**: the new
facts come from the game's files and GameData. Retold from their `docs/FINDINGS.md`,
`docs/NATIVE_UI.md`, `docs/BUILDING.md` and commit messages; none checked here.

**Hooks that share main's import slots with other add-ons (their PR #18, then a fix).** This is the
one that matters most for KaeGae: sloperinaGZ and KaeGae Core both swap main's GOT slots for
`nvnBootstrapLoader` and the five `nn::hid::GetNpadStates` overloads.

- Before 0.0.4.2 sloperinaGZ wrote its wrapper over the slot and called the sdk's function itself,
  so if its module initialised after Core, **Core's wrappers were cut out** (no drawing, no input
  from Core). Now each wrapper calls what the slot held before when that's code in another module.
  So Core and sloperinaGZ 0.0.4.2 can run together whichever starts first. Not tried in a game here yet.
- Their write-up of the trap, which Core's `kp_wrap_import` (`api/core/imports.c`) already avoids
  the same way: main has no `BIND_NOW`. Until the game's first call to an import, its slot points at
  main's PLT0 (`main+0x3c41c50`, which is `0x83c61c50` here), and PLT0 only works when entered from
  that import's own stub (x16 = the slot). A wrapper that calls it gets rtld's "Unresolved symbol" and a
  jump to 0. Or, if x16 still happens to hold the slot, rtld binds it and writes the sdk function over the wrapper.
  So a slot pointing into main is never chained to: call your own import of the function instead.
- The difference between the two: they decide "another module" with `svcQueryMemory` (executable
  memory in a region that doesn't hold main); Core checks the address against main's range. Same answer
  for real modules.
- Not covered by their change: FPV Drone's patches on the `br x17` of each `GetNpadStates` stub
  ([memory map](memory-map.md)) run after the stub has loaded the slot, so it would call whatever
  wrapper sits in the slot. Whether FPV Drone and sloperinaGZ get along is untested.

**What an air wall does to Link: the collision filter.** The rigid body's `EnableLayerHitMask`
alone (what 0.0.4.1 used) gets it wrong. The filter is `Phive/Config/PhiveConfig.byml`, in
`Pack/Bootup.Nin_Ounce_NVN2.pack.zs`:

- A shape's layer mask = `EnableLayerHitMask` (none = `HitAll`) AND each of its `MaterialPresets`'
  `LayerHitMaskEntity`. The sub-layer mask is built the same way from `EnableSubLayerHitMask` and
  `SubLayerHitMaskEntity`. Masks are named in `LayerHitMaskEntityCollection` /
  `SubLayerHitMaskEntityCollection`, bit n = entry n of `LayerEntityCollection` / `SubLayerEntityCollection`.
- Link on foot is layer `Player`, sub-layer `Unspecified` (Player_Base
  `CharacterMatterRigidBodyParam/Player`). Climbing, he is `ClimbingPlayer`.
- A wall stops him when both masks have his bits: 1067 of the 3504 walls. 246 of those carry the
  `Unridable` shape tag and **push him off** (he can't stand on them): `FldObj_AirWall_Player_Unridable`,
  the moving `PushAirWall_Box`, e.g. the ledge in front of the Forest Temple as a child. The other 821 are
  **plain invisible walls** (`FldObj_AirWall_Player`, `_Cylinder`, `_GenerateNavMesh`, `Common_Cube`,
  `HitBomb_Cube`, `ExcludeNpc*` and more), e.g. round the rocks in the Lost Woods.
- They don't touch him on foot: `HitOnlyCharacter` walls (enemies, NPCs, doors' `PushAirWall_DoorFront`),
  camera walls (`Material_AirWall_ForCamera`), and walls whose rigid body or presets leave out
  `Unspecified` (animal, cucco, horse, rolling rock, hookshot, bomb, hiding-hole walls).
  `FldObj_AirWall_ClimbPlayer` stops him only while he climbs.
- Their `tools/airwalls.py` writes this out as each wall's `"link"`: `push`, `block` or none
  (`data/airwalls.json`). Data from the game's files, fine to regenerate ourselves.

**GameData.**

- The game's menus (Plus, Minus) start fading in with `Sequence_IsPreGamePause` (`0xBF5BF25F`, bool) /
  `Sequence_PreGamePauseRequestCount` (`0xEF935C2D`, int), about 60 ms before `Sequence_IsPause`
  (`0x604AEBE1`) / `Sequence_GamePauseRequestCount` (`0x64A61098`). Waiting for `IsPause` left their HUD
  over the menu for a few frames. Read-only use (the counts belong to the sequence graphs, see above).
- Amiibo masks: `Armor_Child_Mask_Amiibo0` (Fairy-Kid Mask) and `Armor_Child_Mask_Amiibo1` (Princess
  Mask). Their own equipment slot (`Pa_HeadEquip_03`, `SpecialDeal: amiibo`), never on an item button.
  Given like the other masks: `PouchData.<name>.StockNum` and `IsGet.<name>`.
- The Great Fairy of Power's spin attack upgrade gives no item. The only trace in the save is
  `HavePlayedEvent.Dm_FairyFountain_Power` (`0x8FA2608E`). Not yet confirmed in game by them.

**The game's heap, again.** More numbers on how little there is to spare:

- Decoding `Common.bntx` takes an 8 MiB zstd window + 1 MiB to slide it + 0.6 MiB for the decoder. A
  tester's decode failed part way on the decoder's own 17 KB and 41 KB blocks while the game was
  loading. Their fix: all of the decoder's small allocations come from one arena taken at the start.
- Gz-style CPU panels need 12 MB at 3x (23 MB with the see-through background), so they're now taken
  one block per panel and only while used.
- Out-of-memory work is retried 10, 30, 60, 120 s later, then every 5 minutes (8 tries at most).
- Pictures made once are cached on the SD card (`sloperinaGZ/cache/pictures-<version>.bin` 4.8 MB,
  `icons-<version>.bin` 1.2 MB), checked by a header and a checksum. SD reads and writes go through a
  64 KiB buffer of the module's own, because the file system locks the memory a call uses.

**Smaller things.**

- `svcQueryMemory` per checked read was a hot spot. Keeping 4 recent regions (cleared each frame)
  turned 2000 alternating reads into 2 queries.
- GPU text in one quad a character: an RG8 atlas (luminance, coverage) with the shadow baked into the
  glyph. Their command memory holds about 4000 quads a frame, so 2000 are kept back for the menu. (Their
  numbers, untested in game by them.)
- A frame whose drawing slot the GPU hadn't finished within a second turned their drawing off for good.
  It now waits 0.1 s, skips that frame's overlay, and gives up only after 5 s of busy slots.
- Searching the whole heap for Link's equipment component is slow enough to feel. After a miss they
  wait 300 frames before searching again.
- The installer knows the new data folders: `%APPDATA%\lichii` (Lichii build 150+), `%APPDATA%\fritchii`
  (Fritchii v5.8+), `%APPDATA%\eden` for older Lichii / Fritchii and Eden.

What this means here:

- KaeGae Core needs no change for sloperinaGZ 0.0.4.2. Worth a test in Fritchii with both installed
  (Core in `subsdk1`, sloperinaGZ in `subsdk9`): Core's menu and input should still work, and so should theirs.
- If Core (or a mod) hides its overlays while the game's menus are open, go by the pre-pause flags
  rather than `IsPause`, or they'll sit over the menu for a few frames.
- Core takes its memory from the same small heap. Keep its blocks small and taken at start, and say in
  the log when one is refused.

## Working with Lichii

- Lichii's GDB stub (Emulation > Configure > Debug, port 6543) gives read and write watchpoints.
  With it on, the game waits at boot for a debugger; Lichii leaves the game halted when a debugger
  detaches, so continue and close the socket instead; turn it off afterwards.
- Patches are read at game start only (the same as we found).
- Their method note worth copying: ask the game's own scripts first. An event flow shows which
  command and parameters the game uses for the thing you want to do.

## Ideas this opens for the mods here

None of these are built or tested.

| Mod | Idea | Uses |
|---|---|---|
| FPV Drone | Make Link ignore the controller while the drone flies by raising the `EventDisableController` pause count, instead of filtering input ourselves | pause manager |
| FPV Drone | No fall damage when a carried Link is dropped: reset the fall history and downward velocity on release | fall damage fields, `f_8014dbe0` |
| FPV Drone | Carry Link through walls cleanly: switch his controller's collision off while carried | `f_80178d40` |
| FPV Drone, First Person | A live FOV setting without a romfs mod | camera `+0x130` and the values derived from it |
| First Person | Child / adult eye height from the game's own state | our `f_804d6db0`; their `LINK_SIZE` by age is from the map name |
| any | A simpler way to read Link's position and velocity | `NaviMgr` copy |
| Slopped Up Sloperina | An air wall view that tells pushing walls from blocking ones, from our own export of `PhiveConfig.byml` and the maps' walls | 0.0.4.2's collision filter rule |
| Slopped Up Sloperina | Amiibo masks and the spin attack upgrade in an inventory page | GameData names above |
| any bigger mod | A `subsdk9` module instead of code caves: real C, no size limit, one small hook in main | their `docs/BUILDING.md` |
