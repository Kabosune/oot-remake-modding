# Kaepora: a shared modding standard for the Ocarina of Time remake

**Draft 0.3, 9 November 2026. A design, not yet software.** Nothing here is implemented or tested
unless it says so. "Kaepora" is a working name (the game's reported codename is Owl).

## Why

Four days after release, mods for this game already step on each other:

- Every code mod patches `main` directly and takes its own piece of one 3.6 KB code cave.
  sloperinaGZ 0.0.3 and the Ultrawide mod claim overlapping bytes of it.
- FPV Drone toggles on L3. So does sloperinaGZ's levitate. Neither knows about the other.
- Any romfs mod whose file grows needs its own copy of the resource size table. Two such mods
  overwrite each other's, and the table is a 1.4 MB game file nobody should be redistributing.
- Every mod finds the game's functions and data again for itself, and hard-codes the addresses.
  A wrong one is fixed in one mod and stays wrong in the others.

Kaepora is a set of rules and shared pieces so that mods from different people can be installed
together, be checked for conflicts before the game starts, and share what is known about the game
instead of each rediscovering it.

**Supported game versions: 1.0.0 and 1.1.1, both.** (1.0.0 is main build `33FA6C2C…`, 1.1.1 is
`E0F3CCFA…`.) Working assumption: 1.1.1 is the game's last update, so nothing is built only to
survive a future one. If one does arrive, the design still copes, since everything
build-specific is in one file per build.

## Goals

1. **Coexistence.** Two mods that follow the standard either work together or are reported as
   conflicting before launch. Never a silent crash.
2. **Longevity.** A mod written against the interface today still loads years from now: the
   interface only ever grows. What is learned about the game is recorded once, by name, for
   every mod.
3. **Works everywhere the game runs.** Emulators (Lichii family), static recompilations where
   possible, and real hardware. Nothing relies on one emulator's quirks.
4. **No game files.** A mod package never contains Nintendo's data, only new code and
   descriptions of changes. Anything derived from game files is built on the user's machine from
   their own dump.
5. **Easy to adopt in steps.** An existing IPS or romfs mod can conform by adding one text file.
6. **Fail safe.** A mod that doesn't fit the running game is switched off with a message.

## Three levels

A mod can stop at any level.

| Level | What the mod does | What it gets | Needs a runtime? |
|---|---|---|---|
| 1. Package | Ships a `mod.toml` manifest in a standard folder layout | Conflict checks, clean install / removal, merged shared files | No |
| 2. Registered | Takes its code cave, memory and hook sites from the shared registry | Guaranteed not to overlap other registered mods | No |
| 3. Core mod | Contains no patches to `main` at all; calls the Kaepora Core API | Shares hooks, input and the Mods menu with other mods; no code size limit; no addresses of its own | Yes |

Levels 1 and 2 can be built and used now. Level 3 is where the long-term value is.

## Level 1: the package

```
my-mod/
  mod.toml            the manifest (required)
  README.md
  exefs/<build id>.ips        patches to main (levels 1 and 2 only)
  romfs/...                   whole new files, or files that are entirely the author's own
  romfs-patch/...             described changes to game files (see below)
  code/<id>.nso, <id>.a       a core mod's module (level 3)
```

The manifest ([example](examples/mod.toml)) states what the mod is and everything it touches:

- **Identity:** `id` (`author.mod-name`, lowercase, never reused), `name`, `version` (semver),
  `authors`, `license`, `manifest = 1`.
- **Game:** the title ID and, per supported build, the build ID.
- **Claims:** for each build, the byte ranges of `main` it writes, the memory it uses, and the
  instructions it hooks. Level 2 mods take these from the registry.
- **romfs:** files added, files patched, and resource size table entries it needs raised.
- **Input:** each action the mod listens for and its default buttons (`toggle = "L3"`).
- **Relations:** `requires`, `conflicts`, `load-after`, by mod ID and version range.
- **For core mods:** the API version built against, the symbols and hook points it needs.

A command-line tool, `kaepora`, reads the manifests of everything installed:

- `kaepora check`: compares each manifest with the mod's real IPS bytes, then reports overlapping
  patches, doubly hooked instructions, clashing romfs paths, clashing buttons and unmet
  requirements. It also reads the IPS files of mods with no manifest, so it finds byte overlaps
  with those too. (Run by hand today, this is the check that found the sloperinaGZ / Ultrawide
  overlap.)
- `kaepora install / remove / list`: puts mods in the right place for the target (an emulator's
  `load/<title id>/` folder, or the LayeredFS layout on hardware).
- `kaepora build`: produces the shared files described below from the user's own dump.

### Changes to game files without shipping game files

`romfs-patch/` holds descriptions, and `kaepora build` applies them to the user's dump:

| Kind | Describes | Merges with other mods? |
|---|---|---|
| Size table | "raise entry X to at least N" | Yes: the largest request wins. One table is built for all mods |
| BYML / BGYML | set, add or remove values by key path | Yes, unless two mods set the same key differently |
| Text (Mals) | replace message X in language Y | Yes, per message |
| Binary | a binary diff against a file with a stated hash | No: one mod per file |
| Script | a build step the mod supplies (Python), with declared inputs and outputs | Declared outputs are checked for clashes |

New kinds can be added without changing old mods. Slow King Zora is the test case: today it ships
a hand-edited ASB and a whole size table; under this scheme it ships a script plus one size table
line.

## Level 2: the registry

`registry/<build id>.toml` is the machine-readable version of today's
[memory map](../docs/memory-map.md): who owns which bytes of the code cave, which padding slots,
which part of the free `.bss` tail, and which hook sites. It includes mods that don't follow the
standard (Lichii's built-in patches, Ultrawide, the FPS mods, sloperinaGZ), read from their
patches, so the checker knows about them.

Rules:

- Space is claimed by pull request, first come first served, in the smallest amount that works.
- A hooked instruction belongs to one mod. If two mods need the same place, that place becomes a
  Core hook point (level 3) and both subscribe to it.
- A claim is released when its author gives it up or the mod is withdrawn.
- The memory map page is generated from the registry, not edited by hand.

Raw patching doesn't scale: the cave is 3,632 bytes and the padding between functions comes in
pieces of at most 28 bytes. Level 2 keeps today's mods honest; level 3 removes the limit.

## Level 3: Kaepora Core

### What is known to work

sloperinaGZ shows the loading method on this game, by its own notes verified in Lichii on both
game versions (not yet on hardware, and not yet re-checked by us):

- The game's exefs holds `main`, `rtld`, `sdk` and `subsdk0`. Slots `subsdk1` to `subsdk9` are
  free. A module placed in one is loaded and linked by the game's own `rtld`, which resolves its
  imports against `main` and `sdk` and runs its init function.
- Such a module can redirect `main`'s calls to system functions (controller reading, graphics) by
  rewriting `main`'s import table from inside, with no patch to `main` and no fixed addresses.

Core builds on exactly that, and adds nothing that needs writable or newly allocated executable
memory, which hardware may refuse.

### Shape

```
            main (the game)
              |  import-table redirects (no addresses needed)
              |  + one generated IPS per build for hook points inside the game's code
              v
   subsdk1  Kaepora Core      events, hook points, symbols, input, config, log, draw
              ^        ^
              |        |      the Core API (C, imported by name)
   subsdk2  mod A    subsdk3  mod B   ...
```

- **Core** is one module in `subsdk1`.
- **A core mod** is its own module in a free slot. The installer assigns slots at install time
  (the file name is the slot). Mods import Core's functions by name; `rtld` connects them.
- Slots `subsdk2` to `subsdk8` are for core mods: seven at once. `subsdk9` is left alone, since
  standalone mods (sloperinaGZ) already use it. Every core mod also ships a static library, so a
  later version of the installer can link many mods into one slot and lift the limit of seven
  without mods changing.

### What Core gets without knowing any addresses

By wrapping the game's imports, which are found by name:

- **A call every frame**, from the game's controller polling.
- **Input:** read every controller, and hide buttons or sticks from the game.
- **The moment before a frame is shown**, for drawing on top (sloperinaGZ does this by copying a
  CPU-drawn panel into the frame, which avoids needing Switch 2 shader tools).
- **Files** on the SD card through the system's file functions, for settings and logs.

A mod that only needs these works on any build of the game.

### Symbol packs: everything build-specific in one place

Anything inside the game's own code or data is reached by **name**, never by address.

`symbols/<build id>.toml` maps names to locations for one build:

```toml
[function.CctChangePosition]
offset = 0x6B2530
args = "controller, float pos[4]"
source = "Hookshot; sloperina"

[field."Actor.position"]
offset = 0x31C
type = "f32[3]"

[hookpoint."Camera.ViewMatrixDone"]
offset = 0x4C5068
replaces = "<instruction bytes>"
context = "x20 = view"
```

- A mod asks Core `kae_sym("CctChangePosition")` and gets a pointer, or null on a build where it
  isn't known. Field offsets are symbols too (`kae_field("Actor.position")`), so no mod compiles
  a game structure layout into itself.
- The manifest lists the names a mod needs. `kaepora check` says "this mod isn't supported on
  your game version yet" before launch; Core says it again at run time and leaves the mod off.
- With one final game version, an address found once stays true. The pack only grows, and a
  correction to it fixes every mod at once.
- There is one pack per supported build, 1.0.0 and 1.1.1. A name only counts as part of the
  standard once it is in both packs, so a core mod runs on both versions without changes.
  Level 1 and 2 mods (their own patches) support whichever builds their author ports them to,
  and say so in the manifest.
- Names are the shared vocabulary. Where a function has a Hookshot-style name (`f_806d2530`),
  that is kept as an alias.
- This repo's `symbols/e0f3ccfa.ld` and the 5,238-entry script-command table are the seed.

### Hook points

Mods often need to run at a precise place inside the game's code. Core owns those places:

- A hook point is an entry in the symbol pack, not code in a mod.
- For each build, a tool generates one IPS from the pack. At every hook point it puts a branch to
  a 24-byte stub (small enough for the padding between functions) that jumps through a pointer in
  writable memory. While the pointer is empty the stub runs the replaced instruction and returns,
  so an unused hook point costs nothing and a missing Core changes nothing.
- At run time Core fills the pointers and calls every subscribed mod, in priority order, with the
  register values. Any number of mods can share a hook point.
- Adding a hook point is a pack and Core update. Mods never ship patches to `main`.
- Before use, Core checks that each patched place holds exactly the expected bytes. A mismatch
  disables that hook point and the mods that need it.

### Events

On top of hook points, Core offers named events that hide where they come from. A mod should use
an event when one exists:

| Event | When | A mod may |
|---|---|---|
| `frame` | once per game frame | do anything |
| `input` | controller state read | read it, change what the game sees |
| `view` | the gameplay camera's matrix is final | read or replace it |
| `player_update` | Link's movement update | read or move him |
| `scene_change` | a map starts loading / is ready | reset its state |
| `pause_change` | the game pauses or resumes | stop its own work |
| `draw` | before the frame is shown | draw text and simple shapes |

The first two and `draw` need no symbol pack. The rest are hook points with a stable meaning,
so a mod doesn't depend on where in the game's code they come from.

### Services

| Service | What it does |
|---|---|
| Input bindings | A mod registers actions with default buttons. Core detects two mods wanting the same buttons, and one shared settings screen lets the player rebind any action of any mod: the [Mods menu](MODS-MENU.md) |
| Config | Typed settings per mod, saved to one file per mod, editable in the shared screen |
| Log | One log for all mods, with the mod's ID on every line |
| Symbols | `kae_sym`, `kae_field`, the build ID, the game version |
| Game helpers | Thin, named wrappers for the common needs: Link's actor, position and controller; the camera view; save fields by name (GameData); pausing by type |
| Memory | Allocation from Core's own pool, so mods don't touch the game's heaps |
| Mod to mod | A mod can export named functions and look up another mod's, by ID |

Helpers are added when two mods need the same thing, not before.

### Interface rules (what keeps old mods working)

1. Plain C, AArch64 calling convention, no C++ types across the boundary. Any language that can
   call C can write a mod.
2. Every function is `kae_<name>`, imported by name. Functions are never removed and never change
   meaning. A better version gets a new name.
3. The API has a version, `major.minor`. Minor versions only add. A mod records the version it
   was built against; Core runs any mod with the same major version and an equal or lower minor.
4. Every structure passed across starts with its own size, so it can grow at the end.
5. A mod asks `kae_has("draw.text")` before using an optional feature and must cope with "no".
6. A mod's init function does one thing: `kae_register(&descriptor)`. `kae_register` only adds to
   a list, so it is safe whichever module the system initialises first. Core calls each mod's
   `start` once everything is loaded.
7. Core never crashes the game on a mod's behalf: unknown build, missing symbol, failed byte
   check or version mismatch each switch off the affected mod, with a logged and on-screen reason.

A draft header is in [include/kaepora.h](include/kaepora.h).

### Living with mods outside the standard

- Import-table redirects chain: Core calls whatever was there before it, and expects the same of
  others, so Core and a standalone module such as sloperinaGZ can both wrap controller reading.
- Mods that patch `main` directly are known to the registry and the checker, as in level 2.
- A standalone mod can adopt Core gradually: register for input bindings first (which removes
  button clashes), move hooks later.

## Where it lives

In this repository, under `api/`, for now. The standard depends directly on what is already here
(the symbol file, the memory map, the patch and romfs tools), and it needs users before it needs
its own home. It is kept self-contained in this folder so it can move to its own repository,
under a neutral organisation, as soon as a second project adopts it. The reference tools and
Core are MIT-licensed like the rest of this repo, so GPL and proprietary mods can both use them.

## Governance

- The spec has a version. Changes are proposed as a pull request against this document, with the
  reason and what it does to existing mods.
- Symbol names, hook points and events are added by pull request with a note on how each was
  found and checked, the same rule this repo's docs already follow.
- Compatibility promises start at version 1.0. Until then (0.x) things may change, and every
  change is listed in a changelog.

## Roadmap

| Step | Delivers | Proves |
|---|---|---|
| M0 | Manifest schema, registry for build E0F3CCFA, `kaepora check` | Level 1 and 2 on today's installed mods |
| M1 | `kaepora build`: size table merge, BYML patches, scripts. Slow King Zora as a package | No game files shipped |
| M2 | Core skeleton in `subsdk1`: `frame`, `input`, log. One tiny test mod in `subsdk2` | The open questions below |
| M3 | Symbol packs for 1.1.1 and 1.0.0, hook points, `view` and `player_update`. First Person rebuilt as a core mod | A real mod with no patch to `main`, running on both versions |
| M4 | Input bindings, config, the shared settings screen, `draw` | FPV Drone and a second author's mod side by side |
| M5 | A hardware test and a second author's mod. Version 1.0 of the spec | It works outside our own setup |

## Open questions (each needs an experiment)

1. **Does `rtld` connect one added module's imports to another added module's exports?** It does
   for `main`, `sdk` and `subsdk0`, and sloperinaGZ only imports from those. If not, mods find
   Core through an agreed pointer in `main`'s unused memory instead; rule 6 already allows for it.
2. **In what order are added modules initialised?** Rule 6 makes the answer not matter, but it
   should be measured.
3. **Does the import-table rewrite work on hardware**, where memory permissions are stricter than
   in an emulator? If not, Core's base hooks become entries in the generated IPS.
4. **Do several added modules load at once** in Lichii and on hardware, and is there a size or
   count limit?
5. **Static recompilations** (Hookshot, NX2navi) don't run `rtld`. Supporting them means their
   runtime offering the same C API natively, which is their authors' decision.
6. **How many hook points fit?** Each needs one padding slot of 24+ bytes within branch range.
   There are thousands of such slots, so this should be comfortable, but the generator has to
   show it.
