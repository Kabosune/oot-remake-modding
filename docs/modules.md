# Modules: mods as their own code (build E0F3CCFA)

Code caves and padding slots hold a few KB at most. A bigger mod can be a module of its own, loaded
by the game's dynamic loader (rtld) from an `exefs/subsdkN` file, the way sloperinaGZ is.
[KaeGae Core](../api/README.md) (`api/core/`) is a shared one that mods build on;
[Mouse Grab](../mods/mouse-grab/README.md) is the first mod on it. This page is what was learned
about modules; the API a mod uses is in `api/include/kaegae.h`.

## What's free

The game ships `main`, `rtld`, `sdk` and `subsdk0`. KaeGae Core uses `subsdk1` and gives `subsdk2`
to `subsdk8` to mods; sloperinaGZ uses `subsdk9`. A mod folder's `exefs/` can hold modules and an
`.ips` for `main` side by side.

## The module

- `api/core/crt0.S`, `module.ld`: the header (MOD0 at the offset in word 4) and a layout of three
  page-aligned segments (code, read-only, data + bss). Built position independent with clang and
  `ld.lld -shared -Bsymbolic`; `-init` names the function rtld calls at load, before `nnMain`
  (`kp_module_init` in Core, `kae_module_init` in a mod's own module).
- `tools/mknso.py` packs the ELF into an NSO (uncompressed, with segment hashes).
  `tools/kaemod.py` does the whole build: Core, mods, the `.ips`, the zip.
- Imports resolve against the other modules by name. `main` exports `nnMain` and `aligned_alloc`;
  `sdk` exports `nvnBootstrapLoader` and the `nn::hid` functions. The build refuses imports it
  doesn't know about (`CORE_IMPORTS` in `tools/kaemod.py`, `[core.imports]` in a mod's `mod.toml`).
- Core finds `main`'s base from `nnMain` and recognises the build by where `nnMain` and MOD0 are
  (`[detect]` in `symbols/<build>.toml`). The base moves from run to run (seen: `0x8052f000`,
  `0x801df000`). Mods get addresses by name (`kae_sym`), or the base itself (`kae_game_base`).
- A mod's own module imports Core's `kae_` functions by name. Not yet seen in the game: whether
  rtld links one added module to another (the test in `api/README.md`). The same mod can be
  linked into Core's module instead, which needs nothing new from rtld.

## Hooking from a module

- **GOT slots** (no patch to main): swap main's slot for an import, call the real function through
  the module's own import of the same symbol (`kp_wrap_import`). Core does this for
  `nvnBootstrapLoader` (drawing), `GetSixAxisSensorStates` (motion) and, new and not yet run in
  the game, `GetNpadStates` and `GetNpadStyleSet` (the `input` and `frame` events).
  Lazy binding: before the first call the slot points into main's PLT, not at the function. If
  another module's hook is already in the slot, Core calls it on.
- **Hook points** (a small `.ips`): `api/core/hookpoints.S` jumps from a site in main to a stub that
  calls a function pointer the module writes into `KP_HOOK_SLOTS` (`0x84ebfb00`). Slot 0 is the
  movement update, `f_82c415e0`'s second instruction (its first is FPV Drone's); it runs on the
  game's thread for every physics actor every frame with `x0` = actor. Mods get it as the
  `actor_move` event. Core checks the stub's tag before writing the slot.
  `tests/test_kaegae_hooks.py` runs the stub on a real main.

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
  state of the first sensor that moves (`kae_motion_direction`).
- Memory: `kae_readable` (svcQueryMemory) before following unknown pointers.

## Rules learned the hard way

- A wrapper on an import stub's `br x17` must leave x16 and x17 as the stub set them (rtld's lazy
  resolver reads x16). Breaking this left the game stuck at "starting...".
- Fritchii's built-in patches use more of main than they say (memory map): writing there made the
  game run twice as fast.
- Fritchii reads a mod's exefs files when the app starts, not when the game boots: close and reopen
  it after installing a build. Log a build name at start to check.
- A wrapper must not assume how the function it wraps returns its result: Core's wrapper on
  `GetNpadStyleSet` is assembly that keeps `x0` and `x8` and jumps to the real function.
- Debug lines from `svcOutputDebugString` show in Fritchii's log (in its data folder's `log` folder: `eden_log.busy.txt` while it
  runs, `eden_log.txt` after; the data folder is `%APPDATA%\fritchii` from v5.8, `%APPDATA%\eden` before) as `Debug.Emulated <Info>`.
