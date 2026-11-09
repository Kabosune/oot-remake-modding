# Address map (main, build E0F3CCFA)

Base `0x80020000`. `main offset = address - 0x80020000`, `IPS offset = main offset + 0x100`.
Machine-readable copy: [`symbols/e0f3ccfa.ld`](../symbols/e0f3ccfa.ld).

"Source" says where a finding comes from. **Hookshot** means it's used in
[Hookshot](https://github.com/NotRexed/Hookshot)'s `host/` or `nx2/oot_patches.py` (and works there).
**Disasm** means it was read from the disassembly here. **Untested** means nobody has confirmed it
in game yet.

## Segments

| | Range (module offset) | Notes |
|---|---|---|
| .text | `0x0000000..0x3C461D0` | zero padding to `0x3C47000` is executable: the shared code cave |
| .rodata | `0x3C47000..0x484C080` | |
| .data | `0x484D000..0x4D46B80` | |
| .bss | `0x4D46B80..0x4EA0000` | nothing in the game references past `0x4E9A4C8` |

## Functions

| Address | What | Source |
|---|---|---|
| `f_804e48c0` | Builds a camera view's matrix from its eye / target / up. `x0` = camera, `[x0+0x18]` = view (kept in `x20`). | Hookshot, Disasm |
| `0x804e5068` | Inside `f_804e48c0`, first instruction after the matrix is stored (also the join point when eye == target). Hook site for First Person. | Hookshot, Disasm |
| `f_82c415e0` | Movement update for a physics actor, `x0` = actor (kept in `x19`). Runs for Link every frame. | Hookshot, Disasm |
| `0x82c41720` | Inside `f_82c415e0`, after the early setup, on every path. Hook site for First Person. | Disasm |
| `f_806d2530` | Physics controller `ChangePosition` (vtable slot `+0xe8` of `0x84c54f10`). Hookshot's flight cheat calls it to move Link. | Hookshot |
| `f_804bd8c0` | Writes an actor's life (hearts) with a compare-and-swap. | Hookshot |
| `f_80b1e140` | Steps a text pane's letter animation (text speed). | Hookshot |
| `f_828d4a70` | `OneShotAddOrRemovePouchContent`: add / remove an inventory item by actor name. | Hookshot |
| `f_831f3200` | Dynamic resolution apply block. | Hookshot |
| `f_804d6db0` | Is the actor child Link? `(actor)` → bool. Fast path `[[actor+0x270]+0x358]+0x1c5d` (bit 8 valid, bit 0 child), else GameData. Used by `QueryPlayerIsChild`. | Disasm |
| `f_80853d60` | Script command → the actor it runs on: `[[[cmd+8]+8]+0x1f0]`. | Disasm |
| `0x82959ea0` | `OneShotSetModelVisible` execute (vtable `0x84a548d0` slot 39): `model = [[actor+0x270]+0x260]`, writes the visible byte `+0xe5`, sets bit `0x800` of `+0x120`. | Disasm |
| `0x82be6cd0` | Debug printer for why an actor isn't drawn: flags `[[actor+0x380]+8]` bit 8 Demo, 9 TL(SelectiveFC), 10 Model, 11 Event, 12 ActorVisibleOffByEvent, 23 ModelAlphaLink. | Disasm |
| `0x83489500..0x834896b0` | The game's own controller polling (`GetNpadStates` with 16 entries). | Disasm |

All ~5,200 script commands (`OneShot*`, `Query*`, `Execute*`, ...) and their functions are in
[`symbols/e0f3ccfa-commands.csv`](../symbols/e0f3ccfa-commands.csv); see [script-commands.md](script-commands.md).

## Globals

| Address | What | Source |
|---|---|---|
| `0x84ca6bc0` | Pointer to the camera manager pointer. See [structures](structures.md#camera-manager). | Hookshot |
| `0x84c9e180` | `GameDataMgr` singleton slot | Hookshot |
| `0x84c9e090` | `EventMgr` singleton slot | Hookshot |

## Vtables

| Address | Class | Source |
|---|---|---|
| `0x84c18a88` | Camera view (matrix, eye, target) | Hookshot, Disasm |
| `0x84b45e18` | Physics actor passed to `f_82c415e0` (has position + rotation) | Hookshot |
| `0x84b6c460` | Player-type actor (Link and others: check the resource name) | Hookshot |
| `0x84c54f10` | Link's physics character controller | Hookshot |

## Imports (PLT stubs → GOT slots)

| Stub | GOT | Function |
|---|---|---|
| `0x83c627f0` | `0x84cdf5c0` | `nn::hid::GetNpadStates(NpadJoyDualState*, int, uint const&)` |
| `0x83c62800` | `0x84cdf5c8` | `nn::hid::GetNpadStates(NpadFullKeyState*, int, uint const&)` |
| `0x83c62830` | `0x84cdf5e0` | `nn::hid::GetNpadStates(NpadHandheldState*, int, uint const&)` |
| `0x83c64810` | `0x84ce05d0` | `nn::hid::GetKeyboardState(KeyboardState*)` (the game reads it itself at `0x83b48820`) |

The full import list is easy to regenerate from `.rela.plt` (`DT_JMPREL`). Every Switch 2 module
also uses packed `DT_RELR` relocations for its own pointers.
