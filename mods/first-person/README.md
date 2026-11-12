# First Person

Link to download: https://github.com/Kabosune/oot-remake-modding/blob/main/releases/first-person.zip

Press **R3** (click the right stick) to switch to Link's eyes. Press it again to switch back.

- Right stick looks around, left stick walks in the direction you look. The game's own camera
  rotation is kept, so its controls, Z-targeting and aim all still drive the view.
- Eye height is measured when you switch on (the game camera's look-at height above Link). It
  suits adult Link; for child Link, lower it with the height keys below. Switch on while standing
  normally, not while Z-targeting.
- The eye sits 0.15 m in front of Link's face, so his head stays behind the camera.
- When Link stops updating (pause, loading), the normal camera comes back by itself until he moves
  again.
- Starts off at every boot. Link is hidden while first person is on; `;` shows him.

### Eye height keys

| Key | |
|---|---|
| `,` | eye down 2 cm |
| `.` | eye up 2 cm |
| `/` | back to the measured height |
| `;` | show / hide Link (only while first person is on; hidden by default, remembered until the game restarts) |

Hiding uses the same switch the game's own `OneShotSetModelVisible` script command uses, and
puts back whatever the game had when you show him again or leave first person.

One step per press (no repeat while held), so you can count presses. The offset stays when you
switch first person off and on, until the game restarts. The keys need the emulator's keyboard
emulation on (Lichii / Eden: Controls → Advanced → Keyboard, or `keyboard_enabled=true` in
`qt-config.ini`).

Works on: Lichii / Fritchii (tested target). On a real Switch 2 (ns2jb-modloader) the normal build
boots but crashes when R3 is pressed; see [Real Switch 2](#real-switch-2-testing) below.

Compatible with: FPV Drone (when both are on, the drone's view wins), Ultrawide, the FPS mods, and Lichii's built-ins (no shared bytes, see
[memory-map](../../docs/memory-map.md)).

## Install

Copy `0400486024DEC000` from `releases/first-person.zip` into the emulator's `load` folder (Fritchii v5.8
and later: `%APPDATA%\fritchii\load\`; Lichii, Eden and older Fritchii: `%APPDATA%\eden\load\`) and restart
the game.

## Real Switch 2 (testing)

Reported in [issue #2](https://github.com/Kabosune/oot-remake-modding/issues/2) (11 November 2026):
with ns2jb-modloader the normal build boots and plays, but the game crashes as soon as R3 is
pressed. The patch loads and the controller is read (the press is seen), so the crash is in what
switching on starts. Two things only run from then on: the keyboard read for the eye height keys
(`nn::hid::GetKeyboardState`, which an emulator always answers but a console may not, with no
keyboard set up), and hiding Link. The first is the main suspect.

Two test builds, each leaving one of them out. They're already in ns2jb-modloader's layout: copy
the zip's `ns2jb-modloader` folder to the root of the microSD card.

| Zip | Leaves out | |
|---|---|---|
| [`first-person-no-keyboard.zip`](https://github.com/Kabosune/oot-remake-modding/blob/main/releases/hardware-test/first-person-no-keyboard.zip) | the keyboard read (no `,` `.` `/` `;`; Link always hidden) | try this first |
| [`first-person-no-keyboard-no-hide.zip`](https://github.com/Kabosune/oot-remake-modding/blob/main/releases/hardware-test/first-person-no-keyboard-no-hide.zip) | the keyboard read and hiding Link (he stays visible) | only if the first one still crashes |

Use one at a time, and take out the normal build's `exefs_patches` folder first: both patch the
same places. If the first one works, the fix is for the mod to switch the keyboard on itself (the
game imports `InitializeKeyboard`) or to leave the keys out of hardware builds.
`python3 tools/build_hw_tests.py` rebuilds these.

## Tune it

```
python mods/first-person/build.py --forward 0.25 --height-add 0.1
```

| Option | Default | |
|---|---|---|
| `--forward` | 0.15 | metres in front of the eyes |
| `--height-add` | 0 | added to the measured height |
| `--height-fixed` | (measure) | use a fixed height instead |
| `--height-min` / `--height-max` | 0.4 / 2.2 | clamp for the measured height |
| `--toggle-bit` | 5 (R3) | Npad button bit, 4 = L3 |
| `--stale-limit` | 30 | views without a Link update before the normal camera returns |
| `--height-step` | 0.02 | metres per `,` / `.` press |
| `--no-height-keys` | off | leave the keyboard keys out (this also removes `;`, so Link always stays hidden) |
| `--no-hide` | off | leave out hiding Link (he stays visible) |
| `--diagnostic` | off | if Link isn't found, use the look-at point as the eye (to tell the two hooks apart) |

## How it works

Two hooks ([first_person.S](first_person.S)):

1. **Link's position.** In the movement update (`0x82c41720`). If the actor is Link (vtable,
   movement component and resource name `"Player"`), copy his position to a small state block in
   free `.bss`.
2. **The view.** Right after the gameplay camera's view matrix is written (`0x804e5068`). Read the
   three controller types through the game's own `nn::hid::GetNpadStates` imports, toggle on an R3
   press, and when on, recompute only the matrix's translation for the new eye. The rotation rows
   are left alone.

## Known issues / next

- Cutscenes that keep Link updating will also be first person. Press R3 to leave.
- The game camera swings behind Link as he runs. In first person that means the view turns
  toward where you run.
- Eye height is measured from the camera's look-at point, which suits adult Link but puts the eye
  above child Link's head. Use the height keys for now; the next version should set child and
  adult heights separately.
- Field of view is the game's. A wider FOV option would suit first person.
- R3 is also the game's camera recenter, so switching first person on levels the view. A version
  that kept the up / down angle is on the `archive/first-person-keep-pitch` branch: it worked, but
  it overrode the view's pitch on top of the game's, so bow and Hookshot aim came out off. A proper
  fix would write the angle into the game camera's own pitch.
- Link is hidden by default; if you show him with `;`, his arms and sword show when you look
  down or attack.
  Weapons and shield are separate equipment models, so they may stay visible while he's hidden.
