# Equip Anything

Child and adult Link can pick every item and piece of equipment in the pause menu: child Link with
the Master Sword, the Hylian or Mirror Shield, the Fairy Bow, the Hookshot, the tunics and boots;
adult Link with the Kokiri Sword, the Slingshot, the masks, and so on.

**Status, 14 November 2026: 0.1.1 works (every item equips for both ages). 0.2.0 (unequip test) not tried yet.** (0.1.0 crashed at
boot: see below). Game 1.1.1. A quick
mod: what the game does with an item that was never meant for that age (models, animations, holding
it) is untested and may look wrong or crash.

## How it works

The pause menu reads which age can use each item from one table,
`UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml`: every item row has `IsUsableChild`
and `IsUsableAdult`. This mod sets both on every row the menu shows (59 flags on 1.1.1). The rows
the menu never shows (`NoDisplayArray`: Deku Seeds, Normal Boots, ...) are left alone.

The changed file is 424 bytes bigger. Its resource size table entry (46,824 bytes) covers more than
the file: the game builds the menu's objects in that same memory. 0.1.0 left the entry as it was,
and the game crashed at boot (about 31 s in, before the title screen): its BYML reader in `main`
(`0x1903e0`, a reflection loader that fills an array of objects from a BYML array) found the third
object of a three-item array missing, apparently because the memory ran out, and called into it.
0.1.1 asks for the entry to be raised to 49,296 (the growth plus 2,048 spare) with a
`[[romfs-patch]] kind = "size-table"` line in its `mod.toml`; `kaegae build` writes the changed
table. No code: KaeGae Core isn't needed, and the mod works next to any Core mod.

**0.2.0 (test):** every equipment button with no `SpecialDeal` (swords, shields, tunics, Stone of
Agony) gets `SpecialDeal: Mask`, the setting that lets a mask come off when it's picked again.
Whether the game's mask code does the same for those slots is what the test shows.

Before 0.2.0: taking off the sword or shield. The table has no setting for that (masks and boots
come off because their rows are a `SpecialDeal: Mask` / `Boot` button); it needs code, likely a
Core mod.

## Building

The game's file can't be in this repository, so build the mod from your own dump:

```
python3 mods/equip-anything/build.py <dump>/romfs/UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml "Equip Anything"
```

Then copy the `Equip Anything` folder into the emulator's `load/0400486024DEC000/` folder (or
`python3 tools/kaegae.py install "Equip Anything"`), and build the size table:

```
python3 tools/kaegae.py build --game-table <dump>/romfs/System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs
```

That writes a `KaeGae Built Files` folder next to it. Without it the game crashes at boot. Instead,
`build.py ... --game-table <that file>` puts the changed table inside the mod's own folder, but then
it overwrites any other mod's table.

## Credits

KaboWabo/Kabosune (me :3), with AI assistance (Claude Opus 5.5).
