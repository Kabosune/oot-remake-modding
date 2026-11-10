# Animation graphs (`AS/*.root.asb.zs`)

Each actor's animation logic is an ASB file: named **commands** (what an event flow or AI asks for,
like `C10` or `Wait`) that point into a graph of **elements** (play this animation, pick by a value,
play in sequence, control the playback rate, ...).

All 919 files in `AS/` are version `0x41B`. Tears of the Kingdom's are `0x417`, so
dt-12345's asb tool refuses them. [`tools/asbtool.py`](../tools/asbtool.py)
reads the parts below:

```
python tools/asbtool.py ls    Dm_Zora_0010_KingZora.root.asb
python tools/asbtool.py refs  Dm_Zora_0010_KingZora.root.asb
python tools/asbtool.py check my_edited.root.asb
```

Everything here was found by reading the files and checked by a survey of all 919 (214,598 elements).
Nothing here comes from the game's code yet, so field meanings marked "?" are guesses from the data.

## Header (0x80 bytes, 32 words)

| Offset | What |
|---|---|
| `0x00` | `"ASB "` |
| `0x04` | version `0x41B` |
| `0x0C`, `0x10` | command count, command array |
| `0x14`, `0x18` | element count, element array |
| `0x1C` | event count. Always equals the number of Event elements (type 10) |
| `0x20`, `0x24` | calc controller array, count ? (the count matches the elements' total in 669 of 919 files) |
| `0x2C`, `0x30` | attachment count ? (matches the elements' total in 777 of 919 files), attachment array (0x18 bytes each, param pointer at +4) |
| `0x34` | attachment index array |
| `0x3C` | string pool. Always the last section in the file |
| `0x60` | string pool size. Pool + size = file size |

The other pointer words are `0x28`, `0x38`, `0x40`, `0x44`, `0x48`, `0x54`, `0x5C`, `0x64`, `0x68`, `0x6C`,
`0x70`, `0x7C`. All pointers in the file are absolute file offsets. String offsets are relative
to the string pool. Sections come in one of four orders; the string pool is last in all of them.

## Commands (0x30 bytes)

`+0x00` name (string offset), `+0x04` tag pointer, `+0x08` a float property (`-1` in cutscene files),
`+0x2C` u16 index of the command's root element.

## Elements (0x24 bytes)

| Offset | What |
|---|---|
| `+0x00` u16 | type (below) |
| `+0x02` u8 | attachment count |
| `+0x03` u8 | flags, 1 or 3 |
| `+0x04` | tag pointer (0 = none) |
| `+0x08` | pointer to this element's param block |
| `+0x0C` u16 | calc controller start index |
| `+0x0E` u16 | calc controller count |
| `+0x10` u16 | attachment start index |
| `+0x12` u16 | ? (non-zero in 897 elements) |
| `+0x14` | GUID (16 bytes) |

**The two start indices are running sums over the element array, and every element has them, even
when its own count is 0.** An element with no attachments after ten attachments' worth of earlier
elements still says 10. This holds for all 214,598 elements in the game. If you add an element by
hand, fill these in.

Param blocks are stored in the same order as the elements.

Types seen (count in the game): 3 SkeletalAnimation (84,685), 10 Event (31,982), 7 Sequential
(24,348), 16 PreviousTagSelector (10,540), 19 InitialFrame (8,971), 20 BoneBlend (8,738), 6 Blend1D
(8,707), 8 IntSelector (8,329), 21 BoolSelector (7,618), 12 FrameController (7,221), 14
RandomSelector (2,760), 1 FloatSelector (2,713), 2 StringSelector (1,632), 9 Simultaneous (1,579),
27 ? (1,359), 11 MaterialAnimation (1,354), 18 BoneAnimation (758), 17 BonePositionSelector (574),
13 Dummy (463), 26 Blend2D (112), 23 SubtractAnimation (81), 4 State (47), 22 Alert (27). The names
follow TotK's ASB node types and haven't been checked against this game's code.

## Properties

A value in a param block is 8 bytes: flags, then the value (a float, an int, or a string offset).
Bit 31 of the flags means the value isn't literal (it comes from a blackboard or similar).

## Plugs: how elements point to each other

A param block has a 12-byte plug header: six (count, first index) byte pairs, for **state, ?, child,
transition, event, frame controller** plugs. Then one u32 per plug: an absolute offset to a u32
holding the target element's index (for a transition, the index is 4 bytes further in).

The header's place in the param block depends on the type: SkeletalAnimation `+0x20`, FrameController
`+0x78`, Sequential `+0x18`, State `+0x00`.

**SkeletalAnimation** (type 3): `+0x00` the animation's name (string property), plug header at `+0x20`.
With no plugs the block is 0x2C bytes; each plug adds 8 (offset word + index word).

**FrameController** (type 12): `+0x00` rate, `+0x08` start frame, `+0x10` loop count ?, `+0x54` end
frame (`-1` = to the end), plug header at `+0x78`. Always 0x84 bytes, never any plugs of its own.

A SkeletalAnimation gets its playback rate by pointing to a FrameController through its **frame
controller plug**. The target is always a FrameController or an InitialFrame (type 19), and it can
come before or after the animation in the element array. 403 commands in the game are exactly this:
command → SkeletalAnimation → frame plug → FrameController with a literal rate. Example,
`Animal_Butterfly.root.asb`: element 4 (an animation) → element 5 (rate 1.1).

## Editing by hand

Nothing writes this format yet. To change a literal value (a rate, an animation name's offset),
change it in place. To add an element, every later section moves, so every absolute pointer after
the insert has to be shifted: header words, command and element tag pointers, element param
pointers, plug offset words, attachment param pointers. Then:

1. Run `asbtool.py check`. It tests: string pool last and its size, both running indices, param
   block order, plug targets, the event count.
2. A longer file with more elements needs more memory to load. Raise its entry in the resource
   size table ([romfs.md](romfs.md#the-resource-size-table)).

Not known yet: how the game reacts to a file that breaks these rules. The one hand-edited file tried
in game so far broke three things at once (new data placed after the string pool, a wrong
attachment start index on the added element, no size table change): the cutscene ran, but the
command using the new element never played. Which of the three caused that isn't known.
