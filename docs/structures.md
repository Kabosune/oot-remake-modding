# Structures (build E0F3CCFA)

Offsets in hex. Types: f32 = float, f64 = double. Units look like metres (Hookshot's free camera
moves 8 units/s and its flight 4 units/s, and both feel right in game).

## Camera view (vtable `0x84c18a88`)

Written by `f_804e48c0` every frame.

| Offset | Type | Field |
|---|---|---|
| `+0x00` | ptr | vtable |
| `+0x08` | f32[3][4] | view matrix, row-major. Row 0 = right, row 1 = up, row 2 = **back** (the camera looks along −row 2). Column 3 = `−(row · eye)`. |
| `+0x38` | f32[3] | eye (float copy) |
| `+0x44` | f32[3] | target (float copy) |
| `+0x50` | f32[3] | up, normalised |
| `+0x60` | f64[3] | eye |
| `+0x78` | f64[3] | target (look-at point) |

Only the matrix needs changing to move what you see. Hookshot's free camera and First Person both
do just that.

## Camera manager

```
mgr     = [[0x84ca6bc0]]
count   = u32 [mgr + 0x20]        (0: no cameras)
cameras = [mgr + 0x28]
camera0 = [cameras + 0]
view    = [camera0 + 0x78]        the gameplay view
```

`f_804e48c0` runs for other views too (menus, previews), so compare against this one.

## Physics actor (vtable `0x84b45e18`)

The object `f_82c415e0` moves.

| Offset | Type | Field |
|---|---|---|
| `+0x270` | ptr | components |
| `+0x31c` | f32[3] | position |
| `+0x328` | f32[3][4] | rotation rows, 0xc apart (yaw = `atan2(+0x330, +0x348)`) |

Finding Link:

```
movement = [[actor + 0x270] + 0x320]
[movement + 0x18] == actor
player   = movement - 0x1d50       vtable 0x84b6c460
res      = [player + 0x10]
res + 0x58 == "Player\0"
```

Model component (found through `OneShotSetModelVisible`'s execute, `0x82959ea0`):

```
model = [[actor + 0x270] + 0x260]
u8  model + 0xe5     visible (1) / hidden (0)
u32 model + 0x120    change flags; set bit 0x800 after writing +0xe5 so the model picks it up
```

The game's script commands are classes: a type-info singleton, a param binder (vtable slot 28)
and an execute (slot 39), with the name string returned by slot 19. Comparing two commands'
vtables shows which slots are theirs.

## Player-type actor (vtable `0x84b6c460`)

| Offset | Type | Field |
|---|---|---|
| `+0x10` | ptr | resource record (name at `+0x58`) |
| `+0x1c10` | ptr | life storage, life at `[+0x1c10] + 8` (Hookshot) |
| `+0x1d50` | | movement component (embedded) |

## Controller state (`NpadCommonState`, 0x28 bytes)

| Offset | Type | Field |
|---|---|---|
| `+0x00` | s64 | sampling number |
| `+0x08` | u64 | buttons: bit 0 A, 1 B, 2 X, 3 Y, 4 L3, 5 R3, 6 L, 7 R, 8 ZL, 9 ZR, 10 +, 11 −, 12–15 D-pad left/up/right/down |
| `+0x10` | s32[2] | left stick |
| `+0x18` | s32[2] | right stick |
| `+0x20` | u32 | attributes (bit 0 connected) |

`GetNpadStates(states, count, &id)` fills up to `count` states, newest first (the nn::hid
convention; FPV Drone relies on entry 0 being the latest), and returns how many it wrote. The game
asks for 16 and keeps them in its per-controller records (see `f_834893d0` in the address map).

Npad IDs: `0` = player 1, `0x20` = handheld. Lichii's default Pro Controller is FullKey on player 1.

## Keyboard state (`nn::hid::KeyboardState`)

| Offset | Type | Field |
|---|---|---|
| `+0x00` | s64 | sampling number |
| `+0x08` | u32 | modifiers |
| `+0x0c` | u32 | attributes |
| `+0x10` | u64[4] | keys, one bit per USB HID usage (`,` = 0x36, `.` = 0x37, `/` = 0x38) |

In Lichii / Eden the game only sees the PC keyboard when keyboard emulation is on
(`keyboard_enabled=true` in `qt-config.ini`, or Controls → Advanced → Keyboard).
