# Adventure Log

The game's own play log, shown in the game. Game version 1.1.1 keeps a rolling log of what you do
(1,024 entries: areas entered, things picked up, talk, songs learned, fights...) for Nintendo's
Zelda Notes app, even with Zelda Notes never set up and offline. This mod reads that log and shows it
on screen: counts by kind for this session and the whole log, and the newest entries by name.

Status: **0.2.0, test build.** 0.1.0 worked in the game (19 November 2026, Fritchii, Core 0.9.0), and
its test round named most kinds of entry; the panel now counts enemies defeated, times hurt and
hearts lost, Game Overs, areas and rooms entered, chests opened, things picked up, lines of talk,
items used, ocarina played and songs learned, and shows Link's life. A few kinds are still guesses
(marked `?`); with "Write new entries to the log" on, every new entry also goes to the emulator's
log. Jumps, rolls and sword swings aren't in the game's log.

- Needs KaeGae Core 0.8 or newer. **Game version 1.1.1 only** (1.0.0 has no play log: the mod does
  nothing there).
- Settings in the Mods menu (- and + together): show on screen, a binding to show / hide it, text
  size, how many of the newest entries to show, the clock's hours from UTC (-8 = US Pacific in
  winter), writing new entries to the log.
- Reads the log at its 1.1.1 address for now (`kae_game_base`); it moves to a name in Core's symbol
  pack with the next Core release.

How the log works: [`docs/zelda-notes.md`](../../docs/zelda-notes.md).

Credits: KaboWabo/Kabosune (me :3), AI assistance (Claude Opus 5.5).
