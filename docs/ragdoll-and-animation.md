# Ragdoll, faces and voices (build E0F3CCFA)

How a mod can drop Link into ragdoll, move and throw him, and play his expressions and voice lines.
Found for [Mouse Grab](../mods/mouse-grab/README.md), November 2026. "Tested" means it worked in
Fritchii v5.6; everything else is read from the disassembly.

All calls below run on the game's thread (from an actor's movement update; see
[modules.md](modules.md#hook-points)).

## Objects

```
components = [actor + 0x270]
holder     = f_80857620(actor)          [[[components + 0x50] + 0x20] + 0x10]; no null checks inside
controller = [holder + 8]               CharacterProperty, vtable 0x84c54f10 (ChangePosition f_806d2530)
body       = [controller + 0x20]        the controller's body, vtable 0x84c54658
ragdoll    = f_806188c0(holder)         a component of holder, looked up by type; 0 if none
player     = [components + 0x358]       [player + 0x18] == actor
personality = [components + 0x340]
```

Only `Player` has a ragdoll component among about 500 actors surveyed in Castle Town, the Market,
Hyrule Field and Kokiri Forest (NPCs, soldiers, animals, Skulltulas: none). The romfs has enemy
ragdoll data (`Phive/Ragdoll/Structure/Enemy_Common`, `EnemyBase`) and ragdoll landing sounds for
Lizalfos, Dinolfos, Bubbles and Gohma larvae; not surveyed yet.

## Starting and ending the ragdoll (tested)

What `ExecuteEventPlayerImmediateRagdollDown` does on entering (`f_826d3ec0`):

```
f_809539f0(player, 0.0)
f_80992a40(player, ZERO, 0)             ZERO = [0x84c9ddc0], points to (0, 0, 0, 1)
f_8094fde0(player, ZERO, 0)
u32 [player + 0x1030] = 0
f_80953270(player, 0, NAMES, 15, 0)     NAMES = [0x84c9f168]: "SlippingDown", "SlippingDownLand"
f_83238d30(ragdoll, &request)           request (0x30 bytes): +0 actor, +8 f32 1.0, +0x1c u32 1,
                                        +0x20 u32 2, rest 0; builds the name "ImmediateDown"
```

Without the `player` preparation the request is accepted (state 3) but a ragdoll started in the
air only shows once he lands. Ending, as the node does when it leaves (`f_826d42c0`):

```
f_83239090(ragdoll, &{ actor, u8 0 })
u8 [player + 0x1c3e] |= 1
```

`u32 [ragdoll + 0x17c]` is 3 while he's down and 0 otherwise. He doesn't get up by himself without
the node's per-frame update (`f_826d3fb0`, not copied).

## The ragdoll's bodies (tested)

`f_83237d70`, which the start request calls to hand the controller's velocity to the ragdoll, shows
where they are:

```
set     = [ragdoll + 0x40]
count   = [set + 0x60] - 1                  18 for Link
entries = [set + 0x68], 0x138 bytes each
body i  = [entries + 0x138 * i + 0x38]      wrapper vtable 0x84c578c0 (not the controller body's)
```

`f_8014dbe0(body, f32 velocity[3], 0)` sets a body's linear velocity; it works on these and on the
controller's body. `f_80142750(body, f32 out[3], 1)` reads it. Setting every body's velocity each
frame carries him limp; setting it once on release throws him.

Moving the controller with `ChangePosition` doesn't move a ragdoll: the game pulls the controller
back to the ragdoll every frame (he twitches and Navi, who follows the controller, flies around).
Characters without a ragdoll can be carried that way (tested with Hylians and Kokiri).

## Playing an AS command: faces, voices, animations

An actor's animation sequencer file (`AS/<actor>.root.asb`, see [asb.md](asb.md)) names its
commands; Link's (`AS/Player_Child.root.asb`, 471 commands, entries 0x30 bytes from header `+0x10`)
include `FaceDamageL`, `FaceDown`, `FaceParalysis`, `FaceDefault`, `DeadRagdoll`, and about 120
`Voice*` lines (`VoiceDamageL`, `VoiceDamageKidnapped`, `VoiceFallDanger`, `VoiceDeath`, ...).

`OneShotASPlay` (`f_80221f80`) fills a request and calls `f_802222a0(&request)`:

| Offset | Field |
|---|---|
| `+0x00` | actor |
| `+0x08` | command name (`char*`) |
| `+0x10` | partial: index in the actor's partial list, 0 when none is given |
| `+0x14` | play rate (`PlayRate`, 1.0) |
| `+0x18` | two f32, -1.0 in every caller seen |
| `+0x20` | `IsIgnoreSameCommand` (u8) |
| `+0x28` | the calling node (passed on to a profiler-like global) |

The partial list is in the actor's animation resource
(`[[[[[[actor+0x270]+0x40]+0x18]+0x18]+0x48]+0x10]`, names via the header's string pool; lookup
`f_80aed6d0(actor, &name)`). Link's: Lower 0, Upper 1, RightArm 2, LeftArm 3, Face 4, Finger 5,
Mouth 6, MaskChange 7, MaskEquip 8. `OneShotPersonalitySetOverwritePartialSlotFace` writes such an
index to `[personality + 0x3c]` (with `[personality + 0x27] |= 1`): it picks which partial is the
face, not an expression.

Untested as of 10 November: `FaceDamageL` on partial 4 and `Voice*` on partial 6, from a mod with a
zeroed stand-in for the node.
