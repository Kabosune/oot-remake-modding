# Dynamic lights (the LocationalLight manager)

How the remake lights things that move: lamps, torches, glowing switches, Navi, and lights an event
makes on the spot. Found 22 November 2026 in both `main`s (1.0.0 `33FA6C2C`, 1.1.1 `E0F3CCFA`) and
the romfs, for [Flashlight & Lantern](../mods/flashlight-lantern/README.md). Nothing here is checked
in the game yet: the in-game test of Flashlight & Lantern 0.1.0 is the first.

## The data

- `System/GameGraphics/LocationalLightMgrInitializeParam/Main.game__gfx__LocationalLightMgrInitializeParam.bgyml`:
  the pools' sizes. `Light_PointNum` 400, `Light_SpotNum` 600, `Light_LineNum` 64,
  `Light_AmplifierNum` 112, `Rig_ObjNum` 512. **`Light_NaviNum`** is a field too (Navi has a pool
  of her own) but `Main` doesn't set it, so it has the code's default.
- `LocationalLightPointSetting/*.bgyml`, `LocationalLightSpotSetting/*`: placed lights. The light
  model is physical: `Color` (RGBA), `Intensity`, `SourceRadius` (m), `ColorTemperature` with
  `IsUseColorTemperature`; spots add `InnerAngle` / `OuterAngle` (degrees), `Latitude` /
  `Longitude`. No range: the falloff is the light's own. Intensities seen: torches 1.2 to 9, a
  castle fire 9, lava 500; spots 8.5 to 165 (a low sun 17,000).
- `LocationalLightRigGroupSetting/*` (listed in `LocationalLightRigSettingList/Main`): lights fixed
  to an actor's bones ("rigs"), by actor and `BonePrefix`, with a `PointLightRigSetting` and / or
  `SpotLightRigSetting` (`LocationalLightRigPointSetting/*`, `...RigSpotSetting/*`, which add
  `FlickeringIntensityRate`, `FlickeringSpeed`, `PositionOffset`). Groups: Npc, Enemy, Gimmick0-7,
  Demo, Entrance, ... **Neither Navi nor Link is in any group.** A rig is the data-only way to put a
  light on an actor: adding Link to a group (romfs mod) would give him a fixed light, but couldn't be
  switched in the game.
- Navi's glow: no light file in `Pack/Actor/Npc_Navi.pack` (no rig, no light component; its
  `NaviParam` and `NaviMgrGlobalParam` have no light fields). It comes from code: the manager's
  Navi pool (`Light_NaviNum`), and the environment palettes have `IsOverWriteNaviLight` and
  `NaviLightIntensity` (the palette binder at 1.1.1 `0x34277E0`), so each area's look can set how
  bright Navi is. Who takes Navi's light from the pool wasn't traced.

## The manager in `main`

| | 1.1.1 | 1.0.0 |
|---|---|---|
| pointer the code reads first (`[main + this]`, through the GOT) | `0x4E3E258` | `0x4DCE228` |
| holder = `[that + 0x1E8]`; holder byte `+0xE20` bit 1 = lights usable | same | same |
| manager = `[holder + this]` | `+0xBA0` | `+0xBA8` |
| named-light insert `(mgr, light, hash)` → 1, or 0 if the name is taken | `0x31C9A30` | `0x3173B20` |
| named-light find `(mgr, hash)` → light or null | `0x31C9AA0` | `0x3173B90` |
| `OneshotCreateLocationalLight`'s execute (vtable `+0x100`) | `0x295F8C0` | `0x290D570` |
| `OneshotEditLocationalLight`'s execute | `0x2961290` | |
| free every named light, empty the map | `0xF09FA0` | |
| manager vtable / constructor | `0x4B8A898` / `0xEAD620` | |

- **Pools:** `[mgr + 0x58 + 8 * kind]`, five of them. A pool's vtable slot 2 (`+0x10`) gives a free
  light (null when full), slot 3 (`+0x18`) takes one back `(pool, light)`. A light's vtable slot 6
  (`+0x30`) says which pool it's from. Kinds: **0 point, 1 spot** (the create action writes the
  spot fields only for 1, and checks the light against the spot light's type info first). The
  rig code (1.1.1 `0x2BCA580`) maps its own light types to pools 0-4 and sends one of them to pool
  3; with the init param's order (Point, Line, Spot, Navi, Amplifier) pool 3 is most likely
  Navi's. Not checked.
- **Named lights:** `mgr + 0xD0E0` holds a table of 16-byte entries `{u32 hash, pad, light}`,
  `+0xD0E8` the count, `+0xD0EC` the capacity; open addressing from `hash % capacity`, 0 = empty.
  The hash is MurmurHash3 (seed 0) of the action's `LightHash` string (the function at 1.1.1
  `0x1739E0`). A second table at `+0xD0F0` is for `LocationalLightCreateType` 1 (the create action
  only makes type 0). There's no function to remove one name: `0xF09FA0` frees every light in the
  table and empties it (when the lights are cleared, most likely on area changes).

## A light object

Common to the kinds (both versions):

| Offset | | |
|---|---|---|
| `+0x00` | vtable | slot 4 (`+0x20`) = the type check (sead RTTI), slot 6 (`+0x30`) = its pool, **slot 9 (`+0x48`) = set position** `(light, x, y, z)` (floats in s0-s2) |
| `+0x18` | f32[4] | colour, RGB divided by its luminance (0.299, 0.587, 0.114), A = 1 (the edit action does the division) |
| `+0x28` | f32 | intensity (the create action starts at 25) |
| `+0x2C` | f32 | source radius in metres (starts at 0.1; the edit action keeps it at least 0.001) |
| `+0xF8` | u64 | set to 0 by the create action |
| `+0x108` | u32 | a tag: 7 for the action's lights, 3 for rig lights. `0xF09FA0` takes every non-7 light out of a list at `mgr + 0xD090` |
| `+0x132` | u8 | flags: bit 0 set by the create action while it sets the light up (and left set); the rig code sets bits 5 and 7 from its params |

Spot lights also: `+0x158` f32[3] the direction (unit), `+0x164` the inner angle and `+0x168` the
outer angle (radians: the action turns its degrees into radians and clamps them to about
0.005 .. 3.13, outer above inner), `+0x16C` = 0.

## Making a light at run time

What `OneshotCreateLocationalLight` does (inputs `LocatioinalLightCreateType` [sic], `LightType`,
`LightHash`, `Position`, `Rot`, `Offset`, `Direction`, `IsEnableRot`, `InnerAngle`, `OuterAngle`):
take a light from pool `LightType`, set `+0xF8` = 0, `+0x108` = 7, `+0x132` |= 1, set its position
(Position + Offset, rotated by Rot if IsEnableRot), white at 25 with radius 0.1, the spot fields
for a spot, then insert it under the hash of `LightHash`; if that name is taken, give the light
back. The light then shines until the lights are cleared. `OneshotEditLocationalLight` (inputs
`LightHash`, `EditColor` / `Color`, `EditIntensity` / `Intensity`, `EditSourceRadius` /
`SourceRadius`, `IsFrameTtransition` [sic], `FrameTransitionCount`) finds a light by its name and
writes those fields straight in.

Flashlight & Lantern does the same from Link's `player_move` event, and each update finds its
lights again by name (a different name per kind), so after the manager clears them it makes new
ones instead of writing into freed lights.

Other event actions around lights (not looked at): `OneshotCreateLocationalLightAtEventCenter`,
`OneshotEditLocationalLightAmplifier`, `OneShotGraphicsRequestSetAmplifierLightParam`,
`TriggerRequestSetLocationalLightRigParam`, `ExecuteModelRigLightIntensity`,
`ExecuteModelRigLightDayTimeIntensity`, `OneShotModelRigLightSetSleep`,
`SeqExecuteApplyLocationalLightScenePlacement`.

## Credits

KaboWabo/Kabosune (me :3), AI assistance (Claude Opus 5.5).
