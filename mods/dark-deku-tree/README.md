# Dark Deku Tree

Inside the Deku Tree with the lights off: no baked light, no ambient or sky light, no fog. The
dungeon is pitch dark apart from Navi, torches and other lights the rooms place themselves, and
things that glow. Made as a place to try [Flashlight & Lantern](../flashlight-lantern/README.md)
(its Navi's glow switch turns Navi off too).

**0.1.0 works in Fritchii on 1.1.1** (22 November 2026: KaboWabo, "d3 map is perfect"). The build
below gives byte for byte the files of that test (D3 in the
[test log](../custom-map-tests/README.md#dark-deku-tree-d1-d2-22-nov-2026)). 1.0.0 not tried.

Doesn't need KaeGae Core. Needs your own dump of the game, Python 3.11 or later (3.10 with `pip install tomli`) and
`pip install zstandard`.

## What it changes

| File | Change |
|---|---|
| `Banc/GameBancParam/InsideTheDekuTree.game__banc__GameBancParam.bgyml` (the scene's settings) | `IsEnableBakeLight` off: no baked light |
| `Pack/EnvPalette.pack.zs`: the Deku Tree's three env palettes (`InsideTheDekuTree`, `_BeforeBossDemo`, `_BossRoom`) | `AmbientIntensity` and `HemiLightIntensity` (the flat ambient and the sky / ground light) 0; the volume fog off (`VolumeFogIsEnabled`, `VolumeFogEnableFog1`, `VolumeFogEnableFog2`) |

The changes are written as `[[romfs-patch]]` lines in [mod.toml](mod.toml): the mod ships no game
file. `kaegae build` makes the two changed files from your dump.

## Install

1. Copy the zip's `0400486024DEC000` folder into the emulator's `load` folder, like any mod
   (Fritchii: `%APPDATA%\fritchii\load\`). The `Dark Deku Tree` folder holds only `mod.toml`
   and this text.
2. Build its files from your dump's romfs (the folder with `Pack`, `Banc`, `System`, ...; see
   [docs/romfs.md](../../docs/romfs.md)), with this repo's tools:

   ```
   python3 tools/kaegae.py build --romfs <your dump's romfs folder>
   ```

   It writes `KaeGae Built Files` into the load folder: the changed palettes, the scene settings
   and a size table with room for them. Keep that folder to yourself (it holds changed game files).
3. Close and reopen the emulator, and switch both `Dark Deku Tree` and `KaeGae Built Files` on in
   the game's Add-Ons.

To go back to the normal Deku Tree, switch off or remove `Dark Deku Tree` and run step 2 again
(or remove `KaeGae Built Files` if no other mod needs it).

## Good to know

- `KaeGae Built Files` is shared: other mods that ask for size table entries or change game files
  are built into the same folder, and a clash between two mods is reported when you build. A mod
  that ships its own whole size table clashes with it (`kaegae check` says so).
- Light that stays: Navi (switch her off with Flashlight & Lantern), the scene's own placed lights
  (torches and the like), glowing materials. Turning down more of the palette's lights crashed the
  game at boot in one test (D2 in the test log), so this mod leaves them.

## Credits

KaboWabo/Kabosune (me :3), AI assistance (Claude Opus 5.5).
