# Equip Anything

Child and adult Link can pick every item and piece of equipment in the pause menu: child Link with
the Master Sword, the Hylian or Mirror Shield, the Fairy Bow, the Hookshot, the tunics and boots;
adult Link with the Kokiri Sword, the Slingshot, the masks, and so on.

**Status, 17 November 2026: 0.1.1 works (every item equips for both ages). 0.3.0 (taking things off) not tried yet.** (0.1.0 crashed at
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

**Taking things off (0.3.0, test): the `unequip/` folder**, a second mod folder, `Equip Anything
(unequip)`: a small patch to main (game 1.1.1; no Core needed). The table has no setting for it:
0.2.0 tried `SpecialDeal: Mask` on the sword / shield / tunic buttons and 0.2.1 tried
`IsChangeActorEquipState`; neither did anything (14 Nov), so 0.3.0's table is 0.1.1's again.

What the game does: the equipped items are GameData strings, `PlayerStatus.EquipWeapon`,
`EquipShield`, `EquipArmor`, `EquipBoot`, `EquipHeadArmor` (String64, the item's actor name; empty
= nothing equipped; struct and member hashes are MurmurHash3 of the names). The pause menu's
equip function is `0xA7ACD0 (menu, name, mode, flag)`; `0xA71080 (menu, name)` says whether an item
is equipped; `0x33A6A40 (menu, name, flag)` is the menu's own unequip: it finds the item's category
and writes the game's empty string into that slot. The menu object is the global at `0x4E78E28`.

The patch: the equip function's second instruction (`0xA7ACD4`) jumps to a stub in the last 48
bytes of `.text` padding that asks `0xA71080`; when the item is already equipped it calls
`0x33A6A40` from padding slot 128 and returns, otherwise it carries on equipping. Source:
`unequip/unequip.S`, built by `unequip/build_ips.py`; its claim is in `registry/e0f3ccfa.toml`.
Not known yet: whether the menu calls the equip function at all for an item that's already
equipped, and whether the game calls it outside the menu (if Link loses his sword when a save
loads, that's why).

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
