# Adventure Log

The game's own play log, shown in the game. Game version 1.1.1 keeps a rolling log of what you do
(1,024 entries: areas entered, things picked up, talk, songs played, fights...) for Nintendo's
Zelda Notes app, even with Zelda Notes never set up and offline. This mod reads that log and shows it
on screen, together with the game's own totals of jumps, rolls and sword swings.

Status: **0.4.0, test build** (0.3.1 is the release: `releases/adventure-log.zip`). 0.3.0 works in
the game (19 November 2026, Fritchii v6.2, KaeGae Core 0.9.0, game 1.1.1).

Two panels (top left; pick one on the Mods menu page, "Panel"):

**Simple** (the default from 0.4.0):

- The area Link is in.
- His hearts, rupees, Gold Skulltulas and heart pieces (the game's own numbers).
- **Today:** enemies defeated, chests opened, areas entered, songs played.
- **Session:** jumps, rolls, sword swings, distance on foot and time played since the game started.
- **All time:** the game's own totals of jumps, rolls, sword swings and kilometres on foot, since the
  file began. They move the moment Link jumps, rolls, swings or runs.
- The newest highlights: enemies defeated, things picked up, areas entered, songs played, chests,
  saves, Game Overs.

**Detailed:** every count for this session and the whole log, the totals with distance run and
walked separately, Link's life, and the newest entries of the log by name (12,409 of the game's
actor, area and event names).

With "Write new entries to the log" on (the default), every new entry and every change of the totals
also goes to the emulator's log. A few kinds of entry are still guesses (marked `?`).

- Needs KaeGae Core 0.8 or newer. **Game version 1.1.1 only** (1.0.0 has no play log: the mod does
  nothing there).
- Settings in the Mods menu (- and + together): show on screen, a binding to show / hide it, text
  size, how many of the newest entries to show, the clock's hours from UTC (-8 = US Pacific in
  winter), writing new entries to the log.
- Reads the log at its 1.1.1 address for now (`kae_game_base`); it moves to a name in Core's symbol
  pack with the next Core release.

How the log and the totals work: [`docs/zelda-notes.md`](../../docs/zelda-notes.md).

Credits: KaboWabo/Kabosune (me :3), AI assistance (Claude Opus 5.5).
