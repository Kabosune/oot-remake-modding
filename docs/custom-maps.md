# Custom maps: what a scene is made of

Research for custom maps (for example: go into the Deku Tree, arrive in a map of your own). Checked on 1.1.1
(12 November 2026) from a dump, using Inside the Deku Tree as the example. Names, sizes and versions only;
no game files are in the repo. See also [warps.md](warps.md) (scene changes, spawn points) and
[engine.md](engine.md#maps-are-bancs).

## One scene, many files

Inside the Deku Tree, by romfs folder:

| What | Where | Notes |
|---|---|---|
| Scene settings | `Banc/GameBancParam/InsideTheDekuTree.game__banc__GameBancParam.bgyml` | `Banc.Main`, `DungeonParam`, `FoliageScene`, `HeightMapParam` (bounding box, layers), bake switches, `OptimizeChangeBancUnits` (neighbour scenes to preload) |
| Placement | `Banc/InsideTheDekuTree/InsideTheDekuTree_Static.bcett.byml.zs` (475 actors), `..._Dynamic...` (1,615) | Static: areas, anchors, doors, enemies, items, the 5 terrain chunks. Dynamic: the level geometry pieces (`Land_*`) |
| Spawn points | `AoC1/Banc/BancBasedResource/StartPos.byml.zs` and `StartPos` actors in the placement | see [warps.md](warps.md) |
| Terrain chunks | actors `InsideTheDekuTree_01` ... `_05` (`Pack/Actor/`, parent `TerrainSceneManual`) | each carries a `.tscb`, collision as a `TeraMesh` (`Work/Phive/Shape/TeraMesh/InsideTheDekuTree_01/X0_Z0.tmb`, 125 x 125 m) |
| Terrain data | `TerrainArc/InsideTheDekuTree_01` ... `_05`, `_B01` (741 files) | mostly baked AO / GI per mesh (`.extm`, with `child`, `reverse`, `dream` variants); `_B01` has `.hght` / `.mate` height and material maps |
| Geometry pieces | `Pack/Actor/Land_*.pack.zs` + `Model/<Project>.<Name>.bfres.zs` + `Tex/*.bntx.zs` | e.g. `Land_Deku_TreeRoot_B_01`: `ModelInfo` (`ModelProjectName` `Land_Deku_Room_A`, `FmdbName`), `PhysicsRef` → `ControllerSetParam` (parent `Ptm_DgnObjStatic_01`) → `ShapeParam` → `PhshMesh` |
| Pre-built static collision | `Phive/StaticCompoundBody/InsideTheDekuTree/InsideTheDekuTree.Nin_Ounce_NVN2.bphsc.zs` (2.6 MB; 1,772 `.bphsc` in the game) | the scene's static pieces baked into one compound, as in TotK. A placement with `Bakeable` and no entry in it got no collision (test B, 12 Nov) |
| Collision | `Phive/Shape/Dcc/<Name>__Physical.Nin_Ounce_NVN2.bphsh.zs` (also `__Airwall`, `__StairSlope`, `__StairStep`) | Havok tagfile with an `hknpMeshShape` |
| Navmesh | `Phive/NavMesh/InsideTheDekuTree.Nin_Ounce_NVN2.bphnm.zs` | for enemies / NPCs |
| Lighting | `Bake/Light/InsideTheDekuTree.bklight.zs`, `Bake/Probe/Scene/InsideTheDekuTree/*.bkprb.zs` | baked light and probes |
| Other | `PreComputedCulling/InsideTheDekuTree/Boxes.bbox.zs`, `Foliage/Placement/Scene/InsideTheDekuTree/*`, `Game/AdjacentRoomsInfo`, `Game/VolumeStatsAABB`, `Game/BakeSceneLayerConfig`, `Scene/Component/DungeonParam`, `WorldMgr/WorldParam`, `System/GameGraphics/VolumeFogAreaParam/*`, `UI/CustomTex/Map/Dungeon/*` (pause-menu map) | |

The most used geometry pieces in the Dynamic file: `Land_Deku_CaveProp_B_09` (169), `Land_Deku_Ground_A_02` (134),
`Land_Deku_Ground_A_03` (74). Placement spans x -83 to 45, y 47 to 140, z -20 to 91 (metres).

## Format versions

| Format | Version seen | Tooling |
|---|---|---|
| `.bfres` | `FRES`, version bytes `00 04 0a 00` (10.4); textures not embedded, material names point at `Tex/*_Alb`, `_Nrm`, `_Rgh` | Switch-Toolbox opens them ([romfs.md](romfs.md)); writing this version for this game not tried |
| `.bntx` | version `01 01 04 00`, platform tag `Ounc` (not `NX  `) | Switch 2 texture layout; a writer for it not tried |
| `.bphsh` | `Phive` header, Havok `SDKV20250200` (2025.2) tagfile, `hknpMeshShape` | no public writer found (12 Nov 2026). The [zeldamods wiki page](https://epd.zeldamods.org/wiki/Bphsh) covers Havok 2023.2 |
| `.bphnm` | `Phive` header | not looked at |
| `.tscb` | `TSCB` version `0d 01` | TotK-like |

## Ways in, easiest first (proposed)

1. **Send a door somewhere else.** Change `NextBancParamName*` / `NextStartPosName` on the
   `FieldAndDungeonEntranceEventRequestActor` in `KokiriForest_Child_Static`, or hook the scene change in Core.
   [`tools/byml.py`](../tools/byml.py) rewrites whole BYML files (strings, added or removed actors), keeping each
   value's type; it reads and rewrites every placement file tried with the same values.
2. **Your own layout from the game's pieces.** Rewrite a scene's placement: remove, move and add `Land_*` actors.
   No new formats.
3. **Collision without Havok.** A `Phive/ShapeParam/*.bgyml` can describe its shape as primitives instead of a Havok
   mesh: `Box` (`HalfExtents`, `OffsetTranslation`, `Center`, `MaterialPresets`) and `Polytope` (convex shapes) were
   seen (`FldObj_AirWall_Common_Cube`, `Obj_TBox_A_02`). So a block map's collision can be a list of boxes in one
   actor's ShapeParam, with no `.bphsh` at all. Round-1 tests: [mods/custom-map-tests](../mods/custom-map-tests/README.md)
   put 10, 1,425 and 9,375 boxes into `Land_Deku_TreeRoot_B_01` (layer `GroundHighRes` from its parent
   `Ptm_DgnObjStatic_01` in `Pack/ResidentCommon.pack.zs`, material preset `Material_Wood`). Untested in game yet.
4. **Your own model.** A new `Land_*`-style actor: pack + `.bfres` + `.bntx` + `.bphsh`. Needs writers for the
   three formats above; the plan would be to start from an existing piece as a template.

Unknown: which of the bake, culling, navmesh and foliage files a scene can do without.

### Collision: what the round-1 tests showed (12 Nov 2026)

- A newly placed **static** actor (no `MotionType`: tree root, air-wall cube) gets **no collision**, with or without
  `Bakeable`, with `PreActorSetting` `Anchor`, or with a Kinematic body on that actor type. Static collision most likely
  comes only from the scene's pre-built `StaticCompoundBody`. Re-checked with an unmissable 4 x 4 m air-wall platform
  marked by a chest (test B10): no collision.
- A newly placed chest (an actor that builds its bodies at load time) works normally.
- `MotionType` values are murmur3 hashes: `Static` 3498399415, `Dynamic` 3672686866, `Kinematic` 4269567940.
- In a ShapeParam of such an actor, boxes can be **resized** and parts **swapped** (polytope → box) and work in game;
  **adding** parts crashed in main's BYML object reader (`0x612760`), even with a bigger entry for the pack and a bigger
  `InstanceHeapSize`. Details: [mods/custom-map-tests](../mods/custom-map-tests/README.md).
- **At most about 1,024 parts per shape (B27–B29, 12 Nov):** 1,022 work, 1,031 don't: the actor isn't created at
  all (no crash, nothing in the log). Not the reach (B26: 1,425 tiles in 3 x 3 m) and not the actor heap (B25).
  A map's collision gets split into shapes of up to ~1,000 boxes.
- **Several hosts work together (B30–B32, 12 Nov):** the 48 x 48 Minecraft cut split into 729 + 699 boxes, one half
  on the closed body of `Obj_TBox_A_02`, the other on `Obj_TBox_A_01`'s (a second chest type, since chests of one type
  share a pack): both solid, normal load time. Each half alone also works (B31), so the cut's reach (48 x 48 m, 6 m up
  to 43 m down) was never the problem.
- **One chest, one map shape (B33, B34):** a new fifth body on the chest isn't added to the world, not even with a unit
  in the chest's controller: the chest adds only the bodies its code knows by name.
- **A host with no behaviour (B35–B38, 12 Nov): `Obj_Flag_A_01`**, a plain `GameActor` (`ActorLogicSimpleActor`, no AI,
  PreActorSetting `ActorOnly`) with one Kinematic body its controller adds to the world. It carries map boxes 15+ m away
  (B35); copies under **new actor names** work (B36: own pack, ActorParam, PhysicsParam, ControllerSetParam and shape,
  new rows in RSDB `ActorInfo` and `GameActorInfo`, which are sorted by `__RowId`, new size table entries). **The whole
  Minecraft map (9,397 boxes) on 14 such hosts works, performance fine (B38).** The flag's `CalcRadius` is 100 m; in B38
  all hosts stood at the entrance, with the map reaching ~120 m away.
- **Seeing it without new formats (B39):** the game's 1 m stone block `Land_SacredForest_Prop_A_06` placed once per
  collision box, scaled to it (uneven `Scale` in the placement, Dynamic file, `Bakeable`), shows the map's shape where the
  collision is; performance fine with 217 blocks. Textures are the block's own, stretched.
- **The closed chest's body works as a host (B22, 12 Nov):** `CloseBody` is a **Static** body the chest builds at
  load (shape `Body_Close` = `Obj_TBox_A_02__Tgt`). Given its own shape file (B19's setup: a new ShapeParam, the
  ControllerSetParam pointing at it, a new size table entry), boxes 15 m from the chest are solid. The open chest's
  body can carry 245 parts close by (B20), but a shape reaching 6+ m away makes the chest lose its Open prompt
  (B12–B17, B21): a chest-only problem.
- **Why adding parts crashed (found 12 Nov, confirmed by test B11):** there is no fixed part count. Every file inside a
  pack has **its own** size table entry, and for a `.bgyml` that entry is the memory for the file *and* the object the
  game reads out of it. B5 / B7 / B8 raised the pack's entry, never the ShapeParam's. See the next section.

### Size table entries of ShapeParams

The entry of every ShapeParam that has only primitives (2,478 files in 1.1.1) follows this, with a mean error of
9 bytes (max 183):

    entry ≈ 5,862 + file size + 176 per Box + 336 per Polytope + 173 per Capsule + 166 per Sphere
            + 173 per Cylinder + 12 per Polytope vertex + 8 per MaterialPresets name

(It predicts the chest's `Obj_TBox_A_02__Body_0` as 10,838; the table has 10,824.) What the tests needed by it:

| Test | Chest shape | Needs | Table gave | Result |
|---|---|---|---|---|
| B5, B7, B8 | 3 boxes + 4 polytopes | ~11,458 | 10,824 | crash |
| B9 | 3 boxes + 2 polytopes | ~9,534 | 10,824 | works |
| B11 | 3 boxes + 4 polytopes | ~11,458 | 15,560 (raised) | works |

So a shape can have any number of parts as long as its entry is raised. `build_tests.py`'s `shape_entry()` computes
it. Biggest entries in the game: `Obj_ForestTemple_FallingCeiling_A_01__Physical` 167,184 (236 polytopes). Rough
need for the Minecraft test map: about 400 KB (1,425 boxes), 2.6 MB (9,375). Whether the game's heaps take a shape
that big, and how much the built Havok shape needs from the actor's `InstanceHeapSize`, is still to test (B12: 400).

The size table in `main` (1.1.1, offsets in `main`; the repo's `0x80…` style adds `0x80000000`):

| Where | What |
|---|---|
| `0x31f5bf0` | resource system setup: the table's path `System/Resource/ResourceSizeTable.%s.%s.Nin_Ounce_NVN2.rsizetable` |
| `0x36c3b90` | reads a table: checks `RESTBL`, stores hashed entries (count `+0x8`, pointer `+0x10`) and named ones (`+0x18`, `+0x20`, 0xA4 bytes each: 160-byte name, size at `+0xA0`) |
| `0x36c3d30` | lookup (leaf, no prologue): `x0` table, `x1` → path string; CRC32 of the path, binary search in the hashed entries, then the named ones. Returns the size, or 0 |
| `0x196340` | the resource manager's size for a file: builds the path, then calls the lookup on each loaded table (list at `+0x760`, lock at `+0x730`) until one answers. Its only direct call of `0x36c3d30` is at `0x1964e0`; `w0` = size right after it (`0x1964e4`), the path's text at `[x29 + 0x18]` |

## Clearing a scene for a custom map (tests C, B40–B59, 13 Nov 2026)

Inside the Deku Tree turned into a blank slate for the Minecraft test map, one change per test (setups and results
in [mods/custom-map-tests](../mods/custom-map-tests/README.md)). Every step is a data file; no code (Core) needed.

| What | Where | Change | What it removed |
|---|---|---|---|
| Placed actors | `Banc/<scene>/<scene>_Static` / `_Dynamic` | Keep only the `StartPos` actors, clear `AiGroups`, `FarDeleteGroups`, `SimultaneousGroups`, `PlgGdTable`, `PhiveHeader.PlacementGroups` (test C) | The level's look, enemies, doors, room areas. Also its exit: leaving needs a save reload |
| Static collision | `Phive/StaticCompoundBody/<scene>/<scene>.Nin_Ounce_NVN2.bphsc.zs` | Replace with the game's empty compound, e.g. `DreamWorld/MorphaStage_X0_Z0`'s (B46; 16 such files, byte-identical unpacked, 53,264 bytes, every body section empty) | Walls, floors, climbable vines (static collision lives here, not in the placement) |
| Foliage | `GameBancParam` `FoliageScene`; `Foliage/Placement/Scene/<scene>/<scene>.LowTree.flnt.zs`, `.Ornament.flnt.zs` | Remove the `FoliageScene` line (B48; 34 of 80 scenes have none); replace `LowTree` and `Ornament` with a near-empty placement, e.g. `LostWood/LostWood_Child.LostWood_Child.Undergrowth8`'s (B54, B57; 56 bytes unpacked; the format number, 2 or 4, doesn't matter) | Moss, stones, grass, undergrowth (`FoliageScene`); climbable-vine leaves (`Ornament`); ferns (`LowTree`) |
| Height map | `GameBancParam` `HeightMapParam` | Remove the line (B55; 27 of 80 scenes, the boss stages, have none) | An abyss floor under the old ground (see below) |
| Preloading the next scene | `GameBancParam` `OptimizeChangeBancUnits` | Remove the line (B56; only 2 of 80 scenes lack it) | The Kokiri Forest preload within 30 m of the entrance. With a big map on top it froze the game once |
| Volume stats | `Phive/VolumeStats/<scene>/<scene>.bpvsts.zs` | Replace with a tiny one, e.g. `DeathMountainTrail/DeathMountainTrail_Adult_X0_Z0`'s (B58; 342 bytes unpacked; 1,065 such files in the game) | **The last walking limit**: Link couldn't go past the old level's space (the Deku Tree's is 1 MB unpacked) |
| Lighting | `GameBancParam` `WorldMgrName` → `WorldMgr/WorldParam/<name>` | Point it at `HyruleField_Child`'s `WorldParam` (B52) | The dark dungeon light. The scene gets Hyrule Field's time-of-day palettes, sky, sun and moon |

Changed in the tests but not needed: `VolumeStatsAABB` (`Game/VolumeStatsAABB/<scene>`, B53), the `HeightMapParam`
box (B42, B51), `RenderingMode` / `EnvSetName` (B49: the lighting comes from the `WorldParam`, not these),
`IsEnableBakeLight` and the scene's own palette (B43, B44, B50: brighter, but superseded by B52).

The map itself is 9,397 collision boxes on 14 copies of `Obj_Flag_A_01` under new names (B38), with one scaled 1 m
stone block per box to see it (B41). The hosts need their real model: with `Dummy` the posts vanish but so does the
collision (B59; the body binds to the model). Placing each host under the middle of its own part, 6 m below the
map's lowest block, with its boxes placed relative to it, hides them and keeps everything solid (B60).

### Abyss (void out) and other limits

The game's word for falling out of a level is **abyss** (`FallIntoAbyss`, with `_Mountain` and `_Whirlpools`
variants, `IsAbyss`, `AbyssType`, `ExecuteEventPlayerAbyss`, `ExecuteEventPlayerPostAbyss`, `ExecuteCameraAbyss`,
`AfterReturnAbyssInvincibleTime`); players call it a void out. Link is put back at his last safe spot, the restart
position (`ReturnToSafePos`, `ExecuteEventPlayerWarpSafePos`, `InvalidateRestartPos`, `QueryPlayerGetRestartPosAndRot`).
Names from `main`'s strings; the code around them hasn't been read.

What the tests showed (positions from Slopped Up Sloperina's x / y / z watches):

- **The height map sets an abyss floor.** With `HeightMapParam` in place, Link was sent back as soon as he went about
  12 m below the old ground (y 88–89 near the entrance, whose floor is y 101). Without it (B55) he fell to about y 66
  (8 m above the map's lowest block) before the abyss; with tiny volume stats as well (B58), to y -44, far below the
  map. So the volume stats count for falling too.
- **The volume stats limit where Link may walk.** With the Deku Tree's `.bpvsts`, Link stopped about 25 m behind the
  spawn (x 2, y 96, z 40), on open map ground, roughly where the old level ends; he was shown tumbling, so it looks like
  the abyss check firing there, but that isn't confirmed. With a tiny `.bpvsts` (B58) the whole map is walkable.
- **Not limits** (no change when widened or removed): `VolumeStatsAABB`, the `HeightMapParam` box, the Kokiri Forest
  preload radius (its 30 m matched the z 40 spot by coincidence).
- Other area limits exist for special places: `NoEscapeRangeArea` / `OutOfNoEscapeArea` (boss rooms; the Deku Tree has
  `NoEscapeArea_Get_StoneOfForest`) and `HoldHountedWastelandOutArea` (the Haunted Wasteland).

## Making a new scene (in progress, tests S1–S2, 13 Nov 2026)

Goal: the custom map as a scene of its own behind a door, so the scene it was built from stays playable. Not working
yet: both tries crash while the new scene loads.

What a new scene `X` gets so far (builder: `new_scene()` in `mods/custom-map-tests/build_tests.py`):

| Piece | Where | Note |
|---|---|---|
| Scene settings | `Banc/GameBancParam/X.game__banc__GameBancParam.bgyml` | `Banc.Main` → `Work/Banc/Scene/X/X.bcett.json`. Other lines point to files by path (`BaseLocation`, `DungeonParam`, `LocationalLightScenePlacement`, `WorldMgrName`) and can keep pointing at the old scene's |
| Placement | `Banc/X/X_Static.bcett.byml.zs`, `_Dynamic` | |
| Files looked up by the scene's name | `Bake/Light/X.bklight`, `Bake/Scene/X_G_i_j.bkres`, `Bake/Probe/Scene/X/*`, `Game/AdjacentRoomsInfo/X`, `Game/BakeSceneLayerConfig/X`, `Game/VolumeStatsAABB/X`, `PreComputedCulling/X/Boxes.bbox`, `Phive/NavMesh/X`, `Phive/StaticCompoundBody/X/X.bphsc`, `Phive/VolumeStats/X/X.bpvsts` + `X.phive__VolumeStatsSourceParam` | The `.bkres` files name their baked textures (`RBake_Scene_<old>_G_*`) inside, so the textures need no copies |
| Scene list | RSDB `GameBancInfo` | One row per scene (`__RowId`, `BancMain`, `SoundSceneryName`), sorted by `__RowId` |
| Per-scene data by scene name | `Banc/BancBasedResource/` **and** `AoC1/Banc/BancBasedResource/` | Two sets (the `AoC1` one adds the Master Quest `_MQ` scenes): `StartPos`, `LocationArea` (every scene has one), `MapParam`, `NoEscapeRangeArea`, `GmdReset` |
| The door | e.g. Kokiri Forest's `FieldAndDungeonEntranceEventRequestActor` `FrontDekuTree` | `NextBancParamNameChild` / `Adult` → `X`, `NextStartPosName`, `NextEventName` |

The crash (S1 and S2 alike, `eden_log.txt`): a logic node (`main` `0x112b3a0`, slot `0xe8` of vtable `0x4ba4b70`, made
by `0xdefb50`, registered under hash `0xd04a2892`) reads a 0x290-byte global manager (`*0x4e919d0`, made at
`0xf96640`: a 256-character name at +0x40, a ref-counted object at +0x38) and calls through +0x38 → +0x150 without
checking. For the new scene +0x38 is empty. The CPU registers hold the text `X` at that point. Other callers of the
manager check +0x38 first (e.g. `0x9eec60`); the getter that copies it is `0x9b7530`. The game's code has fixed
scene-name lists only for dungeon UI / map enums, so that isn't it.

## Test map

`test_map.glb` (KaboWabo's pick): "High quality minecraft world" by SOLDMARS on Sketchfab, CC-BY-4.0 (credit the
author in anything published). 339,960 triangles, 661,505 vertices, 75 meshes, 70 materials (22 cut-out or
see-through), two 1024 x 1024 texture atlases. One block is 1/70 of a unit, so the world is about 171 x 70 x 127
blocks; scaled x70 (1 block = 1 m) it is about the size of Inside the Deku Tree. Child Link's camera height is 1.17 m
([camera.md](camera.md)).

## Placement and size table notes

- An actor in a `.bcett` has `Gyaml` (actor name), `Hash` (u64, also `Phive.Placement.ID`), `SRTHash` (u32),
  `Translate`, optional `Rotate` (radians), `Scale`, `Dynamic`, `Links`, `Bakeable`, `Presence`, `Name`.
  The Static file also has `AiGroups`, `FarDeleteGroups`, `SimultaneousGroups`, `PlgGdTable` and
  `PhiveHeader.PlacementGroups`, which point at actor hashes: the round-1 tests empty them along with the actors.
- Size table entries for these files are the unpacked size plus about 300 bytes (`InsideTheDekuTree_Static`
  109,808 → 110,088; `Land_Deku_TreeRoot_B_01.pack` 2,432 → 2,744). `byml.py`'s output is 1–2 % larger than
  Nintendo's for the same data, so a rewritten file needs its entry raised.
