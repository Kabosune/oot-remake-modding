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
