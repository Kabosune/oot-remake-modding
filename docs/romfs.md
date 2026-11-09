# romfs (update v131072)

186,587 files, about 26 GB. Counts and sizes are from the `.nup` listing of build E0F3CCFA's update.

## Compression

Almost everything ends in `.zs`: a zstd frame. Many frames need one of the game's dictionaries,
which are in `Pack/ZsDic.pack.zs` (itself plain zstd → a SARC):

| Dictionary | Used for |
|---|---|
| `pack.zsdic` | `.pack.zs` (actor packs) |
| `bcett.byml.zsdic` | `.bcett.byml.zs` (map placement) |
| `bkprb.zsdic` | `.bkprb.zs` |
| `zs.zsdic` | everything else |

[`tools/zstool.py`](../tools/zstool.py) tries each dictionary in turn, then lists SARCs and prints BYML:

```
python tools/zstool.py ls  Pack/Actor/PlayerCamera.pack.zs --dict Pack/ZsDic.pack.zs
```

```
python tools/zstool.py cat "Pack/Actor/Player_Child.pack.zs:Component/ModelInfo/Player_Child.engine__component__ModelInfo.bgyml" --dict Pack/ZsDic.pack.zs
```

Switch-Toolbox can open the models and textures once `Pack/ZsDic.pack.zs` is extracted to its
`Lib/ZstdDictionaries` folder ([its issue #757](https://github.com/KillzXGaming/Switch-Toolbox/issues/757)).

## Top level

| Folder | Files | Size | What |
|---|---:|---:|---|
| `Tex` | 20,667 | 9.4 GB | textures (`.bntx.zs`) |
| `TerrainArc` | 51,261 | 6.1 GB | terrain (`.extm`, `.hght`, `.mate`) |
| `Model` | 7,896 | 2.7 GB | models and animations (`<Name>.<Name>.bfres.zs`, `<Name>_Animation.anim.bfres.zs`) |
| `Sound` | 20,147 | 2.1 GB | `.bwav`, `.bars.zs`, listener / BGM params |
| `Bake` | 11,951 | 1.9 GB | baked lighting (`.bkprb.zs`, `.bkres.zs`) |
| `Event` | 1,338 | 1.7 GB | cutscene flows (`EventFlow/*.bfevfl.zs`), settings, pre-rendered movies (`.webm`) |
| `Phive` | 10,846 | 0.9 GB | physics: shapes, static bodies, navmesh, cloth, ragdolls |
| `PreComputedCulling` | 35,364 | 0.4 GB | `.bcul.zs` |
| `Foliage`, `Effect`, `Voice`, `UI` | | | grass, particles, voice lines, menus |
| `Pack` | 8,385 | 63 MB | **actor packs** (`Pack/Actor/*.pack.zs`, 8,373) and shared packs (`ResidentCommon`, `Bootup`, `ZsDic`) |
| `Banc` | 247 | | maps, one folder per area (see [engine.md](engine.md#maps-are-bancs)) |
| `Logic`, `Sequence`, `AI` | | | `.ainb` graphs: level logic, game flow (`Sequence/ChangeBanc.module.ainb`, ...), AI |
| `AS` | 919 | | animation graphs (`.root.asb.zs`) |
| `RSDB` | 20 | | databases: `ActorInfo`, `GameActorInfo`, `PouchActorInfo`, `Location`, `UIScreen`, `Tag`, ... |
| `GameData` | 2 | | `GameDataList.Product.110.byml.zs`: every save flag and value |
| `GameParameter` | 30 | | global tuning: enemies, horse, drops, knockback, `MelodyScoreBook`, Navi |
| `Mals` | 16 | | game text, one `.sarc.zs` per language (`USen`, `EUen`, `JPja`, ...) |
| `System` | 702 | | `Resource/ResourceSizeTable...rsizetable.zs`, `HeapSize`, `AddressTable`, graphics settings |
| `Shader`, `Lib`, `Font2` | | | shader archives (`.bfsha`), engine resources, fonts |
| `AoC1` | 7 | | add-on content: map resources for a DLC (`AoC1/Banc/BancBasedResource/`). Reports link this to Master Quest. |

## Actor packs

`Pack/Actor/<Name>.pack.zs`, by name prefix: `Land` 5,329, `Obj` 997, `Npc` 379, `EftLoc` 362,
`Enemy` 341, `Item` 139, `Pouch` 82, `Dm` 78, `Weapon` 71, `Shop` 56, `Animal` 50, `FldObj` 38, ...

Link is split into `Player_Base`, `Player_Child`, `Player_Adult` and `Player_Event`. The camera that
follows him is its own actor, `PlayerCamera` (see [camera.md](camera.md)).

## Replacing files

Replace a file by putting one at the same path in a romfs mod (`load/<title id>/<mod>/romfs/...`): the loader hands the game your file instead of its own (LayeredFS).
In TotK, a file that grows past its entry in the resource size table needs that table updated too.
This game ships the same table (`System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs`),
so expect the same rule. That hasn't been tested here yet.
