"""tools/byml.py: write BYML and read it back with both byml.py and zstool.py. No game files.

    python3 tests/test_byml.py

For the same check on your own dump: `python3 tools/byml.py check <file> --dict <dump>/Pack/ZsDic.pack.zs`
(checked on 12 Nov 2026: the Deku Tree and Kokiri Forest placement files, StartPos.byml, GameBancInfo, GameBancParam).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import byml  # noqa: E402
import zstool  # noqa: E402

doc = {
    "Actors": [
        {"Gyaml": "StartPos", "Hash": byml.U64(2323315277028202505), "SRTHash": byml.U32(2051745543),
         "Translate": [0.25, 101.0, -14.5], "Name": "Entrance", "Bakeable": True, "Count": -3},
        {"Gyaml": "Obj_TBox_A_02", "Hash": byml.U64(2323315277028202505), "Big": byml.S64(-5), "D": byml.F64(1.5),
         "Translate": [0.25, 101.0, -14.5], "Raw": b"\x01\x02\x03", "Nothing": None, "Empty": [], "E2": {}},
    ],
    "FilePath": "Work/Banc/Scene/Test.bcett.json",
}

data = byml.dumps(doc)
back = byml.loads(data)
assert byml.same(doc, back), "byml.py round trip"
assert byml.loads(byml.dumps(back)) == back
z = zstool.Byml(data).root
assert z["Actors"][0]["Translate"] == [0.25, 101.0, -14.5] and z["Actors"][0]["Name"] == "Entrance"
assert z["Actors"][1]["Hash"] == 2323315277028202505 and z["Actors"][0]["Count"] == -3
assert byml.from_json(byml.to_json(doc)) == doc and byml.same(byml.from_json(byml.to_json(doc)), doc)
# shared sub-trees are stored once: two equal Translate arrays, one copy
assert data.count(bytes([0xC0, 3, 0, 0, 0xD2, 0xD2, 0xD2, 0])) == 1
print("byml: ok")
