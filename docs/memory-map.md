# Memory map: who uses what

Mods that use the same bytes can't be enabled together. Before you claim space, check here, and
then add yourself.

## Code cave: `.text` padding `0x3C461D0..0x3C47000` (3632 bytes, executable, zero)

| Range (module offset) | Used by |
|---|---|
| `0x3C46200..0x3C46278` | Lichii's built-in patches |
| `0x3C46400..0x3C46610` | [craftycorvid/oot-mod](https://github.com/craftycorvid/oot-mod) (Ultrawide) |
| `0x3C46610..0x3C46B00` | FPV Drone (this repo): hooks + constant table (about 470 bytes used) |
| `0x3C46B00..0x3C46FB0` | First Person (this repo): view hook |
| `0x3C46278..0x3C46400` | First Person (this repo): Link position hook |
| everything else | free: `0x3C461D0..0x3C46200` (48), `0x3C46FB0..0x3C47000` (80) |

There's no dead code to use as a second cave: no function in `.text` is unreferenced (every
candidate turned out to be reached through a thunk, a vtable, or a shrink-wrapped entry a few
instructions before its `pacibsp`), so `main` looks fully dead-stripped. Use the padding slots
below instead.

## Padding slots: the compiler's alignment padding between functions

Functions are aligned to 16 / 32 bytes and the gaps are filled with zero words (`udf #0`) that
nothing executes or references: about 1.5 MB in all, but in pieces of at most 28 bytes.
`nxpatch.split_into_slots` cuts a C file's code into slot-sized chunks chained with branches, so
these pieces can hold real code. One mod's slots must lie within 32 KB of each other (the reach of
`tbz`). [`tools/find_slots.py`](../tools/find_slots.py) finds them; the list is
[`symbols/e0f3ccfa-slots.txt`](../symbols/e0f3ccfa-slots.txt) (205 slots of 16+ bytes, 3920 usable
bytes, in `0x817976a8..0x8179f6a8`).

| Range (address) | Used by |
|---|---|
| `0x817976a8..0x8179cb20` | FPV Drone (this repo): its C code, the first 113 slots of the list |
| `0x8179dfe8..0x8179eb00` | First Person (this repo): `fp_pitch.c`, slots 160–183 of the list (it starts at 160 so FPV Drone can grow) |
| everything else in the list | free: slots 113–159 and 184–204 |

For more, `tools/find_slots.py main.bin` lists other 32 KB windows (the best few each hold 2–4 KB).

## Free writable memory: `.bss` tail `0x4E9A4C8..0x4EA0000` (~23 KB, zeroed at boot)

The last variable the game references is the 8-byte pointer at `0x84eba4c0`. No `adrp`
reference, relocation or data pointer reaches past it (checked by scanning all of `.text`,
`.rodata` and `.data`). The space is zeroed when the game starts, so a mod's state begins at 0.

| Range (address) | Used by |
|---|---|
| `0x84ebfc00..0x84ebfc60` | First Person state |
| `0x84ebfd00..0x84ebfe00` | FPV Drone state |
| everything else | free |

## Hook sites

Two mods can't hook the same instruction.

| Site | Used by |
|---|---|
| `0x804e5068` | First Person (view) |
| `0x82c41720` | First Person (Link position) |
| `0x804e506c` | FPV Drone (view; runs after First Person's `0x804e5068`) |
| `0x82c415e0` | FPV Drone (first instruction of the movement update: carrying Link) |
| `0x83c627fc`, `0x83c6280c`, `0x83c6281c`, `0x83c6282c`, `0x83c6283c` | FPV Drone (the `br x17` of each `GetNpadStates` import stub) |
| `main+0x805bd0` | Lichii built-in "Max Resolution" |
| `main+0x4f1e8, 0x20c2b0, 0x23b9a8, 0x25d76c, 0x33b82c, 0x774368, 0x3485cc0, 0x3b5c758` | Ultrawide |
| `main+0x6e0f04..`, `0x3af1920`, `0x3af1994`, `0x3b4ef90..` | TheCraZyDuDee's FPS mods |
