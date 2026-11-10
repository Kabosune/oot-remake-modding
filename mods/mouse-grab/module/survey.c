// Survey 2: what the 0x70-byte entries near Link hold, while he's a ragdoll.
//
// Twice, 10 frames apart (from 40 frames after he goes down), it dumps every entry of the three
// arrays survey 1 found ([[holder+0x18]+0x1e0], [[holder+0x18]+0x1f0], [[holder+0x48]+0x88]) as
// floats, and the first 0x100 bytes of [holder+0x18] as pointers. Entries that change between the
// two dumps are the simulation's; their layout tells where position and velocity are.
#include "core.h"

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))
#define ENTRY 0x70
#define ENTRIES 10

static void dump_array(const char *name, char *base, int first) {
    if (!base || !kp_readable((uintptr_t)base, ENTRY * ENTRIES))
        return;
    kp_log_hex(name, (uintptr_t)base);
    for (int i = first; i < ENTRIES; i++) {
        const float *f = (const float *)(base + i * ENTRY);
        kp_log_floats("  entry, floats 0-11:", f, 12);
        kp_log_floats("         floats 12-23:", f + 12, 12);
        kp_log_floats("         floats 24-27:", f + 24, 4);
    }
}

void survey2(void *actor, void *holder, int pass) {
    kp_log_2("survey2: pass, -", pass, 0);
    kp_log_floats("survey2: Link position", (const float *)((char *)actor + 0x31c), 3);
    char *o18 = AT(holder, 0x18, char *), *o48 = AT(holder, 0x48, char *);
    if (o18 && kp_readable((uintptr_t)o18, 0x200)) {
        if (pass == 0)
            for (int off = 0; off < 0x100; off += 8)
                kp_log_2("  [holder+0x18] + offset, value:", off, AT(o18, off, int64_t));
        dump_array("survey2: array A", AT(o18, 0x1e0, char *), 0);
        dump_array("survey2: array B", AT(o18, 0x1f0, char *), 0);
    }
    if (o48 && kp_readable((uintptr_t)o48, 0x100))
        dump_array("survey2: array C", AT(o48, 0x88, char *), 1);
}
