# Equip Anything

Child and adult Link can pick every item and piece of equipment in the pause menu: child Link with
the Master Sword, the Hylian or Mirror Shield, the Fairy Bow, the Hookshot, the tunics and boots;
adult Link with the Kokiri Sword, the Slingshot, the masks, and so on. And picking an equipped
sword, shield or tunic again takes it off.

**Status, 18 November 2026: 1.0.1 works in the game** (Fritchii v6.1, game 1.1.1; 1.0.0 not
tried, though every address comes from Core's names). It needs **KaeGae Core 0.9**. Download:
[`releases/equip-anything.zip`](../../releases/equip-anything.zip).

What the game does with an item that was never meant for that age (models, animations, holding
it) is untested and may look wrong.

## Settings (on the Mods menu)

| Setting | Default | What it does |
|---|---|---|
| Any age can equip | on | Both ages can pick every item. Off puts the game's own rules back. |
| Pick again to take off | on | Picking an item that is already equipped takes it off (Link then has no sword or shield). |

## How it works

**Any age.** The pause menu reads which age may use an item from its table
(`UI/Pouch/PouchTable/PouchTable.game__ui__PouchTable.bgyml`), as the game parsed it: each item has
`IsUsableChild` and `IsUsableAdult`, each with a "set here" byte (0 = take it from the table's
parent, or false). The mod finds the table through Core's names (`PouchMgrPtr`, then the fields
`PouchMgr.ui`, `PouchUi.table`, `PouchTable.pages`, `PouchButton.items`, `PouchItem.*`), sets
both flags on the items of the menu's seven pages, and keeps what it found so switching the
setting off puts it back. A button that already has an item of its own for an age is left alone
for that age (1.0.1): the Kokiri Tunic's button holds `Obj_Armor_Child_Normal` (child) and
`Armor_Adult_Normal` (adult), and the menu equips the first item the age may use. It looks again every second, in case the game loaded the table anew. The
table's eighth array (+0x88) isn't one of the menu's pages and is left alone, as 0.1.1 left
`NoDisplayArray` alone.

**Taking off.** Core 0.9's `pouch_equip` event comes from the game's `PouchEquip`, the function the
pause menu calls to equip an item (the game calls it too, on area loads and in events). When the
call comes from the menu and the item already is in its slot, the mod calls `kae_pouch_unequip`
(the menu's own `PouchUnequip`, which empties the item's `PlayerStatus.Equip...` slot in GameData)
and the game's equip is skipped. Calls from outside the menu are left alone, so the game putting
Link's sword back after a scene doesn't take it off.

The game's equipped items are GameData strings: `PlayerStatus.EquipWeapon`, `EquipShield`,
`EquipArmor`, `EquipBoot`, `EquipHeadArmor` (String64, the item's actor name; empty = none).

## Before 1.0 (14–17 November)

- 0.1.0 changed the table file in the romfs (both flags on every row the menu shows) and crashed
  at boot: the file's resource size table entry also covers the objects parsed from it, so 424
  more bytes of file left too little memory (main's BYML array loader, `0x1903E0` in 1.1.1, then
  called into a missing element). 0.1.1 asked for a bigger entry (`kaegae build`): worked.
- 0.2.0 (`SpecialDeal: Mask` on the sword, shield and tunic buttons) and 0.2.1
  (`IsChangeActorEquipState`) did nothing.
- 0.3.0 added a small patch to main: at `PouchEquip`'s second instruction, "already equipped?
  then `PouchUnequip` and return". Worked. Core 0.9's `Pouch.Equip` hook point is that patch.
- 1.0.0 needs no romfs file, no size table entry and no patch of its own, so it can't clash with
  other mods that ship a whole size table.

## 1.0.1 (18 November): the tunic bug

1.0.0 opened every item to both ages, so the Kokiri Tunic's child item (listed first on its button)
became usable for adult Link too, and the menu equipped that one: adult Link got
`Obj_Armor_Child_Normal` and his look didn't change back from the Goron Tunic for the rest of the
session (it did after a reload). Seen in the emulator's log of 17 November (the Adventure Log's
`965d02dc` is that name's CRC32). 1.0.1 opens an item to an age only where its button has no item
of that age's own. Tested in the game (18 November): the Kokiri and Goron Tunics switch back and
forth, and taking the Goron Tunic off puts adult Link's own Kokiri Tunic back on (with 1.0.0 it
put the child's one in the slot).

## Building

```
python3 tools/kaemod.py mods/equip-anything --no-core --name "Equip Anything" --out equip-anything.zip
```

Install it next to KaeGae Core 0.9 (its module is `subsdk2` in the zip: give it a free slot, or use
`python3 tools/kaegae.py install`).

## Credits

KaboWabo/Kabosune (me :3), with AI assistance (Claude Opus 5.5).
