# FPV Drone

Fly a first-person-view quadcopter around Hyrule. Press **L3** (click the left stick) and the
camera takes off from wherever the game camera is. Link stands still while you fly. Press L3
again to land back in the normal game.

## Controls

Mode 2, like most FPV radios:

| | Up / down | Left / right |
|---|---|---|
| **Left stick** | throttle | yaw |
| **Right stick** | pitch | roll |

| Button (while flying) | |
|---|---|
| **L3** | drone off (back to the game) |
| **Y** | **Angle** mode: self-levelling. The right stick sets the tilt angle (up to 50°); let go and it levels out. Starts in this mode. |
| **X** | **Acro** mode: the right stick sets how fast it rotates, nothing levels it. Flips, rolls, power loops. |
| **B** | **Simple** mode: self-levelling and holds its height. The throttle stick climbs / sinks (4 m/s), and when you let go of everything it slows down and stops. |
| **A** | back to the game camera's position |
| **+** / **−** | leave the drone (these still reach the game, so the menus work) |

Throttle: a gamepad stick springs back to the middle, so the middle is **hover**. Up gives up to
3.5 g of thrust, down less than hover. Build with `--throttle-half` for radio-style throttle
(middle = half thrust) if you fly with a real radio as a controller.

## How it flies

- Thrust along the drone's up axis, gravity, and air drag (top speed about 29 m/s).
- The camera is tilted up 20° from the drone body, like a real FPV camera, so you see ahead when
  the drone leans forward to fly fast.
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

Copy `0400486024DEC000` from `releases/fpv-drone.zip` into `%APPDATA%\eden\load\` and restart
the game.

## Tune it

```
python mods/fpv-drone/build.py --uptilt 30 --rate-max 800
```

| Option | Default | |
|---|---|---|
| `--uptilt` | 20 | camera tilt above the drone body, degrees |
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
| `--toggle` `--reset` `--acro` `--angle` `--simple` | l3 a x y b | buttons (`a b x y l3 r3 l r zl zr up down left right`) |

## How it works

Two hooks, and the code is spread over three free gaps of the shared code cave (it doesn't fit
in one):

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

The flight state is a position, a velocity and an orthonormal frame (right, up, back). Each step
rotates the frame by the body rates (from the sticks in Acro, from the tilt error in Angle and
Simple), re-orthonormalises it, and integrates thrust, gravity and drag. The step length comes from
the system tick counter (`cntvct_el0` / `cntfrq_el0`), capped at 50 ms.

[`tests/test_fpv_drone.py`](../../tests/test_fpv_drone.py) runs all of it on a patched `main` in
Unicorn, through the game's real import stubs.
