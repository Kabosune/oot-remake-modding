# Sloped Up Sloperina

Practice tools for the Ocarina of Time remake, running on [KaeGae Core](../../api/README.md).
The idea and the name come from [sloperinaGZ](https://github.com/PracticeROM/sloperina) by
PracticeROM, a gz-style practice menu for this game. This is a new mod written from scratch for
KaeGae, not a copy of their code (theirs is GPL-3.0, this repository is MIT); what was learned
from their write-ups is in [docs/sloperina-findings.md](../../docs/sloperina-findings.md).

**Status, 11 November 2026: version 0.2.0. 0.1.0 ran in the real game (Fritchii v5.8.3): everything
worked except that levitate struggled against gravity. 0.2.0 has the fix for that and needs KaeGae
Core 0.5.1 (0.5 itself could hang the game); it works in the real game too (11 November, Fritchii
v5.8.4): Link rises steadily while levitating.** Game version 1.1.1 only.

## What it does

| Tool | How |
|---|---|
| Input display | The buttons the controller reports, lit while held, and both sticks' values. Bottom left. |
| Position watch | Link's position and speed, under the input display. |
| Save position | L + D-pad Left. |
| Load position | L + D-pad Right: puts Link back where he was saved. |
| Levitate | Hold L + D-pad Up: lifts Link, 10 cm a frame, and takes away his falling speed while held (new in 0.2.0: in 0.1.0 gravity kept building up against the lift). He can still take fall damage when let go high up |

Every tool and button combination is on the mod's page in the Mods menu (- and + together):
the displays can be switched off, the text made larger or smaller, the combinations changed, and
the lift speed set. A combination that the mod acts on isn't passed on to the game. Settings are
not saved between runs yet (that comes with KaeGae Core).

## Install

Sloped Up Sloperina needs KaeGae Core, installed once from its own download. Install both:

```
python3 tools/kaegae.py install releases/kaegae-core.zip releases/sloped-up-sloperina.zip
```

or copy both zips' folders into the emulator's mod folder for the game by hand. If another mod
already uses `subsdk2`, the tool moves this one to a free slot; by hand, rename
`exefs/subsdk2` to a free `subsdk3` ... `subsdk8`. Turn off sloperinaGZ itself while using it:
both hook the game's drawing. (`python3 tools/kaemod.py mods/sloped-up-sloperina` still builds the
older one-folder zip with Core inside.)

## How it works

One C file, [sloperina.c](sloperina.c), written against the public API ([kaegae.h](../../api/include/kaegae.h)):
`kae_on_input` for the controller, `kae_on_player_move` for Link's movement update, `kae_player_move`
to put him somewhere (the game's own ChangePosition, the function FPV Drone and Mouse Grab use),
`kae_player_velocity` / `kae_player_set_velocity` to stop his fall, `kae_draw_text` for the display,
and `kae_settings` for its page. There is no game address or offset in the mod: finding Link is
Core's job since API 0.5.

## What sloperinaGZ has that this doesn't yet

Its menu drawn with the game's own font and pictures, warps, inventory and flag editors, a
collision viewer, health bars, frame advance, savestates of more than position, timers and
trainers. Each needs game functions that are not in Core's symbol pack yet or not tested by us.

## Credits

- KaboWabo/Kabosune (me :3): idea, direction, in-game testing
- AI assistance (Claude Fable 5.2)
- PracticeROM's sloperinaGZ: the model for what a practice mod for this game should do
