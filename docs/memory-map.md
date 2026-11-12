# Memory map: who uses what

Mods that use the same bytes can't be enabled together. Before you claim space, check here, and
then add yourself: to this page and to [`registry/e0f3ccfa.toml`](../registry/e0f3ccfa.toml), the
same information in the form `tools/kaegae.py check` reads ([api/MANIFEST.md](../api/MANIFEST.md)).
`python3 tools/kaegae.py registry` prints it with how much of each space is taken.

## Code cave: `.text` padding `0x3C461D0..0x3C47000` (3632 bytes, executable, zero)

| Range (module offset) | Used by |
|---|---|
| `0x3C46200..0x3C46310` | Lichii's built-in patches (Fritchii v5.6): Dynamic FPS's code at `0x3C46200..0x3C46278`, the experimental high refresh rate patch up to `0x3C46310` |
| `0x3C46400..0x3C46610` | [craftycorvid/oot-mod](https://github.com/craftycorvid/oot-mod) (Ultrawide) |
| `0x3C46400..0x3C46410`, `0x3C46440..0x3C46454` | [sloperinaGZ](https://github.com/PracticeROM/sloperina) 0.0.3: an `OOTGZ` tag and the jump into its `subsdk9` module. **Inside Ultrawide's range**: don't expect those two to work together |
| `0x3C46610..0x3C46B00` | FPV Drone (this repo): hooks + constant table (about 470 bytes used) |
| `0x3C46B00..0x3C46FB0` | First Person (this repo) |
| `0x3C46E00..` (extent not known) | Fritchii v5.8.3's built-in "Water ripples at any frame rate". **Inside First Person's range**: with First Person on, Fritchii leaves this fix out and says so in its log (`a user mod already patched main+0x3c46e00`) |
| `0x3C46310..0x3C46400` | KaeGae Core (this repo): its hook point stubs, in every build made with `tools/kaemod.py` (Mouse Probe used it before; the probe is retired and can't be installed alongside) |
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
| `0x8179cb68..0x8179d1c0` | Mouse Grab's input probe (this repo): slots 113–127 |
| `0x8179d1c0..0x8179f6a8` | free: the other 77 slots of the list |

For more, `tools/find_slots.py main.bin` lists other 32 KB windows (the best few each hold 2–4 KB).

## Free writable memory: `.bss` tail `0x4E9A4C8..0x4EA0000` (~23 KB, zeroed at boot)

The last variable the game references is the 8-byte pointer at `0x84eba4c0`. No `adrp`
reference, relocation or data pointer reaches past it (checked by scanning all of `.text`,
`.rodata` and `.data`). The space is zeroed when the game starts, so a mod's state begins at 0.

| Range (address) | Used by |
|---|---|
| `0x84ebfc00..0x84ebfc40` | First Person state |
| `0x84ebfd00..0x84ebfe00` | FPV Drone state |
| `0x84ebfb00..0x84ebfc00` | KaeGae Core's hook slots: one function pointer per hook point |
| `0x84ebfe00..0x84ec0000` | **Lichii's built-in patches** (Fritchii v5.6). Dynamic FPS keeps its last tick and smoothed frame time at `0x84ebfe00` / `+8`; the high refresh rate patch uses `0x84ebfe20` on. Writing here changes the game's speed |
| everything else | free |

## Hook sites

Two mods can't hook the same instruction. sloperinaGZ's ranges and hook were read from its 0.0.3
IPS for this build; none of its bytes overlap First Person or FPV Drone. Running all three
together in game hasn't been tried (its levitate option toggles on L3, like the drone).

| Site | Used by |
|---|---|
| `0x804e5068` | First Person (view) |
| `0x82c41720` | First Person (Link position) |
| `0x804e506c` | FPV Drone (view; runs after First Person's `0x804e5068`) |
| `0x82c415e0` | FPV Drone (first instruction of the movement update: carrying Link) |
| `0x83c627fc`, `0x83c6280c`, `0x83c6281c`, `0x83c6282c`, `0x83c6283c` | FPV Drone (the `br x17` of each `GetNpadStates` import stub) |
| `0x82c415e4` | KaeGae Core: hook point `Actor.MoveUpdate` (the instruction after FPV Drone's) |
| `0x83c627ec`, `0x83c628ac`, `0x83c6480c` | Mouse Probe (retired) (the `br x17` of the `GetNpadStyleSet`, `GetSixAxisSensorStates` and `GetMouseStates` import stubs) |
| `main+0x805bd0` | Lichii built-in "Max Resolution" |
| `main+0x4f1e8, 0x20c2b0, 0x23b9a8, 0x25d76c, 0x33b82c, 0x774368, 0x3485cc0, 0x3b5c758` | Ultrawide |
| `main+0x6e0f04..`, `0x3af1920`, `0x3af1994`, `0x3b4ef90..` | TheCraZyDuDee's FPS mods |
| `main+0x3b500dc` | sloperinaGZ 0.0.3 |
