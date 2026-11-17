# Zelda Notes: the play log the game keeps

Nintendo's Zelda Notes (in the Nintendo Switch App on a phone) has four parts for this game:
Today's Record (what you did that day, with stats), Gossip Quest (find the place in a hint picture),
Play Ocarina (a touchscreen ocarina) and a quiz (extra tries cost rupees). All of it is online. But
the data behind Today's Record is gathered by the game itself, offline, whether Zelda Notes is set up
or not. This page says where it is and what is in it (checked 17 November 2026, game 1.1.1).
**1.0.0 has none of it**: only the setup screen.

Mod on it: [`mods/adventure-log`](../mods/adventure-log). Save reader: `tools/zeldanotes_log.py`.

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

From one save, so the ones with `?` are guesses (a test that does one thing at a time will name
them; Adventure Log 0.1.0 writes every new entry to the emulator's log for that):

| Kind | Seems to be | name1, name2 | values |
|---|---|---|---|
| 2 | an enemy hit Link? | enemy, Link | |
| 3 | Link hit something? | Link, target | |
| 4 | Z-target? | target, or none | |
| 5 | cucco flight? | | many a second while gliding with a cucco |
| 11 | picked up | the object (rupee, heart, Heart Piece) | |
| 14 | a line of talk | who | message hash |
| 16 | an event starts (no name: it ended) | event | |
| 23 / 24 | lift / throw or put down | the thing (cucco, rock) | |
| 25 | area change | from scene, to scene | two packed positions |
| 27 | equip change | old, new item | |
| 28 | was hit by? | target, attacker | |
| 30 | learned a song | `Item_Melody_*` | |
| 33 | an object gone? | -, the object | |
| 37 | defeated? | the enemy | |
| 38 | dropped an item | the enemy or object, the item | |
| 34 | always just before 25 | | |
| 26 | just after arriving in an area | | 0 to 5 |

Kinds 5, 7, 8, 9, 10, 17, 22, 29, 36 and 39 also appear; not known yet.

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
