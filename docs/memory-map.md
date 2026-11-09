# Memory map: who uses what

Mods that use the same bytes can't be enabled together. Before you claim space, check here, and
then add yourself.

## Code cave: `.text` padding `0x3C461D0..0x3C47000` (3632 bytes, executable, zero)

| Range (module offset) | Used by |
|---|---|
| `0x3C46200..0x3C46278` | Lichii's built-in patches |
| `0x3C46278..0x3C46400` | FPV Drone (this repo): hooks + a helper (336 bytes used) |
| `0x3C46400..0x3C46610` | [craftycorvid/oot-mod](https://github.com/craftycorvid/oot-mod) (Ultrawide) |
| `0x3C46610..0x3C46B00` | FPV Drone (this repo): flight code (1260 bytes used) |
| `0x3C46B00..0x3C46FB0` | First Person (this repo) |
| `0x3C46FB0..0x3C47000` | FPV Drone (this repo): constant table (72 bytes used) |
| everything else | free: only `0x3C461D0..0x3C46200` (48 bytes) is left |

The cave is now nearly full. A search for a second cave in dead code found nothing: no function
in `.text` is unreferenced (every candidate turned out to be reached through a thunk, a vtable, or
a shrink-wrapped entry a few instructions before its `pacibsp`), so `main` looks fully
dead-stripped. A future mod that needs more room will have to share, or free space by moving an
existing mod's code.

## Free writable memory: `.bss` tail `0x4E9A4C8..0x4EA0000` (~23 KB, zeroed at boot)

The last variable the game references is the 8-byte pointer at `0x84eba4c0`. No `adrp`
reference, relocation or data pointer reaches past it (checked by scanning all of `.text`,
`.rodata` and `.data`). The space is zeroed when the game starts, so a mod's state begins at 0.

| Range (address) | Used by |
|---|---|
| `0x84ebfc00..0x84ebfc40` | First Person state |
| `0x84ebfd00..0x84ebfe00` | FPV Drone state |
| everything else | free |

## Hook sites

Two mods can't hook the same instruction.

| Site | Used by |
|---|---|
| `0x804e5068` | First Person (view) |
| `0x82c41720` | First Person (Link position) |
| `0x804e506c` | FPV Drone (view; runs after First Person's `0x804e5068`) |
| `0x83c627fc`, `0x83c6280c`, `0x83c6281c`, `0x83c6282c`, `0x83c6283c` | FPV Drone (the `br x17` of each `GetNpadStates` import stub) |
| `main+0x805bd0` | Lichii built-in "Max Resolution" |
| `main+0x4f1e8, 0x20c2b0, 0x23b9a8, 0x25d76c, 0x33b82c, 0x774368, 0x3485cc0, 0x3b5c758` | Ultrawide |
| `main+0x6e0f04..`, `0x3af1920`, `0x3af1994`, `0x3b4ef90..` | TheCraZyDuDee's FPS mods |
