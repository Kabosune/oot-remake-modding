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
| `AS` | 919 | | animation graphs (`.root.asb.zs`), see [asb.md](asb.md) |
| `RSDB` | 20 | | databases: `ActorInfo`, `GameActorInfo`, `PouchActorInfo`, `Location`, `UIScreen`, `Tag`, ... |
| `GameData` | 2 | | `GameDataList.Product.110.byml.zs`: every save flag and value |
| `GameParameter` | 30 | | global tuning: enemies, horse, drops, knockback, `MelodyScoreBook`, Navi |
| `Mals` | 16 | | game text, one `.sarc.zs` per language (`USen`, `EUen`, `JPja`, ...) |
| `System` | 702 | | `Resource/ResourceSizeTable...rsizetable.zs` ([below](#the-resource-size-table)), `HeapSize`, `AddressTable`, graphics settings |
| `Shader`, `Lib`, `Font2` | | | shader archives (`.bfsha`), engine resources, fonts |
| `AoC1` | 7 | | add-on content: map resources for a DLC (`AoC1/Banc/BancBasedResource/`). Reports link this to Master Quest. |

## Actor packs

`Pack/Actor/<Name>.pack.zs`, by name prefix: `Land` 5,329, `Obj` 997, `Npc` 379, `EftLoc` 362,
`Enemy` 341, `Item` 139, `Pouch` 82, `Dm` 78, `Weapon` 71, `Shop` 56, `Animal` 50, `FldObj` 38, ...

Link is split into `Player_Base`, `Player_Child`, `Player_Adult` and `Player_Event`. The camera that
follows him is its own actor, `PlayerCamera` (see [camera.md](camera.md)).

## Replacing files

Replace a file by putting one at the same path in a romfs mod (`load/<title id>/<mod>/romfs/...`): the loader hands the game your file instead of its own (LayeredFS).
A file that grows may also need a bigger entry in the resource size table.

## The resource size table

`System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs` (plain zstd, no
dictionary; 1.7 MB unpacked) is a `RESTBL` version 1 file, the same format as TotK's:

| Offset | What |
|---|---|
| `0x00` | `"RESTBL"` |
| `0x06` | version, 1 |
| `0x0A` | name size, 160 |
| `0x0E` | number of hashed entries, 219,968 |
| `0x12` | number of named entries, 10 |
| `0x16` | hashed entries: CRC32 of the path (u32), size (u32) |
| then | named entries: path (160 bytes), size (u32), for paths whose CRC32 collides |

The path is the romfs path without `.zs`, e.g. `AS/Dm_Zora_0010_KingZora.root.asb`.

The size is not the file's size. It is the memory to set aside for loading the file: always a
multiple of 8 and always larger than the unpacked file. For the 919 `AS/*.asb` files it is close to
`file size + 40 × element count + 600` (the last term runs from about 500 to 900 for 99% of them).
For an event flow it is the file size plus a few hundred bytes.

So an edited file that is longer, or has more elements, can need more than the game's entry gives
it. [`tools/rstb_set.py`](../tools/rstb_set.py) raises entries:

```
python tools/rstb_set.py ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs out/System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs AS/Dm_Zora_0010_KingZora.root.asb=+1024
```

The changed table goes in the mod's romfs at the same path. Two mods that each ship a table
overwrite each other's, so merge their changes into one.

Not tested yet: what this game does when a file outgrows its entry (in TotK that is a crash or a
failed load), and how much room an entry really has to have.
