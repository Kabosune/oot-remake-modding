# First Person

Press **R3** (click the right stick) to switch to Link's eyes. Press it again to switch back.

- Right stick looks around, left stick walks in the direction you look. The game's own camera
  rotation is kept, so its controls, Z-targeting and aim all still drive the view.
- Eye height is measured when you switch on (the game camera's look-at height above Link). It
  suits adult Link; for child Link, lower it with the height keys below. Switch on while standing
  normally, not while Z-targeting.
- The eye sits 0.15 m in front of Link's face, so his head stays behind the camera.
- When Link stops updating (pause, loading), the normal camera comes back by itself until he moves
  again.
- R3 is also the game's camera recenter. Switching first person on swings the view behind Link
  as usual, but keeps your up / down angle instead of levelling it out (see below).
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

Works on: Lichii / Fritchii (tested target). Should work anywhere exefs IPS32 patches load for
this build, including real hardware through ns2jb-modloader, but that's untested.

Compatible with: FPV Drone (when both are on, the drone's view wins), Ultrawide, the FPS mods, and Lichii's built-ins (no shared bytes, see
[memory-map](../../docs/memory-map.md)).

## Install

Copy `0400486024DEC000` from `releases/first-person.zip` into `%APPDATA%\eden\load\` and restart
the game.

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
| `--no-keep-pitch` | off | let R3's recenter level the view too (the game's own behaviour) |
| `--hold-max` | 60 | views at most to ignore the recenter's pitch change |
| `--stick-deadzone` | 6000 | right stick y (of 32767) that ends ignoring the recenter early |
| `--diagnostic` | off | if Link isn't found, use the look-at point as the eye (to tell the two hooks apart) |

## How it works

Two hooks ([first_person.S](first_person.S)):

1. **Link's position.** In the movement update (`0x82c41720`). If the actor is Link (vtable,
   movement component and resource name `"Player"`), copy his position to a small state block in
   free `.bss`.
2. **The view.** Right after the gameplay camera's view matrix is written (`0x804e5068`). Read the
   three controller types through the game's own `nn::hid::GetNpadStates` imports, toggle on an R3
   press, and when on, recompute the matrix's translation for the new eye. The rotation keeps the
   game's yaw.

**Keeping the pitch through the recenter** ([fp_pitch.c](fp_pitch.c)). The game's own R3 recenter
lives in the camera's AI and parameter files (`ResetSpeed`, `Lat` in `PlayerCameraParamChase`), and
there's no setting for "yaw only", so the view hook handles it instead. It tracks the game's pitch
every view. When first person is switched on, it starts from the pitch of the view before the press
and ignores the game's pitch changes until they stop (the recenter is done), the right stick is
moved, or 60 views pass. After that it follows every change the game makes, so the right stick,
Z-targeting and so on still tilt the view, just from where you were. The rotation is rebuilt from
the game's yaw and this pitch, with no roll, and stops 5° short of straight up or down. The code is
C, split over padding slots between the game's functions, because the cave gap was full.

## Known issues / next

- Cutscenes that keep Link updating will also be first person. Press R3 to leave.
- The game camera swings behind Link as he runs. In first person that means the view turns
  toward where you run.
- Eye height is measured from the camera's look-at point, which suits adult Link but puts the eye
  above child Link's head. Use the height keys for now; the next version should set child and
  adult heights separately.
- Field of view is the game's. A wider FOV option would suit first person.
- The kept pitch is an offset on top of the game's. Where the game's pitch matters (aiming the bow
  or Hookshot), the view can sit a little above or below where the game aims, by however much the
  recenter would have moved it. To clear it, press R3 to leave (the game levels the camera), wait
  for it to settle, and press R3 again.
- Link is hidden by default; if you show him with `;`, his arms and sword show when you look
  down or attack.
  Weapons and shield are separate equipment models, so they may stay visible while he's hidden.
