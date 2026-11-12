# FPV Drone

Link to download: https://github.com/Kabosune/oot-remake-modding/blob/main/releases/fpv-drone.zip

Fly a free camera or a first-person-view quadcopter around Hyrule, and take Link along if you
like. Press **L3** (click the left stick) and the camera leaves from wherever the game camera is.
Link stands still while you fly. Press L3 again to go back to the normal game.

The first time you press L3 after starting the game you're in **Free fly**, a noclip camera.
After that it keeps whichever mode you last picked, until the game restarts.

## Controls

In the drone modes (Angle, Acro, Simple) the sticks are Mode 2, like most FPV radios:

| | Up / down | Left / right |
|---|---|---|
| **Left stick** | throttle | yaw |
| **Right stick** | pitch | roll |

| Button (while flying) | |
|---|---|
| **L3** | drone off (back to the game) |
| **L** | **Free fly**: a noclip camera like a map viewer's. See below. The mode you start in. |
| **Y** | **Angle** mode: self-levelling. The right stick sets the tilt angle (up to 50°); let go and it levels out. |
| **X** | **Acro** mode: the right stick sets how fast it rotates, nothing levels it. Flips, rolls, power loops. The camera is tilted up 30° instead of 20°. |
| **B** | **Simple** mode: self-levelling and holds its height. The throttle stick climbs / sinks (4 m/s), and when you let go of everything it slows down and stops. |
| **R** | **Carry Link**: he flies with the camera, his feet at its height and 1 m behind it, out of view. R again drops him. |
| **A** | back to the game camera's position |
| **+** / **−** | leave the drone (these still reach the game, so the menus work). Leaving drops Link. |

### Free fly

No physics, no tilt, no momentum: the camera goes exactly where you push it, and stops when you
let go.

| | |
|---|---|
| Left stick | move forward / back along where you look, and strafe left / right |
| Right stick | look around (turn and look up / down; it stops just short of straight up or down) |
| ZR / ZL | straight up / down |

8 m/s at full stick, 120°/s turning (`--free-speed`, `--free-turn`). Y, X or B switches back to a
drone mode from where you are.

### Carrying Link

R picks Link up wherever he is: every frame his feet are put at the camera's height, 1 m behind
it (along the level part of where it faces), so he stays out of view as you turn, in any mode.
`--carry-drop` and `--carry-back` change the spot. The game moves him itself, through his character controller (`ChangePosition`, the same call
its `OneShotPhysicsCctChangePosition` script command makes), so collision with the world is off
while he's carried, and the area around him loads as he goes. R, L3, + or − drops him, and he falls
from where he is: drop him low, or he'll take fall damage. His controls are still off while the
drone flies.

Throttle: a gamepad stick springs back to the middle, so the middle is **hover**. Up gives up to
3.5 g of thrust, down less than hover. Build with `--throttle-half` for radio-style throttle
(middle = half thrust) if you fly with a real radio as a controller.

## How it flies

- Thrust along the drone's up axis, gravity, and air drag (top speed about 29 m/s).
- The camera is tilted up from the drone body, like a real FPV camera, so you see ahead when the
  drone leans forward to fly fast: 20° in Angle and Simple (a usual beginner setup), 30° in Acro
  (a usual freestyle setup; racers go to 40–55°). Free fly has no tilt.
- Acro rates: 200°/s near the middle of the stick, 670°/s at full stick (similar to
  Betaflight's defaults). Yaw: 120 → 300°/s.
- It's a ghost: no collision. It flies through walls, floors and water.
- Time-based, so it flies the same at 30 or 60 fps.

## What happens to the game

- While flying, the game sees the controller as centred sticks and no buttons (except + and −),
  so Link waits where he is. The world keeps running around him: enemies can still hit him.
- When the gameplay camera isn't being drawn (menus, loading), the drone stands by and the
  controller goes back to the game. It picks up again afterwards.
- Starts off at every boot.

## Works with

First Person (both can be installed: when both are on, the drone wins; leave the drone with L3,
+ or −), Ultrawide, the FPS mods, and Lichii's built-ins. No shared bytes, see
[memory-map](../../docs/memory-map.md).

Works on: Lichii / Fritchii (target). Should work anywhere exefs IPS32 patches load for this build;
untested elsewhere.

## Install

Copy `0400486024DEC000` from `releases/fpv-drone.zip` into the emulator's `load` folder (Fritchii v5.8
and later: `%APPDATA%\fritchii\load\`; Lichii, Eden and older Fritchii: `%APPDATA%\eden\load\`) and restart
the game.

## Tune it

```
python mods/fpv-drone/build.py --acro-uptilt 40 --rate-max 800
```

| Option | Default | |
|---|---|---|
| `--uptilt` / `--acro-uptilt` | 20 / 30 | camera tilt above the drone body, degrees: Angle and Simple / Acro |
| `--rate-center` / `--rate-max` | 200 / 670 | Acro pitch and roll, deg/s near centre / at full stick |
| `--yaw-center` / `--yaw-max` | 120 / 300 | yaw, deg/s |
| `--max-tilt` | 50 | Angle / Simple: tilt at full stick, degrees |
| `--level-gain` | 8 | Angle / Simple: how quickly it follows the stick |
| `--thrust` | 3.5 | full throttle, in g |
| `--drag` | 0.04 | air drag (higher = lower top speed) |
| `--climb-rate` | 4 | Simple: climb speed at full stick, m/s |
| `--brake` | 1.5 | Simple: how quickly it stops sideways |
| `--deadzone` | 0.06 | stick dead zone |
| `--throttle-half` | off | throttle centre = half thrust instead of hover |
| `--free-speed` / `--free-turn` | 8 / 120 | Free fly: m/s and deg/s at full stick |
| `--carry-drop` / `--carry-back` | 0 / 1 | carried Link's feet below / behind the camera, m |
| `--toggle` `--reset` `--acro` `--angle` `--simple` `--free` `--carry` | l3 a x y b l r | buttons (`a b x y l3 r3 l r zl zr up down left right`) |

## How it works

Three hooks. They and the constant table sit in one gap of the shared code cave; the C code
(about 2 KB, more than any gap) is split over the compiler's padding between the game's
functions (see [memory-map](../../docs/memory-map.md#padding-slots-the-compilers-alignment-padding-between-functions)):

- **Controller.** The game reads every controller with `nn::hid::GetNpadStates` through five import
  stubs (one per controller style), each with exactly one caller, in its polling loop
  (`f_834893d0`). The last instruction of each stub, `br x17`, now branches to `npad_wrap`, which
  calls the real function and then `fpv_input` (C) with the states it returned. Because this is a
  function call boundary, the C code runs without saving every register. `fpv_input` reads player
  1's / handheld's latest state, flies one step, writes the drone camera's view matrix into its
  state, and while flying clears the buttons and sticks in all the states before the game sees them.
- **View.** At `0x804e506c` in `f_804e48c0`, one instruction after First Person's hook (the matrix
  is finished there and nothing has read it yet), `fpv_view_hook` checks it's the gameplay view,
  keeps the game camera's eye and back axis for the next take-off, and while flying copies the
  drone's matrix over the game's. It uses integer registers only.
- **Carry.** The first instruction of `f_82c415e0`, the movement update every physics actor runs
  each frame. While carrying (one flag checked before anything else), `fpv_actor` checks that the
  actor is Link (the same checks as First Person) and calls `ChangePosition` on his character
  controller with the point under the drone. At a function's first instruction only its arguments
  are live, so the hook keeps just those.

The flight state is a position, a velocity and an orthonormal frame (right, up, back). Each step
rotates the frame by the body rates (from the sticks in Acro, from the tilt error in Angle and
Simple), re-orthonormalises it, and integrates thrust, gravity and drag. The step length comes from
`svcGetSystemTick` (19.2 MHz), capped at 50 ms. (An earlier build read `cntvct_el0` directly,
which Fritchii's CPU emulator doesn't implement: the game stopped on the first frame.)

[`tests/test_fpv_drone.py`](../../tests/test_fpv_drone.py) runs all of it on a patched `main` in
Unicorn, through the game's real import stubs.
