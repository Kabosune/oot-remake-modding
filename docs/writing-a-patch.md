# Writing a patch

## How a hook works

1. Pick a **site**: one instruction in the game's code where your code should run.
2. The build replaces it with `b your_entry`.
3. Your code, in the cave, does its work, runs the replaced instruction itself, then `b site + 4`.

Branches and `adrp` are PC-relative, so the code works wherever the emulator or console loads
`main`. Never put absolute addresses in data.

## Rules

- A hook on an import stub's `br x17` must leave x16 and x17 as the stub set them: imports are
  bound lazily, and rtld's resolver finds the symbol from x16. (Mouse Probe broke this once: the
  game stuck at "starting...".) More in [modules.md](modules.md#rules-learned-the-hard-way).

- **Keep every register the game uses.** At a hook site you rarely know which registers are live,
  so save what you touch. If you call a function, save all caller-saved registers (x0–x18, x30,
  q0–q7, q16–q31) and NZCV.
- **Keep the flags.** `cmp` in your code changes NZCV. Save it with `mrs x9, nzcv` and restore it
  with `msr nzcv, x9`.
- **Keep sp 16-byte aligned**, and put everything back the way it was before you branch home.
- **Pick a site that's reached on every path you care about.** Check for branches into the middle
  of what you replace (replacing exactly one instruction avoids most of this).
- **Check object types before using them.** Compare vtables (`adrp` + `add` to the vtable
  address) and names, not just null pointers. Many functions run for more than one kind of
  object.
- **Don't read timer or other system registers.** Lichii / Fritchii's CPU emulator (dynarmic)
  stops the game on an `mrs` of a register it doesn't implement, such as `cntvct_el0` or
  `cntfrq_el0` (log: `MRS: ... unreachable`). NZCV is fine. For time, call
  `svcGetSystemTick` (`svc #0x1e`, ticks at 19.2 MHz in `x0`), which every emulator implements.
- **Claim your space** in [memory-map.md](memory-map.md).

## The build

`tools/nxpatch.py` does the mechanical part:

- assembles your `.S` with clang (C preprocessor on, so `#include "params.inc"` and `#define` work)
- links it with ld.lld at the cave address against `symbols/e0f3ccfa.ld`, so `adrp x9, VT_VIEW`
  and `b HOOK_VIEW_RET` resolve
- writes the `b` at each site
- `--verify-main` checks the original bytes at every site and that the cave is still zero
- writes an IPS32 (offsets + 0x100 for the NSO header) and a zip with the
  `0400486024DEC000/<mod>/exefs/<build id>.ips` layout emulators expect

See [mods/first-person/build.py](../mods/first-person/build.py) for a complete example. It's
about 60 lines, most of them options.

### C, and more than one gap

`nxpatch.build_regions()` takes several sources, `.S` or `.c`, and a list of cave regions, each
with the input sections that go there. C is compiled with `-Oz`, `-ffunction-sections` and
`-fdata-sections`, so every function and constant table is its own section you can place. Any
section left unplaced is a link error, so nothing silently goes missing. See
[mods/fpv-drone/build.py](../mods/fpv-drone/build.py).

C code needs a call, and a call from a hook in the middle of a function means saving every
caller-saved register first (about 200 bytes of saves and restores). Two ways around that:

- Hook a **function boundary**, where the ABI already says caller-saved registers are free. The
  `br x17` at the end of an import stub is one: your code is entered as if it were the import.
- Keep the mid-function hook tiny: do the work at a boundary, leave the result in memory, and
  have the hook only copy it (FPV Drone's view hook uses four integer registers).

### Code in the padding between functions

When a mod doesn't fit the cave, give `build_regions` a slot list (`nxpatch.load_slots`,
[`symbols/e0f3ccfa-slots.txt`](../symbols/e0f3ccfa-slots.txt)). The C file is compiled to
assembly (with `-fno-jump-tables`, since jump-table offsets assume the code stays together),
`split_into_slots` puts as many instructions in each slot as fit, ending each with a `b` to the next
slot unless the last one already ends the flow, and every slot is linked at its own address.
Labels stay with their instructions, so branches inside the code still resolve. The data (constant
tables) still goes to a cave region. `verify_slots` checks with `--verify-main` that each slot is
still zero padding after a `ret` / `b` / `br`. See [mods/fpv-drone](../mods/fpv-drone/build.py).

Hooks stay hand-written assembly in a cave region: they're small, and a hook can't be split
without changing the registers it touches.

Code size: one `const` table for float constants reached through one base register, and
`__asm__("" : "+r"(ptr))` to stop the compiler re-deriving a global's address for each field.

## Testing without the game

[`tests/test_first_person.py`](../tests/test_first_person.py) loads the patched `main` into
Unicorn, builds fake game objects in memory, stubs the imports, runs each hook from its site to
`site + 4`, and checks both the result and that no register changed. It's quick, and it catches
most mistakes before you boot the game.
