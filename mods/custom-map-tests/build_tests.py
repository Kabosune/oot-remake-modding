#!/usr/bin/env python3
"""Build the custom-map test mods (round 1). See README.md next to this file and docs/custom-maps.md.

    python3 mods/custom-map-tests/build_tests.py --romfs <folder with the game files below> --glb <map.glb> --out <dir> [--round 1|1b]

--romfs needs, from your own dump (same paths as in the romfs):
    Pack/ZsDic.pack.zs
    System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs
    Banc/KokiriForest/KokiriForest_Child_Static.bcett.byml.zs
    Banc/InsideTheDekuTree/InsideTheDekuTree_Static.bcett.byml.zs
    Banc/InsideTheDekuTree/InsideTheDekuTree_Dynamic.bcett.byml.zs
    Pack/Actor/Land_Deku_TreeRoot_B_01.pack.zs

Needs: pip install zstandard trimesh scipy numpy
"""
import argparse
import copy
import random
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
import byml  # noqa: E402
import zsmod  # noqa: E402
import zstool  # noqa: E402

RSTB = "System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs"
KOKIRI = "Banc/KokiriForest/KokiriForest_Child_Static.bcett.byml.zs"
DEKU_S = "Banc/InsideTheDekuTree/InsideTheDekuTree_Static.bcett.byml.zs"
DEKU_D = "Banc/InsideTheDekuTree/InsideTheDekuTree_Dynamic.bcett.byml.zs"
HOST = "Land_Deku_TreeRoot_B_01"           # a plain static Deku Tree piece; its collision gets replaced
HOST_PACK = f"Pack/Actor/{HOST}.pack.zs"
HOST_SHAPE = f"Phive/ShapeParam/{HOST}__Physical.phive__ShapeParam.bgyml"
SPAWN = (0.21897688508033752, 101.0, 14.710853576660156)   # InsideTheDekuTree "Entrance"
MATERIAL = ["Material_Wood"]
rng = random.Random(0x6B616567)            # fixed seed: same output every build


def f3(x, y, z):
    return {"X": float(x), "Y": float(y), "Z": float(z)}


# ---------------------------------------------------------------- resource size table

class Rstb:
    def __init__(self, path):
        import zstandard
        self.t = bytearray(zstandard.ZstdDecompressor().decompress(Path(path).read_bytes(), max_output_size=1 << 28))
        _, n_hashed, _ = struct.unpack_from("<III", self.t, 10)
        self.at = {struct.unpack_from("<I", self.t, 22 + 8 * i)[0]: 22 + 8 * i + 4 for i in range(n_hashed)}

    def need(self, romfs_path, size):
        """Make sure the entry for romfs_path (with or without .zs) is at least size + 512."""
        p = romfs_path[:-3] if romfs_path.endswith(".zs") else romfs_path
        at = self.at[zlib.crc32(p.encode())]
        old = struct.unpack_from("<I", self.t, at)[0]
        new = max(old, (size + 512 + 7) & ~7)
        struct.pack_into("<I", self.t, at, new)
        return old, new

    def save(self, path):
        import zstandard
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(zstandard.ZstdCompressor(level=19, write_content_size=True).compress(bytes(self.t)))


class Game:
    def __init__(self, romfs):
        self.r = Path(romfs)
        self.dicts = zsmod.dicts_by_id(self.r / "Pack/ZsDic.pack.zs")

    def byml(self, rel):
        return byml.read(self.r / rel, self.dicts)

    def raw(self, rel):
        return zsmod.unzs((self.r / rel).read_bytes(), self.dicts)[0]


def write_mod(out, files, game, notes):
    """files: {romfs path: (object or bytes, dict id)} -> out/romfs/..., with a fitted size table."""
    rstb = Rstb(game.r / RSTB)
    for rel, (obj, did) in files.items():
        raw = obj if isinstance(obj, bytes) else byml.dumps(obj)
        old, new = rstb.need(rel, len(raw))
        notes.append(f"{rel}: {len(raw)} bytes, size table {old} -> {new}")
        dst = out / "romfs" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(zsmod.zs(raw, did, game.dicts) if rel.endswith(".zs") else raw)
    rstb.save(out / "romfs" / RSTB)
    (out / "BUILD.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- scene helpers

def new_hash():
    return byml.U64(rng.getrandbits(64) | 1 << 62)


def placed(gyaml, pos, scale=None, extra=None):
    h = new_hash()
    a = {"Gyaml": gyaml, "Hash": h, "Phive": {"Placement": {"ID": h}}, "SRTHash": byml.U32(rng.getrandbits(32)),
         "Translate": [float(v) for v in pos]}
    if scale:
        a["Scale"] = [float(v) for v in scale]
    a.update(extra or {})
    return a


def emptied_deku(game):
    """Inside the Deku Tree with every actor removed except the spawn points (and all groups cleared)."""
    st, dy = game.byml(DEKU_S), game.byml(DEKU_D)
    keep = lambda a: a["Gyaml"] == "StartPos"  # noqa: E731
    st["Actors"] = [a for a in st["Actors"] if keep(a)]
    dy["Actors"] = [a for a in dy["Actors"] if keep(a)]
    for k in ("AiGroups", "FarDeleteGroups", "SimultaneousGroups", "PlgGdTable"):
        st[k] = []
    st["PhiveHeader"]["PlacementGroups"] = []
    return st, dy


def a_chest(game, pos, yaw=0.0):
    """A copy of the Deku Tree's compass chest, moved (a landmark you can see)."""
    st = game.byml(DEKU_S)
    src = next(a for a in st["Actors"] if a["Gyaml"] == "Obj_TBox_A_02" and a.get("Dynamic", {}).get("Drop__DropActor") == "Item_Dungeon_Compass")
    c = copy.deepcopy(src)
    h = new_hash()
    c["Hash"], c["Phive"] = h, {"Placement": {"ID": h}}
    c["SRTHash"] = byml.U32(rng.getrandbits(32))
    c["Translate"] = [float(v) for v in pos]
    c["Rotate"] = [0.0, float(yaw), 0.0]
    c.pop("Links", None)
    return c


def host_pack(game, boxes):
    """HOST's pack with its collision replaced by `boxes` [(min xyz, max xyz) in metres, actor-local]."""
    sarc = zstool.Sarc(game.raw(HOST_PACK))
    files = {n: sarc.read(n) for n in sarc.names()}
    lo = np.min([b[0] for b in boxes], axis=0)
    hi = np.max([b[1] for b in boxes], axis=0)
    size = hi - lo
    vol = float(sum(np.prod(np.subtract(b[1], b[0])) for b in boxes))
    shape = {
        "AutoCalc": {
            "Axis": f3(0, 0, 0), "Center": f3(*((lo + hi) / 2)), "Max": f3(*hi), "Min": f3(*lo),
            "Tensor": f3((size[1] ** 2 + size[2] ** 2) / 12, (size[0] ** 2 + size[2] ** 2) / 12, (size[0] ** 2 + size[1] ** 2) / 12),
            "Volume": vol,
        },
        "Box": [{
            "Center": f3(0, 0, 0),
            "HalfExtents": f3(*((np.subtract(b[1], b[0])) / 2)),
            "MaterialPresets": list(MATERIAL),
            "OffsetTranslation": f3(*((np.add(b[0], b[1])) / 2)),
        } for b in boxes],
    }
    files[HOST_SHAPE] = byml.dumps(shape)
    return zsmod.sarc_pack(files, like=game.raw(HOST_PACK))


# ---------------------------------------------------------------- test 1: door redirect

def test1(game, out):
    st = game.byml(KOKIRI)
    door = next(a for a in st["Actors"] if a["Gyaml"] == "FieldAndDungeonEntranceEventRequestActor"
                and a.get("Dynamic", {}).get("NextBancParamNameChild") == "InsideTheDekuTree")
    d = door["Dynamic"]
    d["NextBancParamNameChild"] = d["NextBancParamNameAdult"] = "DodongoCavern"
    d["NextStartPosName"] = "EntrancePos"
    d["NextEventName"] = "Dm_SY_BancChangeArrive"
    d.pop("InitEventName", None)
    d.pop("InitEventFlag", None)
    notes = ["Test 1: the Deku Tree's door (Kokiri Forest, child) goes to DodongoCavern / EntrancePos."]
    write_mod(out, {KOKIRI: (st, 3)}, game, notes)


# ---------------------------------------------------------------- test 2: box room

def test2(game, out):
    st, dy = emptied_deku(game)
    sx, sy, sz = SPAWN
    # actor-local boxes (host placed at the spawn point, so 0,0,0 = where Link arrives; y 0 = his feet)
    B = [((-10, -1, -10), (10, 0, 10))]                                   # floor 20 x 20
    for i in range(6):                                                    # stairs going -z, 0.5 m per step
        B.append(((-2, 0, -11 - i), (2, 0.5 * (i + 1), -10 - i)))
    B.append(((-4, 0, -21), (4, 3, -16)))                                 # top platform at 3 m
    B.append(((6, 0, -2), (8, 8, 0)))                                     # pillar 8 m tall
    B.append(((-10, 0, 9), (10, 1, 10)))                                  # low wall at the back, 1 m
    host = placed(HOST, (sx, sy, sz), extra={"Bakeable": True})
    dy["Actors"].append(host)
    # an air-wall cube as a floating step: can Link stand on air walls?
    dy["Actors"].append(placed("FldObj_AirWall_Common_Cube", (sx + 5, sy + 1.0, sz - 5), scale=(3, 0.5, 3)))
    st["Actors"].append(a_chest(game, (sx, sy + 3, sz - 19)))             # on the top platform
    st["Actors"].append(a_chest(game, (sx - 5, sy, sz - 3)))              # on the floor
    files = {DEKU_S: (st, 3), DEKU_D: (dy, 3), HOST_PACK: (host_pack(game, B), 4)}
    notes = [f"Test 2: Inside the Deku Tree emptied; {len(B)} collision boxes in one actor ({HOST}) at the entrance,",
             "a floating air-wall cube step, two chests."]
    write_mod(out, files, game, notes)


# ---------------------------------------------------------------- tests 3 and 4: the Minecraft map's collision

SKIP = ("Water", "Lava", "Grass", "Dandelion", "Poppy", "Sunflower", "Carrot", "Wheat", "Glow_Lichen", "Torch",
        "Seagrass", "Ladder", "Carpet", "Snow", "Glass_Pane", "Fence", "Fence_Gate", "Bell", "Oak_Door",
        "Oak_Pressure_Plate", "Oak_Trapdoor", "Pointed_Dripstone", "Small_Amethyst_Bud", "Chest", "Grindstone")


def voxels(glb, scale):
    import trimesh
    s = trimesh.load(glb)
    solid = set()
    for node in s.graph.nodes_geometry:
        T, gname = s.graph[node]
        g = s.geometry[gname]
        name = getattr(getattr(g.visual, "material", None), "name", "") or ""
        if name != "Grass_Block" and any(name == k or name.endswith("_" + k) for k in SKIP):
            continue
        v = trimesh.transform_points(g.vertices, T) * scale
        f = g.faces
        n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        ln = np.linalg.norm(n, axis=1)
        ok = ln > 1e-9
        n[ok] /= ln[ok, None]
        ax = np.argmax(np.abs(n), axis=1)
        flat = ok & (np.abs(n[np.arange(len(n)), ax]) > 0.999)      # block faces only (plants are diagonal)
        c = v[f].mean(axis=1)
        for i in np.nonzero(flat)[0]:
            p = c[i].copy()
            p[ax[i]] -= np.sign(n[i, ax[i]]) * 0.5                   # the block behind the face
            solid.add(tuple(np.floor(p + 1e-4).astype(int)))
    return np.array(sorted(solid))


def fill_and_merge(cells):
    from scipy import ndimage
    mn = cells.min(0)
    a = cells - mn
    g = np.zeros(a.max(0) + 3, bool)
    g[a[:, 0] + 1, a[:, 1] + 1, a[:, 2] + 1] = True
    air, _ = ndimage.label(~g)
    edge = np.unique(np.concatenate([air[0].ravel(), air[-1].ravel(), air[:, 0].ravel(), air[:, -1].ravel(),
                                     air[:, :, 0].ravel(), air[:, :, -1].ravel()]))
    solid = (g | ~np.isin(air, edge[edge > 0]))[1:-1, 1:-1, 1:-1]    # closed-off insides count as solid
    return solid, mn


def greedy(solid):
    s = solid.copy()
    X, Y, Z = s.shape
    out = []
    for y in range(Y):
        for z in range(Z):
            for x in range(X):
                if not s[x, y, z]:
                    continue
                x2 = x
                while x2 + 1 < X and s[x2 + 1, y, z]:
                    x2 += 1
                z2 = z
                while z2 + 1 < Z and s[x:x2 + 1, y, z2 + 1].all():
                    z2 += 1
                y2 = y
                while y2 + 1 < Y and s[x:x2 + 1, y2 + 1, z:z2 + 1].all():
                    y2 += 1
                s[x:x2 + 1, y:y2 + 1, z:z2 + 1] = False
                out.append(((x, y, z), (x2 + 1, y2 + 1, z2 + 1)))
    return out


def spawn_column(solid):
    """A flat, open column near the middle: (x, z, height of its top)."""
    X, Y, Z = solid.shape
    top = np.where(solid.any(1), Y - 1 - np.argmax(solid[:, ::-1, :], axis=1), -1)
    best = None
    for x in range(2, X - 2):
        for z in range(2, Z - 2):
            h = top[x, z]
            if h < 0 or (top[x - 1:x + 2, z - 1:z + 2] != h).any():
                continue
            d = (x - X / 2) ** 2 + (z - Z / 2) ** 2
            if best is None or d < best[0]:
                best = (d, x, z, h + 1)
    return best[1:]


def minecraft(game, out, glb, radius, label):
    cells = voxels(glb, 70.0)                    # the file has 70 blocks per unit: 1 block = 1 m
    solid, _ = fill_and_merge(cells)
    cx, cz, top = spawn_column(solid)
    if radius:
        x0, z0 = max(cx - radius, 0), max(cz - radius, 0)
        solid = solid[x0:cx + radius, :, z0:cz + radius]
        cx, cz = cx - x0, cz - z0
    boxes = greedy(solid)
    st, dy = emptied_deku(game)
    sx, sy, sz = SPAWN
    origin = (sx - (cx + 0.5), sy - top, sz - (cz + 0.5))   # grid -> scene: the spawn column's top under Link
    dy["Actors"].append(placed(HOST, origin, extra={"Bakeable": True}))
    st["Actors"].append(a_chest(game, (sx + 2, sy, sz - 2)))
    files = {DEKU_S: (st, 3), DEKU_D: (dy, 3), HOST_PACK: (host_pack(game, boxes), 4)}
    notes = [f"{label}: Inside the Deku Tree emptied; the Minecraft map as {len(boxes)} collision boxes in one actor",
             f"({HOST}), {solid.shape[0]} x {solid.shape[1]} x {solid.shape[2]} blocks, 1 block = 1 m.",
             f"Spawn column {cx},{cz} top {top}; actor at {tuple(round(v, 3) for v in origin)}. One chest next to the spawn."]
    write_mod(out, files, game, notes)
    return len(boxes)


# ---------------------------------------------------------------- round 1b: one change per test

def test_b(game, out):
    """The real Deku Tree, untouched, plus one invisible box platform in front of the entrance."""
    dy = game.byml(DEKU_D)
    sx, sy, sz = SPAWN
    B = [((-1.5, 0.5, -1.5), (1.5, 1.0, 1.5))]                           # 3 x 3 m, top 1 m above the floor
    dy["Actors"].append(placed(HOST, (sx, sy, sz - 4), extra={"Bakeable": True}))
    files = {DEKU_D: (dy, 3), HOST_PACK: (host_pack(game, B), 4)}
    notes = ["Test B: Inside the Deku Tree as normal, plus one invisible 3 x 3 m box, top 1 m up, 4 m in front of the",
             f"entrance (the collision of {HOST}; its 7 other copies in the dungeon get the same small box)."]
    write_mod(out, files, game, notes)


def test_c(game, out, keep_terrain):
    """Inside the Deku Tree emptied to its spawn points (C), or to spawn points + the 5 terrain chunks (D)."""
    st, dy = emptied_deku(game)
    if keep_terrain:
        orig = game.byml(DEKU_S)
        st["Actors"] += [a for a in orig["Actors"] if a["Gyaml"].startswith("InsideTheDekuTree_0")]
    files = {DEKU_S: (st, 3), DEKU_D: (dy, 3)}
    what = "spawn points and the 5 terrain chunks" if keep_terrain else "only its spawn points"
    write_mod(out, files, game, [f"Test {'D' if keep_terrain else 'C'}: Inside the Deku Tree emptied to {what}; nothing added."])


def main_1b(game, out):
    test1(game, out / "KaeGae Map Test A - Deku door to Dodongo")
    test_b(game, out / "KaeGae Map Test B - Deku Tree plus one box")
    test_c(game, out / "KaeGae Map Test C - Deku Tree emptied", False)
    test_c(game, out / "KaeGae Map Test D - Deku Tree emptied, terrain kept", True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--romfs", required=True)
    ap.add_argument("--glb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--round", default="1b", choices=["1", "1b"])
    a = ap.parse_args()
    game, out = Game(a.romfs), Path(a.out)
    if a.round == "1b":
        main_1b(game, out)
        print("built round 1b")
        return
    test1(game, out / "KaeGae Map Test 1 - Deku door to Dodongo")
    test2(game, out / "KaeGae Map Test 2 - Box room")
    n3 = minecraft(game, out / "KaeGae Map Test 3 - Minecraft small", a.glb, 24, "Test 3")
    n4 = minecraft(game, out / "KaeGae Map Test 4 - Minecraft full", a.glb, 0, "Test 4")
    print("built; boxes:", n3, n4)


if __name__ == "__main__":
    main()
