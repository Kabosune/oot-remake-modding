# Kaepora (draft)

A proposed shared standard for Ocarina of Time remake mods: one package format, one registry of
who patches what, and a small core module that mods call instead of patching the game themselves.

- [DESIGN.md](DESIGN.md): the design, its reasons, the roadmap and the open questions.
- [MODS-MENU.md](MODS-MENU.md): the shared in-game Mods menu (settings, button mapping), with working menu code and host tests in `menu/`.
- [examples/mod.toml](examples/mod.toml): what a mod's manifest looks like.
- [include/kaepora.h](include/kaepora.h): a sketch of the core API.

**Status: a design draft. The Mods menu's code exists and is tested on a PC; nothing runs in the game yet.** Comments and objections are the point
of publishing it this early: open an issue.
