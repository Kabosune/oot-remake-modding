# Modules: mods as their own code (build E0F3CCFA)

Code caves and padding slots hold a few KB at most. A bigger mod can be a module of its own, loaded
by the game's dynamic loader (rtld) from an `exefs/subsdkN` file, the way sloperinaGZ is. Kaepora
Core (`api/core/`) is the start of a shared one; [Mouse Grab](../mods/mouse-grab/README.md) is the
first mod built on it.

## What's free

The game ships `main`, `rtld`, `sdk` and `subsdk0`. Mouse Grab uses `subsdk1`; sloperinaGZ uses
`subsdk9`. A mod folder's `exefs/` can hold the module and an `.ips` for `main` side by side.

## The module

- `api/core/crt0.S`, `module.ld`: the header (MOD0 at the offset in word 4) and a layout of three
  page-aligned segments (code, read-only, data + bss). Built position independent with clang and
  `ld.lld -shared -Bsymbolic`; `-init kp_module_init` makes rtld call Core at load, before `nnMain`.
- `tools/mknso.py` packs the ELF into an NSO (uncompressed, with segment hashes).
- Imports resolve against the other modules by name. `main` exports `nnMain` and `aligned_alloc`;
  `sdk` exports `nvnBootstrapLoader` and the `nn::hid` functions. The build refuses imports it
  doesn't know about (`IMPORTS` in `mods/mouse-grab/build.py`).
- Core finds `main`'s base from `nnMain` (`kp_main`); main's functions are then `kp_main + offset`
  (`KP_FN`). The base moves from run to run (seen: `0x8052f000`, `0x801df000`).

## Hooking from a module

- **GOT slots** (no patch to main): swap main's slot for an import, call the real function through
  the module's own import of the same symbol. Core does this for `nvnBootstrapLoader` (drawing) and
  `GetSixAxisSensorStates` (motion). `kp_import_slot` finds a slot from main's dynamic section.
  Lazy binding: before the first call the slot points into main's PLT, not at the function.
- **Hook points** (a small `.ips`): `api/core/hookpoints.S` jumps from a site in main to a stub that
  calls a function pointer the module writes into `KP_HOOK_SLOTS` (`0x84ebfb00`). Slot 0 is the
  movement update, `f_82c415e0`'s second instruction (its first is FPV Drone's); it runs on the
  game's thread for every physics actor every frame with `x0` = actor. The module checks the stub's
  tag before writing the slot. `tests/test_kaepora_hooks.py` runs the stub.

## Drawing (tested)

Core wraps three NVN functions the game fetches by name (`nvnDeviceInitialize`,
`nvnWindowBuilderSetTextures`, `nvnQueuePresentTexture`; the game asks through
`nvnDeviceGetProcAddress` and the bootstrap loader, both are wrapped). Before each frame is shown
it fills rectangles of the texture being presented with scissored clears: no shaders, no blending.
The picture is 2560 x 1440 in Fritchii with its max-resolution patch. sloperinaGZ takes the same
GOT slot and doesn't chain, so the two don't run together.

## Input

- Mouse: `nn::hid::GetMouseStates`, 1280 x 720, left button bit 0, right bit 1, middle bit 2;
  attributes bit 1 = connected. Fritchii: turn on the emulated mouse (`mouse_enabled`).
- Motion: the game reads `GetSixAxisSensorStates` about 40 times a second; Core keeps the newest
  state of the first sensor that moves (`kp_motion_direction`).
- Memory: `kp_readable` (svcQueryMemory) before following unknown pointers.

## Rules learned the hard way

- A wrapper on an import stub's `br x17` must leave x16 and x17 as the stub set them (rtld's lazy
  resolver reads x16). Breaking this left the game stuck at "starting...".
- Fritchii's built-in patches use more of main than they say (memory map): writing there made the
  game run twice as fast.
- Fritchii reads a mod's exefs files when the app starts, not when the game boots: close and reopen
  it after installing a build. Log a build name at start to check.
- Debug lines from `svcOutputDebugString` show in Fritchii's log (`eden_log.busy.txt` while it
  runs, `eden_log.txt` after) as `Debug.Emulated <Info>`.
