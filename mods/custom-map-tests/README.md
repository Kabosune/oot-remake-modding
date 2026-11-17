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

Result of B48 (13 Nov 2026): **mostly works**: most foliage is gone; some is left (the climbable-vine kind and
bushes: they load another way, not looked into yet). The scene is still really dim; KaboWabo asked for stronger
lighting everywhere, like Hyrule Field's.

Hyrule Field (`HyruleField_Child`) uses `RenderingMode` `1713552710` (also Kokiri Forest and 14 `Master_Field`
scenes: the outdoor mode) and `EnvSetName` `Master_Field` (time-of-day palettes with sun and sky); the Deku Tree has
`121762225` (the dungeon mode, 14 scenes) and `Dungeon`.

| Test | What it changes | Tells us |
|---|---|---|
| B49. B48 with Hyrule Field's lighting | Only `GameBancParam`: `RenderingMode` -> `1713552710`, `EnvSetName` -> `Master_Field` | Lit like a field (sun, sky): the outdoor mode works in this scene. Broken / black: try the outdoor mode alone, or B50 |
| B50. B48 with a brighter palette | Only the Deku Tree's env palette: `AmbientIntensity` and `HemiLightIntensity` 1.0 -> 3.0 | A fallback: evenly brighter everywhere, no sun |

Result of B49 (13 Nov 2026): **no change**: lighting exactly as B48, nothing broken, the map the same, vines and some
bushes still there. Checked: the installed files match the build (`RenderingMode` 1713552710, `EnvSetName`
`Master_Field` in place) and nothing is switched off in Fritchii. So neither value picks the lighting here; the
Deku Tree's own palette (by scene name, or its `Location`) most likely does. Result of B50 (13 Nov 2026): **works**: way brighter, much better lighting. KaboWabo wants it to look more like
Hyrule Field next. The vines and bushes are still there, and the out-of-bounds limit is still strict: Link can't go
far horizontally at all.

The palette a scene uses comes from its `WorldParam` (`GameBancParam` `WorldMgrName` -> `WorldMgr/WorldParam/...`):
the Deku Tree's has `DefaultEnvPalette` = its own palette (parent `Dungeon`: `WorldType` 121762225). Hyrule Field's
(`HyruleField_Child`, parent `MainField`) has time-of-day palette tables (`MainField_Bluesky_*`, `MainField_Cloudy`),
a sun and moon, and cloud shadows. That's why B49 (`RenderingMode`, `EnvSetName`) changed nothing.

With the Deku Tree's own level gone, the `HeightMapParam` bounding box (x -90..50, y 40..124, z -25..100) is the next
suspect for the horizontal limit (B42 couldn't show it while the Deku Tree's placement was still there); the map
reaches past it to the right (x 86) and ahead (z -77).

| Test | What it changes | Tells us |
|---|---|---|
| B51. B50 with wider scene bounds | Only `GameBancParam`: `HeightMapParam` box -> x -95..95, y 0..135, z -85..100 | Link can walk the whole map: that box is the limit (and maybe the vertical one) |
| B52. B51 with Hyrule Field's world settings | Only `GameBancParam`: `WorldMgrName` -> `HyruleField_Child`'s `WorldParam` | Lit like Hyrule Field (sun, sky, time of day). If dark or odd: add the outdoor `RenderingMode` too |

Result of B51 (13 Nov 2026): **no change**: the out-of-bounds limit feels the same (strict); vines and some foliage
still there. So `HeightMapParam`'s box isn't the limit.

Next suspect: **`Game/VolumeStatsAABB/InsideTheDekuTree.game__VolumeStatsAABB.bgyml`** (136 bytes, one per scene, 78 in
the game): `Min` (-83, 47, -21), `Max` (42, 134, 89), exactly the Deku Tree's rooms. The map reaches x 86 and z -77,
past it to the right and ahead. (A Havok volume-stats file goes with it: `Phive/VolumeStats/InsideTheDekuTree/
InsideTheDekuTree.bpvsts.zs`, 532 KB, the next suspect if the AABB isn't it.)

The leftover foliage: `LowTree` (format 2, 34 entries, `ResShootBranch` pieces) and `Ornament` (format 4, 3,302 entries,
`ResShootLeaf` pieces) load without `FoliageScene`. The game's smallest foliage placements are 34 bytes packed
(`LostWood_*.Undergrowth8`, format 4, one entry, 56 bytes unpacked).

| Test | What it changes | Tells us |
|---|---|---|
| B53. B52 with a wider VolumeStatsAABB | Only `VolumeStatsAABB`: -> x -95..95, y 0..150, z -90..100 | No respawn walking the whole map: that box is the out-of-bounds limit (maybe the vertical one too) |
| B54. B53 without the Ornament foliage | Only `InsideTheDekuTree.Ornament.flnt.zs`: replaced by `LostWood_Child...Undergrowth8`'s (same format) | Vines / leafy bits gone; what's left is `LowTree` (bushes) |

Result of B52 (13 Nov 2026): **works: the lighting looks way better and like Hyrule Field.** Time of day comes from
`MainField`'s `WorldParam` (in `Pack/Bootup`): palette time tables (`MainField_Bluesky` / `_Cloudy` in
`EnvPalette.pack`: BeforeSunrise 3:20, Sunrise 5:00, ... each blended over 20–30 game minutes), the sun and moon moving
with the clock (`IsSolarMotion`; child Hyrule Field: sunrise 4:00, sunset 19:40), and a first-visit table with a fixed
sun angle while `HyruleField_ChangeENV` holds. The Deku Tree's `GameBancParam` has `IsEnableTimerCounting: false`
(dungeons stop the clock; Hyrule Field has no such line), so on the map the time likely stays where it was on entry. Result of B53 (13 Nov 2026): **out-of-bounds unchanged**, read with Slopped Up Sloperina's watches: the respawn
triggers at **x 6.45, y 89.0, z 22.39**, only ~8 m from the spawn (0.2, 101, 14.7) but 12 m below its floor. So it's
not a box around the map but a floor under the Deku Tree's old ground: the scene's height map (`HeightMapParam`,
`MultiLayeredMapHeight`, `TerrainArc/InsideTheDekuTree_B01` `.hght`) is the prime suspect. 27 of the game's 80 scenes
(the boss stages) have no `HeightMapParam`. **The game also froze** at x 6.00, y 95.40, z 35.74 (behind the spawn, toward
the entrance). `OptimizeChangeBancUnits` preloads Kokiri Forest when Link is within 30 m (`LoadRadius`) of (0, 101,
10.6) by the entrance; with the map's memory on top (14 hosts at heap + 2 MiB, a 1.45 MB placement) that preload is the
prime suspect. Only 2 of 80 scenes have no `OptimizeChangeBancUnits` (`SageRoom`, `Demo_ShootingLocation_Tapestry_ED`).
Seen in the screenshots: Hyrule Field's night sky and lighting, the map lit and solid, and log pillars with leaves left
over (foliage).

| Test | What it changes | Tells us |
|---|---|---|
| B55. B54 without the height map | Only `GameBancParam`: `HeightMapParam` removed | No respawn going down: the height map was the limit |
| B56. B55 without the preload list | Only `GameBancParam`: `OptimizeChangeBancUnits` removed | No freeze near the entrance: the Kokiri Forest preload was it (leaving the scene may then load slower) |

Result of B54 (13 Nov 2026): **half**: the climbable vines are gone (so they were the Ornament foliage); ferns are
still there (`LowTree`, format 2, 34 `ResShootBranch` pieces). The out-of-bounds respawn again at x 8.84, **y 88.0**,
z 24.11 (same height as in B53, as expected: B54 didn't touch it). **The "log pillars" seen in the screenshots are the
14 flag hosts** (`KaeGae_MapHost_00`..`13`, copies of `Obj_Flag_A_01`) standing in a row at the entrance, poles and
cloth showing, now in mid-air with the floor gone.

No empty format-2 foliage file exists (smallest: Gerudo Valley's Ornament, 22 entries). But Ornament files come in
both formats (Gerudo Valley's are 2, the Deku Tree's 4), so the format isn't tied to the kind of foliage.

| Test | What it changes | Tells us |
|---|---|---|
| B57. B56 without the LowTree foliage | Only `InsideTheDekuTree.LowTree.flnt.zs`: replaced by the same 56-byte format-4 file as B54 | Ferns gone: no Deku Tree foliage left |

Result of B55 (13 Nov 2026): **the falling limit moved down**: clipping through the floor and falling, Link is sent
back at **x -13.53, y 66.08, z 4.57** (black screen), where in B53 / B54 it was y 88–89 near the spawn. So the height
map set that floor; what's left is the normal "fell off the level" respawn, below the map's bottom. The flag hosts still
show (expected). Walking as far as possible behind the spawn, Link stops at **x 2.03, y 96.00,
z 40.50**: 30.36 m from `OptimizeChangeBancUnits`' Kokiri Forest point (0.03, 101.12, 10.64), whose `LoadRadius` is 30
(that entry also has `IsUseFailSafe`). The B53 freeze (x 6.00, y 95.40, z 35.74) was in the same area. So B56 tests
both. Result of B56 (13 Nov 2026): **the limit behind the spawn is unchanged**: Link still stops at x 2.03, y 96.00,
z 40.13 (so the 30 m preload radius was a coincidence). The ferns are still there (expected: B57). Checked: the map is
open there (at x 2 the ground is at y 96 and runs on to z 50, no wall), so something invisible stops Link roughly
where the old Deku Tree's entrance is. Next suspect: the scene's Havok volume stats
`Phive/VolumeStats/InsideTheDekuTree/InsideTheDekuTree.bpvsts.zs` (1,015,667 bytes unpacked, a detailed map of the
old level; source param `IsUseMutableLayer: true`, no `PresenceSetting`). The game has 1,065 `.bpvsts`; the smallest
(Death Mountain Trail tiles) are 342 bytes unpacked, same `Phive` header.

| Test | What it changes | Tells us |
|---|---|---|
| B58. B57 with tiny volume stats | Only `InsideTheDekuTree.bpvsts.zs`: replaced by `DeathMountainTrail_Adult_X0_Z0`'s (342 bytes) | Link walks past z 40: the volume stats were the limit. Worse (respawn everywhere) or crash: they define where Link may be, and need writing for the map |

Result of B57 (13 Nov 2026): **works: the ferns are gone, no foliage left at all.** No freeze near the entrance
(around z 35) in B56 / B57 either (it froze there once in B53, with the Kokiri Forest preload still on). Result of B58 (13 Nov 2026): **works: the map is fully walkable.** Link walks past z 40 and anywhere around the map.
So **the scene's Havok volume stats (`.bpvsts`) were the last limit** (the game's own name for falling out is "abyss":
`FallIntoAbyss`, `ExecuteEventPlayerAbyss`, back to the `RestartPos` / `SafePos`). The only respawn left is the normal
abyss far below the map (seen at x 1.49, y -44.24, z 15.56), which this map doesn't need to care about.

**So a clean slate for a custom map in an existing scene is:** the placement emptied to its spawn points (C), the
game's empty static compound (B46), no `FoliageScene` line plus near-empty `LowTree` / `Ornament` foliage files
(B48, B54, B57), no `HeightMapParam` (B55), no `OptimizeChangeBancUnits` (B56), tiny volume stats (B58), and for the
looks Hyrule Field's `WorldParam` (B52).

Hiding the 14 flag hosts (their poles and cloth stand in a row at the entrance): `Obj_Flag_A_01`'s ActorParam points
`ModelInfoRef` at its own model (`Obj_Flag_A` / `Obj_Flag_A_01`); its parent `Obj_Default_A_00` uses
`Component/ModelInfo/Dummy` (what model-less actors use).

| Test | What it changes | Tells us |
|---|---|---|
| B59. B58 with hidden flag hosts | Only the 14 host packs: each ActorParam's `ModelInfoRef` -> `?Component/ModelInfo/Dummy.engine__component__ModelInfo.bgyml` | Flags gone and the map still solid: hosts need no visible model. Collision gone or hosts missing: the body needs the model's skeleton |

Result of B59 (13 Nov 2026): **posts gone, but so is the collision**: the map shows, Link falls through it. So the
host's body needs its real model: the flag's body controller binds to the model (`BoneBindModePosition` /
`BoneBindModeRotation`), and with `Dummy` no body is built. (Air walls use `Component/ModelInfo/None`, empty names, but
newly placed air walls never got collision in round 1, so that's no way out.)

Instead: keep the flag model and put the posts where nobody looks.

| Test | What it changes | Tells us |
|---|---|---|
| B60. B58 with the flag hosts under the map | Only the hosts: each placed at the middle of its own part of the map, 6 m below the part's lowest block (all at y 52, the map's bottom is y 58), its boxes shifted to match so the collision stays exactly where it was | Posts out of sight, map solid everywhere: hidden hosts. Parts of the map not solid: a host's reach or radius (`CalcRadius` 100) |

Result of B60 (13 Nov 2026): **works: the posts are out of sight and the map is solid everywhere.** So hosts can stand
anywhere, as long as their boxes are placed relative to them; spread under the map, each sits close to the part it
carries. **The cleanup is done: the Minecraft map stands in the Deku Tree's place with nothing of the old level left.**

Noticed: noclipping downward **into** the map's solid blocks, the game froze once at x 75.25, y 81.78, z 14.74 (inside
the blocks, screen dark). Most likely the noclip mod pushing Link into solid boxes; not seen in normal play. Not looked
into further (to tell: does it happen without noclip, or when noclipping into the vanilla Deku Tree's walls?). Also
still there: the Deku Tree's dungeon map in the corner (B1 floor), from its `UI/CustomTex/Map/Dungeon` / `DungeonParam`.

## The map as a scene of its own (S1, 13 Nov 2026)

KaboWabo picked the new scene next ("I just want to see it mostly complete now"), so the real Deku Tree stays
playable. Everything from B60, moved to a new scene `KaeGae_Minecraft`:

- The B60 build's Deku Tree files under the new name: scene settings (`Banc.Main` → `Work/Banc/Scene/KaeGae_Minecraft/
  KaeGae_Minecraft.bcett.json`), both placement files, empty static compound, tiny volume stats, widened
  `VolumeStatsAABB`. No leftover-foliage files (a new scene has none) and no change to the shared palette pack.
- The Deku Tree's other files looked up by the scene's name, copied under the new name: `Bake/Light`, `Bake/Scene`
  (4), `Bake/Probe/Scene/<scene>/` (30), `Game/AdjacentRoomsInfo`, `Game/BakeSceneLayerConfig`,
  `PreComputedCulling/<scene>/Boxes.bbox`, `Phive/NavMesh`, the volume stats' source param. (Sound, `Sound/Shape`, the
  `VolumeFogAreaParam`s and the HUD map textures are named per actor, area or dungeon, not per scene.)
- RSDB `GameBancInfo`: a row for `KaeGae_Minecraft` (a copy of the Deku Tree's, sorted by `__RowId`).
- `AoC1/Banc/BancBasedResource/StartPos.byml`: every scene's start positions by scene name; a `KaeGae_Minecraft`
  entry (a copy of the Deku Tree's: `Entrance` at 0.2, 101, 14.7, ...).
- Kokiri Forest's Deku Tree door (`FrontDekuTree`, `FieldAndDungeonEntranceEventRequestActor` in
  `KokiriForest_Child_Static`): `NextBancParamNameChild` / `Adult` → `KaeGae_Minecraft`, `NextStartPosName` `Entrance`,
  `NextEventName` → the generic `Dm_SY_BancChangeArrive` (as the Kokiri Forest → Hyrule Field door uses), the
  Deku Tree's `InitEventName` / `InitEventFlag` dropped.

No control test before it (KaboWabo asked for few test rounds): if S1 fails, the controls are test A (the door to
an existing scene) and a plain renamed copy of the Deku Tree.

| Test | What it changes | Tells us |
|---|---|---|
| S1. The map as its own scene | All of the above; the real Deku Tree's files untouched | Entering the Deku Tree from Kokiri Forest lands on the map, same as B60: new scenes work. Black screen / crash / back in Kokiri: a missing piece (then test A and a renamed Deku Tree as controls) |

Result of S1 (13 Nov ~20:20 PT): **froze while loading** the new scene. The emulator log (`fritchii\log\eden_log.txt`)
shows a crash, not a hang: a read through an empty pointer in `main` at `0x112b3f4` (called from the logic node at slot
`0xe8` of vtable `0x4ba4b70`, `0x112b3a0`; the node is made by `0xdefb50`, registered under hash `0xd04a2892`). The function
reads a 0x290-byte global manager (`*0x4e919d0`, built at `0xf96640`; a 256-character name at +0x40 and a ref-counted
object at +0x38 that is empty here) and calls through +0x38 → +0x150 without checking. The CPU registers still held
the text `KaeGae_Minecraft`: something looked the new name up and found nothing. Other callers check +0x38 for empty
first (e.g. `0x9eec60`).

What a new scene still lacked: `AoC1/Banc/BancBasedResource/` is only one of **two** sets of per-scene files keyed by
scene name. The base game has its own `Banc/BancBasedResource/` (the `AoC1` set adds the Master Quest `_MQ` scenes),
and S1 added only a StartPos entry, only to the `AoC1` set. Both sets have `StartPos`, `LocationArea` (an entry for
every scene: 80 / 93), `MapParam`, `NoEscapeRangeArea`, `GmdReset` (plus the empty `AlternativeAnchor` and
`StaticGameDataArea`). The baked-scene files name their textures (`RBake_Scene_InsideTheDekuTree_G_*`) inside the
file, so those need no copies.

## Every per-scene entry (S2, 13 Nov 2026)

| Test | What it changes | Tells us |
|---|---|---|
| S2. S1 with every per-scene entry | S1 + a `KaeGae_Minecraft` entry (a copy of the Deku Tree's) in all five scene-keyed `BancBasedResource` files, in both the base and the `AoC1` set (`BANC_KEYED` in the builder) | Loads: new scenes work, the recipe is complete. Still crashes at the same spot (`0x112b3f4` in the log): the empty object comes from somewhere else |

Result of S2 (13 Nov ~20:35 PT): **crashed at the same spot** (`main` `0x112b3a0` / `0x112b3f4`, the same empty
+0x38, `KaeGae_Minecraft` in the same registers; `eden_log.txt.old.txt`, main loaded at `0x80422000` that run). So the
per-scene `BancBasedResource` entries weren't what the game was missing (S2 keeps them: a new scene needs them anyway,
or the start position is missing in the base set). Next leads: what fills the manager's +0x38 (and what the manager
is); a plain renamed copy of the vanilla Deku Tree as a control (does any new scene name load?); test A, the door
redirect to an existing scene (is the door edit fine?); the Deku Tree's own arrival event on the door.

## The size table was the problem (S3, S4, 17 Nov 2026)

Found without a test round, from `main` and the size table:

- The 0x290-byte manager at `*0x4e919d0` is the **Banc (scene) manager**: its vtable `0x4c5da18` slot `0xc8`
  (`0xf967d0`) returns the text `Banc`. Its +0x38 is the **current scene's loaded settings** (a ref-counted handle,
  count at +0x164) and +0x40 the 256-character path they were looked up by.
- The only code that writes +0x38 is `0xcb0aa0`, called only from `0xcb08b0`: slot `0xe8` (the run function, same
  slot as the crashing node) of a scene sequence node (vtable `0x4bb3300`, made by `0xe1a450`, registered under hash
  `0x2e589ab2` at `0x1069c80`). The node takes a path (or, if empty, its owner's `GameBancParam` property, `0xcb0980`),
  `0xcb0aa0` looks it up among the **already loaded** resources (`0xa57350` on the registry `*0x4e7f7c8`; the key drops a
  leading `Work/` and the extension, `0x6172e0` / `0x3dbc80`) and stores the result in +0x38, **empty if not found**,
  without checking. The node at `0x112b3a0` then reads +0x38 → +0x150 and crashes.
- So the new scene's settings weren't loaded. Why: S1 / S2 gave every file the new scene got under its own name a
  **size table entry of its size + 512**, while the game needs much more for most of them (for a `.bgyml` the entry is
  the file plus the object read from it, as found for ShapeParams in B11). B60, which works, shipped the same 1,984-byte
  scene settings file under the Deku Tree's name with the Deku Tree's entry, 10,784; S2 gave it 2,496. Every one of
  the game's 80 `GameBancParam` entries is at least 6,424 bytes over its file size. **40 of S2's files were short**:

| File (new scene) | S2 gave | The Deku Tree original's entry |
|---|---|---|
| `Banc/GameBancParam/<scene>.game__banc__GameBancParam.bgyml` | 2,496 | 10,784 |
| `Game/AdjacentRoomsInfo`, `Game/BakeSceneLayerConfig`, `Game/VolumeStatsAABB`, the volume stats source param (`.bgyml`) | 608–968 | 5,208–6,840 |
| `Bake/Scene/<scene>_G_*.bkres` (4) | size + 512 | about 2.1 x the size (51,960–525,592) |
| `Bake/Probe/Scene/<scene>/resident.bkprcb` and the `X*_Y*_Z*` probes | size + 512 | up to 2.5 x the size |
| `PreComputedCulling/<scene>/Boxes.bbox` | 16,008 | 29,912 |
| The empty static compound | 53,776 | 55,952 (MorphaStage's own) / 3,991,536 (the Deku Tree's, which B60 used) |

Builder: `write_mod(..., like=)` and `Rstb.get()`; `new_scene()` returns which Deku Tree file each new file was made
from, and every new file gets at least that file's entry (as B60 had). `scene_path()` names foliage files right
(`<scene>.<foliage scene>.<kind>`: only the first part is the scene).

Also found while installing (17 Nov): **Fritchii most likely uses the first mod folder by name that has a file** (how
the yuzu family layers mod romfs folders; not tested here), so of several
switched-on mods shipping the whole size table, only the alphabetically first counts. `KaeGae Built Files` (written by
`kaegae build` on 15 Nov for Equip Anything) sorts before `KaeGae Map Test ...`, so it would have hidden S3's table. S3's
and S4's tables include its one raise (`UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml` 49,296), and it was
moved to `load\.kaegae-staging\KaeGae Built Files (moved out for map test S3)` for the test. S1 and S2 (13 Nov) were
before that folder existed.

| Test | What it changes | Tells us |
|---|---|---|
| S3. S2 with full size table entries | Only the size table: every new-scene file gets at least its Deku Tree original's entry (all other files byte-identical to S2) | Loads and shows the map as in B60: new scenes work, the recipe is complete. Same crash: the empty +0x38 has another cause too (then S4) |
| S4. Control: the vanilla Deku Tree as a new scene `KaeGae_DekuCopy` | The unchanged Deku Tree (settings, placement, compound, volume stats, foliage) under a new name with S3's way of copying and sizing, the same door change. Only installed if S3 fails | Loads as the normal Deku Tree: new names work and S3's problem is in the map build. Crashes: new scene names need something more |

Result of S3 (17 Nov ~07:50 PT): **no crash, but the new scene never finished loading** ("nothing loads"; the game kept
drawing until KaboWabo closed it, `eden_log.txt`: no error before the shutdown, the `Userspace PANIC` at the end is the
forced stop). So the size table fix got past the crash. What still named the old scene: **the placement files'
`FilePath`** (`Work/Banc/Scene/InsideTheDekuTree/InsideTheDekuTree.bcett.json` in both `_Static` and `_Dynamic`), while
the scene settings' `Banc.Main` says `.../KaeGae_Minecraft/KaeGae_Minecraft.bcett.json`. In all 160 of the game's own
placement files `FilePath` is exactly their scene's `Banc.Main`; S3's were the only ones that didn't match, so the loader
most likely waits for a placement under the new path that never arrives. (Other files still naming the Deku Tree do so by
path to files that exist: `BaseLocation`, `DungeonParam`, `LocationalLightScenePlacement`, the `.bkres` texture names.)
S4 had the same mismatch and wasn't tried; it's rebuilt with the fix.

| Test | What it changes | Tells us |
|---|---|---|
| S5. S3 with the placement's `FilePath` | Only `FilePath` in both placement files → the new scene's `Banc.Main` (`new_scene()` does it now) | Loads: new scenes work. Still stuck: something else names the old scene (then S4, rebuilt with the same fix) |

Result of S5 (17 Nov ~10:29 PT): **still stuck loading after the Deku Tree door** (Kokiri Forest loads fine; no error in
the log). So `FilePath` alone wasn't it (S5 keeps it: the game's own files all match). The other untested difference
from B60 (which works): **the door**. B60 left the Kokiri Forest door alone; S1–S5 also gave it Hyrule Field's generic
arrival event (`Dm_SY_BancChangeArrive`) and dropped the Deku Tree's `InitEventName` (`InsideTheDekuTree_Arrive`) /
`InitEventFlag` (`HavePlayedEvent.Dm_Deku_0000`). The door's own values are `NextEventName`
`Dm_SY_BancChangeArrive_InsideTheDekuTree_01`, `FirstEventName` `Dm_SY_BancChangeGo`, `NextStartPosName` `Entrance`.
Also still missing for a new scene: a row in RSDB `DungeonParam` (24 rows, keyed by scene name, sorted; the Deku Tree's
lists its rooms A–M). Not checked as causes: `Game/MapMenuInfo` (`BancName` lists, pause map) and the location names in
`Mals` (text).

| Test | What it changes | Tells us |
|---|---|---|
| S6. S5 with the door's own arrival event | The door keeps all its Deku Tree values except `NextBancParamNameChild` / `Adult` (`new_scene(door_event="keep")`, the default now; `"generic"` was S1–S5) | Loads: the generic arrival event was what waited |
| S7. S6 with a `DungeonParam` row | Plus a copy of the Deku Tree's RSDB `DungeonParam` row under `KaeGae_Minecraft` (`new_scene(dungeon_row=True)`). Only tried if S6 stalls | Loads: dungeon scenes need their row |
| S4 (rebuilt) | The vanilla Deku Tree as `KaeGae_DekuCopy`, with S6's door. Only tried if S7 stalls too | Loads: the problem is in the map build on top of a new scene. Stalls: new scene names need something more |

Result of S6 (17 Nov ~10:43 PT): **still stuck after the door** ("some of the game's functions still work": the game
runs on). Log: `player: found Link` at 77 s in Kokiri Forest, then nothing until the shutdown; no error. So the door's
event wasn't it either. S7 and S4 not tried yet.

Checked without a test: every file path `main` builds from a scene name (the `%s` patterns among its strings:
`Bake/Light/%s.bklight`, `Bake/Scene/%s_%%s_%%u_%%u.bkres`, `Bake/Probe/Scene/%s` + `X%u_Y%u_Z%u_%u.bkprb` /
`meta.bkprmb` / `resident.bkprcb`, `Banc/BancBasedResource/%s%s%s.byml`, `Game/BakeSceneLayerConfig/%s`,
`Phive/NavMesh/%s.%s.bphnm`, `Phive/StaticCompoundBody/%s/%s_X%d_Z%d.%s.bphsc` and `%s/%s.%s.bphsc`,
`Phive/VolumeStats/%s/%s_X%d_Z%d`, `PreComputedCulling/%s/Boxes.bbox`, `Foliage/Placement/%s/%s.%s.flnt`, ...): the new
scene has every one the Deku Tree has. (`Phive/StitchedNavMesh/` is Hyrule Field only; `Sound/Shape/` is per actor.)
**But `main` has the dungeon scene names built in**, as enum name lists (e.g. `None, InsideTheDekuTree, DodongoCavern,
InsideJabuJabuBelly, ForestTemple, ...` at `0x3eea746`, `0x3f0cef6`, `0x3f14ec9`; 33 of the 80 scene names appear as
strings in `main`, all the dungeons among them), and the new scene's settings still say it is a dungeon (`DungeonParam`
→ the Deku Tree's). 30 of the game's 80 scenes have no `DungeonParam` line (Hyrule Field among them).

| Test | What it changes | Tells us |
|---|---|---|
| S8. S6 without `DungeonParam` | Only the scene settings: the `DungeonParam` line removed (a plain non-dungeon scene) | Loads: the dungeon code didn't know the new name |

Results (17 Nov ~10:52–11:04 PT): **S8 stuck** like S6 (so not the `DungeonParam` line; S7 not tried). **S4 loads: the
vanilla Deku Tree under the new name `KaeGae_DekuCopy` works** ("that one loads deku tree fine"). So the game loads new
scene names, and the stall is in what the map build adds or removes on top. B60 has all of it under the Deku Tree's name
and works, so it's one of those changes *together with* a new name (a file or table keyed by scene name that the build
removes, or that a setting makes the game look for). Not found by reading: 41 of 80 scenes have no `LowTree` /
`Ornament` foliage files (the S builds drop them), `main` also looks palettes up by name
(`Work/WorldMgr/ResEnvPalette/%s...`, `ResEnvPaletteAreaUnique/%s`). Bisecting from S4 instead, without the map
(`test_scene_step()`):

| Test | What it changes | Tells us |
|---|---|---|
| S9. S4 with S6's scene settings | Only the scene settings: `IsEnableBakeLight` off, no `FoliageScene`, `HeightMapParam`, `OptimizeChangeBancUnits`, Hyrule Field's `WorldParam` (`S6_BANC`) | Stuck: one of these lines (then split them) |
| S10. S9 with S6's clean slate | Plus the placement emptied to its spawn points, the empty compound, tiny volume stats, the widened AABB, no foliage files | Stuck: one of these (S9 loads). Loads: the map's own actors in a new scene |

Results (17 Nov ~11:10–11:15 PT): **S9 loads** (very dark: baked light off with the full Deku Tree level still there) and
**S10 loads** (Link falls forever, as expected with the empty compound and no map; noclip works). So S6's settings and
its clean slate both work under a new name: the stall comes from **the map's own actors**. Split them
(`test_b40(only="hosts" / "blocks")`):

| Test | What it changes | Tells us |
|---|---|---|
| S11. S10 with the map's hosts | S6 without the 9,397 stone blocks (the 14 `KaeGae_MapHost_*` flags, their packs and RSDB rows): invisible but solid | Stuck: the hosts |
| S12. S10 with the map's blocks | S6 without the hosts (no host packs, no `ActorInfo` / `GameActorInfo` copies): visible, not solid | Stuck: the blocks |

**What "stuck loading" really was (KaboWabo, 17 Nov ~11:24–11:29 PT):** the scenes *do* load. With noclip Link moves
around in S10 and S11 (and probably in S3–S8 too), but **the game's UI never appears**: the pause menu works but isn't
drawn, no HUD. That's what looked like an endless load. The log shows nothing either way (Core finds Link once per
run). S11 looked the same as S10 (dark, empty: its hosts are invisible collision). So the test criterion is now "does
the game's UI show". S4 / S9 (full Deku Tree placement under the new name) loaded "fine"; S10 (plus the clean slate) is
the first without UI; B60 (the clean slate under the Deku Tree's name) had its HUD (the Deku Tree's dungeon map in the
corner). So one clean-slate part breaks the UI only under a new name. Split (`test_scene_step(clean={...})`):

| Test | What it changes | Tells us |
|---|---|---|
| S13. S9 with the emptied placement | Only the placement emptied to its spawn points (groups cleared) | No UI: something in the level's placement is needed under a new name |
| S14. S9 with the rest of the clean slate | The empty compound, tiny volume stats, widened AABB, no foliage files | No UI: one of these |

More from KaboWabo (~11:33 PT): in every test without the UI, **Link can't be controlled either** (only moved by noclip).
Hidden UI plus no control is what the game does during a scene-change event, so the door's arrival event most likely
never finishes. **S13 result (~11:36 PT): no control, no UI.** So it's in the emptied placement: something in the Deku
Tree's placement lets the arrival finish under a new name (under the Deku Tree's own name, B60's emptied placement was
fine). The placement's 475 static actors are 103 types; split by kind (`test_scene_step(keep=)`, groups still cleared):

| Test | What it changes | Tells us |
|---|---|---|
| S15. S13 with the system actors back | 303 static / 96 dynamic actors: areas, anchors, event requests (`EventRequestActor`, `EventProxyRequestActor`), the exit door (`FieldAndDungeonEntranceEventRequestActor`), `ChangeBancBeforehandAnchor`, `AbilityChangeAreaForSceneChange`, dungeon room / location areas, air walls, ... (`is_system_actor()`) | Works: one of these (then split them) |
| S16. S13 with the level actors back | The other 174 static / 1,523 dynamic: geometry, terrain chunks, enemies, objects, plants, effects | Works: one of these |

**S15 result (17 Nov ~11:43 PT): works** ("level loads and i can control link"). So one of the system actors is what the
arrival needs under a new name. Near the entrance spawn (`Entrance`, 0.2 / 101 / 14.7): `DungeonRoomIdAnchor` (1.8 m),
`DungeonRoomArea` (2 m), `MapIconEntranceAnchor` (2.9 m), `DestinationAnchor` `HorsePos` and **`ChangeBancBeforehandAnchor`**
(4.1 m; its name 先読みの基準座標となるアンカー = "the anchor used as the reference point for preloading", `IsUseFailSafe: true`
like the preload entries of `OptimizeChangeBancUnits`), `DestinationAnchor` `FieldDungeonEntranceGo` (9 m), the exit door
`FieldAndDungeonEntranceEventRequestActor` `Entrance` (11 m).

| Test | What it changes | Tells us |
|---|---|---|
| S17. S13 with the preload anchor | Only `ChangeBancBeforehandAnchor` kept (1 static + 1 dynamic) | Works: a new scene needs it |
| S18. S13 with the room actors | Only `DungeonRoomIdAnchor`, `DungeonRoomArea`, `DungeonRoomCenterAnchor` | Works: one of these |
| S19. S13 with the entrance anchors and exit door | Only `DestinationAnchor`, `MapIconEntranceAnchor`, `FieldAndDungeonEntranceEventRequestActor` | Works: one of these |
| S20. S6 with the preload anchor | The Minecraft map (S6) plus the Deku Tree's `ChangeBancBeforehandAnchor`s (`test_b40(keep_gyaml=)`) | Only if S17 works: the map behind the door |

**S17 result (17 Nov ~12:21 PT): stuck** (no control, no UI): not the preload anchor. Next: S18 (installed). S21 / S22
are prebuilt so the map can be tried right after S18 or S19 works:

| Test | What it changes | Tells us |
|---|---|---|
| S21. S6 with the room actors | The Minecraft map plus the Deku Tree's `DungeonRoomIdAnchor`, `DungeonRoomArea`, `DungeonRoomCenterAnchor` | If S18 works: the map behind the door |
| S22. S6 with the entrance anchors and exit door | The map plus the Deku Tree's `DestinationAnchor`s, `MapIconEntranceAnchor`, `FieldAndDungeonEntranceEventRequestActor` | If S19 works: the map behind the door |

**S18 result (~12:26 PT): stuck. S19 result (~12:31 PT): works** ("it loads properly"). So a new scene needs one of the
Deku Tree's entrance actors: the `DestinationAnchor`s (51; near the entrance `HorsePos`, `FieldDungeonEntranceGo`), the
`MapIconEntranceAnchor` or the exit door `FieldAndDungeonEntranceEventRequestActor` `Entrance` (11 m above the spawn).
The arrival flow `Event/EventFlow/Dm_SY_BancChangeArrive.bfevfl` has steps like `EventPlayerWarpToTargetActor` /
`EventWarpToTargetActor`: most likely the arrival looks for one of these by name and waits. (Why B60's emptied placement
under the Deku Tree's name didn't need them is still open.) **S22** (installed) = the Minecraft map with them. S23 /
S24 (the rest of S15's system actors) were built but aren't needed.

**S22 result (17 Nov ~12:38 PT): works.** ("Nice! it works.") The Minecraft map as its own scene `KaeGae_Minecraft`
behind the Deku Tree door, with control and UI; the real Deku Tree untouched. The recipe is in `docs/custom-maps.md`,
"Making a new scene". Summary of the new-scene tests:

| Test | Result | Learned |
|---|---|---|
| S1, S2 | crash `0x112b3a0` | new files need their originals' size table entries |
| S3 | no control / UI | (size entries fixed) |
| S5 | no control / UI | placement `FilePath` = `Banc.Main` (kept) |
| S6, S8 | no control / UI | not the door's event, not `DungeonParam` |
| S4 | works | the vanilla Deku Tree as a new scene: new names work |
| S9, S10 | work | S6's scene settings and clean slate are fine (no map) |
| S11 | no control / UI | (the map's hosts; "stuck" was really "no control, no UI", seen with noclip) |
| S13 | no control / UI | the emptied placement is the cause |
| S15 / S16 | S15 works | a system actor of the placement |
| S17, S18 | no control / UI | not the preload anchor, not the room actors |
| S19 | works | the entrance anchors / exit door |
| S22 | **works** | the map + the Deku Tree's `DestinationAnchor`s, `MapIconEntranceAnchor`, exit door |

Not tried / not needed: S7, S12, S14, S16, S20, S21, S23, S24 (all in `load\.kaegae-staging\map-tests\round1b\`).

## The looks: Minecraft block textures (S25–S28, 17 Nov 2026)

All four are S22 (the map as scene `KaeGae_Minecraft`, same hosts and collision) with only the visible blocks changed.
Every visible block is now a copy of the stone block `Land_SacredForest_Prop_A_06` under a new actor name
`KaeGae_MC_00` .. `_44`: its pack (all five files renamed, refs to match), RSDB `ActorInfo` / `GameActorInfo` rows (the
stone's, with `ModelProjectName` = the copy's), a `.bfres` copy with its file name and Alb texture name patched in place
(`KaeGae_Minecraft_Blk_<nnn>.Land_SacredForest_Prop_A_06.bfres`), and its own Alb `.bntx`
(`KaeGae_Minecraft_Block_<nnnnn>_Alb`, same length as `Stone_SacredForest_Prop_A_06_Alb`; the texture dictionary
stays valid since only the radix bit of the last character counts and that's `b` in both). Block 0 is the **control**:
the stone's own pixels, only the names changed. Blocks 1–44 are the map's 44 materials, most used first (Stone,
Grass_Block, Dirt, Acacia_Leaves, ...). Nrm / Rgh stay the stone's. Textures: `make_looks.py` (how: its docstring and
`docs/custom-maps.md` "Looks"). Each test also has a floating **palette** in front of the entrance, 3 m above the
ground: the original stone first, then blocks 0, 1, 2, ... in rows of 10 (S25: only the stone and block 0).

| Test | Blocks | Count | Tells us |
|---|---|---|---|
| S25. control, the renamed stone with its own pixels | B40's blocks (one per merged collision box), all block 0 | 9,397 | Looks like S22 (stone): renamed copies work, the texture names are right. Plain grey / missing blocks: a copy problem, not the pixels |
| S26. Minecraft textures on the merged blocks | the same 9,397 boxes, each its most common material's block | 9,397 | New pixels work (stretched over each merged box) |
| S27. one textured block per visible Minecraft block | one 1 m block per visible cell (a solid cell with an open side; under the map counts as closed) | 65,812 | The real Minecraft look; whether the game takes ~7 times B41's block count |
| S28. S27 within 60 m of the map's spawn column | S27's blocks within 60 cells (horizontally) of the spawn column | 25,425 | A middle step for the block count, if S27 fails |

What to check in each: does it load (Link can move, the pause menu opens, the HUD shows), how the blocks look (the
palette's blocks next to the original stone), frame rate / pop-in, and in the emulator log anything new. The stone
actor's `ActorInfo` row has `CalcRadius` 20, `DisplayRadius` 80, `LoadRadius` 180 and `UsePreActorRenderer`, so far
blocks are most likely drawn without being full actors; that's what S27 / S28 test.

Installed: S25 (`load\0400486024DEC000\`); S26–S28 in `load\.kaegae-staging\map-tests\round1b\`, S22 moved there too.

**S25 result (17 Nov ~13:14 PT): works** ("yep, it works"): the map looks like S22 (stone), the palette's original stone
and block 0 look the same. So a renamed copy of the block (new actor, `.bfres` file name and Alb name patched, the
`.bntx` renamed) works. Next: **S26** (installed ~13:15 PT; S25 moved to `round1b\`).

**S26 result (17 Nov, reported ~15:29 PT): works** ("the map works great"): the Minecraft textures show on the merged
blocks (stretched, as expected); the log of that run has no crash. So the new pixels work (ASTC 8x5 encode, swizzle of
all 10 mips, the 44 copies). Next: **S27** (installed ~15:30 PT; S26 moved to `round1b\`).

**Shadows, for later tests:** the scenes' `GameBancParam` has a `SceneShadowSetting`. Hyrule Field (child):
`IsEnableScreenSpaceShadow: true`, `IsIncludeFarActorToShadow: true`, `ShadowSoftnessRatio` 0.15, cloud shadow fade
50 m. Kokiri Forest (child): static depth shadows (`IsEnableStaticDepthShadow`, `IsEnableStaticLocalDepthShadow`,
`IsEnableFadeStaticDepthShadow`) in a manual box (`ManualStaticDepthShadowAABBMax` 140 / 160 / 70 ...,
`IsEnableAutoCalcSDShadowAABB: false`). The Deku Tree: only `UseJitteringAndBlurAtLDS: true`, so the map scene has
none of these. Outdoor scenes also have `EnableLODSetting`, `VrsType`, `StaticCompoundMode`, `VolumeStatsMode`,
`TerrainSceneName`, `IsPlayerCameraWideMode`, which the Deku Tree lacks.

## Building

```
python3 mods/custom-map-tests/build_tests.py --romfs <folder> --glb <map.glb> --out <dir>
```

`--romfs` is a folder with these files from your own dump, at their romfs paths: `Pack/ZsDic.pack.zs`, the resource
size table, `Banc/KokiriForest/KokiriForest_Child_Static.bcett.byml.zs`, both `Banc/InsideTheDekuTree/` placement
files, `Pack/Actor/Land_Deku_TreeRoot_B_01.pack.zs`, `Pack/Actor/Obj_TBox_A_02.pack.zs`, `Pack/Actor/Obj_TBox_A_01.pack.zs`
and `RSDB/ActorInfo.Product.111.rstbl.byml.zs`. Needs `pip install zstandard trimesh scipy numpy`.

The looks tests (S25–S28) also need `Pack/Actor/Land_SacredForest_Prop_A_06.pack.zs`,
`Model/Land_SacredForest_Prop_A.Land_SacredForest_Prop_A_06.bfres.zs` and `Tex/Stone_SacredForest_Prop_A_06_Alb.bntx.zs`
in `--romfs`, and the textures made first (ARM's `astcenc`, built from https://github.com/ARM-software/astc-encoder):

```
python3 mods/custom-map-tests/make_looks.py --glb <map.glb> --bfres <stone .bfres, unpacked> --alb <stone Alb .bntx, unpacked> --astcenc <astcenc> --out <assets>
python3 mods/custom-map-tests/build_tests.py --romfs <folder> --glb <map.glb> --out <dir> --looks <assets>
```

Test map used: "High quality minecraft world" by SOLDMARS (Sketchfab), CC-BY-4.0. It isn't included here.

## Credits

KaboWabo/Kabosune (me :3), AI assistance (Claude Opus 5.5).
