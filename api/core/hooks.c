// KaeGae hook points: the module's side. See hookpoints.S for the patch to main.
//
// A hook point is a place in main's code, named in the symbol pack, where Core's patch jumps to
// a stub. The stub calls the function pointer in the hook point's slot, when there is one. Core
// fills the slot only after checking that the place holds its own stub.
#include "core.h"

#define TAG 0x31304B4F4F48504BULL   // "KPHOOK01", just before each stub

void kp_view_entry(void);   // view_entry.S

static bool same_text(const char *a, const char *b) {
    for (; *a == *b; a++, b++)
        if (!*a)
            return true;
    return false;
}

static void on_move(void *actor) {
    kp_fire_actor_move(actor);
    if (kp_wants_player_move()) {
        const KaePlayer *link = kae_player_of(actor);
        if (link)
            kp_fire_player_move(link);
    }
}

// Puts `fn` in the hook point's slot if main holds Core's own stub there. Logs why not.
static bool place(const char *name, void *fn) {
    const kp_hookpoint_t *point = 0;
    for (uint32_t i = 0; i < kp_build->hookpoint_count; i++)
        if (same_text(kp_build->hookpoints[i].name, name))
            point = &kp_build->hookpoints[i];
    if (!point || !kp_build->hook_slots) {
        kp_logf("hook point %s off: this build's symbol pack doesn't have it", name);
        return false;
    }
    uint32_t word = *(const uint32_t *)(kp_main + point->site);
    if ((word & 0xFC000000) != 0x14000000) {   // a b instruction
        kp_logf("hook point %s off: main isn't patched there (Core's .ips is missing or older)", name);
        return false;
    }
    int32_t offset = (int32_t)(word << 6) >> 4;   // imm26 * 4, signed
    uintptr_t stub = kp_main + point->site + offset;
    if (stub < kp_main + 8 || stub >= kp_main + kp_build->size || *(const uint64_t *)(stub - 8) != TAG) {
        kp_logf("hook point %s off: something else patches that place in main", name);
        return false;
    }
    void **slots = (void **)(kp_main + kp_build->hook_slots);
    slots[point->slot] = fn;
    kp_logf("hook point in place: %s", name);
    return true;
}

bool kp_hooks_start(void) {
    if (!kp_build->hook_slots) {
        kp_log("hook points off: this build's symbol pack has none");
        return false;
    }
    if (kp_view_start() && place("Camera.View", (void *)kp_view_entry))
        kp_event_on[KP_EV_VIEW] = true;
    if (!place("Actor.MoveUpdate", (void *)on_move))
        return false;
    kp_event_on[KP_EV_ACTOR_MOVE] = true;
    return true;
}
