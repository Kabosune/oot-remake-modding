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
   Needs a BYML writer that can change strings (`zsmod.py` can't).
2. **Your own layout from the game's pieces.** Rewrite a scene's placement: remove, move and add `Land_*` actors.
   No new formats.
3. **Collision without Havok, for blocky maps.** A voxel map can be turned into a few hundred boxes and placed as
   scaled box actors (`FldObj_AirWall_Common_Cube` takes `Scale`). Untested: whether Link can stand on air walls, or
   which box actor is solid ground.
4. **Your own model.** A new `Land_*`-style actor: pack + `.bfres` + `.bntx` + `.bphsh`. Needs writers for the
   three formats above; the plan would be to start from an existing piece as a template.

Unknown: which of the bake, culling, navmesh and foliage files a scene can do without.

## Test map

`test_map.glb` (KaboWabo's pick): "High quality minecraft world" by SOLDMARS on Sketchfab, CC-BY-4.0 (credit the
author in anything published). 339,960 triangles, 661,505 vertices, 75 meshes, 70 materials (22 cut-out or
see-through), two 1024 x 1024 texture atlases. One block is 1/70 of a unit, so the world is about 171 x 70 x 127
blocks; scaled x70 (1 block = 1 m) it is about the size of Inside the Deku Tree. Child Link's camera height is 1.17 m
([camera.md](camera.md)).
