# The engine

The remake runs on Nintendo's **ModuleSystem** engine, the one Tears of the Kingdom uses
([reported by oatmealdome](https://mynintendonews.com/2026/11/06/zelda-ocarina-of-time-remake-codenamed-owl-it-uses-modulesystem-game-engine-same-used-for-zelda-tears-of-the-kingdom/),
codename "Owl"). The romfs layout, file formats and many class names match TotK, so a lot of TotK
modding knowledge carries over. Treat any specific detail as "check it here first", though: this is a
newer branch of the engine on a new console.

What that means in practice:

## Actors are made of components

An actor is defined by an `ActorParam` file (`Pack/Actor/<Name>.pack.zs` →
`Actor/<Name>.engine__actor__ActorParam.bgyml`). It lists component references (`ModelInfoRef`,
`PhysicsRef`, `PlayerCameraTargetRef`, `LifeRef`, ...), and each reference points to another `.bgyml`
in the pack. Files can inherit from each other with `$parent`. The child version only lists what it
changes. For example, `Player_Child`'s camera-target file overrides `TargetHeight` and keeps the rest
from `Player`.

In memory, the physics actor that `f_82c415e0` moves keeps its components at `[actor + 0x270]`:

| Component (offset in the components block) | What | Source |
|---|---|---|
| `+0x260` | model (visible byte `+0xe5`, change flags `+0x120`) | `OneShotSetModelVisible` |
| `+0x320` | movement | Hookshot |
| `+0x358` | read by `f_804d6db0`: the `u16` at `+0x1c5d` caches child/adult (bit 8 valid, bit 0 child), otherwise it asks GameData | `f_804d6db0` |

## Behaviour is AINB graphs calling script commands

AI, sequence and level logic live in `.ainb` node graphs (`AI/`, `Logic/`, `Sequence/`, and inside
actor packs). Each node is a named script command implemented in `main`: `OneShotSetModelVisible`,
`QueryPlayerIsChild`, `ExecuteModelSetVisible`, and so on. This repo maps all ~5,200 of them to their
code: see [script-commands.md](script-commands.md).

That makes the commands the best starting point for finding anything in `main`. Search the CSV for
a name that sounds like what you want, then read its function.

## Maps are "Bancs"

Areas are `Banc/<Area>/` with placement files per age and layer, for example
`Banc/KokiriForest/KokiriForest_Child_Static.bcett.byml.zs` and `..._Adult_Dynamic...`. Per-area
settings are `Banc/GameBancParam/<Area>.game__banc__GameBancParam.bgyml`. Hookshot's teleport cheat
changes Banc by starting the game's own `Dm_SY_BancChangeGo` event with `NextBanc`, `NextStartPos`
and `BootEventName` arguments.

## Game state is GameData

Flags and values (`Sequence_IsChildhood`, `Sequence_IsLoadingBanc`, ...) live in GameData, defined
by `GameData/GameDataList.Product.110.byml.zs` and looked up by name hash through the `GameDataMgr`
singleton (`0x84c9e180`). Hookshot reads `Sequence_IsChildhood` (hash `0xcea220d3`) this way.

## Data files

`.bgyml` / `.byml` (BYML parameter files), `.pack` / `.sarc` (SARC archives), `.bfres` (models),
`.bntx` (textures), `.ainb` / `.asb` (AI / animation graphs), `.bfevfl` (event flows), `.bcett.byml`
(map placement), `.rstbl.byml` (RSDB tables). Most are zstd-compressed (`.zs`), many with one of the
game's four dictionaries. See [romfs.md](romfs.md).
