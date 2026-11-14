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
    Pack/Actor/Obj_TBox_A_02.pack.zs
    Pack/Actor/Obj_TBox_A_01.pack.zs (B30 on)
    Pack/Actor/Obj_Flag_A_01.pack.zs (B35 on)
    RSDB/GameActorInfo.Product.111.rstbl.byml.zs (B36 on)
    Pack/Actor/Land_SacredForest_Prop_A_06.pack.zs (B39 on; not changed, only checked)
    Pack/EnvPalette.pack.zs, Banc/GameBancParam/InsideTheDekuTree.game__banc__GameBancParam.bgyml (B42 on)
    Phive/StaticCompoundBody/DreamWorld/MorphaStage_X0_Z0.Nin_Ounce_NVN2.bphsc.zs (B46 on)
    RSDB/ActorInfo.Product.111.rstbl.byml.zs

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
ENV_PACK = "Pack/EnvPalette.pack.zs"   # B44 on
DEKU_PALETTE = "WorldMgr/ResEnvPalette/InsideTheDekuTree.game__wm__ResEnvPalette.bgyml"
DEKU_COMPOUND = "Phive/StaticCompoundBody/InsideTheDekuTree/InsideTheDekuTree.Nin_Ounce_NVN2.bphsc.zs"   # B46 on
EMPTY_COMPOUND = "Phive/StaticCompoundBody/DreamWorld/MorphaStage_X0_Z0.Nin_Ounce_NVN2.bphsc.zs"   # one of the game's
# 16 byte-identical empty static compounds (53,264 bytes unpacked, every body section empty)
DEKU_BANC = "Banc/GameBancParam/InsideTheDekuTree.game__banc__GameBancParam.bgyml"   # B42 on
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

        self.added = {}                      # new hashed entries {crc32: size}, inserted in order on save

    def need(self, romfs_path, size, extra=512):
        """Make sure the entry for romfs_path (with or without .zs) is at least size + extra. A path the table
        doesn't have gets a new entry (the hashed entries are sorted by hash; the game binary-searches them)."""
        p = romfs_path[:-3] if romfs_path.endswith(".zs") else romfs_path
        h = zlib.crc32(p.encode())
        want = (size + extra + 7) & ~7
        if h not in self.at:
            self.added[h] = max(self.added.get(h, 0), want)
            return 0, self.added[h]
        at = self.at[h]
        old = struct.unpack_from("<I", self.t, at)[0]
        new = max(old, want)
        struct.pack_into("<I", self.t, at, new)
        return old, new

    def save(self, path):
        import zstandard
        t = self.t
        if self.added:
            _, n_hashed, n_named = struct.unpack_from("<III", t, 10)
            end = 22 + 8 * n_hashed
            rows = [struct.unpack_from("<II", t, 22 + 8 * i) for i in range(n_hashed)]
            rows = sorted(rows + list(self.added.items()))
            t = bytearray(t[:22]) + b"".join(struct.pack("<II", h, s) for h, s in rows) + t[end:]
            struct.pack_into("<I", t, 14, len(rows))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(zstandard.ZstdCompressor(level=19, write_content_size=True).compress(bytes(t)))


class Game:
    def __init__(self, romfs):
        self.r = Path(romfs)
        self.dicts = zsmod.dicts_by_id(self.r / "Pack/ZsDic.pack.zs")

    def byml(self, rel):
        return byml.read(self.r / rel, self.dicts)

    def raw(self, rel):
        return zsmod.unzs((self.r / rel).read_bytes(), self.dicts)[0]


PRIMITIVES = ("Box", "Polytope", "Capsule", "Sphere", "Cylinder")


def shape_entry(raw):
    """Size table entry a ShapeParam .bgyml (inside a pack) needs: the file plus its parsed parts. Every file inside a
    pack has its own entry, and the game's parsed shape has to fit in it (B5 / B7 / B8 crashed for lack of it).
    Fitted on the 2,478 ShapeParams of 1.1.1 that have only these primitives: mean error 9 bytes, max 183."""
    shape = byml.loads(raw)
    parts = {k: shape.get(k) or [] for k in PRIMITIVES}
    presets = sum(len(p.get("MaterialPresets") or []) for v in parts.values() for p in v)
    vertices = sum(len(p.get("Vertices") or []) for p in parts["Polytope"])
    cost = {"Box": 176, "Polytope": 336, "Capsule": 173, "Sphere": 166, "Cylinder": 173}
    return 5862 + len(raw) + sum(cost[k] * len(v) for k, v in parts.items()) + 8 * presets + 12 * vertices


def write_mod(out, files, game, notes, extra=None, entries=None):
    """files: {romfs path: (object or bytes, dict id)} -> out/romfs/..., with a fitted size table.
    extra: {romfs path: bytes of room on top of the file's size} (default 512).
    entries: {path of a file inside a pack: size table entry it needs} (raised, never lowered)."""
    rstb = Rstb(game.r / RSTB)
    for rel, size in (entries or {}).items():
        old, new = rstb.need(rel, size, 0)
        notes.append(f"{rel}: size table {old} -> {new}")
    for rel, (obj, did) in files.items():
        raw = obj if isinstance(obj, bytes) else byml.dumps(obj)
        old, new = rstb.need(rel, len(raw), (extra or {}).get(rel, 512))
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


def a_chest(game, pos, yaw=0.0, gyaml="Obj_TBox_A_02"):
    """A copy of the Deku Tree's compass chest, moved (a landmark you can see). Another gyaml: a copy of the Deku
    Tree's first chest of that type (Obj_TBox_A_01: the small Deku nut chest), with the compass chest's room index."""
    st = game.byml(DEKU_S)
    compass = next(a for a in st["Actors"] if a["Gyaml"] == "Obj_TBox_A_02" and a.get("Dynamic", {}).get("Drop__DropActor") == "Item_Dungeon_Compass")
    src = compass if gyaml == "Obj_TBox_A_02" else next(a for a in st["Actors"] if a["Gyaml"] == gyaml)
    c = copy.deepcopy(src)
    if src is not compass:
        c["Dynamic"]["DefaultDungeonRoomIndex"] = copy.deepcopy(compass["Dynamic"]["DefaultDungeonRoomIndex"])
    h = new_hash()
    c["Hash"], c["Phive"] = h, {"Placement": {"ID": h}}
    c["SRTHash"] = byml.U32(rng.getrandbits(32))
    c["Translate"] = [float(v) for v in pos]
    c["Rotate"] = [0.0, float(yaw), 0.0]
    c.pop("Links", None)
    return c


TBOX_PACK = "Pack/Actor/Obj_TBox_A_02.pack.zs"
KINEMATIC_BODY = f"Phive/RigidBodyEntityParam/{HOST}_Kinematic.phive__RigidBodyEntityParam.bgyml"


def host_pack(game, boxes, pre_actor=None, kinematic=False):
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
    if pre_actor:                                  # e.g. Anchor, as the air walls use, instead of ConstPassive
        ap = f"Actor/{HOST}.engine__actor__ActorParam.bgyml"
        a = byml.loads(files[ap])
        a["Components"]["PreActorSettingRef"] = f"?ActorSystem/PreActorSetting/{pre_actor}.game__actor__PreActorSetting.bgyml"
        files[ap] = byml.dumps(a)
    if kinematic:
        # Static bodies (no MotionType) come from the scene's pre-built StaticCompoundBody; a chest's main body is
        # Kinematic (MotionType = murmur3("Kinematic")) and is built when the actor loads. Use the chest body's setup.
        tbox = zstool.Sarc(game.raw(TBOX_PACK))
        body = byml.loads(tbox.read("Phive/RigidBodyEntityParam/Obj_TBox_Body_2_Body.phive__RigidBodyEntityParam.bgyml"))
        body["ShapeName"] = "Physical"
        files[KINEMATIC_BODY] = byml.dumps(body)
        cs = f"Phive/ControllerSetParam/{HOST}.phive__ControllerSetParam.bgyml"
        c = byml.loads(files[cs])
        c["RigidBodyEntityNamePathAry"] = [{"FilePath": "Work/" + KINEMATIC_BODY.replace(".bgyml", ".gyml"), "Name": "Physical"}]
        files[cs] = byml.dumps(c)
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


def test_b46(game, out):
    """Test C (the Deku Tree emptied to its spawn points) plus the scene's pre-built static collision replaced by one of
    the game's empty static compounds, so the Deku Tree's walls, floor and vines (which C kept) should be gone too."""
    st, dy = emptied_deku(game)
    files = {DEKU_S: (st, 3), DEKU_D: (dy, 3), DEKU_COMPOUND: (game.raw(EMPTY_COMPOUND), 1)}
    write_mod(out, files, game, ["Test B46: test C plus the Deku Tree's static compound (walls, floor, vines) replaced by the game's",
                                 f"empty one ({EMPTY_COMPOUND}). Only that file differs from C."])


def test_b2(game, out):
    """Like B, but the box actor is placed without Bakeable (so it isn't expected in the scene's pre-built static
    collision), plus an air-wall cube (an actor that always builds its own collision) 4 m to its left."""
    dy = game.byml(DEKU_D)
    sx, sy, sz = SPAWN
    B = [((-1.5, 0.0, -1.5), (1.5, 1.0, 1.5))]                           # a 3 x 3 x 1 m block on the floor
    dy["Actors"].append(placed(HOST, (sx, sy, sz - 4)))                   # no Bakeable
    dy["Actors"].append(placed("FldObj_AirWall_Common_Cube", (sx - 4, sy, sz - 4), scale=(3, 1, 3)))
    files = {DEKU_D: (dy, 3), HOST_PACK: (host_pack(game, B), 4)}
    notes = ["Test B2: Inside the Deku Tree as normal. 4 m in front of the entrance: the tree-root actor (no Bakeable) with",
             "a 3 x 3 x 1 m box as collision. 4 m to its left: an air-wall cube scaled to 3 x 1 x 3 m."]
    write_mod(out, files, game, notes)


def test_b3(game, out):
    """B2 with the box actor set up like an air wall (PreActorSetting Anchor), and the air-wall cube moved onto the
    path to it: a 1 x 1.5 x 1 m post halfway between the entrance and the tree."""
    dy = game.byml(DEKU_D)
    sx, sy, sz = SPAWN
    B = [((-1.5, 0.0, -1.5), (1.5, 1.0, 1.5))]
    dy["Actors"].append(placed(HOST, (sx, sy, sz - 4)))
    dy["Actors"].append(placed("FldObj_AirWall_Common_Cube", (sx, sy, sz - 2), scale=(1, 1.5, 1)))
    files = {DEKU_D: (dy, 3), HOST_PACK: (host_pack(game, B, pre_actor="Anchor"), 4)}
    notes = ["Test B3: the tree-root actor 4 m in front of the entrance, set up like an air wall (PreActorSetting Anchor),",
             "3 x 3 x 1 m box collision; an air-wall post (1 x 1.5 x 1 m) halfway to it, 2 m from the entrance."]
    write_mod(out, files, game, notes)


def test_b4(game, out):
    """The tree-root actor with a Kinematic body (like a chest's), and a copied chest 2 m from the entrance as a check
    that a newly placed actor can collide at all."""
    dy = game.byml(DEKU_D)
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    B = [((-1.5, 0.0, -1.5), (1.5, 1.0, 1.5))]
    dy["Actors"].append(placed(HOST, (sx, sy, sz - 4)))
    st["Actors"].append(a_chest(game, (sx, sy, sz - 2)))
    files = {DEKU_S: (st, 3), DEKU_D: (dy, 3), HOST_PACK: (host_pack(game, B, pre_actor="Anchor", kinematic=True), 4)}
    notes = ["Test B4: the tree-root actor 4 m in front of the entrance with a Kinematic rigid body (the chest body's",
             "settings) and 3 x 3 x 1 m box collision; a copy of the compass chest 2 m from the entrance as a check."]
    write_mod(out, files, game, notes)


def tbox_with_boxes(game, extra, presets=None, drop_polytopes=0):
    """Obj_TBox_A_02's pack with extra boxes [(min, max), chest-local metres] added to its main body's shape."""
    sarc = zstool.Sarc(game.raw(TBOX_PACK))
    files = {n: sarc.read(n) for n in sarc.names()}
    name = "Phive/ShapeParam/Obj_TBox_A_02__Body_0.phive__ShapeParam.bgyml"
    shape = byml.loads(files[name])
    proto = shape["Box"][0]
    ac = shape["AutoCalc"]
    if drop_polytopes:                       # keep the number of parts: swap polytopes for the added boxes
        shape["Polytope"] = shape["Polytope"][:-drop_polytopes]
    for lo, hi in extra:
        b = copy.deepcopy(proto)
        b["Center"] = f3(0, 0, 0)
        b["HalfExtents"] = f3(*(np.subtract(hi, lo) / 2))
        b["OffsetTranslation"] = f3(*(np.add(lo, hi) / 2))
        if presets is not None:
            b["MaterialPresets"] = list(presets)
        shape["Box"].append(b)
        for i, k in enumerate("XYZ"):
            ac["Min"][k] = float(min(ac["Min"][k], lo[i]))
            ac["Max"][k] = float(max(ac["Max"][k], hi[i]))
    files[name] = byml.dumps(shape)
    return zsmod.sarc_pack(files, like=game.raw(TBOX_PACK))


def test_b5(game, out):
    """Boxes added to a chest's own collision (a chest builds its collision when it loads)."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)),     # a 3 x 3 m slab, 0.5 m high, beside the chest (+x)
             ((-2.5, 0.0, -0.5), (-1.5, 2.5, 0.5))]   # a 1 x 1 m pillar, 2.5 m tall, on the other side (-x)
    files = {DEKU_S: (st, 3), TBOX_PACK: (tbox_with_boxes(game, extra), 4)}
    notes = ["Test B5: a compass chest 3 m from the entrance. Its own collision gets two extra boxes: a 3 x 3 m slab,",
             "0.5 m high, starting 1.5 m to one side, and a 1 x 2.5 x 1 m pillar 2 m to the other side. Every Obj_TBox_A_02",
             "chest gets them while this is on."]
    write_mod(out, files, game, notes)


def tbox_bigger_base(game, half=(2.0, 0.25, 2.0)):
    """Obj_TBox_A_02's pack with the one Box of its main body's shape made bigger (no boxes added: adding them made
    the game crash while building the shape, test B5)."""
    sarc = zstool.Sarc(game.raw(TBOX_PACK))
    files = {n: sarc.read(n) for n in sarc.names()}
    name = "Phive/ShapeParam/Obj_TBox_A_02__Body_0.phive__ShapeParam.bgyml"
    shape = byml.loads(files[name])
    b = shape["Box"][0]
    b["HalfExtents"] = f3(*half)
    b["OffsetTranslation"] = f3(0, half[1], 0)
    ac = shape["AutoCalc"]
    ac["Min"] = f3(min(ac["Min"]["X"], -half[0]), ac["Min"]["Y"], min(ac["Min"]["Z"], -half[2]))
    ac["Max"] = f3(max(ac["Max"]["X"], half[0]), max(ac["Max"]["Y"], 2 * half[1]), max(ac["Max"]["Z"], half[2]))
    files[name] = byml.dumps(shape)
    return zsmod.sarc_pack(files, like=game.raw(TBOX_PACK))


def test_b6(game, out):
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    files = {DEKU_S: (st, 3), TBOX_PACK: (tbox_bigger_base(game), 4)}
    write_mod(out, files, game, ["Test B6: a compass chest 3 m from the entrance; the base box of every Obj_TBox_A_02 chest's",
                                 "collision made 4 x 0.5 x 4 m (was about 1.3 x 0.06 x 1 m). Nothing added."])


def test_b7(game, out):
    """B5 again (two boxes added to the chest's shape), with far more room in the size table entry for the chest's
    pack (the entry is the memory for loading and unpacking it; B5's +512 bytes likely ran out), and material presets
    that allow ledge grabs."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)), ((-2.5, 0.0, -0.5), (-1.5, 2.5, 0.5))]
    files = {DEKU_S: (st, 3), TBOX_PACK: (tbox_with_boxes(game, extra, presets=["Material_Wood_Thick"]), 4)}
    write_mod(out, files, game, ["Test B7: as B5 (3 x 3 x 0.5 m slab on one side, 1 x 2.5 x 1 m pillar on the other, added to the",
                                 "chest's shape), with the chest pack's size table entry raised by 256 KiB instead of 512 bytes;",
                                 "the added boxes have only Material_Wood_Thick (no Wall_NoClamber). Open the chest first."],
              extra={TBOX_PACK: 256 * 1024})


ACTORINFO = "RSDB/ActorInfo.Product.111.rstbl.byml.zs"


def actorinfo_heap(game, sizes):
    """RSDB ActorInfo with InstanceHeapSize changed: {actor name: bytes}. Each actor gets a fixed heap of that size;
    a bigger collision shape needs more (B5 / B7 crashed with the chest's own 195,616)."""
    rows = game.byml(ACTORINFO)
    for r in rows:
        if r.get("__RowId") in sizes:
            r["InstanceHeapSize"] = type(r["InstanceHeapSize"])(sizes[r["__RowId"]])
    return rows


def test_b8(game, out):
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)), ((-2.5, 0.0, -0.5), (-1.5, 2.5, 0.5))]
    files = {DEKU_S: (st, 3), TBOX_PACK: (tbox_with_boxes(game, extra, presets=["Material_Wood_Thick"]), 4),
             ACTORINFO: (actorinfo_heap(game, {"Obj_TBox_A_02": 195616 + 1024 * 1024}), None)}
    write_mod(out, files, game, ["Test B8: as B7 (slab and pillar added to the chest's shape, size table room), plus the chest's",
                                 "InstanceHeapSize in RSDB/ActorInfo raised from 195,616 to 1,244,192 bytes. Open the chest first."],
              extra={TBOX_PACK: 256 * 1024})


def test_b9(game, out):
    """Two boxes added to the chest's shape while two of its four polytopes (side walls) are removed: same number of
    parts (5). Adding parts crashed (B5, B7, B8) even with a bigger size table entry and actor heap."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)), ((-2.5, 0.0, -0.5), (-1.5, 2.5, 0.5))]
    files = {DEKU_S: (st, 3), TBOX_PACK: (tbox_with_boxes(game, extra, presets=["Material_Wood_Thick"], drop_polytopes=2), 4)}
    write_mod(out, files, game, ["Test B9: the chest's main shape as 3 boxes + 2 polytopes (was 1 + 4): slab and pillar added,",
                                 "two side walls removed, same number of parts. Open the chest first."])


def test_b10(game, out):
    """Re-check of B2 / B3 that can't be missed: a newly placed air-wall cube as a 4 x 4 m platform, 0.6 m high, where
    B9's slab was (beside the chest 3 m from the entrance), with a second chest floating on top to mark it.
    No pack is changed."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    st["Actors"].append(a_chest(game, (sx + 3, sy + 0.6, sz - 3)))
    st["Actors"].append(placed("FldObj_AirWall_Common_Cube", (sx + 3, sy, sz - 3), scale=(4, 0.6, 4),
                               extra={"Rotate": [0.0, 0.0, 0.0]}))
    write_mod(out, {DEKU_S: (st, 3)}, game, ["Test B10: a chest 3 m from the entrance (as in B9) and, where B9's slab was, a new",
                                             "air-wall cube scaled to a 4 x 4 x 0.6 m platform with a second chest on top marking it."])


TBOX_SHAPE = "Phive/ShapeParam/Obj_TBox_A_02__Body_0.phive__ShapeParam.bgyml"


def tbox_shape_entry(pack):
    """The chest shape's own size table entry for a changed pack, with 4 KiB of room."""
    return shape_entry(zstool.Sarc(pack).read(TBOX_SHAPE)) + 4096


def test_b11(game, out):
    """B7 again (slab and pillar added to the chest's shape), with the shape file's own size table entry raised.
    B5 / B7 / B8 raised only the pack's entry; the shape needs about 11,458 bytes and the game gives it 10,824."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)), ((-2.5, 0.0, -0.5), (-1.5, 2.5, 0.5))]
    pack = tbox_with_boxes(game, extra, presets=["Material_Wood_Thick"])
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B11: as B7 (3 x 3 x 0.5 m slab on one side, 1 x 2.5 x 1 m pillar on the other, added to the chest's",
               "shape), plus the shape file's own size table entry raised. Open the chest first."],
              entries={TBOX_SHAPE: tbox_shape_entry(pack)})


def stair_boxes(rows=20, cols=20, step=0.25):
    """rows x cols 1 x 1 m columns ahead of the chest (-z, into the room), each row one step higher: an invisible
    staircase cols m wide, rising to rows * step m."""
    return [((c - cols / 2, 0.0, -2.0 - r - 1), (c - cols / 2 + 1, step * (r + 1), -2.0 - r))
            for r in range(rows) for c in range(cols)]


def test_b12(game, out):
    """400 boxes in the chest's shape (the game's biggest shape has 236 parts), with the shape's entry raised and
    the chest's actor heap raised by 2 MiB (room for the built Havok shape; how much it needs isn't known)."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    pack = tbox_with_boxes(game, stair_boxes(), presets=["Material_Wood_Thick"])
    files = {DEKU_S: (st, 3), TBOX_PACK: (pack, 4),
             ACTORINFO: (actorinfo_heap(game, {"Obj_TBox_A_02": 195616 + 2 * 1024 * 1024}), None)}
    write_mod(out, files, game,
              ["Test B12: 400 boxes added to the chest's shape: an invisible staircase 20 m wide, 20 steps of",
               "0.25 m (up to 5 m), starting 2 m in front of the chest, going into the room. The shape's own",
               "size table entry is raised, and the chest's InstanceHeapSize by 2 MiB. Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries={TBOX_SHAPE: tbox_shape_entry(pack)})


MAP_SHAPE = "Phive/ShapeParam/Obj_TBox_A_02__KaeGaeMap.phive__ShapeParam.bgyml"
TBOX_CSP = "Phive/ControllerSetParam/Obj_TBox_A_02.phive__ControllerSetParam.bgyml"


def tbox_own_map_shape(game, extra, presets=None, grow_bounds=True, source=None, body="Body_Body", chest="Obj_TBox_A_02"):
    """Obj_TBox_A_02's pack where only the open chest's body (Body_Body) gets a shape of its own: the chest's shape
    plus `extra` boxes, in a new file. Body_0 stays as it is for the other user of it, the Tgt sensor (TgtBody):
    B12 put the boxes in Body_0 and the chest lost its Open prompt. `chest`: another chest type's pack (B30 on:
    Obj_TBox_A_01, whose closed body is set up the same way); the added boxes are always copies of A_02's box."""
    pack_p = f"Pack/Actor/{chest}.pack.zs"
    csp_p = f"Phive/ControllerSetParam/{chest}.phive__ControllerSetParam.bgyml"
    map_p = f"Phive/ShapeParam/{chest}__KaeGaeMap.phive__ShapeParam.bgyml"
    sarc = zstool.Sarc(game.raw(pack_p))
    files = {n: sarc.read(n) for n in sarc.names()}
    shape = byml.loads(files[source or TBOX_SHAPE])
    proto, ac = byml.loads(zstool.Sarc(game.raw(TBOX_PACK)).read(TBOX_SHAPE))["Box"][0], shape["AutoCalc"]
    shape.setdefault("Box", [])
    for lo, hi in extra:
        b = copy.deepcopy(proto)
        b["Center"] = f3(0, 0, 0)
        b["HalfExtents"] = f3(*(np.subtract(hi, lo) / 2))
        b["OffsetTranslation"] = f3(*(np.add(lo, hi) / 2))
        if presets is not None:
            b["MaterialPresets"] = list(presets)
        shape["Box"].append(b)
        for i, k in enumerate("XYZ"):
            if grow_bounds:
                ac["Min"][k] = float(min(ac["Min"][k], lo[i]))
                ac["Max"][k] = float(max(ac["Max"][k], hi[i]))
    files[map_p] = byml.dumps(shape)
    csp = byml.loads(files[csp_p])
    row = next(r for r in csp["ShapeNamePathAry"] if r["Name"] == body)
    row["FilePath"] = "Work/" + map_p[:-len(".bgyml")] + ".gyml"
    files[csp_p] = byml.dumps(csp)
    pack = zsmod.sarc_pack(files, like=game.raw(pack_p))
    entries = {map_p: shape_entry(files[map_p]) + 4096, csp_p: len(files[csp_p]) + 8 * 1024 + 2048}
    return pack, entries


def test_b13(game, out):
    """B12's 400-box staircase, in a shape file of its own that only the open chest's body uses."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    pack, entries = tbox_own_map_shape(game, stair_boxes(), presets=["Material_Wood_Thick"])
    files = {DEKU_S: (st, 3), TBOX_PACK: (pack, 4),
             ACTORINFO: (actorinfo_heap(game, {"Obj_TBox_A_02": 195616 + 2 * 1024 * 1024}), None)}
    write_mod(out, files, game,
              ["Test B13: B12's invisible staircase (400 boxes, 20 m wide, 20 steps of 0.25 m up to 5 m, from 2 m in",
               "front of the chest into the room), but in a new shape file that only the open chest's body uses; the",
               "chest's own shape (also used by its Tgt sensor) is unchanged. New size table entry for the new file.",
               "Chest InstanceHeapSize + 2 MiB as in B12. Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def test_b14(game, out):
    """B13 without the RSDB ActorInfo change (no bigger chest heap). B12 and B13 lost the chest's Open prompt; B11,
    which worked, didn't ship ActorInfo. If this crashes instead, the built shape needs the heap."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    pack, entries = tbox_own_map_shape(game, stair_boxes(), presets=["Material_Wood_Thick"])
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B14: as B13 (the 400-box staircase in the open chest's own new shape file), but without the",
               "RSDB ActorInfo file: the chest's InstanceHeapSize stays at the game's 195,616. Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def test_b15(game, out):
    """B14 with the new shape's AutoCalc (centre, bounds, mass) left as the chest's own. B12-B14 grew its bounds over
    the whole staircase (centre about 11 m behind the chest, 2.5 m up) and lost the Open prompt; B11 grew them by
    about 1 m and kept it. The open body is the chest's Main body, which the prompt may be aimed at."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    pack, entries = tbox_own_map_shape(game, stair_boxes(), presets=["Material_Wood_Thick"], grow_bounds=False)
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B15: as B14 (the 400-box staircase in the open chest's own new shape file, the game's heap), but",
               "the new shape's AutoCalc (centre, bounds, mass) is left as the chest's own. Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def side_stair_boxes(rows=20, cols=20, step=0.25, start=4.0):
    """stair_boxes turned to the chest's +x side, where B11's slab worked: rows x cols 1 x 1 m columns from `start` m
    beside the chest outwards, each row one step higher, cols m deep (centred on the chest)."""
    return [((start + r, 0.0, c - cols / 2), (start + r + 1, step * (r + 1), c - cols / 2 + 1))
            for r in range(rows) for c in range(cols)]


def test_b16(game, out):
    """B15 with the staircase beside the chest (+x, from 4 m out) instead of in front of / behind it. B11's boxes were
    beside the chest and it kept its Open prompt; B12-B15 had the staircase from 2 m along -z and lost it."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    pack, entries = tbox_own_map_shape(game, side_stair_boxes(), presets=["Material_Wood_Thick"], grow_bounds=False)
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B16: as B15 (400 boxes in the open chest's own shape file, the chest's bounds, the game's heap), but",
               "the staircase is beside the chest: from 4 m out to its +x side (where B11's slab was), 20 m deep,",
               "rising 0.25 m per 1 m step away from the chest. Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def side_stair_test(game, out, cols, label):
    """B16's staircase beside the chest, 20 steps of `cols` boxes. B16 (400 boxes, 405 parts) lost the Open prompt
    wherever the boxes went; the biggest shape in the game has 236 parts. B17 / B18 sit just under and over 256."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    boxes = side_stair_boxes(cols=cols)
    pack, entries = tbox_own_map_shape(game, boxes, presets=["Material_Wood_Thick"], grow_bounds=False)
    parts = len(boxes) + 5
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              [f"Test {label}: as B16, but {len(boxes)} boxes ({parts} parts in the shape with the chest's own 5): 20 steps of",
               f"{cols} boxes, from 4 m out on the chest's +x side, {cols} m deep. Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def test_b19(game, out):
    """Control: B11's two boxes (which kept the Open prompt), but put the B13-B17 way: in the new shape file used only
    by the open body, with the rewritten ControllerSetParam and the added size table entry. B17 (245 parts) still lost
    the prompt, and every test since B13 shares this setup."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)), ((-2.5, 0.0, -0.5), (-1.5, 2.5, 0.5))]
    pack, entries = tbox_own_map_shape(game, extra, presets=["Material_Wood_Thick"])
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B19: B11's slab and pillar, but in a new shape file only the open chest's body uses (as in",
               "B13-B17), with the ControllerSetParam pointing at it and a new size table entry. Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def tiled_slab(nx=15, nz=16, lo=(1.5, 0.0, -1.5), hi=(4.5, 0.5, 1.5)):
    """B11's 3 x 3 x 0.5 m slab cut into nx x nz tiles (same footprint, same top)."""
    dx, dz = (hi[0] - lo[0]) / nx, (hi[2] - lo[2]) / nz
    return [((lo[0] + i * dx, lo[1], lo[2] + j * dz), (lo[0] + (i + 1) * dx, hi[1], lo[2] + (j + 1) * dz))
            for i in range(nx) for j in range(nz)]


def test_b20(game, out):
    """B17's part count (245) in B11's footprint: B11's slab cut into 240 tiles, no pillar. B17's staircase (245 parts,
    up to 24 m out, into the wall) lost the Open prompt; B19 (B11's two boxes, same setup) kept it. Tells count apart
    from size / overlapping the level."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    pack, entries = tbox_own_map_shape(game, tiled_slab(), presets=["Material_Wood_Thick"])
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B20: B11's 3 x 3 x 0.5 m slab beside the chest, cut into 240 tiles (15 x 16), no pillar: 245 parts,",
               "as many as B17, in B11's footprint. Set up as B19 (own shape file). Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def test_b21(game, out):
    """B19 (B11's slab and pillar, own shape file) plus one 2 x 0.5 x 2 m box floating 12 m into the room (-z) and
    8 m up, touching nothing. B20 (245 parts in B11's footprint) kept the Open prompt, so the count isn't what broke
    B12-B17; their staircases reached 20+ m and ran into the floor and walls. This tells reach apart from overlap."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)), ((-2.5, 0.0, -0.5), (-1.5, 2.5, 0.5)),
             ((-1.0, 8.0, -13.0), (1.0, 8.5, -11.0))]
    pack, entries = tbox_own_map_shape(game, extra, presets=["Material_Wood_Thick"])
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B21: as B19 (B11's slab and pillar in the open chest's own shape file), plus one 2 x 0.5 x 2 m box",
               "floating 12 m into the room and 8 m up, touching nothing. Open the chest first."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


TBOX_CLOSE_SHAPE = "Phive/ShapeParam/Obj_TBox_A_02__Tgt.phive__ShapeParam.bgyml"   # the closed chest's Body_Close


def test_b22(game, out):
    """The boxes on the closed chest's body (CloseBody, a Static body, shape Body_Close), which is solid without
    opening the chest. B12-B17 and B21 (a shape reaching 6+ m from the chest) lost the Open prompt, so whether far
    boxes are solid couldn't be checked. Here: the closed chest's own two polytopes, B11's slab beside it as a check,
    and a 1 m wide bridge from 2 m in front of the chest 15 m into the room, ending in a 3 x 3 m landing."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)),            # B11's slab (right of the entrance)
             ((-0.5, 0.1, -17.0), (0.5, 0.3, -2.0)),         # a 1 m wide bridge, top 0.3 m, into the room
             ((-1.5, 0.1, -20.0), (1.5, 0.3, -17.0))]        # a 3 x 3 m landing at its end
    pack, entries = tbox_own_map_shape(game, extra, presets=["Material_Wood_Thick"],
                                       source=TBOX_CLOSE_SHAPE, body="Body_Close")
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B22: DON'T open the chest. The closed chest's body (Static, shape Body_Close) gets a shape of its own:",
               "its two polytopes, B11's slab beside it, and a 1 m wide invisible bridge (top 0.3 m) from 2 m in front",
               "of the chest 15 m into the room, ending in a 3 x 3 m landing. Open chest unchanged."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def test_b23(game, out):
    """B12's 400-box staircase on the closed chest's body (as B22), from 2 m in front of the chest into the room.
    B22's bridge was solid 15 m out; this checks 400 boxes (402 parts with the closed chest's 2 polytopes) and the
    load time."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    pack, entries = tbox_own_map_shape(game, stair_boxes(), presets=["Material_Wood_Thick"],
                                       source=TBOX_CLOSE_SHAPE, body="Body_Close")
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B23: DON'T open the chest. B12's invisible staircase (400 boxes, 20 m wide, 20 steps of 0.25 m up",
               "to 5 m, from 2 m in front of the chest into the room) on the closed chest's body, as in B22."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def minecraft_cut(glb, radius, at):
    """The Minecraft map's (2 radius) x (2 radius) block cut around its spawn column, as merged boxes in host-local
    metres, placed so the spawn column's top sits at `at`."""
    solid, _ = fill_and_merge(voxels(glb, 70.0))
    cx, cz, top = spawn_column(solid)
    x0, z0 = max(cx - radius, 0), max(cz - radius, 0)
    solid = solid[x0:cx + radius, :, z0:cz + radius]
    cx, cz = cx - x0, cz - z0
    off = np.subtract(at, (cx + 0.5, top, cz + 0.5))
    return [(tuple(np.add(lo, off)), tuple(np.add(hi, off))) for lo, hi in greedy(solid)], solid.shape


def test_b24(game, out, glb):
    """The 48 x 48 block cut of the Minecraft map (1,425 boxes) on the closed chest's body, as B23 (400 boxes,
    solid). Placed in the normal Deku Tree with the map's spawn column top level with the chest's base, 24 m in front
    of the chest (into the room): nothing of it rises above the floor within 3 m of the chest. Only the box count
    changes from B23."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    boxes, size = minecraft_cut(glb, 24, (0.0, 0.0, -24.0))
    pack, entries = tbox_own_map_shape(game, boxes, presets=["Material_Wood_Thick"],
                                       source=TBOX_CLOSE_SHAPE, body="Body_Close")
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              [f"Test B24: DON'T open the chest. The Minecraft map's 48 x 48 block cut ({len(boxes)} boxes, {size[0]} x {size[1]} x",
               f"{size[2]} blocks, 1 block = 1 m) on the closed chest's body, as in B23. Its spawn column's top is level with the",
               "chest's base, 24 m in front of the chest; the map spans about 1 to 49 m in front of it, as invisible hills and walls in",
               "and under the room."],
              extra={TBOX_PACK: 512 * 1024}, entries=entries)
    return len(boxes)


def test_b25(game, out, glb):
    """B24 with the chest's InstanceHeapSize raised by 2 MiB. In B24 (1,425 boxes) the chest didn't appear at all;
    B23 (400 boxes) fit the game's 195,616. The built shape is probably made in that heap."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    boxes, size = minecraft_cut(glb, 24, (0.0, 0.0, -24.0))
    pack, entries = tbox_own_map_shape(game, boxes, presets=["Material_Wood_Thick"],
                                       source=TBOX_CLOSE_SHAPE, body="Body_Close")
    files = {DEKU_S: (st, 3), TBOX_PACK: (pack, 4),
             ACTORINFO: (actorinfo_heap(game, {"Obj_TBox_A_02": 195616 + 2 * 1024 * 1024}), None)}
    write_mod(out, files, game,
              [f"Test B25: DON'T open the chest. As B24 (the Minecraft cut, {len(boxes)} boxes, on the closed chest's body,",
               "about 1 to 49 m in front of the chest), plus the chest's InstanceHeapSize raised from 195,616 by 2 MiB."],
              extra={TBOX_PACK: 512 * 1024}, entries=entries)


def test_b26(game, out, nx=57, nz=25, label="B26"):
    """B25's box count (1,425) and heap raise, but in B11's 3 x 3 m footprint: B11's slab cut into 57 x 25 tiles, on
    the closed chest's body. B24 / B25 (the Minecraft cut: 48 x 48 m, 6 m up to 43 m down) had no chest at all; B23
    (400 boxes, about 22 x 20 x 5 m) worked. Tells the count / file size apart from the reach."""
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    boxes = tiled_slab(nx, nz)
    pack, entries = tbox_own_map_shape(game, boxes, presets=["Material_Wood_Thick"],
                                       source=TBOX_CLOSE_SHAPE, body="Body_Close")
    files = {DEKU_S: (st, 3), TBOX_PACK: (pack, 4),
             ACTORINFO: (actorinfo_heap(game, {"Obj_TBox_A_02": 195616 + 2 * 1024 * 1024}), None)}
    write_mod(out, files, game,
              [f"Test {label}: DON'T open the chest. B11's 3 x 3 x 0.5 m slab beside the chest, cut into {len(boxes)} tiles ({nx} x {nz}),",
               "on the closed chest's body; chest InstanceHeapSize + 2 MiB, as in B25."],
              extra={TBOX_PACK: 512 * 1024}, entries=entries)


# ---------------------------------------------------------------- B30-B32: the Minecraft cut over two chests

A01 = "Obj_TBox_A_01"
A01_PACK = f"Pack/Actor/{A01}.pack.zs"
A01_CLOSE_SHAPE = f"Phive/ShapeParam/{A01}__Tgt.phive__ShapeParam.bgyml"   # A_01's Body_Close (1 polytope)
A01_HEAP, A02_HEAP = 178704, 195616                                          # their InstanceHeapSize in 1.1.1
A01_AT = 2.0                                                                 # A_01 sits 2 m right of A_02


def minecraft_halves(glb, radius, at, split):
    """minecraft_cut, split at grid column x = split into two shapes greedied on their own: (left, right, size).
    With radius 24 and split 24 (the spawn column's x): 699 + 729 boxes."""
    solid, _ = fill_and_merge(voxels(glb, 70.0))
    cx, cz, top = spawn_column(solid)
    x0, z0 = max(cx - radius, 0), max(cz - radius, 0)
    solid = solid[x0:cx + radius, :, z0:cz + radius]
    cx, cz = cx - x0, cz - z0
    off = np.subtract(at, (cx + 0.5, top, cz + 0.5))
    halves = []
    for keep in (slice(0, split), slice(split, None)):
        s = np.zeros_like(solid)
        s[keep] = solid[keep]
        halves.append([(tuple(np.add(lo, off)), tuple(np.add(hi, off))) for lo, hi in greedy(s)])
    return halves[0], halves[1], solid.shape


def shift(boxes, dx):
    return [((lo[0] + dx, lo[1], lo[2]), (hi[0] + dx, hi[1], hi[2])) for lo, hi in boxes]


def test_b30(game, out):
    """Control for the second chest type: B22's bridge and landing (no slab) on Obj_TBox_A_01's closed body
    (CloseBody, Static, shape Body_Close = Obj_TBox_A_01__Tgt), A_01 heap + 2 MiB as B26-B29. The A_01 chest sits
    where B32 puts it, 2 m right of the usual chest spot. Nothing else in the scene changes."""
    rng.seed("B30")
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx + A01_AT, sy, sz - 3), gyaml=A01))
    extra = [((-0.5, 0.1, -17.0), (0.5, 0.3, -2.0)),         # B22's 1 m wide bridge, top 0.3 m, into the room
             ((-1.5, 0.1, -20.0), (1.5, 0.3, -17.0))]        # B22's 3 x 3 m landing at its end
    pack, entries = tbox_own_map_shape(game, extra, presets=["Material_Wood_Thick"],
                                       source=A01_CLOSE_SHAPE, body="Body_Close", chest=A01)
    files = {DEKU_S: (st, 3), A01_PACK: (pack, 4),
             ACTORINFO: (actorinfo_heap(game, {A01: A01_HEAP + 2 * 1024 * 1024}), None)}
    write_mod(out, files, game,
              ["Test B30: DON'T open the chests. Control for a second chest type: a small chest (Obj_TBox_A_01, a copy of the",
               "Deku Tree's Deku nut chest) 3 m in front of the entrance, 2 m to the right. Its closed body gets a shape of",
               "its own: its polytope plus B22's 1 m wide invisible bridge (top 0.3 m) from 2 m in front of it 15 m into the",
               "room, ending in a 3 x 3 m landing. A_01 InstanceHeapSize + 2 MiB."],
              extra={A01_PACK: 64 * 1024}, entries=entries)


def test_b31(game, out, glb):
    """Half of B24's Minecraft cut (the right half, grid x 24-47, with the spawn column: 729 boxes, 731 parts) on
    the closed A_02 chest's body, heap + 2 MiB as B25 / B28. Only change from B25: half the boxes. Tells whether the
    map's own shapes and reach (24 x 48 m, 6 m up to 43 m down) are fine under the part cap."""
    rng.seed("B31")
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    _, right, size = minecraft_halves(glb, 24, (0.0, 0.0, -24.0), 24)
    assert len(right) < 1000
    pack, entries = tbox_own_map_shape(game, right, presets=["Material_Wood_Thick"],
                                       source=TBOX_CLOSE_SHAPE, body="Body_Close")
    files = {DEKU_S: (st, 3), TBOX_PACK: (pack, 4),
             ACTORINFO: (actorinfo_heap(game, {"Obj_TBox_A_02": A02_HEAP + 2 * 1024 * 1024}), None)}
    write_mod(out, files, game,
              [f"Test B31: DON'T open the chest. The right half of B24's Minecraft cut ({len(right)} boxes: grid x 24-47 of",
               f"{size[0]} x {size[1]} x {size[2]} blocks, with the spawn column) on the closed chest's body; heap + 2 MiB as B25.",
               "The spawn column's top is level with the chest's base, 24 m in front of it. The half spans from the chest's",
               "line about 24 m to the right, and 1 to 49 m in front."],
              extra={TBOX_PACK: 512 * 1024}, entries=entries)
    return len(right)


def test_b32(game, out, glb):
    """The whole Minecraft cut over two chest types: B31's right half (729 boxes) on A_02's closed body and the
    left half (699 boxes) on A_01's closed body (B30's setup), the A_01 chest 2 m right of the A_02 one. Both heaps
    + 2 MiB. Chests of one type share a pack, so the two halves need two types."""
    rng.seed("B32")
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    st["Actors"].append(a_chest(game, (sx + A01_AT, sy, sz - 3), gyaml=A01))
    left, right, size = minecraft_halves(glb, 24, (0.0, 0.0, -24.0), 24)
    assert len(left) < 1000 and len(right) < 1000
    pack2, e2 = tbox_own_map_shape(game, right, presets=["Material_Wood_Thick"],
                                   source=TBOX_CLOSE_SHAPE, body="Body_Close")
    pack1, e1 = tbox_own_map_shape(game, shift(left, -A01_AT), presets=["Material_Wood_Thick"],
                                   source=A01_CLOSE_SHAPE, body="Body_Close", chest=A01)
    files = {DEKU_S: (st, 3), TBOX_PACK: (pack2, 4), A01_PACK: (pack1, 4),
             ACTORINFO: (actorinfo_heap(game, {"Obj_TBox_A_02": A02_HEAP + 2 * 1024 * 1024,
                                               A01: A01_HEAP + 2 * 1024 * 1024}), None)}
    write_mod(out, files, game,
              [f"Test B32: DON'T open the chests. B24's whole Minecraft cut ({len(left) + len(right)} boxes, {size[0]} x {size[1]} x",
               f"{size[2]} blocks) split at the spawn column: the right half ({len(right)} boxes) on the big chest's closed body",
               f"(as B31), the left half ({len(left)} boxes) on a small chest's closed body (Obj_TBox_A_01, as B30), the small",
               "chest 2 m right of the big one. Both heaps + 2 MiB."],
              extra={TBOX_PACK: 512 * 1024, A01_PACK: 512 * 1024}, entries={**e1, **e2})
    return len(left), len(right)


# ---------------------------------------------------------------- B33 on: more bodies on one chest

TBOX_CLOSE_BODY = "Phive/RigidBodyEntityParam/Obj_TBox_Body_2_Close.phive__RigidBodyEntityParam.bgyml"
CLOSE_BODY_ENTRY = 5552                                   # its size table entry in 1.1.1 (file 216 bytes)


TBOX_CONTROLLER = "Phive/RigidBodyControllerEntityParam/Obj_TBox_A_02_Body.phive__RigidBodyControllerEntityParam.bgyml"


def tbox_extra_bodies(game, bodies, presets=None, controller=False):
    """Obj_TBox_A_02's pack with extra Static bodies, each a copy of the closed chest's body (CloseBody) with a shape
    of its own: bodies = [(name, extra boxes, source shape)]. Each shape is `source` (e.g. the closed chest's two
    polytopes) plus the boxes, as tbox_own_map_shape makes them. The chest's own bodies are left as they are. Every
    body listed in the ControllerSetParam looks built at load (the AirWall body has no alias and exists).
    B33: not so, the new body was never solid. controller=True also adds each body to the chest's controller
    (Obj_TBox_A_02_Body: one unit per body, IsAddToWorldOnReset), as a copy of CloseBody's unit."""
    sarc = zstool.Sarc(game.raw(TBOX_PACK))
    files = {n: sarc.read(n) for n in sarc.names()}
    proto = byml.loads(files[TBOX_SHAPE])["Box"][0]
    csp = byml.loads(files[TBOX_CSP])
    entries = {}
    for name, extra, source in bodies:
        shape = byml.loads(files[source])
        ac = shape["AutoCalc"]
        shape.setdefault("Box", [])
        for lo, hi in extra:
            b = copy.deepcopy(proto)
            b["Center"] = f3(0, 0, 0)
            b["HalfExtents"] = f3(*(np.subtract(hi, lo) / 2))
            b["OffsetTranslation"] = f3(*(np.add(lo, hi) / 2))
            if presets is not None:
                b["MaterialPresets"] = list(presets)
            shape["Box"].append(b)
            for i, k in enumerate("XYZ"):
                ac["Min"][k] = float(min(ac["Min"][k], lo[i]))
                ac["Max"][k] = float(max(ac["Max"][k], hi[i]))
        shape_p = f"Phive/ShapeParam/Obj_TBox_A_02__{name}.phive__ShapeParam.bgyml"
        body_p = f"Phive/RigidBodyEntityParam/Obj_TBox_A_02_{name}.phive__RigidBodyEntityParam.bgyml"
        files[shape_p] = byml.dumps(shape)
        body = byml.loads(files[TBOX_CLOSE_BODY])
        body["ShapeName"] = name
        files[body_p] = byml.dumps(body)
        csp["RigidBodyEntityNamePathAry"].append({"FilePath": "Work/" + body_p[:-len(".bgyml")] + ".gyml", "Name": name})
        csp["ShapeNamePathAry"].append({"FilePath": "Work/" + shape_p[:-len(".bgyml")] + ".gyml", "Name": name})
        entries[shape_p] = shape_entry(files[shape_p]) + 4096
        entries[body_p] = CLOSE_BODY_ENTRY + len(files[body_p]) - len(files[TBOX_CLOSE_BODY]) + 1024
    files[TBOX_CSP] = byml.dumps(csp)
    entries[TBOX_CSP] = len(files[TBOX_CSP]) + 8 * 1024 + 2048
    if controller:
        ctl = byml.loads(files[TBOX_CONTROLLER])
        unit = next(u for u in ctl["RigidBodyControllerUnitAry"] if u["Name"] == "CloseBody")
        for name, _, _ in bodies:
            u = copy.deepcopy(unit)
            u["Name"] = name
            ctl["RigidBodyControllerUnitAry"].append(u)
        files[TBOX_CONTROLLER] = byml.dumps(ctl)
        entries[TBOX_CONTROLLER] = len(files[TBOX_CONTROLLER]) + 8 * 1024 + 2048
    return zsmod.sarc_pack(files, like=game.raw(TBOX_PACK)), entries


def test_b33(game, out):
    """Control for more than one map body on one chest: B22's shape (the closed chest's two polytopes, B11's slab,
    the 15 m bridge and landing) on a NEW fifth Static body, KaeGaeMap0, a copy of CloseBody. The chest's own
    CloseBody is left vanilla. Only change from B22: which body carries the shape."""
    rng.seed("B33")
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)),            # B22's boxes, exactly
             ((-0.5, 0.1, -17.0), (0.5, 0.3, -2.0)),
             ((-1.5, 0.1, -20.0), (1.5, 0.3, -17.0))]
    pack, entries = tbox_extra_bodies(game, [("KaeGaeMap0", extra, TBOX_CLOSE_SHAPE)], presets=["Material_Wood_Thick"])
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B33: DON'T open the chest. As B22 (B11's slab beside the chest, a 1 m wide invisible bridge from 2 m in front",
               "of it 15 m into the room, a 3 x 3 m landing), but the shape is on a new, fifth Static body of the chest (KaeGaeMap0,",
               "a copy of the closed chest's body); the closed chest's own body is unchanged."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


def test_b34(game, out):
    """B33 plus a unit for the new body in the chest's controller (Obj_TBox_A_02_Body), a copy of CloseBody's
    (IsAddToWorldOnReset). B33's body was in the ControllerSetParam only and was never solid."""
    rng.seed("B33")                                          # same placement as B33
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(a_chest(game, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)),
             ((-0.5, 0.1, -17.0), (0.5, 0.3, -2.0)),
             ((-1.5, 0.1, -20.0), (1.5, 0.3, -17.0))]
    pack, entries = tbox_extra_bodies(game, [("KaeGaeMap0", extra, TBOX_CLOSE_SHAPE)], presets=["Material_Wood_Thick"],
                                      controller=True)
    write_mod(out, {DEKU_S: (st, 3), TBOX_PACK: (pack, 4)}, game,
              ["Test B34: DON'T open the chest. As B33 (B22's slab, bridge and landing on a new fifth Static body of the chest,",
               "KaeGaeMap0), plus that body added to the chest's controller (Obj_TBox_A_02_Body) as a copy of the closed body's",
               "unit, which adds it to the world when the chest is set up."],
              extra={TBOX_PACK: 64 * 1024}, entries=entries)


# ---------------------------------------------------------------- B35 on: a host with no behaviour of its own

FLAG = "Obj_Flag_A_01"                      # a plain GameActor (ActorLogicSimpleActor, no AI, PreActorSetting
FLAG_PACK = f"Pack/Actor/{FLAG}.pack.zs"    # ActorOnly): one Kinematic body "Physical", added to the world by its
FLAG_SHAPE = f"Phive/ShapeParam/{FLAG}__Physical.phive__ShapeParam.bgyml"   # controller; a 4.6 m flag pole
FLAG_HEAP = 26912                           # its InstanceHeapSize in 1.1.1


def flag_with_boxes(game, extra, presets=("Material_Wood_Thick",)):
    """Obj_Flag_A_01's pack with `extra` boxes (actor-local metres) added to its one shape (its pole polytope stays).
    The shape file is used by this actor only, so it's changed in place; returns (pack, {shape: entry})."""
    sarc = zstool.Sarc(game.raw(FLAG_PACK))
    files = {n: sarc.read(n) for n in sarc.names()}
    shape = byml.loads(files[FLAG_SHAPE])
    proto, ac = byml.loads(zstool.Sarc(game.raw(TBOX_PACK)).read(TBOX_SHAPE))["Box"][0], shape["AutoCalc"]
    shape.setdefault("Box", [])
    for lo, hi in extra:
        b = copy.deepcopy(proto)
        b["Center"] = f3(0, 0, 0)
        b["HalfExtents"] = f3(*(np.subtract(hi, lo) / 2))
        b["OffsetTranslation"] = f3(*(np.add(lo, hi) / 2))
        b["MaterialPresets"] = list(presets)
        shape["Box"].append(b)
        for i, k in enumerate("XYZ"):
            ac["Min"][k] = float(min(ac["Min"][k], lo[i]))
            ac["Max"][k] = float(max(ac["Max"][k], hi[i]))
    files[FLAG_SHAPE] = byml.dumps(shape)
    return zsmod.sarc_pack(files, like=game.raw(FLAG_PACK)), {FLAG_SHAPE: shape_entry(files[FLAG_SHAPE]) + 4096}


def test_b35(game, out):
    """Control for a host with no behaviour: one Obj_Flag_A_01 3 m in front of the entrance (where the chests stood),
    its shape = its pole plus B22's slab, bridge and landing; flag heap + 2 MiB as B30. No chest."""
    rng.seed("B35")
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(placed(FLAG, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)),            # B22's boxes, exactly
             ((-0.5, 0.1, -17.0), (0.5, 0.3, -2.0)),
             ((-1.5, 0.1, -20.0), (1.5, 0.3, -17.0))]
    pack, entries = flag_with_boxes(game, extra)
    files = {DEKU_S: (st, 3), FLAG_PACK: (pack, 4),
             ACTORINFO: (actorinfo_heap(game, {FLAG: FLAG_HEAP + 2 * 1024 * 1024}), None)}
    write_mod(out, files, game,
              ["Test B35: a host with no behaviour of its own. One flag (Obj_Flag_A_01, a plain actor with one Kinematic body)",
               "3 m in front of the entrance, where the chests stood; no chest. Its shape: its pole plus B22's slab (to its",
               "right), the 1 m wide invisible bridge from 2 m in front of it 15 m into the room, and the 3 x 3 m landing.",
               "Flag InstanceHeapSize + 2 MiB."],
              extra={FLAG_PACK: 64 * 1024}, entries=entries)


# ---------------------------------------------------------------- B36 on: hosts under new actor names

GAMEACTORINFO = "RSDB/GameActorInfo.Product.111.rstbl.byml.zs"


def rstb_entry(game, path):
    """The size table entry the game has for a path (0 if none)."""
    rs = Rstb(game.r / RSTB)
    at = rs.at.get(zlib.crc32(path.encode()))
    return struct.unpack_from("<I", rs.t, at)[0] if at else 0


def rows_with(rows, src, names, change=None):
    """An RSDB table (rows sorted by __RowId) with a copy of row `src` for each new name, inserted in order."""
    import bisect
    base = next(r for r in rows if r.get("__RowId") == src)
    for n in names:
        r = copy.deepcopy(base)
        r["__RowId"] = n
        if change:
            change(r)
        ids = [x["__RowId"] for x in rows]
        assert n not in ids
        rows.insert(bisect.bisect(ids, n), r)
    return rows


def flag_copy(game, name, extra, presets=("Material_Wood_Thick",)):
    """A new actor `name`: Obj_Flag_A_01 (same model, body and controller) with an ActorParam, PhysicsParam,
    ControllerSetParam and shape of its own; the shape is the pole plus `extra` boxes. Returns (pack, entries) for
    the new pack's own files. The RSDB rows come from host_rows()."""
    sarc = zstool.Sarc(game.raw(FLAG_PACK))
    files = {n: sarc.read(n) for n in sarc.names()}
    fpack, fentries = flag_with_boxes(game, extra, presets)
    shape_raw = zstool.Sarc(fpack).read(FLAG_SHAPE)
    ren = {f"Actor/{FLAG}.engine__actor__ActorParam.bgyml": f"Actor/{name}.engine__actor__ActorParam.bgyml",
           f"Component/Physics/{FLAG}.engine__component__PhysicsParam.bgyml": f"Component/Physics/{name}.engine__component__PhysicsParam.bgyml",
           f"Phive/ControllerSetParam/{FLAG}.phive__ControllerSetParam.bgyml": f"Phive/ControllerSetParam/{name}.phive__ControllerSetParam.bgyml",
           FLAG_SHAPE: f"Phive/ShapeParam/{name}__Physical.phive__ShapeParam.bgyml"}
    gy = lambda p: "Work/" + p[:-len(".bgyml")] + ".gyml"          # noqa: E731
    out = {ren.get(n, n): b for n, b in files.items()}
    out[ren[FLAG_SHAPE]] = shape_raw
    ap = byml.loads(files[f"Actor/{FLAG}.engine__actor__ActorParam.bgyml"])
    ap["Components"]["PhysicsRef"] = "?" + ren[f"Component/Physics/{FLAG}.engine__component__PhysicsParam.bgyml"]
    out[ren[f"Actor/{FLAG}.engine__actor__ActorParam.bgyml"]] = byml.dumps(ap)
    ph = byml.loads(files[f"Component/Physics/{FLAG}.engine__component__PhysicsParam.bgyml"])
    ph["ControllerSetPath"] = gy(ren[f"Phive/ControllerSetParam/{FLAG}.phive__ControllerSetParam.bgyml"])
    out[ren[f"Component/Physics/{FLAG}.engine__component__PhysicsParam.bgyml"]] = byml.dumps(ph)
    cs = byml.loads(files[f"Phive/ControllerSetParam/{FLAG}.phive__ControllerSetParam.bgyml"])
    next(r for r in cs["ShapeNamePathAry"] if r["Name"] == "Physical")["FilePath"] = gy(ren[FLAG_SHAPE])
    out[ren[f"Phive/ControllerSetParam/{FLAG}.phive__ControllerSetParam.bgyml"]] = byml.dumps(cs)
    entries = {ren[FLAG_SHAPE]: fentries[FLAG_SHAPE]}
    for old, new in ren.items():
        if old != FLAG_SHAPE:
            entries[new] = rstb_entry(game, old) + len(out[new]) - len(files[old]) + 1024
    return zsmod.sarc_pack(out, like=game.raw(FLAG_PACK)), entries


def host_rows(game, names, heap):
    """ActorInfo and GameActorInfo with a copy of Obj_Flag_A_01's row for each new host name (heap: InstanceHeapSize)."""
    def h(r):
        r["InstanceHeapSize"] = type(r["InstanceHeapSize"])(heap)
    return {ACTORINFO: (rows_with(game.byml(ACTORINFO), FLAG, names, h), None),
            GAMEACTORINFO: (rows_with(game.byml(GAMEACTORINFO), FLAG, names), None)}


def test_b36(game, out):
    """B35 with the flag as a new actor, KaeGae_MapHost_00: a copy of Obj_Flag_A_01 under a new name (own pack,
    ActorParam, PhysicsParam, ControllerSetParam and shape; new RSDB ActorInfo / GameActorInfo rows; new size table
    entries). Same place and boxes as B35. Control for hosts under new names (a map needs ~10 shapes)."""
    rng.seed("B35")                                          # same placement hash as B35
    name = "KaeGae_MapHost_00"
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(placed(name, (sx, sy, sz - 3)))
    extra = [((1.5, 0.0, -1.5), (4.5, 0.5, 1.5)),
             ((-0.5, 0.1, -17.0), (0.5, 0.3, -2.0)),
             ((-1.5, 0.1, -20.0), (1.5, 0.3, -17.0))]
    pack, entries = flag_copy(game, name, extra)
    files = {DEKU_S: (st, 3), f"Pack/Actor/{name}.pack.zs": (pack, 4), **host_rows(game, [name], FLAG_HEAP + 2 * 1024 * 1024)}
    write_mod(out, files, game,
              ["Test B36: as B35 (a flag 3 m in front of the entrance carrying B22's slab, bridge and landing), but the flag is a",
               "new actor, KaeGae_MapHost_00: a copy of Obj_Flag_A_01 under a new name, with its own pack, ActorParam,",
               "PhysicsParam, ControllerSetParam and shape, new RSDB rows (ActorInfo, GameActorInfo) and new size table entries.",
               "Heap + 2 MiB as B35."],
              extra={f"Pack/Actor/{name}.pack.zs": 64 * 1024}, entries=entries)


def test_b37(game, out, glb):
    """B32 on flags instead of chests: the Minecraft cut's right half (729 boxes) on KaeGae_MapHost_00 where the big
    chest stood, the left half (699) on KaeGae_MapHost_01 2 m to its right where the small chest stood (B36's host
    setup, each heap + 2 MiB). No chests."""
    rng.seed("B37")
    names = ["KaeGae_MapHost_00", "KaeGae_MapHost_01"]
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    st["Actors"].append(placed(names[0], (sx, sy, sz - 3)))
    st["Actors"].append(placed(names[1], (sx + A01_AT, sy, sz - 3)))
    left, right, size = minecraft_halves(glb, 24, (0.0, 0.0, -24.0), 24)
    assert len(left) < 1000 and len(right) < 1000
    files, entries, extra = {DEKU_S: (st, 3)}, {}, {}
    for name, boxes in ((names[0], right), (names[1], shift(left, -A01_AT))):
        pack, e = flag_copy(game, name, boxes)
        files[f"Pack/Actor/{name}.pack.zs"] = (pack, 4)
        entries.update(e)
        extra[f"Pack/Actor/{name}.pack.zs"] = 512 * 1024
    files.update(host_rows(game, names, FLAG_HEAP + 2 * 1024 * 1024))
    write_mod(out, files, game,
              [f"Test B37: B32 on flags instead of chests. The Minecraft cut ({len(left) + len(right)} boxes, {size[0]} x {size[1]} x {size[2]} blocks)",
               f"split at the spawn column: the right half ({len(right)} boxes) on KaeGae_MapHost_00 (a flag where the big chest stood),",
               f"the left half ({len(left)} boxes) on KaeGae_MapHost_01 (a flag 2 m to its right, where the small chest stood).",
               "Both are B36's flag copy under new names, heap + 2 MiB. No chests."],
              extra=extra, entries=entries)
    return len(left), len(right)


def map_chunks(solid, limit=950):
    """Split a block grid along x / z (the longer side, in halves) until each part greedies to <= limit boxes:
    [(x0, x1, z0, z1, boxes in grid cells)]. The whole Minecraft map: 14 parts, 9,397 boxes (9,375 in one piece)."""
    def split(x0, x1, z0, z1):
        s = np.zeros_like(solid)
        s[x0:x1, :, z0:z1] = solid[x0:x1, :, z0:z1]
        boxes = greedy(s)
        if len(boxes) <= limit:
            return [(x0, x1, z0, z1, boxes)]
        if x1 - x0 >= z1 - z0:
            m = (x0 + x1) // 2
            return split(x0, m, z0, z1) + split(m, x1, z0, z1)
        m = (z0 + z1) // 2
        return split(x0, x1, z0, m) + split(x0, x1, m, z1)
    return split(0, solid.shape[0], 0, solid.shape[2])


def test_b38(game, out, glb):
    """The whole Minecraft map on flag hosts: B37's setup and alignment (the spawn column's top level with the floor,
    24 m in front of where the chest stood), but the whole map (171 x 70 x 127 blocks) split into 14 parts of up to
    920 boxes, one per host KaeGae_MapHost_00..13, all in a row at the entrance 1 m apart (centred where the chest
    stood), heaps + 2 MiB each. Only the map's size and the number of hosts change from B37."""
    rng.seed("B38")
    solid, _ = fill_and_merge(voxels(glb, 70.0))
    cx, cz, top = spawn_column(solid)
    off = np.subtract((0.0, 0.0, -24.0), (cx + 0.5, top, cz + 0.5))      # grid -> metres from the chest spot
    chunks = map_chunks(solid)
    names = [f"KaeGae_MapHost_{i:02d}" for i in range(len(chunks))]
    st = game.byml(DEKU_S)
    sx, sy, sz = SPAWN
    files, entries, extra = {DEKU_S: (st, 3)}, {}, {}
    for i, (name, ch) in enumerate(zip(names, chunks)):
        dx = i - (len(chunks) - 1) / 2
        st["Actors"].append(placed(name, (sx + dx, sy, sz - 3)))
        boxes = [(tuple(np.add(lo, off)), tuple(np.add(hi, off))) for lo, hi in ch[4]]
        pack, e = flag_copy(game, name, shift(boxes, -dx))
        files[f"Pack/Actor/{name}.pack.zs"] = (pack, 4)
        entries.update(e)
        extra[f"Pack/Actor/{name}.pack.zs"] = 512 * 1024
    files.update(host_rows(game, names, FLAG_HEAP + 2 * 1024 * 1024))
    n = sum(len(c[4]) for c in chunks)
    write_mod(out, files, game,
              [f"Test B38: the whole Minecraft map ({solid.shape[0]} x {solid.shape[1]} x {solid.shape[2]} blocks, {n} boxes) on {len(chunks)} flag hosts",
               f"(KaeGae_MapHost_00..{len(chunks) - 1:02d}, B36 / B37's flag copy, heap + 2 MiB each), {min(len(c[4]) for c in chunks)} to "
               f"{max(len(c[4]) for c in chunks)} boxes each, all standing in a row at the entrance 1 m apart. Same alignment as B37: the",
               "spawn column's top level with the floor, 24 m in front of where the chest stood; the map reaches about 85 m left",
               "and right, 87 m ahead and 40 m back, 27 m up and 43 m down, through the Deku Tree's walls.",
               "Parts (grid x0-x1, z0-z1: boxes): " + ", ".join(f"{c[0]}-{c[1]},{c[2]}-{c[3]}: {len(c[4])}" for c in chunks)],
              extra=extra, entries=entries)
    return len(chunks), n


# ---------------------------------------------------------------- B39 on: seeing the map with the game's own models

CUBE = "Land_SacredForest_Prop_A_06"   # a 1 x 1 x 1 m stone block (model bounds 0 to 1 m up, centred in x / z), a
                                       # plain Land piece: newly placed it shows its model and adds no collision


def cube_actor(lo, hi, at):
    """A CUBE placed (Dynamic file, as the game's Land pieces) and scaled to cover the box lo..hi (metres from `at`)."""
    size = np.subtract(hi, lo)
    pos = (at[0] + (lo[0] + hi[0]) / 2, at[1] + lo[1], at[2] + (lo[2] + hi[2]) / 2)
    return placed(CUBE, pos, scale=[float(v) for v in size], extra={"Bakeable": True, "Rotate": [0.0, 0.0, 0.0]})


def test_b39(game, out, glb):
    """B37 (the Minecraft cut's collision on two flags) plus a stone block (CUBE) per collision box that reaches above
    the floor, scaled to the box, so the map's shape can be seen; and one unscaled block 2 m left of the flags as a
    control. Textures are the block's own, stretched. Only the visible blocks change from B37."""
    rng.seed("B37")                                          # B37's placement hashes for the flags
    names = ["KaeGae_MapHost_00", "KaeGae_MapHost_01"]
    st, dy = game.byml(DEKU_S), game.byml(DEKU_D)
    sx, sy, sz = SPAWN
    st["Actors"].append(placed(names[0], (sx, sy, sz - 3)))
    st["Actors"].append(placed(names[1], (sx + A01_AT, sy, sz - 3)))
    left, right, size = minecraft_halves(glb, 24, (0.0, 0.0, -24.0), 24)
    files, entries, extra = {}, {}, {}
    for name, boxes in ((names[0], right), (names[1], shift(left, -A01_AT))):
        pack, e = flag_copy(game, name, boxes)
        files[f"Pack/Actor/{name}.pack.zs"] = (pack, 4)
        entries.update(e)
        extra[f"Pack/Actor/{name}.pack.zs"] = 512 * 1024
    files.update(host_rows(game, names, FLAG_HEAP + 2 * 1024 * 1024))
    rng.seed("B39")
    shown = [b for b in left + right if b[1][1] > 0.01]       # boxes whose top is above the floor
    at = (sx, sy, sz - 3)                                     # the boxes are in metres from the chest spot
    dy["Actors"] += [cube_actor(lo, hi, at) for lo, hi in shown]
    dy["Actors"].append(cube_actor((-2.5, 0.0, -0.5), (-1.5, 1.0, 0.5), at))    # the control block
    files.update({DEKU_S: (st, 3), DEKU_D: (dy, 3)})
    write_mod(out, files, game,
              [f"Test B39: B37 (the Minecraft cut's collision on two flags) plus {len(shown)} stone blocks ({CUBE}, 1 m, scaled to",
               f"each collision box whose top is above the floor) so the map's shape shows, and one unscaled 1 m block 2 m left",
               "of the flags as a control. The blocks are in the Dynamic placement file, like the game's own Land pieces."],
              extra=extra, entries=entries)
    return len(shown)


def test_b40(game, out, glb, show_all=False, bounds=None, banc_set=None, palette_set=None, empty=False, no_compound=False, label="B40"):
    """B38 (the whole Minecraft map's collision on 14 flags) plus a stone block (CUBE) per collision box that reaches
    above the floor, scaled to the box, as B39 did for the cut; and B39's unscaled control block 2 m left of the
    flags. Only the visible blocks change from B38."""
    rng.seed("B38")                                          # B38's placement hashes for the flags
    solid, _ = fill_and_merge(voxels(glb, 70.0))
    cx, cz, top = spawn_column(solid)
    off = np.subtract((0.0, 0.0, -24.0), (cx + 0.5, top, cz + 0.5))
    chunks = map_chunks(solid)
    names = [f"KaeGae_MapHost_{i:02d}" for i in range(len(chunks))]
    st, dy = emptied_deku(game) if empty else (game.byml(DEKU_S), game.byml(DEKU_D))   # B45: test C's emptied scene
    sx, sy, sz = SPAWN
    files, entries, extra, every = {}, {}, {}, []
    for i, (name, ch) in enumerate(zip(names, chunks)):
        dx = i - (len(chunks) - 1) / 2
        st["Actors"].append(placed(name, (sx + dx, sy, sz - 3)))
        boxes = [(tuple(np.add(lo, off)), tuple(np.add(hi, off))) for lo, hi in ch[4]]
        every += boxes
        pack, e = flag_copy(game, name, shift(boxes, -dx))
        files[f"Pack/Actor/{name}.pack.zs"] = (pack, 4)
        entries.update(e)
        extra[f"Pack/Actor/{name}.pack.zs"] = 512 * 1024
    files.update(host_rows(game, names, FLAG_HEAP + 2 * 1024 * 1024))
    rng.seed("B40")
    shown = every if show_all else [b for b in every if b[1][1] > 0.01]   # B40: boxes whose top is above the floor
    at = (sx, sy, sz - 3)
    dy["Actors"] += [cube_actor(lo, hi, at) for lo, hi in shown]
    dy["Actors"].append(cube_actor((-9.5, 0.0, -0.5), (-8.5, 1.0, 0.5), at))    # the control block, left of the row
    files.update({DEKU_S: (st, 3), DEKU_D: (dy, 3)})
    notes = []
    if bounds:                                                # B42: the scene's HeightMapParam bounding box
        bp = game.byml(DEKU_BANC)
        hm = bp["HeightMapParam"]
        old = (dict(hm["BoundingBoxMin"]), dict(hm["BoundingBoxMax"]))
        for k, v in zip("XYZ", bounds[0]):
            hm["BoundingBoxMin"][k] = float(v)
        for k, v in zip("XYZ", bounds[1]):
            hm["BoundingBoxMax"][k] = float(v)
        files[DEKU_BANC] = (bp, 0)
        notes = [f"{label}: only change from B40: {DEKU_BANC} HeightMapParam bounding box {old[0]}..{old[1]} -> "
                 f"{dict(hm['BoundingBoxMin'])}..{dict(hm['BoundingBoxMax'])} (the map spans x -85..86, y 58..128, z -77..50)."]
    if show_all:
        notes = [f"{label}: only change from B40: a block for every collision box ({len(shown)}), not just those above the floor."]
    if banc_set:                                              # B43 on: B41 plus GameBancParam values
        bp = game.byml(DEKU_BANC)
        for k, v in banc_set.items():
            notes.append(f"{label}: {DEKU_BANC} {k} {bp.get(k)!r} -> {'(removed)' if v is None else repr(v)}")
            if v is None:                                     # B48: drop the line (FoliageScene)
                bp.pop(k, None)
            else:
                bp[k] = v
        files[DEKU_BANC] = (bp, 0)
    if no_compound:                                           # B47: B45 plus B46's empty static compound
        files[DEKU_COMPOUND] = (game.raw(EMPTY_COMPOUND), 1)
        notes.append(f"{label}: only change from B45: {DEKU_COMPOUND} replaced by the game's empty compound ({EMPTY_COMPOUND}).")
    if empty:
        notes.append(f"{label}: only change from B44: the map in test C's emptied Deku Tree (only its 6 spawn points kept, groups cleared).")
    if palette_set:                                           # B44 on: B43 plus a brighter Deku Tree env palette
        raw = game.raw(ENV_PACK)
        sarc = zstool.Sarc(raw)
        names = [str(n) for n in sarc.names()]
        inner = {n: sarc.read(n) for n in names}
        pal = byml.loads(inner[DEKU_PALETTE])
        for k, v in palette_set.items():
            notes.append(f"{label}: only change from B43: {ENV_PACK} {DEKU_PALETTE} {k} {pal.get(k)!r} -> {v!r}")
            pal[k] = v
        inner[DEKU_PALETTE] = byml.dumps(pal)
        entries[DEKU_PALETTE] = len(inner[DEKU_PALETTE]) + 512
        files[ENV_PACK] = (zsmod.sarc_pack(inner, like=raw), byml.frame_dict_id(game.r / ENV_PACK))
    write_mod(out, files, game, notes +
              [f"Test B40: B38 (the whole Minecraft map's collision, {len(every)} boxes on {len(chunks)} flags) plus {len(shown)} stone blocks",
               f"({CUBE}, 1 m, scaled to each collision box whose top is above the floor) so the whole map shows, and one",
               "unscaled 1 m block 2 m left of the row of flags as a control. Blocks in the Dynamic placement file, as in B39."],
              extra=extra, entries=entries)
    return len(shown)


def main_1b(game, out, glb=None):
    if glb:
        test_b40(game, out / "KaeGae Map Test B48 - B47 without foliage", glb, show_all=True,
                 banc_set={"IsEnableBakeLight": False, "FoliageScene": None},
                 palette_set={"AmbientIntensity": 1.0, "HemiLightIntensity": 1.0}, empty=True, no_compound=True, label="B48")
        test_b40(game, out / "KaeGae Map Test B47 - B45 without the Deku Tree's collision", glb, show_all=True,
                 banc_set={"IsEnableBakeLight": False},
                 palette_set={"AmbientIntensity": 1.0, "HemiLightIntensity": 1.0}, empty=True, no_compound=True, label="B47")
        test_b40(game, out / "KaeGae Map Test B45 - B44 in the emptied Deku Tree", glb, show_all=True,
                 banc_set={"IsEnableBakeLight": False},
                 palette_set={"AmbientIntensity": 1.0, "HemiLightIntensity": 1.0}, empty=True, label="B45")
        test_b40(game, out / "KaeGae Map Test B44 - B43 with a brighter palette", glb, show_all=True,
                 banc_set={"IsEnableBakeLight": False},
                 palette_set={"AmbientIntensity": 1.0, "HemiLightIntensity": 1.0}, label="B44")
        test_b40(game, out / "KaeGae Map Test B43 - B41 with baked light off", glb, show_all=True,
                 banc_set={"IsEnableBakeLight": False}, label="B43")
        test_b40(game, out / "KaeGae Map Test B42 - B40 with wider scene bounds", glb,
                 bounds=((-95.0, 40.0, -85.0), (95.0, 135.0, 100.0)), label="B42")
        test_b40(game, out / "KaeGae Map Test B41 - B40 with every box drawn", glb, show_all=True, label="B41")
        test_b40(game, out / "KaeGae Map Test B40 - whole Minecraft map you can see", glb)
        test_b39(game, out / "KaeGae Map Test B39 - Minecraft cut you can see", glb)
        test_b38(game, out / "KaeGae Map Test B38 - whole Minecraft map on 14 flags", glb)
        test_b37(game, out / "KaeGae Map Test B37 - Minecraft cut on two flags", glb)
    test_b46(game, out / "KaeGae Map Test B46 - C without the Deku Tree's collision")
    test_b36(game, out / "KaeGae Map Test B36 - flag copy under a new name")
    test_b35(game, out / "KaeGae Map Test B35 - flag host, far bridge")
    test_b34(game, out / "KaeGae Map Test B34 - second body in the controller")
    test_b33(game, out / "KaeGae Map Test B33 - second body, far bridge")
    if glb:
        test_b32(game, out / "KaeGae Map Test B32 - Minecraft cut on two chests", glb)
        test_b31(game, out / "KaeGae Map Test B31 - Minecraft half on one chest", glb)
    test_b30(game, out / "KaeGae Map Test B30 - small chest, far bridge")
    test_b26(game, out / "KaeGae Map Test B29 - slab as 1,029 tiles", 49, 21, "B29")
    test_b26(game, out / "KaeGae Map Test B28 - slab as 1,020 tiles", 34, 30, "B28")
    test_b26(game, out / "KaeGae Map Test B27 - slab as 800 tiles", 40, 20, "B27")
    test_b26(game, out / "KaeGae Map Test B26 - slab as 1,425 tiles")
    if glb:
        test_b25(game, out / "KaeGae Map Test B25 - Minecraft cut, bigger heap", glb)
        test_b24(game, out / "KaeGae Map Test B24 - closed chest, Minecraft cut", glb)
    test_b23(game, out / "KaeGae Map Test B23 - closed chest, 400-box staircase")
    test_b22(game, out / "KaeGae Map Test B22 - closed chest, far bridge")
    test_b21(game, out / "KaeGae Map Test B21 - B11 boxes plus a far box")
    test_b20(game, out / "KaeGae Map Test B20 - slab as 240 tiles")
    test_b19(game, out / "KaeGae Map Test B19 - B11 boxes, own shape file")
    side_stair_test(game, out / "KaeGae Map Test B18 - 260 boxes beside the chest", 13, "B18")
    side_stair_test(game, out / "KaeGae Map Test B17 - 240 boxes beside the chest", 12, "B17")
    test_b16(game, out / "KaeGae Map Test B16 - 400 boxes beside the chest")
    test_b15(game, out / "KaeGae Map Test B15 - 400 boxes, chest's bounds")
    test_b14(game, out / "KaeGae Map Test B14 - 400 boxes, game's heap")
    test_b13(game, out / "KaeGae Map Test B13 - 400 boxes, own shape file")
    test_b12(game, out / "KaeGae Map Test B12 - 400 boxes on a chest")
    test_b11(game, out / "KaeGae Map Test B11 - boxes on a chest, shape entry")
    test_b10(game, out / "KaeGae Map Test B10 - air-wall platform recheck")
    test_b9(game, out / "KaeGae Map Test B9 - swap chest parts")
    test_b8(game, out / "KaeGae Map Test B8 - boxes on a chest, bigger heap")
    test_b7(game, out / "KaeGae Map Test B7 - boxes on a chest, more room")
    test_b6(game, out / "KaeGae Map Test B6 - bigger chest base")
    test_b5(game, out / "KaeGae Map Test B5 - boxes on a chest")
    test_b4(game, out / "KaeGae Map Test B4 - kinematic body, chest check")
    test_b3(game, out / "KaeGae Map Test B3 - anchor setting, air-wall post")
    test_b2(game, out / "KaeGae Map Test B2 - box without bake, air wall")
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
        main_1b(game, out, a.glb)
        print("built round 1b")
        return
    test1(game, out / "KaeGae Map Test 1 - Deku door to Dodongo")
    test2(game, out / "KaeGae Map Test 2 - Box room")
    n3 = minecraft(game, out / "KaeGae Map Test 3 - Minecraft small", a.glb, 24, "Test 3")
    n4 = minecraft(game, out / "KaeGae Map Test 4 - Minecraft full", a.glb, 0, "Test 4")
    print("built; boxes:", n3, n4)


if __name__ == "__main__":
    main()
