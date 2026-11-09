# Name the game's script-command functions in Ghidra from symbols/e0f3ccfa-commands.csv.
# Load main.bin as raw AArch64 (little-endian, v8A) at base 0x80020000, then run this from the Script Manager.
# @category OoT
import csv

from ghidra.program.model.symbol import SourceType

path = askFile("e0f3ccfa-commands.csv", "Open").getAbsolutePath()
fm = currentProgram.getFunctionManager()
named = 0
with open(path) as fh:
    for row in csv.DictReader(fh):
        for column, suffix in (("main_slot20", "main"), ("binder_slot9", "binder"),
                               ("slot10", "slot10"), ("slot11", "slot11"), ("slot12", "slot12")):
            if not row[column]:
                continue
            addr = toAddr(int(row[column], 16))
            fn = fm.getFunctionAt(addr) or createFunction(addr, None)
            label = "%s_%s" % (row["name"], suffix)
            if fn is not None:
                fn.setName(label, SourceType.IMPORTED)
            else:
                createLabel(addr, label, True)
            named += 1
print("named %d functions" % named)
