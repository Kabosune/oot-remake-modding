// Survey 3: which actors have a ragdoll. Every physics actor passes through the movement update;
// the first time one is seen, log its name, whether it has a ragdoll component and how many bodies
// that ragdoll has.
#include "core.h"

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))
#define F_HOLDER       0x837620    // f_80857620(actor): [[[actor+0x270]+0x50]+0x20]+0x10, no null checks
#define F_FIND_RAGDOLL 0x5F88C0    // f_806188c0(holder)
#define MAX_ACTORS     512

static void *seen[MAX_ACTORS];
static int seen_count;

static void name_of(void *actor, char *out, int size) {
    const char *name = AT(actor, 0x20, const char *);
    int i = 0;
    if (name && kp_readable((uintptr_t)name, 1))
        for (; i < size - 1 && kp_readable((uintptr_t)name + i, 1) && name[i]; i++)
            out[i] = name[i];
    out[i] = 0;
}

void *actor_holder(void *actor) {
    char *c = AT(actor, 0x270, char *);
    if (!c || !kp_readable((uintptr_t)c + 0x50, 8))
        return 0;
    c = AT(c, 0x50, char *);
    if (!c || !kp_readable((uintptr_t)c + 0x20, 8))
        return 0;
    c = AT(c, 0x20, char *);
    if (!c || !kp_readable((uintptr_t)c + 0x10, 8))
        return 0;
    return KP_FN(void *(*)(void *), F_HOLDER)(actor);
}

// Bodies of an actor's ragdoll: -1 = no ragdoll component.
int actor_ragdoll_bodies(void *actor, void **ragdoll_out) {
    void *holder = actor_holder(actor);
    void *ragdoll = holder ? KP_FN(void *(*)(void *), F_FIND_RAGDOLL)(holder) : 0;
    if (ragdoll_out)
        *ragdoll_out = ragdoll;
    if (!ragdoll)
        return -1;
    char *set = AT(ragdoll, 0x40, char *);
    return set && kp_readable((uintptr_t)set, 0x70) ? AT(set, 0x60, int32_t) - 1 : 0;
}

void actors_survey(void *actor) {
    for (int i = 0; i < seen_count; i++)
        if (seen[i] == actor)
            return;
    if (seen_count == MAX_ACTORS)
        return;
    seen[seen_count++] = actor;
    if (!kp_readable((uintptr_t)actor, 0x330))
        return;
    char name[48];
    name_of(actor, name, sizeof name);
    int bodies = actor_ragdoll_bodies(actor, 0);
    kp_log(name[0] ? name : "(no name)");
    kp_log_2(bodies < 0 ? "  actor: no ragdoll. -" : "  actor: HAS A RAGDOLL, bodies:", bodies, seen_count);
}
