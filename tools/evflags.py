#!/usr/bin/env python3
"""List the story flags the event scripts (Event/EventFlow/*.bfevfl.zs) set and check.

    python3 tools/evflags.py <dump romfs dir> > flags.tsv

Writes `flag<TAB>scripts that set it<TAB>scripts that check it` (comma separated). Reads the scripts with the
`evfl` package and the game's dictionaries from <romfs>/Pack/ZsDic.pack.zs. A flag whose name is itself an
argument of the script (shown as `GameDataName`, or a name the script gets from its caller) is listed under that
placeholder, not under the real names.
Needs: pip install zstandard evfl
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evfl  # noqa: E402
import zsmod  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1])
    dicts = zsmod.dicts_by_id(str(root / "Pack" / "ZsDic.pack.zs"))
    sets, checks = collections.defaultdict(set), collections.defaultdict(set)
    for f in sorted((root / "Event" / "EventFlow").glob("*.bfevfl.zs")):
        raw, _ = zsmod.unzs(f.read_bytes(), dicts)
        flow = evfl.EventFlow()
        flow.read(raw)
        if flow.flowchart is None:
            continue
        name = f.name[: -len(".bfevfl.zs")]
        for ev in flow.flowchart.events:
            d = ev.data
            if isinstance(d, evfl.ActionEvent):
                act = str(d.actor_action)
                p = d.params.data if d.params else {}
                if act.endswith(("SetGameDataBool", "SetGameDataInt")):
                    sets[str(p.get("GameDataName"))].add(name)
            elif isinstance(d, evfl.SwitchEvent):
                q = str(d.actor_query)
                p = d.params.data if d.params else {}
                if "GameData" in q:
                    key = p.get("GameDataName") or p.get("GameData")
                    if key is not None:
                        checks[str(key)].add(name)
    print("flag\tset_in\tchecked_in")
    for k in sorted(set(sets) | set(checks)):
        print(f"{k}\t{','.join(sorted(sets.get(k, [])))}\t{','.join(sorted(checks.get(k, [])))}")


if __name__ == "__main__":
    main()
