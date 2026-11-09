# Community projects (as of 9 November 2026)

The game came out on 5 November 2026, and things are moving daily. Links go to each project's own
page, which is where to check what's current.

## Running it

| Project | What | Notes |
|---|---|---|
| [zortos293/Lichii](https://github.com/zortos293/Lichii) | Switch 2 emulator (Eden / yuzu family) | loads exefs IPS and romfs mods from `load/<title id>/`; has built-in OoT patches |
| Fritchii | a Lichii build with OoT visual fixes | what this repo's mods are tested on |
| [NotRexed/Hookshot](https://github.com/NotRexed/Hookshot) | static recompilation to native Windows / Linux | has cheats (free camera, flight, teleport, inventory) whose findings this repo builds on |
| NX2navi (tangerineturtle1) | another native port by static recompilation | [TechPowerUp](https://www.techpowerup.com/354592/zelda-ocarina-of-time-remake-gets-a-native-pc-port-through-static-recompilation) |
| [cheemu21/kid-with-sword-remake](https://github.com/cheemu21/kid-with-sword-remake) | native iPhone / Mac app (nxnative fork) | |
| [riyadhHDA/wichforks](https://github.com/riyadhHDA/wichforks) | guide to which emulator fork to use for which game | |

## Mods

| Project | What |
|---|---|
| [craftycorvid/oot-mod](https://github.com/craftycorvid/oot-mod) | ultrawide 21:9 / 32:9 (IPS32) |
| [TheCraZyDuDee/Ocarina-of-Time-Remake-Mods](https://github.com/TheCraZyDuDee/Ocarina-of-Time-Remake-Mods) | fixed 30 / adaptive / variable FPS (IPS32) |
| this repo | First Person |

## Tools

| Project | What |
|---|---|
| [KillzXGaming/Switch-Toolbox](https://github.com/KillzXGaming/Switch-Toolbox) | opens models and textures (needs the game's `ZsDic.pack.zs`, see [romfs.md](romfs.md)) |
| [TKVSC - Ocarina of Time](https://gamebanana.com/tools/24818) | a modding tool on GameBanana; its page doesn't say much yet |
| [SebaaMG/ns2jb-modloader](https://github.com/SebaaMG/ns2jb-modloader) | loads romfs / exefs mods on a jailbroken Switch 2 |

## Background

- Engine: ModuleSystem, as in Tears of the Kingdom ([reported](https://mynintendonews.com/2026/11/06/zelda-ocarina-of-time-remake-codenamed-owl-it-uses-modulesystem-game-engine-same-used-for-zelda-tears-of-the-kingdom/) from oatmealdome's findings).
- [MacNativeGames issue #1773](https://github.com/ly05010419/MacNativeGames/issues/1773): notes from bringing the game up on another runtime (ZBIC, boot, NVN2).
