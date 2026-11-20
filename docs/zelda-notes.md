# Zelda Notes: the play log the game keeps

Nintendo's Zelda Notes (in the Nintendo Switch App on a phone) has four parts for this game:
Today's Record (what you did that day, with stats), Gossip Quest (find the place in a hint picture),
Play Ocarina (a touchscreen ocarina) and a quiz (extra tries cost rupees). All of it is online. But
the data behind Today's Record is gathered by the game itself, offline, whether Zelda Notes is set up
or not. This page says where it is and what is in it (checked 17 November 2026, game 1.1.1).
**1.0.0 has none of it**: only the setup screen.

Mod on it: [`mods/adventure-log`](../mods/adventure-log). Save reader: `tools/zeldanotes_log.py`.

When the game starts the recorder is empty; loading a file fills it from the save at once (Adventure
Log saw 0 entries, then 163 in one frame, 19 Nov).

## In memory: the recorder

- **main `0x4E6B718` (1.1.1, `.bss`) holds a pointer to the recorder**; 0 until the game made it.
  About 30 functions read it to add entries.
- **recorder + `0x0000`: 1,024 entries of 24 bytes**, `{u32 time, u32 kind, u32 name1, u32 name2, s32 value1, s32 value2}`.
- **recorder + `0x6000`: u32 next slot, u32 count** (up to 1,024). Adding an entry
  (`0xE46590`, `(recorder, const Entry*)`) writes the slot, moves the next slot on (wrapping at
  1,024), raises the count to at most 1,024, and also queues the entry at recorder + `0xB420`
  (a second queue: pointer +8, capacity +0x10, start +0x14, count +0x18; most likely what is sent).
- recorder + `0x7418`: the position log, 1,024 x 16 bytes, its next slot / count after it.
- Each kind has its own small function that fills an entry and calls the add function, e.g.
  `0x323EFE0` makes kind 2 from two actor name strings and two values; `0xE46400` makes kind 25
  (area change) from two scene names and two positions.
- `0x587E80` copies both logs into the save (GameData Binary fields, below); `0x10A4EC0` reads
  them back.
- **Times** are seconds since 1 January 2026, UTC (the game takes the time now minus that date).

## In the save: `option.sav`

`option.sav` (one per user, next to the `slot_NN` folders) has both logs as Binary fields:
events `0x5392E233` (24,576 bytes) and positions `0x3C99C416` (16,384 bytes), with their next slot
and count as Int fields (`0x25418E68` / `0xE110CEB6`, `0x9B03CB4F` / `0xC2A3144C`). A Binary field's
table value is the offset of `[u32 size][bytes]`. The save format itself is in
[`game-versions.md`](game-versions.md) ("What 1.1.1 adds for Zelda Notes"). In a save played for a
day and a half the 1,024 events covered about 34 hours: the app has to pick them up often.

## Names

- **Actor names are CRC32** of the actor name (`Enemy_Stalchild`, `Player_Child`, `Obj_Rupee_Green`,
  `Weapon_Range_SlingShot`), the names of the actor packs in `Pack/Actor/`.
- **Scene and event names are MurmurHash3 (seed 0)** (`HyruleField_Child`, `Dm_SY_Ocarina`): the
  scenes in `Banc/`, the event flows in `Event/EventFlow/`.
- With those, 79 of the 101 names in that save resolved; the rest are mostly NPCs' talk targets.

## Kinds of entry

Named from two saves and a test round (19 November 2026, Fire Temple, with Adventure Log writing
each new entry to the emulator's log while KaboWabo did one thing at a time). **Seen** = matched to
something done in the test; **likely** = fits every case seen; `?` = not known.

| Kind | What | name1, name2 | values | |
|---|---|---|---|---|
| 1 | Link hurt | what hurt him, - | -, damage (quarter hearts) | seen (life drops by value2 right after) |
| 2 | Link defeated | what did it, Link | | seen (Game Over follows) |
| 3 | Link defeated an enemy | Link, the enemy | 10, ? | seen (its drop follows) |
| 4 | Z-target | the target; none = let go | | seen |
| 5 | an item readied | | the item's kind, 1 | likely (before shooting) |
| 8 | a sword swing | | | seen (5 swings, 5 entries) |
| 7 | an item used | | the item's kind (3 bomb, 6 bow, 8 hookshot), 1 | likely |
| 11 | picked up | the thing (rupee, heart, small key) | | seen |
| 14 | a line of talk | who | the message | seen |
| 16 | an event; no name = it ended | the event | | seen. Opening a chest is `Dm_SY_Treasurebox` / `Dm_SY_TreasureboxSmall`, the ocarina `Dm_SY_Ocarina`, falling into lava or a pit `DmF_SY_FallDown`, Game Over `DmF_SY_GameOver` |
| 17 | a file loaded | | value1 = the slot | seen |
| 23 / 24 | lift / throw or put down | the thing (cucco, rock, bomb) | | seen |
| 25 | area change | from, to (scene) | the two positions | seen |
| 26 | the game saved | | value1 = the slot (0 to 5) | seen (the same second the slot's file was written) |
| 27 | equip change | old, new | the slot (0 sword, 4 tunic, 6 ocarina?, 8 the item button) | seen |
| 28 | an attack landed | the target, the attacker | ?, ? | seen (arrow on a Keese, bomb on a cracked wall) |
| 30 | learned a song | `Item_Melody_*` | | seen |
| 32 | came into play | enemies as a room starts, arrows as they're shot | | likely |
| 33 | removed | -, the thing (a chain lock opened, a heart taken, a wall blown up, a bomb gone) | ?, ? | likely |
| 34 | room change | | old and new floor / room code (`0x7F7F` outside, `0x80xx` in a dungeon) | likely |
| 37 | Link hurt by the world | `internal` (falls, lava) or what holds him (ReDead) | ?, damage | likely |
| 38 | dropped an item | who or what dropped it, the item | | seen |
| 39 | life and magic | | `max << 16 \| life` in quarter hearts; the same for magic (240 = full) | seen (a heart: +4; a fall: -4; Game Over at 0) |

**Not in the log:** jumps and rolls (their totals are in the save: next section). Kinds 9, 10, 22,
29, 36 appear in older logs; not known yet.

Quarter hearts and magic 240 agree with the save keys `PlayerStatus.MaxLife` (hearts x 4) and
`PlayerStatus.MPMax` (240 with magic), as [Hyrule Tracker](https://github.com/jv-prado/hyrule-tracker)
(MIT, a desktop tracker that reads this game's saves and memory) maps them.

## Totals in the save: jumps, swings, rolls (19 November 2026)

Jumps and rolls aren't in the play log, but the game counts them in each slot's `progress.sav`, as
**Int64** fields (GameData type 22: the table value is the offset of an `s64`). Found by a diff: one
save before and one after KaboWabo jumped 4 times, swung the sword 5 times and rolled 6 times, and
nothing else, in the same slot. Names unknown (no string in `main` hashes to them):

| Field (MurmurHash3) | Changed by | Before → after | What |
|---|---|---|---|
| `0xA6454431` | +4 | 2,152 → 2,156 | **jumps** |
| `0x2A24450A` | +5 | 1,233 → 1,238 | **sword swings** (also logged one by one: kind 8) |
| `0x4AC3FF5D` | +6 | 1,285 → 1,291 | **rolls** |
| `0x3EEAFADD` | +10 | 61,987 → 61,997 | ? (maybe distance) |
| `0xCE97845E` | +25 | 53,942 → 53,967 | ? (maybe distance) |
| `0xE53EB6D1`, `0xE573F564` (UInt) | +39 each | | likely play time in seconds |
| `0x3F8D9D86` (UInt) | +34 | | ? |
| `0xEF10B80F` (UInt64) | +2,062 | | ? |

Also kinds of the log named by that run: **8 = a sword swing** (5 entries, one a swing), **17 = a file
loaded** and **26 = the game saved**, both with the slot number as value1 (26's value 1 at the second
`slot_01/progress.sav` was written). These totals are the game's own, so they are presumably what
`jump_count_total`, `sword_swing_count_total` and `roll_count_total` send to the app.

## Positions

16 bytes each: `{u32 time, u32 packed position, u32 scene (MurmurHash3), u32 floor / room}`, about
one a second while Link moves. The position is in whole metres: x and z each clamped to
-1000..1000 and stored + 1000 in 11 bits, the height clamped to -500..500 and stored + 500 in the top
10 bits (from the code that packs it). Which low field is x and which z is assumed. Floor / room is
`0x807F` outdoors.

## What the app gets

The upload's keys are strings in `main`: totals (`playtime_total`, `defeat_total`, `death_times`,
`rupee_total`, `travel_distance_total`, `treasure_box_count`, `gold_skulltula_count`,
`npc_talked_count`, `fishing_total`, `mini_game_play_total`, `ocarina_play_total`,
`grass_cut_count_total`, `pots_broken_total`, `cucco_flight_distance_total`, `z_targeting_total`,
`jump_count_total`, `roll_count_total`, `gossip_stone_access_total`, `underwater_time_total`,
`stones_lifted_total`, `sword_swing_count_total`, `navi_talk_count_total`, ...), daily counts and per-item use
(`dins_fire`, `hookshot`, `bombchu`, ...). Where the totals are kept isn't found yet (probably
among the 1,104 fields 1.1.1 adds to each slot's `progress.sav`).

Online only, through the server: Gossip Quest (`gossip_research_actor_check_request` with
`action_id` / `is_bonus_checked`, `gossip_research_stone_action` with `zone_id`), the quiz's rupees
(AINB nodes `ExecuteZeldaNotesSendRupee` / `QueryZeldaNotesSendRupeeResult`, `player_current_rupee`),
and probably a destination the app can set (`target_position`, `next_position`, models
`Item_Navigation_StartingPoint` / `_DestinationPoint`) and songs sent from it (`ocarina_score`).
