# Mouse Grab (in progress)

A mouse cursor that grabs Link (and later other things), turns him into a ragdoll, and lets you
move and throw him. The mouse gives two axes; the third, towards and away from the camera, comes
from the controller's pitch.

Nothing playable yet. This folder holds the findings and the test builds.

## Input: what the game already imports

`main` (build `E0F3CCFA`) imports all the input functions this mod needs, so the mod can call them
through the game's own import stubs.

| What | Functions | Import stub |
|---|---|---|
| Mouse | `nn::hid::InitializeMouse()` | `0x83c647e0` |
| | `nn::hid::GetMouseStates(MouseState*, int)` | `0x83c64800` |
| Switch 2 mouse | `nn::hid::GetNmouseHandles(NmouseHandle*, int, uint)` | `0x83c628d0` |
| | `nn::hid::GetNmouseTypeSet(BitFlagSet<32, NmouseType>*, NmouseHandle)` | `0x83c628e0` |
| | `nn::hid::FinalizeNmouse()` | `0x83c627c0` |
| "Jcms" | `nn::hid::GetJcmsHandle(uint const&, JcmsType const&)` | `0x83c62890` |
| | `nn::hid::StartJcms` / `StopJcms(JcmsHandle const&)` | `0x83c628c0` / `0x83c628b0` |
| | `nn::hid::FinalizeJcms()` | `0x83c627b0` |
| Motion | `nn::hid::GetSixAxisSensorHandles(...)` | `0x83c62840` |
| | `nn::hid::StartSixAxisSensor(SixAxisSensorHandle const&)` | `0x83c62870` |
| | `nn::hid::GetSixAxisSensorStates(SixAxisSensorState*, int, SixAxisSensorHandle const&)` | `0x83c628a0` |
| | `nn::hid::GetSensorFusionHandles(...)` | `0x83c628f0` |

What the game does with them:

- **Mouse and keyboard device, `f_83b48780`.** Each call reads `GetMouseStates(buf, 16)` and then
  `GetKeyboardState`. It stores the newest mouse position in its object as floats: pixels at
  `+0x1a8` / `+0x1ac`, and scaled to -1..1 at `+0x1b0` / `+0x1b4`; the wheel sum at `+0x1c0`. If
  bit 0 of the mouse state's attributes is set it returns before reading the keyboard. Its
  constructor (ending at `0x83b48750`) calls `InitializeMouse` and `InitializeKeyboard`.
  Whether the game runs this every frame in the shipped build isn't known yet; the probe counts it.
- **Controller polling, `f_834893d0`.** The Nmouse, Jcms and motion calls are all in here, per
  controller slot. It gets a Jcms handle for the left and the right Joy-Con (`+0xea0`, `+0xea4` of
  the slot) and starts or stops them depending on a byte at `+0x780` of `this + 0x8000`; Nmouse
  handles go to `+0xea8`. The game imports no function that reads an Nmouse or Jcms state, so
  those two only switch the sensor on and off here.

Guesses, not checked: "Jcms" is the Joy-Con 2's mouse sensor, and with it started the position
arrives through `GetMouseStates`.

## Emulators (9 November 2026)

- Fritchii v5.6 (Lichii) logs `SetMouseLibraryVersion: (STUBBED)` when the game starts, and has
  yuzu's emulated mouse (`mouse_enabled` in `qt-config.ini`). Its exe has no Nmouse or Jcms names.
- A PokeDinner fork merged "hid: Switch 2 mouse (Nmouse), so Joy-Con 2 mouse mode works" on
  4 November 2026 (for Pokopia). Not read yet.

## The probe (`probe/`)

A test build that changes nothing in the game. Twice a second it writes a line starting with
`MGP` to the debug log: how often the game polls, how often the game itself reads the mouse, the
mouse state read through `GetMouseStates`, and the newest motion sensor state the game read.
`probe/probe.c` lists the fields.

```
python3 mods/mouse-grab/probe/build.py --verify-main work/main.bin
```

```
python3 tests/test_mouse_probe.py work/main.bin releases/mouse-probe.zip
```

To see the lines in a yuzu-family emulator, the log filter has to let debug lines of the
`Debug.Emulated` class through (`*:Info Debug.Emulated:Debug`), and `mouse_enabled` has to be on
for the emulated mouse.

## Plan

1. Probe: what does the emulator feed the game (this step).
2. A module of its own (the code cave is too small): loads, runs every frame, reads input, draws a
   cursor. This becomes the start of Kaepora Core (`api/`).
3. Link ragdolls on a button; then move him with the cursor; depth from pitch; throw; other things.

## Credits

- KaboWabo/Kabosune (me :3): idea, design, in-game testing
- AI assistance (Claude Fable 5.2)
