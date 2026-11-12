# Kaepora packages: the manifest, the registry and the checker

**Manifest version 1. Part of the Kaepora draft ([DESIGN.md](DESIGN.md)); may still change before
spec 1.0.** This page is the reference for levels 1 and 2 of the standard: what a mod folder
looks like, what its `mod.toml` says, how space in `main` is shared, and what
[`tools/kaepora.py`](../tools/kaepora.py) checks. Everything here runs on a PC and needs no game
files.

## The short version

- An existing mod conforms by adding one file, `mod.toml`, to its folder. `kaepora init` writes a
  first version from the mod's patch.
- `kaepora check` reads every installed mod, with or without a manifest, and says which ones can't
  be on together and why, before the game starts.
- `kaepora install` runs that check first, then copies the mod into the emulator's folder.
- The registry (`registry/<build>.toml`) records who uses which bytes of `main`.

```
python3 tools/kaepora.py init "My Mod" --id me.my-mod --author Me --license MIT
python3 tools/kaepora.py check "My Mod" --with-installed
python3 tools/kaepora.py install my-mod.zip
python3 tools/kaepora.py list
```

Needs Python 3.11 or later (3.10 works after `pip install tomli`).

## A mod folder

A package is the folder a player copies into the emulator's `load/<title id>/` folder today, plus
a manifest. The emulator ignores files it doesn't know, so a package still installs by hand.

```
My Mod/
  mod.toml                     the manifest
  README.txt
  exefs/<build id>.ips         a patch to main (levels 1 and 2)
  exefs/subsdk2                a module (a core mod; Kaepora Core's own module is subsdk1)
  romfs/...                    files added to the game's file system
```

A download is a zip of that folder, either on its own or inside a `0400486024DEC000/` folder (both
are in use; the tools read both).

## mod.toml

Complete examples: [a mod that patches main](../mods/first-person/mod.toml),
[a mod with slots and several hooks](../mods/fpv-drone/mod.toml),
[a core mod's source folder](examples/hello/mod.toml).

All offsets are **module offsets**: the address used in this repo's docs minus `0x80020000`, which
is also the offset inside an IPS32 patch minus the `0x100`-byte NSO header. Ranges are written
`"0x3C46B00..0x3C46FB0"` and leave the end out.

### Identity (required)

| Key | Meaning |
|---|---|
| `manifest` | `1`: the version of this format |
| `id` | `author.mod-name`, lower case letters, digits and `-`. Never reused for another mod. It is how other mods and the registry refer to this one |
| `name` | The name shown to players |
| `version` | `1.2.0` (up to three numbers; text after `-` or `+` is allowed and ignored when comparing) |
| `authors` | A list of names |
| `license` | Missing is a warning: without it nobody knows whether they may share the mod |
| `homepage`, `description` | Optional |
| `[game] title` | The title ID, `0400486024DEC000` |

### `[build.<build id>]`: what the mod does to main

One table per build of the game the mod supports (1.1.1 is `E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348`,
1.0.0 is `33FA6C2C23848282A77E8B88A0A93F4887C55920`).

| Key | Meaning |
|---|---|
| `ips` | The patch file, normally `exefs/<build id>.ips` |
| `code` | Ranges of main the patch fills with new code or data: code cave or padding slots. One range may cover a run of padding slots and the game code between them |
| `hooks` | Offsets of single instructions the patch replaces (4 bytes each) |
| `memory` | Ranges of main's writable memory the mod uses while the game runs. No tool can see these in the patch, so they are only as good as the author's word |

The manifest must tell the truth about the patch, and `check` holds it to that: every byte the
patch writes has to be inside a `code` range or be a listed hook, every listed hook has to be
written, and a patch for a build with no table is an error.

### `[modules]`: added modules

```toml
[modules]
subsdk1 = "kaepora.core@0.3"
subsdk2 = "kaepora.hello@0.3.0"
```

Each `exefs/subsdkN` in the folder is named: which mod it is, and which version. When several are
linked into one module (`tools/kaemod.py --bundle`), the value is a list. `tools/kaemod.py` writes
this table, and Core's `[build]` claims, into every folder it builds.

A folder "provides" its own id and every id in its modules. One id may be provided by one folder
only, which is how two copies of Kaepora Core are caught.

### `[core]`: a mod that runs on Kaepora Core

| Key | Meaning |
|---|---|
| `api` | The Core API version the mod is built for, `"0.3"`. Before 1.0 it must equal Core's |
| `sources`, `imports`, `symbols`, `events` | Read by the build (`tools/kaemod.py`): source files, system functions the mod imports itself, the symbols and events it uses |

A core mod has no `code` or `hooks` of its own. The only folder that has both `[core]` and claims
on main is one that also holds Kaepora Core.

### `[input]`: default buttons

```toml
[input]
toggle   = "R3"
levitate = "L+Up"
eye-down = "key:,"
```

One line per action, with its default. Buttons: `A B X Y L R ZL ZR L3 R3 Plus Minus Up Down Left
Right` (and `SL SR Home Capture C`); a chord joins them with `+`; `key:` is a keyboard key,
`mouse:` a mouse button. Two mods with the same default get a warning. Core mods bind their
buttons in the Mods menu instead and need not list them.

### `[relations]`

```toml
[relations]
requires   = ["kaepora.core==0.3"]
conflicts  = ["someone.other-mod"]
load-after = []
```

An entry is an id, optionally with `>=`, `<=`, `==`, `>` or `<` and a version. An unmet
requirement and a present conflict are errors. `load-after` is recorded and not yet used.

### romfs

Files under `romfs/` need no listing: the tools read the folder. Two folders with the same romfs
path are an error.

`[[romfs-patch]]` tables describe changes to game files without shipping them (DESIGN.md, "Changes
to game files without shipping game files"). The kinds `size-table`, `byml`, `text`, `binary` and
`script` are read and checked for their required keys. Only `size-table` is acted on so far:

```toml
[[romfs-patch]]
kind     = "size-table"
path     = "AS/Dm_Zora_0010_KingZora.root.asb"     # the romfs path, without .zs
at-least = 6368                                    # bytes; rounded up to a multiple of 8
```

A mod whose file grows asks for its entry this way instead of shipping the table (a changed copy
of a 1.4 MB game file, and any two mods that ship one overwrite each other). A folder that does
ship a whole table gets a warning.

## Building the shared files

`kaepora build --game-table <file>` collects the size table requests of every installed mod that
is on, raises those entries in a copy of the game's own table (the largest request wins, nothing
is ever lowered) and writes the result as a mod folder, `Kaepora Built Files`, in the load folder.
The game's table is
`romfs/System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs` from your own
dump ([docs/romfs.md](../docs/romfs.md)). Needs `pip install zstandard`.

- Run it again after installing or removing a mod that asks for entries. `check` warns when
  requests have no built table (`size-table-not-built`) and fails when the built table is too
  small for a request (`size-table-stale`).
- The folder holds a changed copy of a game file: it stays on the player's machine.
- A path the game's table has no entry for is reported and left out: adding entries is not
  implemented.
- Checked against a real dump (11 November): for Slow King Zora's one request, the built table is
  byte for byte the table made by hand with `tools/rstb_set.py`. Whether the game needs the raised
  entry at all is still untested in the game.

## The registry

`registry/<build id, first 8 digits>.toml`: [1.1.1](../registry/e0f3ccfa.toml),
[1.0.0](../registry/33fa6c2c.toml). It is the machine-readable form of
[the memory map](../docs/memory-map.md).

```toml
[space.cave]                       # free space mods may claim
kind  = "code"                     # or "memory"
range = "0x3C461D0..0x3C47000"

[[claim]]                          # one per mod
owner  = "kabosune.first-person"
name   = "First Person"
code   = ["0x3C46B00..0x3C46FB0"]
memory = ["0x4E9FC00..0x4E9FC40"]
hooks  = ["0x4C5068", "0x2C21720"]
```

Rules:

- **Claim by pull request, first come first served, in the smallest amount that works.** A claim
  in the registry and the `[build]` table in the mod's manifest must say the same thing
  (`tests/test_kaepora_tools.py` checks this for the mods in this repo).
- **Claims may not overlap.** The test fails if two do.
- **Mods that don't follow the standard are recorded too**, read from their patches, with
  `standard = false`, so the checker knows them. `builtin = ["fritchii"]` marks a patch an
  emulator applies by itself. Where two such mods already overlap each other, `shared` names the
  other one: that records the clash, it doesn't approve it.
- **A hooked instruction has one owner.** When two mods need the same place it becomes a Core hook
  point and both subscribe.
- `retired = true` keeps the record of a mod that is no longer distributed.

`kaepora registry` prints the registry with how much of each space is taken.

## What `check` reports

Errors mean the set of mods shouldn't be started as it is. Warnings mean something may not work
the way the player expects. Notes are information. The name in brackets is stable, for searching.

| Finding | Level | Meaning |
|---|---|---|
| `byte-overlap` | error | Two patches write different bytes to the same place in main |
| `same-bytes` | warning | Two patches write identical bytes: it works, but it is usually two copies of one thing |
| `hook-clash`, `code-clash`, `memory-clash` | error | Two manifests claim the same instruction or range, even if no byte collides yet |
| `exefs-clash` | error | Two folders have the same `exefs` file, such as two `subsdk1` |
| `romfs-clash` | error | Two folders replace the same romfs file |
| `duplicate-id` | error | One id is provided by two folders |
| `requires`, `conflicts` | error | A requirement nobody meets, or a mod its neighbour says it can't run with |
| `no-core`, `api-mismatch` | error | A core mod without Kaepora Core, or built for another API version |
| `undeclared-write`, `undeclared-patch`, `hook-not-written`, `ips-missing`, `undeclared-module`, `module-missing` | error | The manifest and the folder's files disagree |
| `overwrites-game` | error | With `--main`: new code lands on bytes that aren't zero padding |
| `input-clash` | warning | Two mods have the same default button |
| `builtin-clash` | warning | The patch uses bytes an emulator's built-in patch also uses (a note on other emulators) |
| `unregistered`, `outside-claim` | warning | A mod that patches main has no claim in the registry, or writes outside it |
| `ships-size-table` | warning | The folder ships a whole resource size table |
| `size-table-not-built` | warning | Mods ask for resource size table entries and `kaepora build` hasn't been run |
| `size-table-stale` | error | The built table is too small for a request: run `kaepora build` again |
| `registered-to-other` | note | The patch uses space registered to a mod that isn't installed |
| `recognised`, `unknown-patch`, `unnamed-core`, `empty` | note | What a folder without a manifest turned out to be |

Mods switched off in the emulator's Add-Ons list are left out (`--all` includes them). The tool
reads that list from the emulator's `config/qt-config.ini` and never writes to it.

`check --main main.bin` (a flat image of your own unpatched main, from `tools/flatten_nso.py`)
adds the check that new code replaces only zero padding.

## Installing

`kaepora install <zip or folder>...`:

1. Unpacks to a temporary place (a zip entry that points outside the zip is refused).
2. **Assigns module slots.** If a new mod's `subsdkN` is taken by an installed mod, its module is
   renamed to the lowest free slot from `subsdk2` to `subsdk8` and its installed `mod.toml` is
   updated. `subsdk1` is Kaepora Core's; `subsdk9` is left to standalone mods. The source is never
   changed.
3. Runs `check` on the new mods together with the installed ones that are on. Any error stops the
   install (`--force` overrides, `--dry-run` stops here on purpose).
4. Copies each folder into `load/0400486024DEC000/`, replacing a folder of the same name.

`kaepora remove <folder name>` deletes an installed folder. Neither command switches mods on or
off: that stays in the emulator's Add-Ons list.

### Where the emulators keep mods

| `--target` | Folder | How this is known |
|---|---|---|
| `fritchii` | `%APPDATA%\fritchii\load\` | Seen with Fritchii v5.8.3 on Windows. Fritchii used Eden's folder up to v5.7 |
| `eden`, `lichii` | `%APPDATA%\eden\load\` on Windows, `$XDG_DATA_HOME/eden/load/` elsewhere | Lichii's source (`src/common/fs`, 6 November 2026) |
| any | `--load-dir <folder>` | For a portable install (a `user` folder next to the emulator's `.exe` takes the place of `%APPDATA%`, same source), macOS, or another emulator |

Fritchii's place outside Windows is assumed to follow the same pattern and has not been checked.
The emulator's log is `log/eden_log.txt` in the same data folder, under that name in Fritchii too.

What the Lichii family does with the folder (same source, `patch_manager.cpp`): mod folders are
taken in order of their names; each folder's `exefs` is layered over the game's, so a file name
(`subsdk1`) reaches the game from one folder only; every `exefs/<build id>.ips` (and `.pchtxt`)
whose name matches the module's build is applied in turn, so two patches to the same bytes
overwrite each other silently; `romfs` and `romfslite` are layered the same way. Fritchii v5.8.3
skips one of its own built-in patches when a mod has already written its bytes, and says so in
the log.

**Real hardware** (Atmosphère's layout: `atmosphere/contents/<title id>/exefs`, `romfs`, and
`atmosphere/exefs_patches/<name>/<build id>.ips`, as sloperinaGZ's package uses) is not supported
by `install` yet. There every mod shares one `exefs` and one `romfs` folder, so slot assignment
and the clash checks matter even more, and removal needs a record of who installed what. `check`
works on any set of folders today.

## Not done yet

- The rest of `kaepora build` (roadmap M1): the `byml`, `text`, `binary` and `script` kinds, and adding
  size table entries for files the game doesn't have.
- Reading `.pchtxt` patches (they are reported and skipped).
- Generating the memory map page from the registry.
- A registry survey for 1.0.0 (needs a 1.0.0 dump).
- Hardware install.
