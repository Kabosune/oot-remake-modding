// Link's face while he's a ragdoll.
//
// OneShotPersonalitySetOverwritePartialSlotFace (f_8291dd30) shows how a script changes a face:
//   index = f_80aed6d0(actor, &name)   looks name up in a list of the actor's animation resource:
//           res = [[[[[[actor+0x270]+0x40]+0x18]+0x18]+0x48]+0x10], header = [res+8],
//           count [header+0x24], entries of 16 bytes from [res+0x30], each starting with a string
//           offset into the header's string pool ([header+0x3c] from the header)
//   p = [[actor+0x270]+0x340]           the personality component
//   p+0x3c = index, p+0x27 |= 1
// Which names the list holds isn't known, so the first time Link is seen they're all logged, and
// the first one that sounds like pain is used while he's down.
#include "core.h"

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))
#define MAX_NAMES 200

static int pain = -1;          // index of the pain face, -1 = none found
static bool listed, set_now;
static int32_t saved;

static char *chain(void *actor) {
    static const uint16_t steps[] = { 0x270, 0x40, 0x18, 0x18, 0x48, 0x10 };
    char *p = actor;
    for (unsigned i = 0; i < sizeof steps / sizeof *steps; i++) {
        if (!p || !kp_readable((uintptr_t)p + steps[i], 8))
            return 0;
        p = AT(p, steps[i], char *);
    }
    return p;
}

static bool contains(const char *s, const char *word) {
    for (; *s; s++) {
        int i = 0;
        while (word[i] && (s[i] | 0x20) == (word[i] | 0x20))
            i++;
        if (!word[i])
            return true;
    }
    return false;
}

static void list_names(void *actor) {
    listed = true;
    char *res = chain(actor);
    char *header = res && kp_readable((uintptr_t)res + 0x30, 8) ? AT(res, 8, char *) : 0;
    char *entries = res ? AT(res, 0x30, char *) : 0;
    if (!header || !entries || !kp_readable((uintptr_t)header, 0x40)) {
        kp_log("face: no face list found");
        return;
    }
    int count = AT(header, 0x24, int32_t);
    const char *pool = header + AT(header, 0x3c, int32_t);
    kp_log_2("face: names in Link's list:", count, 0);
    static const char *const words[] = { "pain", "damage", "hurt", "ouch", "dead", "faint" };
    for (int i = 0; i < count && i < MAX_NAMES; i++) {
        if (!kp_readable((uintptr_t)entries + 16 * i, 4))
            break;
        const char *name = pool + AT(entries, 16 * i, int32_t);
        if (!kp_readable((uintptr_t)name, 2))
            continue;
        kp_log_2("face: entry", i, 0);
        kp_log(name);
        for (unsigned w = 0; pain < 0 && w < sizeof words / sizeof *words; w++)
            if (contains(name, words[w]))
                pain = i;
    }
    kp_log_2("face: pain face entry (-1 = none):", pain, 0);
}

// Called every frame for Link with whether he's down.
void face_update(void *actor, bool down) {
    if (!listed)
        list_names(actor);
    char *c = AT(actor, 0x270, char *);
    char *p = c ? AT(c, 0x340, char *) : 0;
    if (pain < 0 || !p || !kp_readable((uintptr_t)p, 0x40))
        return;
    if (down && !set_now) {
        saved = AT(p, 0x3c, int32_t);
        AT(p, 0x3c, int32_t) = pain;
        AT(p, 0x27, uint8_t) |= 1;
        set_now = true;
        kp_log_2("face: pain face on (was entry):", saved, 0);
    } else if (!down && set_now) {
        AT(p, 0x3c, int32_t) = saved;
        AT(p, 0x27, uint8_t) |= 1;
        set_now = false;
        kp_log("face: face back");
    }
}
