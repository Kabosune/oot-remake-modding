# Custom map tests (round 1)

Test mods toward custom maps: go into the Deku Tree, arrive somewhere else or in a map of your own.
Background: [docs/custom-maps.md](../../docs/custom-maps.md). These are romfs mods (no Core needed). They are
built from your own dump with `build_tests.py`, so nothing from the game is in this repository.

**Turn on one test at a time.** Each one ships its own resource size table, and two tables overwrite each other.

| Test | What it changes | What to look for |
|---|---|---|
| 1. Deku door to Dodongo | The Deku Tree's entrance in Kokiri Forest (child) now leads to Dodongo's Cavern, start position `EntrancePos` | Does the scene change happen? Is Link placed at Dodongo's Cavern's entrance? Any odd fade or cutscene? |
| 2. Box room | Inside the Deku Tree emptied (only spawn points kept). In its place: 10 collision boxes in one actor (a 20 x 20 m floor, 6 steps up to a platform at 3 m, an 8 m pillar, a 1 m wall), a floating air-wall cube, two chests | Does the emptied scene load? Can Link stand and walk on the invisible floor, climb the steps, stand on the air-wall cube? |
| 3. Minecraft small | Like 2, but the boxes are a 48 x 48 block cut of the Minecraft test map: 1,425 boxes | Can he walk on the terrain? Load time, frame rate |
| 4. Minecraft full | The whole map, 171 x 70 x 127 blocks: 9,375 boxes | Same, and whether that many boxes is too many |

In 2 to 4 the floor is **invisible**: only the chests (and a tree root model) show. The boxes are the collision of
`Land_Deku_TreeRoot_B_01`, a Deku Tree piece whose collision these tests replace, placed once at the entrance
(tests 3 and 4: so the spawn point sits on the top of a block column near the map's middle; 1 block = 1 m).
If Link falls off, warp out or load a save.

How it works: a collision shape (`Phive/ShapeParam/*.bgyml`) can be a list of plain boxes (`Box`, with
`HalfExtents` and `OffsetTranslation`) instead of a Havok mesh. Block maps fit that well: the map's visible block
faces are turned into blocks, closed-off insides filled, and the blocks merged into as few boxes as possible.

## Round 1 result and round 1b

Round 1 (12 Nov): with all four turned on at once, going into the Deku Tree hung on the loading screen (the game
kept drawing frames). Mixed files, so not conclusive. Round 1b (`--round 1b`, the default) splits it into one
change per test:

| Test | What it changes | Tells us |
|---|---|---|
| A. Deku door to Dodongo | Same as test 1 | Whether a door can point at another scene |
| B. Deku Tree plus one box | The real Deku Tree, rewritten by `byml.py`, plus one invisible 3 x 3 m box (top 1 m up) 4 m in front of the entrance | Whether rewritten placement files load, and whether box collision works |
| C. Deku Tree emptied | Only the spawn points left, nothing added | Whether an emptied scene loads |
| D. Deku Tree emptied, terrain kept | Spawn points and the 5 terrain chunks | Whether the loader needs the terrain chunks |

Result of B (12 Nov): **loads fine** (so `byml.py`'s rewritten placement and the raised size table entries work), the
tree-root model shows in front of the entrance, but **no collision**. The scene has pre-built static collision,
`Phive/StaticCompoundBody/InsideTheDekuTree/InsideTheDekuTree.Nin_Ounce_NVN2.bphsc.zs` (2.6 MB); an actor placed
with `Bakeable` is probably expected to be in it and gets no collision of its own. B2: the same actor without
`Bakeable`, plus an air-wall cube (3 x 1 x 3 m) beside it.

Result of B2: still **no collision** on the tree root without `Bakeable` (the air-wall cube may have landed outside the
playable area). B3: the tree-root actor set up like an air wall (`PreActorSettingRef` `Anchor` instead of
`ConstPassive`), and the air-wall cube as a 1 x 1.5 x 1 m post 2 m from the entrance, on the way to the tree.

Result of B3: **nothing collides**, not even the air-wall post. So a newly placed static actor gets no collision at
all: static bodies (no `MotionType`) most likely come only from the scene's pre-built `StaticCompoundBody`, looked
up by placement ID. `MotionType` values are murmur3 hashes: `Static` 3498399415, `Dynamic` 3672686866, `Kinematic`
4269567940. A chest's main body is Kinematic. B4: the tree root with a Kinematic body (the chest body's settings), and
a copied chest 2 m from the entrance as a check that a new placement can collide at all.

Result of B4: the copied chest shows up, opens, and comes back when the map reloads; the Kinematic tree root still has
no collision. B5: two boxes added to the chest's own collision shape (`Obj_TBox_A_02__Body_0`): a 3 x 3 x 0.5 m
slab on one side and a 1 x 2.5 x 1 m pillar on the other. If those are solid, box shapes work on an actor type that
builds its collision at load time, and custom maps go on such an actor.

Result of B5: **no scene loaded** (main menu fine). Fritchii's log: a crash on a game thread while building the chest's
shape (`hapePara…` text in a register, writes of the shape's numbers through a null pointer at `0x40`…, then a jump
to 0). So **adding** boxes to a shape that gets built at load time crashes; the space for the shape's parts looks
fixed. (B–B4 never crashed because the tree root's shape is never built.) B6: no boxes added, the chest's one base box
made 4 x 0.5 x 4 m.

## Building

```
python3 mods/custom-map-tests/build_tests.py --romfs <folder> --glb <map.glb> --out <dir>
```

`--romfs` is a folder with these files from your own dump, at their romfs paths: `Pack/ZsDic.pack.zs`, the resource
size table, `Banc/KokiriForest/KokiriForest_Child_Static.bcett.byml.zs`, both `Banc/InsideTheDekuTree/` placement
files and `Pack/Actor/Land_Deku_TreeRoot_B_01.pack.zs`. Needs `pip install zstandard trimesh scipy numpy`.

Test map used: "High quality minecraft world" by SOLDMARS (Sketchfab), CC-BY-4.0. It isn't included here.

## Credits

KaboWabo/Kabosune (me :3), AI assistance (Claude Opus 5.5).
