# Flashlight & Lantern

Two real lights that follow Link, made with the game's own dynamic lighting:

- **Lantern**: a glow all around Link, like Navi's light. Brightness, colour (warm, white, Navi
  blue, fairy green, fire red), size, height, and a glow style (steady, candle flicker, or a slow
  pulse like Navi).
- **Flashlight**: a beam out of Link's chest, where he faces (or where the camera looks).
  Brightness, colour, beam width, tilt, height and how far in front of him it starts.

Both are switched on and off on the mod's page in KaeGae's Mods menu (- and + together), and each
can get a button to switch it while playing. **0.1.0 is a test build**: for now both lights shine
out of Link himself (later the flashlight and lantern can be items he holds).

A core mod: it needs [KaeGae Core](../../api/README.md) 0.8 or later.

## Settings

| Setting | Default | What it does |
|---|---|---|
| Lantern | on | The lantern's light |
| Lantern on / off | (none) | A button to switch the lantern while playing |
| Lantern brightness | 12 | The light's intensity (the game's torches use about 1 to 10, lava 500) |
| Lantern colour | Warm | |
| Lantern glow | Steady | Steady, Candle flicker, Navi pulse |
| Lantern height (cm) | 110 | Above Link's feet |
| Lantern size (cm) | 30 | The light's own radius: bigger is softer |
| Lantern light kind | Point light | Point light, or a light from the pool the game keeps for Navi (a test: what it does there isn't known yet) |
| Flashlight | off | The flashlight's beam |
| Flashlight on / off | (none) | A button to switch the flashlight while playing |
| Flashlight brightness | 80 | The beam's intensity (the game's spot lights use about 10 to 200) |
| Flashlight colour | White | White, Warm, Cool |
| Beam width (degrees) | 25 | The beam's outer angle; its bright middle is 60 % of it |
| Flashlight aim | Where Link faces | Or where the camera looks (nice with First Person) |
| Beam tilt down (degrees) | 10 | For "Where Link faces" |
| Flashlight height (cm) | 90 | Above Link's feet |
| Flashlight forward (cm) | 30 | In front of Link |
| Show status | off | Two lines on screen: whether each light exists, its kind, how often it was made |

Switching a light off makes it dark; the light itself stays until the area changes (the game has
no way to give back one named light). Switching the whole mod off in the Mods menu stops its
updates, so the lights stay as they were until the next area: use the two switches instead.

## How it works

The game draws its lamps, torches and Navi's glow with its LocationalLight manager. Events make new
lights with an action called `OneshotCreateLocationalLight`; this mod makes its two lights the same
way that action does (a light from the manager's point or spot pool, set up and given a name), then
moves them with Link every frame. If the area changes and the manager clears its lights, the mod
notices the name is gone and makes new ones. Details: [docs/lights.md](../../docs/lights.md).

## Game versions

Reads the light manager by each version's own addresses, for 1.0.0 and 1.1.1 (found in both
`main`s). Not tried in the game yet. Those addresses move into KaeGae Core's symbol packs at the
next Core release.

Installing by hand: the zip's module is `exefs/subsdk2`; rename it to a slot no other switched-on
mod uses (`python3 tools/kaegae.py install` does that for you).

## Credits

KaboWabo/Kabosune (me :3), AI assistance (Claude Opus 5.5).
