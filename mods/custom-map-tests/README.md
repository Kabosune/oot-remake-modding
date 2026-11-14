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

Result of B6: **loads, and the bigger box works**, but only once the chest is open (a closed chest uses its `CloseBody`;
the base box is in the open chest's `Body`). Link can stand on it, not grab its edge (`Wall_NoClamber` in its
`MaterialPresets`). So box shapes can be edited. Likely cause of B5's crash: the size table entry is the memory for
loading **and unpacking** the pack, and +512 bytes left no room for the unpacked extra boxes. B7: B5's two added
boxes again, with the pack's entry raised by 256 KiB, presets `Material_Wood_Thick` only.

Result of B7: **same crash** as B5, so the size table wasn't the limit. Each actor type has its own fixed heap,
`InstanceHeapSize` in `RSDB/ActorInfo.Product.111.rstbl.byml.zs` (zstd without a dictionary; the chest's is 195,616,
the tree root's 25,336, air walls 0). B8: B7 plus the chest's `InstanceHeapSize` raised to 1,244,192.

Result of B8: **same crash**. It is in main's generic BYML-to-object reader (`0x612760`, crash at `+0xf0`, a call
through an object that was never allocated). So neither the size table nor the actor heap sets the room for a
shape's parts. B9: the same number of parts (3 boxes + 2 polytopes instead of 1 + 4: two side walls swapped for the
slab and the pillar).

Result of B9: **works.** After opening the chest the added boxes are solid, and their edges can be grabbed (no
`Wall_NoClamber`). So a shape's **number of parts is fixed** (adding one crashes the reader), but each part can be
changed into any box. Where that number is kept is not known yet (not the size table, not `InstanceHeapSize`,
not `GameActorInfo`).

Actors whose shapes have the most parts (all 8,373 packs scanned): `Obj_ForestTemple_FallingCeiling_A_01` 236
(Dynamic + Kinematic bodies), `Obj_ForestTemple_PivotedFloor_A_01` 206, `Obj_DodongoCave_CrackWall_A_02` 81 (Static),
`Obj_DodongoCave_BrokenStair_A_01` 55 (Kinematic), `Obj_InsideJabu_Jabu_ElevatorLift_A_02` 50. The Minecraft test map
needs 1,425 boxes (48 x 48 cut) or 9,375 (whole).

B10 re-checks the air-wall result (B2's cube may have been out of bounds, B3's 1 m post was easy to miss): a new
air-wall cube as a 4 x 4 x 0.6 m platform where B9's slab worked, with a chest floating on top marking it.

Result of B10: **no collision.** The marker chest ended up tipped over by the wall, and the floor there is normal.
Confirmed: a newly placed static actor gets no collision. (The spot beside the entrance is close to walls on both
sides: put later test pieces straight ahead, further into the room.)

**Why B5 / B7 / B8 crashed (found 12 Nov, from the size table):** every file inside a pack has its own size table
entry, and a `.bgyml`'s entry covers the object the game reads out of it. The chest shape's own entry is 10,824; with
the two added boxes it needs about 11,458 (B9's swap needs about 9,534, which is why it worked). B5 / B7 / B8 only
raised the pack's entry. The formula is in [docs/custom-maps.md](../../docs/custom-maps.md#size-table-entries-of-shapeparams).

| Test | What it changes | Tells us |
|---|---|---|
| B11. Boxes on a chest, shape entry | B7 again (slab and pillar added to the chest's shape), plus the shape file's own size table entry raised (10,824 → 15,560) | Whether the entry was the whole problem: no crash, and both boxes solid once the chest is open |
| B12. 400 boxes on a chest | 400 boxes added to the chest's shape: an invisible staircase 20 m wide, 20 steps of 0.25 m up to 5 m, starting 2 m in front of the chest and going into the room. Shape entry raised (126,312), chest `InstanceHeapSize` + 2 MiB | Whether more parts than any shape in the game (236) work, and the load time. Run it after B11 |

Result of B11 (12 Nov): **works.** No crash; after opening the chest the pillar (left of the entrance) and the slab
(right, its edges grabbable) are solid. So the shape's own size table entry was the whole problem: a shape can have
more parts than it shipped with once its entry is raised.

Result of B12: loads, no crash, the chest is solid, but **no Open prompt**, so the staircase couldn't be checked. Likely
cause (a guess): `Body_0` is also the shape of the chest's `Tgt` sensor (`Tgt_TgtBody` in its ControllerSetParam),
which the Open prompt probably goes by; with the boxes in it, that sensor covers the whole 20 x 22 m staircase. B11
only grew it by about 2 m.

| Test | What it changes | Tells us |
|---|---|---|
| B13. 400 boxes, own shape file | B12's staircase in a **new** shape file, `Obj_TBox_A_02__KaeGaeMap`, used only by the open chest's body (`Body_Body`); `Body_0` and the sensor unchanged. The new file gets a new size table entry (inserted in hash order) | Open prompt back (then the sensor was the cause), and whether 400 boxes work. Also that a new file in a pack plus a new size table entry works |

Result of B13: **still no Open prompt**, so the shared sensor shape wasn't (the only) cause. The other thing B12 / B13
change that B11 didn't: the chest's `InstanceHeapSize` (+2 MiB, in a byml.py-rewritten `RSDB/ActorInfo`). B14 drops
that file.

| Test | What it changes | Tells us |
|---|---|---|
| B14. 400 boxes, game's heap | B13 without the `RSDB/ActorInfo` file (same pack as B13) | Prompt back: the heap raise or the rewritten ActorInfo broke the chest. A crash: the built shape needs a bigger heap (then try a smaller raise). Still no prompt: it's the boxes themselves (where they are, or how many) |

Result of B14: **no crash, still no Open prompt.** So the heap raise wasn't the cause, and 400 boxes fit in the
chest's own heap (195,616). It's the boxes. B12–B14 also grew the shape's `AutoCalc` bounds over the whole staircase
(centre about 11 m behind the chest, 2.5 m up); B11 grew them by about 1 m. The open body is the chest's `Main` alias,
which the prompt may be aimed at.

| Test | What it changes | Tells us |
|---|---|---|
| B15. 400 boxes, chest's bounds | B14 with the new shape's `AutoCalc` left as the chest's own | Prompt back: the bounds moved the prompt. Then also: is the staircase solid outside those bounds? |

Result of B15: **still no Open prompt**, so the bounds weren't the cause. Left: where the boxes are (B11's were beside
the chest, B12–B15's along its -z from 2 m) or how many.

| Test | What it changes | Tells us |
|---|---|---|
| B16. 400 boxes beside the chest | B15 with the staircase on the chest's +x side, from 4 m out (where B11's slab was), 20 m deep, rising away from the chest | Prompt back: the staircase was in the way along -z (the chest's front or its line of sight). No prompt: the number of boxes |

Result of B16: **still no Open prompt**, so it's not where the boxes are: it's how many. Guess: a limit of 256 parts
per shape (the biggest shape in the game has 236). Over it, the open body's shape probably fails to build without a
crash, and the chest's opening logic gives up with it.

| Test | What it changes | Tells us |
|---|---|---|
| B17. 240 boxes beside the chest | B16 with 20 steps of 12 boxes: 245 parts | Prompt back: under the limit works. Then is the staircase solid? |
| B18. 260 boxes beside the chest | B16 with 20 steps of 13 boxes: 265 parts | With B17: whether the limit sits between 245 and 265 (256 fits) |

Result of B17: **still no Open prompt** at 245 parts (B18 not run). But every test since B13 also uses the new
shape file (rewritten ControllerSetParam, added size table entry), which B11 didn't; and B12's failure had other
causes possible (heap, the shared sensor shape). So the new-file setup itself may be what breaks the chest.

| Test | What it changes | Tells us |
|---|---|---|
| B19. B11 boxes, own shape file | B11's slab and pillar, put the B13–B17 way (new shape file for the open body only, rewritten ControllerSetParam, new size table entry) | Prompt: the setup is fine and the count matters (then halve: ~120, ~60). No prompt: the new-file setup breaks the chest |

Result of B19: **works**: Open prompt, and the slab (right of the entrance, climbable) and pillar are solid. So the
new-file setup is fine. Left: the number of parts, or the size of the shape (the staircases reached 20+ m and ran
into the floor and walls; B11's boxes stay within 4.5 m).

| Test | What it changes | Tells us |
|---|---|---|
| B20. Slab as 240 tiles | B11's slab cut into 240 tiles (15 x 16), no pillar: 245 parts like B17, in B11's footprint. Set up as B19 | Prompt: the count is fine, and the size / reach (or running into the level) broke the staircases. No prompt: the count (then halve) |

Result of B20: **works**: Open prompt, and the tiled slab is solid. So **245 parts are fine**; the number of parts
didn't break B12–B17. Their staircases reached 20+ m from the chest and ran into the floor and walls.

| Test | What it changes | Tells us |
|---|---|---|
| B21. B11 boxes plus a far box | B19 plus one 2 x 0.5 x 2 m box floating 12 m into the room, 8 m up, touching nothing | Prompt: reach is fine, overlapping the level broke the staircases. No prompt: a shape can't reach that far from its actor |

Result of B21: **no Open prompt**, with the far box touching nothing. So it's not overlapping the level: a shape that
reaches far from the chest (6+ m) makes the chest refuse to open. Guess: the prompt is aimed at the centre of the open
body's real bounds (not `AutoCalc`), which the far boxes pull away. It only matters for the chest: the closed chest's
body (`CloseBody`, shape `Body_Close` = `Obj_TBox_A_02__Tgt`) is a **Static** body the chest builds at load, and it's
solid without opening.

| Test | What it changes | Tells us |
|---|---|---|
| B22. Closed chest, far bridge | **Don't open the chest.** `Body_Close` gets its own shape: its two polytopes, B11's slab, and a 1 m wide bridge (top 0.3 m) from 2 m in front of the chest 15 m into the room, ending in a 3 x 3 m landing | Whether a shape's far parts are solid (walk the bridge), and whether a static body works as the map's host |

Result of B22: **works.** Without opening the chest, B11's slab and the whole bridge (15 m into the room) are solid.
So a **Static body that an actor builds at load can carry collision far from the actor**; the missing prompt in
B12–B17 and B21 was only the open chest's prompt logic.

| Test | What it changes | Tells us |
|---|---|---|
| B23. Closed chest, 400-box staircase | **Don't open the chest.** B12's staircase (400 boxes, 20 m wide, up to 5 m) on the closed chest's body, as in B22: 402 parts | Whether more than 256 parts (more than any shape in the game) are solid, and the load time |

Result of B23: **works**: the whole staircase is solid and reaches far. 400 boxes in one shape, more than any shape
in the game, with the chest's own heap and no change to `RSDB/ActorInfo`.

| Test | What it changes | Tells us |
|---|---|---|
| B24. Closed chest, Minecraft cut | **Don't open the chest.** The Minecraft map's 48 x 48 block cut (1,425 boxes) on the closed chest's body, as B23. Its spawn column's top is level with the chest's base, 24 m in front of it; the map spans about 1 to 49 m in front of the chest (nothing rises above the floor within 3 m). Shape entry 421,392 | Whether 1,425 boxes load and are solid (invisible hills and block walls in the room), and the load time |

Result of B24: the scene loads, but **the chest isn't there at all** (nothing to see, nothing solid). Nothing in the
log. Guess: the built shape is made in the chest's own heap (`InstanceHeapSize` 195,616), which held 400 boxes (B23)
but not 1,425, so the game drops the chest.

| Test | What it changes | Tells us |
|---|---|---|
| B25. Minecraft cut, bigger heap | B24 (same pack) plus the chest's `InstanceHeapSize` raised by 2 MiB | Chest back and the map solid: the heap was it (then find how much a box needs). Still no chest: something else (the size of the shape file, 421 KB) |

Result of B25: **still no chest.** So not the heap (or 2 MiB isn't enough). B23 (worked) and B24 / B25 differ in the
number of boxes (400 vs 1,425, with a shape file 3.5 times bigger) and in reach: the cut spans 48 x 48 m, from 6 m up
to 43 m down (it includes the map's underground); B23 about 22 x 20 x 5 m.

| Test | What it changes | Tells us |
|---|---|---|
| B26. Slab as 1,425 tiles | B11's 3 x 3 m slab cut into 1,425 tiles (57 x 25) on the closed chest's body, heap + 2 MiB as B25 | Chest there: the count is fine and the cut's reach / depth was it (then trim the map's underground, or split it over several hosts). No chest: the count or the file size (then halve, ~800) |

Result of B26: **no chest.** So it's the number of parts (or the file size that grows with it), not the reach:
402 parts work (B23), 1,427 don't.

| Test | What it changes | Tells us |
|---|---|---|
| B27. Slab as 800 tiles | B26 with 800 tiles (40 x 20): shape entry 234,600 | Which half the limit is in (402–802 or 802–1,427) |

Result of B27: **works**: chest there, slab solid. So 802 parts are fine; the limit is between 802 and 1,427.

| Test | What it changes | Tells us |
|---|---|---|
| B28. Slab as 1,020 tiles | B26 with 1,020 tiles (34 x 30): 1,022 parts, shape entry 295,544 | Chest there: up to 1,022 parts work (then try just over 1,024). No chest: the limit is between 802 and 1,022, or it's the file size (B27's entry was 234,600) |

Result of B28: **works**: chest there, slab solid. So 1,022 parts are fine.

| Test | What it changes | Tells us |
|---|---|---|
| B29. Slab as 1,029 tiles | B26 with 1,029 tiles (49 x 21): 1,031 parts, shape entry 298,040 (B28's 295,544) | No chest: the limit is 1,024 parts per shape. Chest there: it's higher (between 1,031 and 1,427) |

Result of B29: **no chest.** So **one shape holds at most about 1,024 parts** (1,022 work, 1,031 don't; the files
differ by 1 %). Over it, the game doesn't create the actor at all, with nothing in the log. So far:

- the shape's own size table entry must fit it (`shape_entry()`), B11;
- up to 1,022 parts work, close by or 22+ m away (B22, B23, B27, B28); 1,031+ drop the actor (B24–B26, B29);
- the actor's `InstanceHeapSize` didn't need raising up to 402 parts (B23), and raising it didn't help over the cap;
- on the **open** chest's body, a shape reaching 6+ m from the chest also costs the chest its Open prompt (B12–B17,
  B21); the closed chest's body has no such problem.

A map's collision gets split into shapes of at most ~1,000 boxes: the 1,425-box Minecraft cut needs 2, the whole map
(9,375) about 10.

Next: the Minecraft cut in two halves on two bodies. Chests of one type share one pack (and so one shape), so the
second half goes on a second chest type, `Obj_TBox_A_01` (the small chest; the Deku Tree has one, with Deku nuts).
Its pack is set up like A_02's: a Static `CloseBody` whose shape `Body_Close` is `Obj_TBox_A_01__Tgt` (one polytope),
its own ControllerSetParam, `InstanceHeapSize` 178,704. Split at the spawn column (grid x 24), each half greedied on
its own: 699 + 729 boxes (1,428, three more than in one piece). Three tests, one change each:

| Test | What it changes | Tells us |
|---|---|---|
| B30. Small chest, far bridge | Control for A_01: B22's bridge and landing (no slab) on A_01's closed body, A_01 heap + 2 MiB; the small chest 3 m in front of the entrance, 2 m to the right (where B32 puts it). No big chest | Small chest there and the bridge solid 15 m out: A_01 hosts like A_02 (then B32 can use it) |
| B31. Minecraft half on one chest | B25 with only the right half of the cut (729 boxes, 731 parts, entry 223,784): grid x 24-47, from the big chest's line 24 m to the right, 1 to 49 m in front, 6 m up to 43 m down | Chest there and that half solid: the map's shapes and reach are fine under the cap |
| B32. Minecraft cut on two chests | B31 plus the left half (699 boxes, 700 parts, entry 212,696) on the small chest's closed body (B30's setup), both heaps + 2 MiB | Both chests there and the whole cut solid: a map can be spread over several hosts |

Result of B30: **works**: the small chest is there and the bridge is solid out to the landing. So `Obj_TBox_A_01`'s
closed body hosts collision like A_02's (with its heap + 2 MiB), and B32 can use it.

Result of B31: **works**: the chest is there and the right half of the cut is solid. So the map's own shapes and
reach (24 x 48 m, 6 m up to 43 m down) are fine on a closed chest's body under the part cap; B24 / B25 failed only
by the count.

Result of B32: **works**: both chests there, the whole 48 x 48 cut solid, loading time normal. The seam between
the halves can't be seen (the boxes are invisible); nothing odd walking over it. So **a map's collision can be spread
over several host actors**, each shape under the part cap: the whole map (9,375 boxes) would need about 10.

One chest type per shape would run out of chest types (and fill maps with chests). Next: more than one map body on one
chest. The chest's ControllerSetParam lists 4 rigid bodies (Cover, Body, CloseBody, AirWall); AirWall has no alias and
still exists, so every listed body looks built at load.

| Test | What it changes | Tells us |
|---|---|---|
| B33. Second body, far bridge | B22's exact shape (the closed chest's two polytopes, B11's slab, the bridge and landing) on a new, fifth Static body `KaeGaeMap0` (a copy of `CloseBody`'s RigidBodyEntityParam, own shape name, new size table entries); `CloseBody` left vanilla | Bridge solid: an actor builds extra bodies listed in its ControllerSetParam, so one host can carry several map shapes. Chest there but no bridge: only the bodies the chest's code asks for are built |

Result of B33: the chest is there, but **no slab and no bridge**. So a body listed only in the ControllerSetParam
isn't added to the world. Each of the chest's four bodies also has a unit in its controller
(`Obj_TBox_A_02_Body`, a RigidBodyControllerEntityParam: Cover, Body, CloseBody, AirWall, all `IsAddToWorldOnReset`);
B33's body had none. (The chest's AI also asks for `CloseBody` by name, to add and remove it.)

| Test | What it changes | Tells us |
|---|---|---|
| B34. Second body in the controller | B33 plus a unit for `KaeGaeMap0` in the chest's controller, a copy of `CloseBody`'s (only that file differs from B33) | Bridge solid: a body needs a controller unit, and then one host can carry several shapes. Still nothing: the chest's code adds only the bodies it knows by name |

Result of B34: chest there, **still no slab and no bridge**. So the chest adds only the bodies its own code knows by name
(its AI asks for `CloseBody` by name). Its other two bodies don't help: `AirWall` only hits small objects
(`HitOnlySmallObject`) and, like `Cover`, follows the lid's bone. **One chest, one map shape.**

So, a host without chest behaviour. The game has `_NoBake` versions only of chests. A scan of all shapes for actors
with one Kinematic body found `Obj_Flag_A_01`: a plain `GameActor` (`ActorLogicSimpleActor`, no AI, PreActorSetting
`ActorOnly` rather than the baked pieces' `ConstPassive`), one Kinematic body `Physical` that its controller adds to the
world, one shape (its 4.6 m pole, one polytope), `InstanceHeapSize` 26,912.

| Test | What it changes | Tells us |
|---|---|---|
| B35. Flag host, far bridge | No chest. One `Obj_Flag_A_01` 3 m in front of the entrance (where the chests stood), its shape = its pole plus B22's slab, bridge and landing (changed in place, entry raised); flag heap + 2 MiB | Flag there and the bridge solid: a plain actor hosts map collision (then: the Minecraft halves on two flags, which would share one pack, so on two copies under new names or one shape per flag type). No flag: a new actor type in this scene doesn't load as placed. Flag but no bridge: its body isn't solid to Link |

Result of B35: **works**: the flag is there, the slab and the whole bridge out to the landing are solid. So **a plain
actor with no behaviour hosts map collision**, built at load and solid 15+ m away.

Actors of one name share one pack (and shape), so a map needs hosts under new names. A copy needs rows in two RSDB
tables (both sorted by `__RowId`): `ActorInfo` (heap, model) and `GameActorInfo` (`MainRigidBodyLayer`); the `Tag`
table doesn't list the flag.

| Test | What it changes | Tells us |
|---|---|---|
| B36. Flag copy under a new name | B35 with the flag as `KaeGae_MapHost_00`: own pack, ActorParam (PhysicsRef), PhysicsParam (ControllerSetPath), ControllerSetParam (shape path) and shape; flag's model, body and controller files reused; new rows in `ActorInfo` (heap + 2 MiB) and `GameActorInfo`; new size table entries | Flag there and bridge solid: new actor names work, so a map gets as many hosts as it needs |

Result of B36: **works**: flag there, slab and bridge solid. So **new actor names work**: a map can have as many hosts
as it needs, with no chests.

| Test | What it changes | Tells us |
|---|---|---|
| B37. Minecraft cut on two flags | B32 with the two chests replaced by B36-style flags: the right half (729 boxes) on `KaeGae_MapHost_00` where the big chest stood, the left half (699) on `KaeGae_MapHost_01` 2 m to its right; both heaps + 2 MiB | The whole cut solid with no chests: the setup for whole maps (the full map would be about 10 such hosts) |

Result of B37: **works**: both flags there, the whole cut solid, seam fine, load time as B32. **The setup for whole
maps: flag hosts under new names, each shape under ~1,000 boxes.**

The whole map, split by halving regions along x / z until each part greedies to at most 950 boxes (`map_chunks()`):
14 parts, 444 to 920 boxes, 9,397 in all (9,375 in one piece). It reaches about 85 m left and right, 87 m ahead and
40 m back. The flag's `ActorInfo` row has `CalcRadius` 100 (`LoadRadius` 200), so hosts more than ~100 m from Link
may not be kept: B38 keeps every host at the entrance (only the map's size and host count change), B39 would move each
host to the middle of its part if far parts go missing.

| Test | What it changes | Tells us |
|---|---|---|
| B38. Whole Minecraft map on 14 flags | B37's setup and alignment, with the whole map: 14 hosts `KaeGae_MapHost_00`..`13`, all in a row at the entrance 1 m apart (centred where the chest stood), heaps + 2 MiB each (28 MiB in all) | 14 flags there and the map solid: whole maps work. Missing flags: too many hosts or too much heap. Ground missing only far out (~100 m): the hosts' radius (then B39) |

Result of B38: **works**: the whole map is solid, performance fine (load time and frame rate). **A whole custom map's
collision works today with romfs files only**: flag hosts under new names (`flag_copy()`, `host_rows()`), the map split
into parts of at most ~950 boxes (`map_chunks()`), each part's shape with its own size table entry (`shape_entry()`).
B39 (hosts moved into their parts) isn't needed for now (the number went to the next test).

A quick look at the map before real models (own `.bfres` / `.bntx`, a big job): the game's own 1 m stone block
`Land_SacredForest_Prop_A_06` (a plain Land piece; model bounds 0 to 1 m up, centred) placed once per collision box and
scaled to it. The game's own Deku Tree placement has 68 actors with uneven scales, so that's supported.

| Test | What it changes | Tells us |
|---|---|---|
| B39. Minecraft cut you can see | B37 plus 217 stone blocks, one per collision box whose top is above the floor, scaled to it (Dynamic placement file, `Bakeable`, as the game's Land pieces), and one unscaled 1 m block 2 m left of the flags as a control | Blocks show where the collision is: the map's shape can be seen with stretched stone textures. Only the control shows: scaled placements don't render. Nothing shows: a newly placed Land piece of a type the scene doesn't use doesn't render |

Result of B39: **works**: the control block shows (no collision, as expected for a newly placed Land piece), the
scaled blocks show the cut's shape, they match the collision (you walk on top of them), performance fine. So **scaled
placements of the game's own models are a quick way to see a map** (stretched textures), until real models exist.

The whole map you can see (KaboWabo picked option 1 of 4, 13 Nov 2026):

| Test | What it changes | Tells us |
|---|---|---|
| B40. Whole Minecraft map you can see | B38 (byte-identical hosts, RSDB rows and Static file) plus 2,450 stone blocks, one per collision box whose top is above the floor, scaled to it, as in B39; and one unscaled control block 2 m left of the row of flags. Dynamic placement file 553 KB (size table entry 230,472 -> 553,600) | Blocks show the whole map's shape where it's solid. Blocks missing far out only: their draw distance (or the scene's culling boxes). Load fails or frame rate drops a lot: too many placed actors in one scene, so merge blocks per material or real models are needed sooner |

Result of B40 (13 Nov 2026): **works, partly**: loads normally, frame rate fine with 2,450 blocks. The stone blocks
show, the Deku Tree's own level is still there, and there's solid ground you can't see: the map's boxes whose top is
at the old floor got no block (outside the Deku Tree's room there's no old floor to hide them). Walking far out, the
game sends Link back for going out of bounds, so the far map (and the control block) couldn't be checked.
Likely cause of the respawn: the scene's `HeightMapParam` bounding box in `GameBancParam` (x -90..50, y 40..124,
z -25..100) is smaller than the map (x -85..86, y 58..128, z -77..50). `WorldAabb` (-125..125, y to 250) already covers it.

Two follow-ups, each one change from B40:

| Test | What it changes | Tells us |
|---|---|---|
| B42. B40 with wider scene bounds | Only `InsideTheDekuTree.game__banc__GameBancParam.bgyml`: `HeightMapParam` bounding box to x -95..95, y 40..135, z -85..100 (same file size, so the size table is unchanged) | No respawn when walking out over the map: that box is the out-of-bounds limit. Still a respawn: something else (next guess: being outside every `DungeonRoomArea`). Crash or odd ground: the box also indexes the height map |
| B41. B40 with every box drawn | A block for each of the 9,397 collision boxes, not just those above the floor (Dynamic file 1.45 MB, entry 230,472 -> 1,448,496) | No invisible ground left, and whether 9,397 placed blocks still load and run fine |

Result of B42 (13 Nov 2026): **no change**: the Deku Tree looks and plays normally, but its own walls still stop
Link, and past them (with a noclip mod) the game still sends Link back for going out of bounds. So the
`HeightMapParam` box isn't the limit. The control block wasn't seen: it's 2 m left of the leftmost flag (about 9 m
left of the entrance's middle), most likely inside the entrance's left wall. Candidates left: being outside every
`DungeonRoomArea` (25, no links), the `LocationArea` (origin, scale 100), or a check in code (`main` has
`ReturnToSafePos`, `InvalidateRestartPos`, `OutOfRange`).

Result of B41 (13 Nov 2026): **works**: blocks now show everywhere there's collision, reaching far from the spawn;
collision fine, frame rate fine with 9,397 placed blocks. The Deku Tree's own level and its out-of-bounds respawn are
still there. Outside the Deku Tree's rooms it's very dark, which makes the map hard to see.

| Test | What it changes | Tells us |
|---|---|---|
| B43. B41 with baked light off | Only `GameBancParam` `IsEnableBakeLight` true -> false (same file size) | Out-of-bounds map lit: the darkness is the baked light (probes only cover the real rooms). Everything dark or black: the scene needs its bake, try the environment next (`EnvSetName` / `RenderingMode` from Kokiri Forest, or the room env in `DungeonRoomEnvParam`) |

Result of B43 (13 Nov 2026): **a little lighter, still mostly dark**: out of bounds is barely lit; the Deku Tree
itself turns very dark (not black). Navi's light lights things up around Link, so dynamic lights still work. The
out-of-bounds respawn is unchanged.

The Deku Tree's env palette (`Pack/EnvPalette.pack.zs`, `WorldMgr/ResEnvPalette/InsideTheDekuTree...`, parent
`Parent_Dungeon`) has `AmbientIntensity` 0.1 (the parent's is 1.0), `HemiLightIntensity` 0.25, `BgDifIntensity` 0,
`ExposureValue` 2.88.

| Test | What it changes | Tells us |
|---|---|---|
| B44. B43 with a brighter palette | Only the Deku Tree's env palette in `EnvPalette.pack.zs`: `AmbientIntensity` 0.1 -> 1.0, `HemiLightIntensity` 0.25 -> 1.0 (same file size; the pack's entry 422,744 -> 422,936) | Map lit everywhere: a temporary light for map tests (tune the two numbers). No change: the palette isn't read here or the bake-off path ignores it |

Result of B44 (13 Nov 2026): **works**: a little dim, but the map can be seen out of bounds. So turning off the bake
and raising the palette's ambient and hemi light is the temporary map-test light for now. Exploring with the noclip mod,
the game froze once (not looked into: could be the noclip mod, or something far out), and the out-of-bounds respawn
is still there.

KaboWabo agreed (13 Nov) to go for the emptied scene: the map should replace the Deku Tree's own level, not sit inside
it. Control first: **test C** (built on 12 Nov, never tested; rebuilt byte-identical): Inside the Deku Tree emptied to
its 6 spawn points (Static 475 actors and Dynamic 1,615 actors removed, all groups cleared), nothing added. Then:

| Test | What it changes | Tells us |
|---|---|---|
| B45. B44 in the emptied Deku Tree | B44 with C's emptied placement files (only the 6 spawn points left), hosts and blocks added to them as before | The map on its own: no Deku Tree level, and maybe no out-of-bounds respawn (if it came from the placement) |

Result of C (13 Nov 2026): **loads**. The Deku Tree's level is mostly gone from view (some foliage is still there:
it comes from the scene's own foliage files, not the placement). The out-of-bounds respawn is mostly gone too: only
far out does the game send Link back. But **the Deku Tree's collision is still there, climbable vines included**: it
lives in the scene's pre-built static compound (`Phive/StaticCompoundBody/InsideTheDekuTree/...bphsc`, 2.6 MB
packed, 3.98 MB unpacked), not in the placement. B45 (the map in C) waits for the next step.

The game has 16 tiny static compounds (DarkLinkStage and MorphaStage tiles, 85 / 88 bytes packed), all **byte-identical**
when unpacked (53,264 bytes, same header layout as the Deku Tree's, every body section empty): a generic empty compound.
`GameBancParam`'s `StaticCompoundMode` (Kokiri and 24 other scenes have `1277310799`, 9 have `2165085917`, the Deku Tree
and 45 others have none) is a murmur3 hash that no word in `main` matched.

| Test | What it changes | Tells us |
|---|---|---|
| B46. C without the Deku Tree's collision | C plus `InsideTheDekuTree.Nin_Ounce_NVN2.bphsc.zs` replaced by the empty compound (`MorphaStage_X0_Z0`'s); only that file differs from C | Walls, floor and vines gone (Link falls or voids out at the spawn): the compound is the Deku Tree's collision and an empty one loads. Crash: the scene needs a matching compound |
| B47. B45 without the Deku Tree's collision | B45 (the map, every box drawn, the B44 light, in C's emptied scene) plus B46's empty compound | The map alone in the Deku Tree's place |

Result of B46 (13 Nov 2026): **works**: loads, the Deku Tree's walls and floor are gone. Only the foliage decoration
is left (the scene's foliage files). So the static compound is the Deku Tree's collision, and the game's empty one
loads in its place. Result of B47 (13 Nov 2026): **works: the map alone in the Deku Tree's place.** It loads, Link arrives where he
would in the vanilla Deku Tree, the map is there (foliage still there too). The horizontal out-of-bounds limit is now
far out, but **low parts of the map trip a vertical out-of-bounds respawn** (the map reaches 43 m below the spawn,
down to world y 58). Height of the trigger not known yet.

The foliage is six placement files (`Foliage/Placement/Scene/InsideTheDekuTree/InsideTheDekuTree.*.flnt.zs`: Moss,
Stone, Turf, Undergrowth4, LowTree, Ornament), tied to the scene by `GameBancParam`'s `FoliageScene`. 34 of the game's
80 scenes have no `FoliageScene` line at all.

| Test | What it changes | Tells us |
|---|---|---|
| B48. B47 without foliage | Only `GameBancParam`: the `FoliageScene` line removed | Foliage gone: the scene settings switch it off. Some left (low trees, ornaments): those load another way |

Result of B48: not tested yet.

## Building

```
python3 mods/custom-map-tests/build_tests.py --romfs <folder> --glb <map.glb> --out <dir>
```

`--romfs` is a folder with these files from your own dump, at their romfs paths: `Pack/ZsDic.pack.zs`, the resource
size table, `Banc/KokiriForest/KokiriForest_Child_Static.bcett.byml.zs`, both `Banc/InsideTheDekuTree/` placement
files, `Pack/Actor/Land_Deku_TreeRoot_B_01.pack.zs`, `Pack/Actor/Obj_TBox_A_02.pack.zs`, `Pack/Actor/Obj_TBox_A_01.pack.zs`
and `RSDB/ActorInfo.Product.111.rstbl.byml.zs`. Needs `pip install zstandard trimesh scipy numpy`.

Test map used: "High quality minecraft world" by SOLDMARS (Sketchfab), CC-BY-4.0. It isn't included here.

## Credits

KaboWabo/Kabosune (me :3), AI assistance (Claude Opus 5.5).
