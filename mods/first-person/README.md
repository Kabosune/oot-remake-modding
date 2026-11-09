# First Person

Press **R3** (click the right stick) to switch to Link's eyes. Press it again to switch back.

- Right stick looks around, left stick walks in the direction you look. The game's own camera
  rotation is kept, so its controls, Z-targeting and aim all still drive the view.
- Eye height is measured when you switch on (the game camera's look-at height above Link), so it
  fits child and adult Link. Switch on while standing normally, not while Z-targeting.
- The eye sits 0.15 m in front of Link's face, so his head stays behind the camera.
- When Link stops updating (pause, loading), the normal camera comes back by itself until he moves
  again.
- Starts off at every boot.

Works on: Lichii / Fritchii (tested target). Should work anywhere exefs IPS32 patches load for
this build, including real hardware through ns2jb-modloader, but that's untested.

Compatible with: Ultrawide, the FPS mods, and Lichii's built-ins (no shared bytes, see
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
- Field of view is the game's. A wider FOV option would suit first person.
- Link's arms and sword show when you look down or attack. That's intended for now (body cam).
