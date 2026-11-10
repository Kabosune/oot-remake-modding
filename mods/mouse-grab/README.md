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

## Emulators (10 November 2026)

- Fritchii v5.6 (Lichii) logs `SetMouseLibraryVersion: (STUBBED)` when the game starts, and has
  yuzu's emulated mouse (`mouse_enabled` in `qt-config.ini`). Its exe has no Nmouse or Jcms names.
- A PokeDinner fork merged "hid: Switch 2 mouse (Nmouse), so Joy-Con 2 mouse mode works" on
  4 November 2026 (for Pokopia). Not read yet.

Probe results in Fritchii v5.6 with `mouse_enabled` on (KaboWabo, 10 November):

- `GetMouseStates` works from a mod. Position is in a 1280 x 720 space (seen: x 0..1260,
  y 0..719) and follows the PC mouse over the game window; the left button is bit 0 of the
  buttons; attributes are 2 (connected). Movement deltas are filled in too.
- The game reads the motion sensor about 40 times a second and gets real values from the
  controller: acceleration (about 1 g when still), angular velocity, and the direction matrix,
  whose third row tilts with the controller. Enough to take pitch from.
- Debug lines written with `svcOutputDebugString` appear in Fritchii's log at its default filter
  (`Debug.Emulated <Info>`).
- Not answered: whether the game itself reads the mouse every frame. The first probe's counters
  shared memory with Fritchii's Dynamic FPS patch (see docs/memory-map.md) and were overwritten,
  which also made the game run fast.

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

The lines appear in Fritchii's log (`eden_log.txt`) as `Debug.Emulated <Info>`. `mouse_enabled`
has to be on for the emulated mouse.

## The cursor build (`module/`, `build.py`)

The first build that is a module of its own: Kaepora Core's first skeleton (`api/core/`) and the
cursor (`module/cursor.c`) linked together into `exefs/subsdk1`. It patches nothing in `main`.

```
python3 mods/mouse-grab/build.py
```

- `api/core/crt0.S`, `module.ld`: the module header (MOD0) and layout rtld expects.
- `api/core/core.c`: finds main from the exported `nnMain` and checks the build (1.1.1 only for
  now), then starts drawing and the mod.
- `api/core/draw.c`: swaps main's GOT slot for `nvnBootstrapLoader`, so it can wrap the NVN
  functions the game fetches by name (`nvnDeviceInitialize`, `nvnWindowBuilderSetTextures`,
  `nvnQueuePresentTexture`). Before each frame is shown it fills rectangles of the texture being
  presented: a scissored clear per rectangle, no shaders. The same idea sloperinaGZ uses (learned
  from its docs, code written from scratch).
- `tools/mknso.py`: packs the linked ELF into an NSO.

Known clash: sloperinaGZ 0.0.3 also takes over main's `nvnBootstrapLoader` slot and doesn't pass
the call on to a hook that was there before it. With both installed, whichever module rtld
initialises last wins, so disable sloperinaGZ while testing this.

What it logs (lines start with `kaepora:`): `module loaded, main at ...`, `the game asked for NVN`,
`drawing ready`, `first frame, picture size W H`, and the cursor position every 300 frames.

## Ragdoll test build (`module/ragdoll.c`)

Right click drops Link into ragdoll; right click again gets him up. All of it is logged.

- Tested 10 November: the ragdoll works (KaboWabo). The first try at ending it called the wrong
  thing; ending now copies what the node does when it leaves (`f_83239090`, then
  `player[0x1c3e] |= 1`). The ragdoll component's `+0x17c` is 3 while he is down.

- Calls the same three functions the game's `ExecuteEventPlayerImmediateRagdollDown` node calls
  when it starts (`f_80857620`, `f_806188c0`, `f_83238d30` with the `ImmediateDown` request),
  from Link's movement update. It doesn't copy the node's state change or its per-frame update.
- Ending uses `OneShotRagdollReactionEnd`'s call (`f_82eb2f80` on the reaction component at
  `[components + 0x390]`); not known to be the right one for this kind of ragdoll.
- Game logic must run on the game's thread, so this build adds Kaepora's first **hook point**:
  `api/core/hookpoints.S`, patched in by the mod's `.ips`, jumps from the movement update's second
  instruction to a stub that calls the function the module put in `KP_HOOK_SLOTS`. It sits right
  after FPV Drone's hook, so both work together. `tests/test_kaepora_hooks.py` checks the stub.
- Mouse Probe is retired: the hook stubs use its code cave space, so the two can't be installed
  together.

## Survey of the ragdoll (first `module/survey.c`, 10 November; in git history)

Run once a second after Link went down, following pointers from the ragdoll component. Found
(holder = `[ragdoll + 0x10]`, the same object `f_80857620` returns):

- `[holder + 8]` is the character controller, `[[holder + 8] + 0x20]` its body (as sloperina's notes say).
- Arrays of positions near Link with a stride of 0x70 bytes: `[[holder + 0x18] + 0x1e0]` (10 entries),
  `[[holder + 0x18] + 0x1f0]` (10), `[[holder + 0x48] + 0x88]` (9, from `+0x70`). Probably bone or
  ragdoll body transforms; not known which.
- Four more objects with the body vtable: `[[holder + 0x18] + 8]`, `+0x10`, `[[holder + 0xc8] + 0x30]`,
  `+0x38`, `[[holder + 0xd0] + 0x30]`.

## Grab build (`module/grab.c`)

Hold the left button on Link to pick him up, move the mouse to carry him, let go to throw him; he
ragdolls as he flies. The cursor is turned into a ray through the gameplay camera (sloperina's
camera fields); he's held at the distance he was grabbed at.

- First try (10 November): moving his character controller while he's a ragdoll doesn't move
  him. The game pulls the controller back to the ragdoll every frame: he twitched and Navi, who
  follows the controller, flew around. The ragdoll's own bodies are Havok's; not found yet.
- So for now he comes out of ragdoll while held and is carried like FPV Drone carries him
  (ChangePosition, velocity zeroed every frame). On release his controller body gets the throw
  velocity and he ragdolls. Next: find the ragdoll's bodies and pull those, so he's limp while held.
- Tested: carry and throw work. Thrown, he only went limp when he landed (the request was
  accepted at once: state 3). Now the ragdoll start also runs the player preparation the game's
  node does first (see `ragdoll.c`), and the throw velocity is set after it.

**The ragdoll's bodies (found 10 November).** `f_83237d70`, which the start request calls to hand the
controller's velocity to the ragdoll, shows where they are: `set = [ragdoll + 0x40]`, count
`[set + 0x60] - 1`, entries of 0x138 bytes from `[set + 0x68]`, and in each entry at `+0x38` a body of
the same wrapper class as the controller's (`f_8014dbe0` sets its velocity). So the carry now
keeps him a ragdoll and pulls the bodies toward the held point every frame; middle click switches
between pulling every body and pulling only the first. The throw gives every body the velocity.
`module/survey.c` now dumps the 0x70-byte arrays (survey 2) a second after he goes down.

## Depth from controller pitch, and survey 3 (10 November)

- Tested: carrying him limp works (18 ragdoll bodies found; their wrapper's vtable is main offset
  `0x4c378c0`, not the controller body's).
- `api/core/motion.c` swaps main's GOT slot for `GetSixAxisSensorStates` and keeps the newest
  direction matrix of the first sensor that moves. While Link is held, turning the controller up
  or down changes the hold distance. First build: distance followed the tilt angle (like a
  stick). KaboWabo asked for it reversed and mouse-like, so now only the turning counts: each
  frame's change of pitch moves him, faster turns go further, and turns slower than `GYRO_DEAD`
  are ignored so the controller can be brought back slowly.
- `module/actors.c` (survey 3): the first time each physics actor passes through the movement
  update, it logs its name (`char*` at `+0x20`) and whether it has a ragdoll component, with the
  number of bodies. Result (Castle Town, Market, Hyrule Field, 10 November): only `Player` has
  one. No NPC (`Npc_Hylia_*`, soldiers), animal (cuccos, dogs) or Skulltula did. The romfs has
  enemy ragdoll data (`Phive/Ragdoll/Structure/Enemy_Common`, `EnemyBase`, reaction lists) and
  ragdoll landing sounds for Lizalfos, Dinolfos, Bubbles and Gohma larvae, so some enemies do have
  ragdolls, maybe only once they die. The survey now also logs the ragdoll reaction component
  (`[components + 0x390]`), which enemies may use instead.

## Plan

1. Probe: what does the emulator feed the game (this step).
2. A module of its own (the code cave is too small): loads, runs every frame, reads input, draws a
   cursor. This becomes the start of Kaepora Core (`api/`). (Built, waiting for a test.)
3. Link ragdolls on a button; then move him with the cursor; depth from pitch; throw; other things.

## Credits

- KaboWabo/Kabosune (me :3): idea, design, in-game testing
- AI assistance (Claude Fable 5.2, Claude Opus 5.5)
