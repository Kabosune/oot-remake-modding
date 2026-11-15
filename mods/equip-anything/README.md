# Equip Anything

Child and adult Link can pick every item and piece of equipment in the pause menu: child Link with
the Master Sword, the Hylian or Mirror Shield, the Fairy Bow, the Hookshot, the tunics and boots;
adult Link with the Kokiri Sword, the Slingshot, the masks, and so on.

**Status, 14 November 2026: version 0.1.0, built, not tried in the game yet.** Game 1.1.1. A quick
mod: what the game does with an item that was never meant for that age (models, animations, holding
it) is untested and may look wrong or crash.

## How it works

The pause menu reads which age can use each item from one table,
`UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml`: every item row has `IsUsableChild`
and `IsUsableAdult`. This mod sets both on every row the menu shows (59 flags on 1.1.1). The rows
the menu never shows (`NoDisplayArray`: Deku Seeds, Normal Boots, ...) are left alone.

The changed file is 424 bytes bigger; the game's size table already sets aside 46,824 bytes for
it, so the size table isn't changed. No code: KaeGae Core isn't needed, and the mod works next to
any Core mod.

Not in 0.1.0: taking off the sword or shield. The table has no setting for that (masks and boots
come off because their rows are a `SpecialDeal: Mask` / `Boot` button); it needs code, likely a
Core mod.

## Building

The game's file can't be in this repository, so build the mod from your own dump:

```
python3 mods/equip-anything/build.py <dump>/romfs/UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml "Equip Anything"
```

Then copy the `Equip Anything` folder into the emulator's `load/0400486024DEC000/` folder (or
`python3 tools/kaegae.py install "Equip Anything"`).

## Credits

KaboWabo/Kabosune (me :3), with AI assistance (Claude Opus 5.5).
