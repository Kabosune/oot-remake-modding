# Script commands

The game's AINB graphs (AI, level logic, game sequence) are built from named commands, and every one
is a C++ class in `main`. [`symbols/e0f3ccfa-commands.csv`](../symbols/e0f3ccfa-commands.csv) lists
all 5,238 of them with the address of their code: 4,953 have at least one class-specific function.

| Family | Count | What they do |
|---|---:|---|
| `Query*` | 2,090 | answer a question (`QueryPlayerIsChild`, `QueryIsInWater`, ...) |
| `Execute*` | 1,266 | ongoing actions that run over several frames |
| `OneShot*` | 1,117 | do one thing once (`OneShotSetModelVisible`, `OneShotAddOrRemovePouchContent`, ...) |
| `Seq*` | 644 | game-flow versions (`SeqOneShot*`, `SeqQuery*`, ...) |
| `Hold*`, `Trigger*` | 119 | conditions held over time, events |

Categories (the `category` column): `AI` 4,636, `Sequence` 456, `Logic` 119, `CommonSequence` 24.

## Columns

| Column | What |
|---|---|
| `name` | the command name, as AINB files refer to it |
| `vtable_slot0` | address of the vtable entry holding `getName()` |
| `binder_slot9` | registers the command's inputs and outputs (their type names, like `"Bool"`, are strings in it) |
| `main_slot20` | **the command itself**, for `OneShot` / `Query` / `Trigger` / `SeqOneShot` / `SeqQuery` |
| `slot10`–`slot12` | `Execute*` / `Seq*` keep their code here instead. Guess: enter / update / leave. |

Empty cells are slots that only contain shared base-class code.

## How it was found

Each class has a `getName()` that is just `adrp x0, <string>; add; ret`. Pointers to those
functions in the data section are the class vtables. Comparing many vtables shows which slots are
class-specific. [`tools/gen_commands.py`](../tools/gen_commands.py) does all of it from a flat
`main`, so the table can be regenerated for another build.

Checked against independent findings:
- `OneShotAddOrRemovePouchContent` → `f_828d4a70`, the same function Hookshot calls by hand to add items.
- `OneShotSetModelVisible` → `0x82959ea0` writes the model's visible byte, which First Person's `;`
  key now uses in game.

## Using a command

The actor a command runs on is `[[[cmd + 8] + 8] + 0x1f0]` (that's `f_80853d60`). From there, the
command's code shows which component and which field it touches. For example, `QueryPlayerIsChild`
(`0x82ae47d0`) gets the actor, calls `f_804d6db0(actor)` and writes the result as its output.

## Ghidra

[`tools/ghidra_label_commands.py`](../tools/ghidra_label_commands.py) names every function in the CSV
(`OneShotSetModelVisible_main`, `..._binder`, ...). Load `main.bin` as raw AArch64 at base
`0x80020000`, then run the script from the Script Manager.
