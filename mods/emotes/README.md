# Emotes

Hold a button (L by default) to open a list of Link's emotes, pick one, and he plays it. A core
mod: install [KaeGae Core](../../api/README.md) first (Core 0.6 or newer).

**0.1.0 is a test build.** Which emotes play cleanly outside cutscenes isn't known yet: some
may do nothing, freeze Link for a moment, or be cut off when he moves.

## Using it

- **Hold L** (about a sixth of a second) and the list opens on the left.
- **Up / down** (D-pad or left stick) to choose, **A** to play, **B** or letting go of L to close.
- **A quick tap of L** still does what L normally does; the game gets it a few frames late.
- While the list is open the game doesn't see A, B, the D-pad or the left stick, so Link stands still.

## Settings (Mods menu, - and +)

| Setting | Default | What it does |
|---|---|---|
| Emote list (hold) | L | The button (or combination) that opens the list |
| Hide the button from the game | While the list is open | **Off:** the game always gets the button too. **While the list is open:** the game doesn't get it while you hold it (a tap is handed back). **Always:** the game never gets it. That takes away the button's own use (shield, targeting) |
| Tap goes to the game | On | With "While the list is open": a short tap still does the button's own thing. Off: the list opens at once and a tap does nothing |
| Hold time (frames) | 10 | How long to hold before the list opens (60 frames = 1 second) |
| Voice | On | Link's voice with the emotes that have one |
| List rows | 10 | How many emotes the list shows at once |
| Body slot (test) | 0 | Which animation slot the emote plays in. For testing which one plays a whole-body animation |
| Debug log | On | Logs each emote played, for testing |

## The emotes

Stop, Wave, Nod (yes), Shake head (no), Wonder, Talking, Surprised, Surprised (small), Turn around
surprised, Notice, Caution, Look around, Stretch, Flinch, Unsteady, Off balance, Step back, Item get,
Item get (smile), Show item, Show item (wrong), Bottle pose, Drink, Read letter, Ocarina, Plant beans,
Backflip, Sidestep.

They are commands of Link's animation graph (`AS/Player_Child.root.asb`, `AS/Player_Adult.root.asb`;
both have the same 471 commands), played through the game's own function for it, as Mouse Grab plays
Link's face. The idle animations (sword spin, shield spin, tightening his belt...) sit inside his
standing animation and aren't reachable by name yet.

## Limits

- **Game 1.1.1 only:** it calls the game's animation function by its address. A Core function for
  playing animations on Link would make it work on 1.0 too.

## Credits

- KaboWabo/Kabosune (me :3)
- AI assistance (Claude Opus 5.5)
