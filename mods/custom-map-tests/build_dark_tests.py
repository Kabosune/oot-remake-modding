#!/usr/bin/env python3
"""Build the dark Deku Tree test mods (D1, D2): Inside the Deku Tree with its baked light turned off and its env
palettes' ambient light at 0, a dark place to try Flashlight & Lantern in. See README.md ("Dark Deku Tree").

    python3 mods/custom-map-tests/build_dark_tests.py --romfs <folder with the game files below> --out <dir>

--romfs needs (same paths as in the romfs, game version 1.1.1):
    Pack/ZsDic.pack.zs
    System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs
    Pack/EnvPalette.pack.zs
    Banc/GameBancParam/InsideTheDekuTree.game__banc__GameBancParam.bgyml

Needs: pip install zstandard numpy
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_tests as bt  # noqa: E402
from build_tests import byml, zsmod, zstool  # noqa: E402

# The Deku Tree's three env palettes (the dungeon, the room before Gohma's cutscene, Gohma's room)
PALETTES = [f"WorldMgr/ResEnvPalette/InsideTheDekuTree{s}.game__wm__ResEnvPalette.bgyml"
            for s in ("", "_BeforeBossDemo", "_BossRoom")]

# D1: what B43 / B44 showed works, turned down instead of up: the bake off (B43: "very dark, not black"), then the
# palette's flat ambient and its sky / ground (hemisphere) light at 0.
D1_BANC = {"IsEnableBakeLight": False}
D1_PALETTE = {"AmbientIntensity": 0.0, "HemiLightIntensity": 0.0}

# D2: D1 plus the palette's other light sources, as far as their names say (none tried before): the added specular
# light (Parent_Dungeon 0.4), Link's own fill light (SubCharaLightIntensity 0.05), the volume fog's glow
# (lit by the baked probes, 3.5) and the cube map's ambient colour (white -> black).
D2_PALETTE = {**D1_PALETTE, "AddSpecLightIntensity": 0.0, "SubCharaLightIntensity": 0.0,
              "VolumeFogProbeBakeLightScale": 0.0,
              "CubeMapAmbientColor": {"A": 1.0, "B": 0.0, "G": 0.0, "R": 0.0}}


def build(game, out, label, banc_set, palette_set, about):
    files, entries, notes = {}, {}, [f"{label}: {about}"]
    bp = game.byml(bt.DEKU_BANC)
    for k, v in banc_set.items():
        notes.append(f"{label}: {bt.DEKU_BANC} {k} {bp.get(k)!r} -> {v!r}")
        bp[k] = v
    files[bt.DEKU_BANC] = (bp, 0)
    raw = game.raw(bt.ENV_PACK)
    sarc = zstool.Sarc(raw)
    inner = {str(n): sarc.read(str(n)) for n in sarc.names()}
    for name in PALETTES:
        pal = byml.loads(inner[name])
        for k, v in palette_set.items():
            notes.append(f"{label}: {bt.ENV_PACK} {name.split('/')[-1]} {k} {pal.get(k, '(from the parent)')!r} -> {v!r}")
            pal[k] = v
        inner[name] = byml.dumps(pal)
        entries[name] = len(inner[name]) + 512
    files[bt.ENV_PACK] = (zsmod.sarc_pack(inner, like=raw), byml.frame_dict_id(game.r / bt.ENV_PACK))
    bt.write_mod(out, files, game, notes, entries=entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    game, out = bt.Game(a.romfs), Path(a.out)
    build(game, out / "KaeGae Dark Test D1 - Deku Tree, bake and ambient off", "D1", D1_BANC, D1_PALETTE,
          "Inside the Deku Tree with its baked light off and its palettes' ambient and hemi light at 0")
    build(game, out / "KaeGae Dark Test D2 - D1 with the palette's other lights off", "D2", D1_BANC, D2_PALETTE,
          "D1 plus the palettes' added specular, Link's fill light, the fog's probe light and the cube map ambient off")


if __name__ == "__main__":
    main()
