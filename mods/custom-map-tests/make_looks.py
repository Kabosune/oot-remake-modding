#!/usr/bin/env python3
"""The texture step of the looks tests (S25 on): one block per Minecraft material, each a copy of the stone block
Land_SacredForest_Prop_A_06 with a new albedo. See docs/custom-maps.md "Looks: Minecraft block textures".

    python3 mods/custom-map-tests/make_looks.py --glb test_map.glb --bfres <stone .bfres> --alb <stone Alb .bntx> \
        --astcenc <astcenc binary> --out <assets dir>

--bfres / --alb: Model/Land_SacredForest_Prop_A.Land_SacredForest_Prop_A_06.bfres and
Tex/Stone_SacredForest_Prop_A_06_Alb.bntx from your dump, unpacked (zsmod.unzs). --astcenc: ARM's astcenc
(https://github.com/ARM-software/astc-encoder, any ISA build). Uses only the textures inside the .glb.

Writes to --out: per block i (0 = the control: the stone's own pixels under a new name, 1.. = the map's materials,
most used first) KaeGae_Minecraft_Block_<i:05d>_Alb.bntx and KaeGae_Minecraft_Blk_<i:03d>.Land_SacredForest_Prop_A_06.bfres,
plus materials.json (index, material, names, visible count) and materials.npz (the block grid's material per cell,
for build_tests.py --looks). Then: build_tests.py --looks <assets dir>.

How a texture is made: the stone's Alb is a UV atlas (islands with padding, a bevelled cube of 318 vertices), so
every texel of each triangle is mapped back to its spot on the cube face and filled from the Minecraft tile for that
face (top / bottom / sides, taken from the .glb's own UVs), nearest texel, so the pixel look stays. Top faces win
over sides, sides over the bottom, where islands share texels. Empty texels get the nearest painted one. Cut-out
texels (leaves) get the tile's average colour, darkened. Then 10 mips (box filter), ASTC 8x5 sRGB, swizzled.

Needs: pip install numpy scipy trimesh pillow
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
sys.path.insert(0, str(HERE))
import bntx  # noqa: E402
from build_tests import SKIP, fill_and_merge  # noqa: E402

OLD_ALB = b"Stone_SacredForest_Prop_A_06_Alb"
OLD_FRES = b"Land_SacredForest_Prop_A.Land_SacredForest_Prop_A_06"
DIRS = {(0, 1): "px", (0, -1): "nx", (1, 1): "py", (1, -1): "ny", (2, 1): "pz", (2, -1): "nz"}
SIDES = ["px", "nx", "pz", "nz"]
PLANE = {0: (2, 1), 1: (0, 2), 2: (0, 1)}   # face axis -> (s, t) axes inside the cell; t = y on the sides
W = 512


# ---------------------------------------------------------------- the stone block's cube

def cube(bfres):
    """Positions, UVs and triangles of the stone block's one mesh. Read from fixed offsets of this one file (FVTX at
    0x1B0: 318 vertices, stride 24: _p0 half4 at +0, _n0 / _t0 10:10:10:2 at +8 / +12, _u0 unorm16x2 at +16,
    bake at +20; the buffer data at 0x4000: 702 u16 indices, then the vertices at 0x4600), checked below."""
    assert bfres[:4] == b"FRES" and struct.unpack_from("<I", bfres, 0x1B0 + 0x50)[0] == 318
    a = np.frombuffer(bfres[0x4600:0x4600 + 318 * 24], np.uint8).reshape(318, 24)
    p = a[:, 0:8].copy().view(np.float16).astype(float)[:, :3]
    u = a[:, 16:20].copy().view(np.uint16).reshape(-1, 2) / 65535.0
    idx = np.frombuffer(bfres[0x4000:0x4000 + 702 * 2], np.uint16).reshape(-1, 3)
    assert idx.max() < 318 and np.allclose(p.min(0), (-0.5, 0, -0.5), atol=0.01) and np.allclose(p.max(0), (0.5, 1, 0.5))
    return p, u, idx


# ---------------------------------------------------------------- the map

def read_map(glb, scale=70.0):
    """Per cell: material votes (from the block faces behind it, as build_tests.voxels() finds the cells); per
    (material, face): the affine maps (s, t, 1) -> .glb UV seen, with counts; the atlas images."""
    import trimesh
    s = trimesh.load(glb)
    votes, aff, atlas_of, images = defaultdict(Counter), defaultdict(Counter), {}, {}
    for node in s.graph.nodes_geometry:
        T, gname = s.graph[node]
        g = s.geometry[gname]
        mat = g.visual.material
        name = mat.name or ""
        images.setdefault(id(mat.baseColorTexture), mat.baseColorTexture)
        if name != "Grass_Block" and any(name == k or name.endswith("_" + k) for k in SKIP):
            continue
        atlas_of[name] = id(mat.baseColorTexture)
        v = trimesh.transform_points(g.vertices, T) * scale
        uv = np.asarray(g.visual.uv)
        f = g.faces
        n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        ln = np.linalg.norm(n, axis=1)
        ok = ln > 1e-9
        n[ok] /= ln[ok, None]
        ax = np.argmax(np.abs(n), axis=1)
        sg = np.sign(n[np.arange(len(n)), ax]).astype(int)
        flat = ok & (np.abs(n[np.arange(len(n)), ax]) > 0.999)
        c = v[f].mean(axis=1)
        for i in np.nonzero(flat)[0]:
            q = c[i].copy()
            q[ax[i]] -= sg[i] * 0.5
            cell = tuple(np.floor(q + 1e-4).astype(int))
            votes[cell][name] += 1
            sa, ta = PLANE[ax[i]]
            P = v[f[i]] - np.array(cell)
            M = np.stack([P[:, sa], P[:, ta], np.ones(3)], 1)
            if abs(np.linalg.det(M)) > 1e-6:
                aff[(name, DIRS[(ax[i], sg[i])])][tuple(np.round(np.linalg.solve(M, uv[f[i]]).ravel(), 4))] += 1
    keys = list(images)
    return votes, aff, {n: keys.index(i) for n, i in atlas_of.items()}, [images[k] for k in keys]


def face_maps(aff, mat):
    """The most common (s, t, 1) -> UV map per face of a material; missing faces borrow another side / top."""
    out = {dn: np.array(max(c, key=c.get)).reshape(3, 2) for dn in DIRS.values() if (c := aff.get((mat, dn)))}
    for dn in SIDES:
        if dn not in out:
            out[dn] = out[([s for s in SIDES if s in out] or [k for k in ("py", "ny") if k in out])[0]]
    for a, b in (("py", "ny"), ("ny", "py")):
        out.setdefault(a, out.get(b, out["px"]))
    return out


# ---------------------------------------------------------------- painting

def paint(maps, at, cube_mesh):
    """The block's 512 x 512 albedo: each texel of each cube triangle filled from its face's Minecraft tile."""
    from scipy import ndimage
    p, u, idx = cube_mesh
    H, Wa = at.shape[:2]
    v = p[idx]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    n /= np.linalg.norm(n, axis=1)[:, None]
    ax = np.argmax(np.abs(n), 1)
    sg = np.sign(n[np.arange(len(n)), ax]).astype(int)
    out = np.zeros((W, W, 4), np.uint8)
    done = np.zeros((W, W), bool)
    for i in sorted(range(len(idx)), key=lambda i: {(1, -1): 0, (1, 1): 2}.get((ax[i], sg[i]), 1)):
        tu = u[idx[i]] * W                    # texel space; v = 0 is the first row in memory
        x0, y0 = np.floor(tu.min(0)).astype(int)
        x1, y1 = np.ceil(tu.max(0)).astype(int)
        xs, ys = np.meshgrid(np.arange(max(x0, 0), min(x1 + 1, W)), np.arange(max(y0, 0), min(y1 + 1, W)))
        P = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], 1)
        T = np.array([[tu[0, 0] - tu[2, 0], tu[1, 0] - tu[2, 0]], [tu[0, 1] - tu[2, 1], tu[1, 1] - tu[2, 1]]])
        if abs(np.linalg.det(T)) < 1e-9:
            continue
        lam = np.linalg.solve(T, (P - tu[2]).T).T
        b = np.concatenate([lam, 1 - lam.sum(1, keepdims=True)], 1)
        inside = (b >= -0.02).all(1)
        if not inside.any():
            continue
        px = P[inside].astype(int)
        pos = b[inside] @ v[i] + np.array([0.5, 0.0, 0.5])           # 0..1 inside the cell
        sa, ta = PLANE[ax[i]]
        st = np.clip(np.stack([pos[:, sa], pos[:, ta], np.ones(len(pos))], 1), [0.02, 0.02, 1], [0.98, 0.98, 1])
        uv = st @ maps[DIRS[(ax[i], sg[i])]]
        cx = np.clip((uv[:, 0] * Wa).astype(int), 0, Wa - 1)
        cy = np.clip(((1 - uv[:, 1]) * H).astype(int), 0, H - 1)     # trimesh's UVs have v up
        out[px[:, 1], px[:, 0]] = at[cy, cx]
        done[px[:, 1], px[:, 0]] = True
    a = out[..., 3]
    cut, solid = done & (a <= 128), done & (a > 128)
    if cut.any() and solid.any():
        out[cut, :3] = (out[solid][:, :3].mean(0) * 0.6).astype(np.uint8)
    out[..., 3] = 255
    _, (iy, ix) = ndimage.distance_transform_edt(~done, return_indices=True)
    return out[iy, ix]


# ---------------------------------------------------------------- .bntx and .bfres copies

def make_bntx(stone, name, img, astcenc):
    """The stone's Alb .bntx with a same-length name; with img, new ASTC 8x5 sRGB pixels in every mip."""
    from PIL import Image
    assert len(name) == len(OLD_ALB) and stone.count(OLD_ALB) == 1
    d = bytearray(stone)
    i = d.find(OLD_ALB)
    d[i:i + len(OLD_ALB)] = name.encode()
    if img is None:
        return bytes(d)
    t = bntx.info(stone)
    assert t["format"] == 0x3206 and t["width"] == t["height"] == W
    end = stone.find(b"_RLT")                     # the image data ends where the relocation table starts
    offs = t["mip_offsets"] + [end]
    img = Image.fromarray(img)
    for m in range(t["mips"]):
        w = max(W >> m, 1)
        with tempfile.TemporaryDirectory() as td:
            a, b = os.path.join(td, "i.png"), os.path.join(td, "o.astc")
            (img.resize((w, w), Image.BOX) if m else img).save(a)
            subprocess.run([astcenc, "-cs", a, b, "8x5", "-thorough", "-silent"], check=True)
            blocks = open(b, "rb").read()[16:]   # after the .astc header
        bx, by = (w + 7) // 8, (w + 4) // 5
        assert len(blocks) == bx * by * 16
        size = offs[m + 1] - offs[m]
        d[offs[m]:offs[m] + size] = bntx.swizzle(blocks, bx * 16, by, bntx.mip_gobs(by, t["gobs_high"]), size)
    return bytes(d)


def make_bfres(stone, project, alb):
    """The stone's .bfres with its file name (<project>.<FmdbName>) and the Alb texture name patched in place."""
    b = bytearray(stone)
    for old, new in ((OLD_FRES, (project + ".Land_SacredForest_Prop_A_06").encode()), (OLD_ALB, alb.encode())):
        assert len(old) == len(new) and b.count(old) == 1
        i = b.find(old)
        b[i:i + len(old)] = new
    return bytes(b)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glb", required=True)
    ap.add_argument("--bfres", required=True)
    ap.add_argument("--alb", required=True)
    ap.add_argument("--astcenc", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--previews", action="store_true", help="also write each block's albedo as a PNG")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stone_bfres, stone_alb = Path(a.bfres).read_bytes(), Path(a.alb).read_bytes()
    mesh = cube(stone_bfres)
    votes, aff, atlas_of, images = read_map(a.glb)
    atlases = [np.array(im.convert("RGBA")) for im in images]
    cells = np.array(sorted(votes))
    solid, mn = fill_and_merge(cells)
    cnt = Counter(max(v, key=v.get) for v in votes.values())
    mats = [m for m, _ in cnt.most_common()]
    grid = np.zeros(solid.shape, np.uint8)
    for c, v in votes.items():
        grid[tuple(np.subtract(c, mn))] = mats.index(max(v, key=v.get)) + 1
    np.savez_compressed(out / "materials.npz", grid=grid, mn=mn, shape=np.array(solid.shape))
    table = []
    for i, m in enumerate(["(control: the stone, renamed)"] + mats):
        project, alb = f"KaeGae_Minecraft_Blk_{i:03d}", f"KaeGae_Minecraft_Block_{i:05d}_Alb"
        img = None if i == 0 else paint(face_maps(aff, m), atlases[atlas_of[m]], mesh)
        if img is not None and a.previews:
            from PIL import Image
            Image.fromarray(img).save(out / f"{alb}.png")
        (out / f"{alb}.bntx").write_bytes(make_bntx(stone_alb, alb, img, a.astcenc))
        (out / f"{project}.Land_SacredForest_Prop_A_06.bfres").write_bytes(make_bfres(stone_bfres, project, alb))
        table.append({"index": i, "material": m, "project": project, "alb": alb, "voxels": cnt.get(m, 0)})
    (out / "materials.json").write_text(json.dumps(table, indent=1))
    print(f"{len(table)} blocks in {out}")


if __name__ == "__main__":
    main()
