# Super Sloperina

Practice tools for the Ocarina of Time remake, running on [Kaepora Core](../../api/README.md).
The idea and the name come from [sloperinaGZ](https://github.com/PracticeROM/sloperina) by
PracticeROM, a gz-style practice menu for this game. This is a new mod written from scratch for
Kaepora, not a copy of their code (theirs is GPL-3.0, this repository is MIT); what was learned
from their write-ups is in [docs/sloperina-findings.md](../../docs/sloperina-findings.md).

**Status, 10 November 2026: version 0.1.0, a first slice. It passes its test in an emulated game
with a stand-in Link. It has not run in the real game yet.** Game version 1.1.1 only.

## What it does

| Tool | How |
|---|---|
| Input display | The buttons the controller reports, lit while held, and both sticks' values. Bottom left. |
| Position watch | Link's position and speed, under the input display. |
| Save position | L + D-pad Left. |
| Load position | L + D-pad Right: puts Link back where he was saved. |
| Levitate | Hold L + D-pad Up: lifts Link, 10 cm a frame. |

Every tool and button combination is on the mod's page in the Mods menu (- and + together):
the displays can be switched off, the text made larger or smaller, the combinations changed, and
the lift speed set. A combination that the mod acts on isn't passed on to the game. Settings are
not saved between runs yet (that comes with Kaepora Core).

## Install

Super Sloperina needs Kaepora Core. `python3 tools/kaemod.py mods/super-sloperina` builds a zip
with Core and the mod; copy its folder into the emulator's mod folder for the game. Turn off
sloperinaGZ itself while using it: both hook the game's drawing.

## How it works

One C file, [sloperina.c](sloperina.c), written against the public API ([kaepora.h](../../api/include/kaepora.h)):
`kae_on_input` for the controller, `kae_on_actor_move` to find Link and move him with the game's own
ChangePosition (the function FPV Drone and Mouse Grab use), `kae_draw_text` for the display, and
`kae_settings` for its page. Game addresses come from Core's symbol pack by name. The walk from
an actor to Link's player object and character controller still has its offsets written out in
the mod; that belongs in Core as one function every mod can call.

## What sloperinaGZ has that this doesn't yet

Its menu drawn with the game's own font and pictures, warps, inventory and flag editors, a
collision viewer, health bars, frame advance, savestates of more than position, timers and
trainers. Each needs game functions that are not in Core's symbol pack yet or not tested by us.

## Credits

- KaboWabo/Kabosune (me :3): idea, direction, in-game testing
- AI assistance (Claude Fable 5.2)
- PracticeROM's sloperinaGZ: the model for what a practice mod for this game should do
