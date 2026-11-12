// KaeGae hook points: the module's side. See hookpoints.S for the patch to main.
//
// A hook point is a place in main's code, named in the symbol pack, where Core's patch jumps to
// a stub. The stub calls the function pointer in the hook point's slot, when there is one. Core
// fills the slot only after checking that the place holds its own stub.
#include "core.h"

#define TAG 0x31304B4F4F48504BULL   // "KPHOOK01", just before the first stub

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

bool kp_hooks_start(void) {
    const kp_hookpoint_t *move = 0;
    for (uint32_t i = 0; i < kp_build->hookpoint_count; i++)
        if (same_text(kp_build->hookpoints[i].name, "Actor.MoveUpdate"))
            move = &kp_build->hookpoints[i];
    if (!move || !kp_build->hook_slots) {
        kp_log("hook points off: this build's symbol pack has none");
        return false;
    }
    uint32_t word = *(const uint32_t *)(kp_main + move->site);
    if ((word & 0xFC000000) != 0x14000000) {   // a b instruction
        kp_log("hook points off: main isn't patched (Core's .ips is missing)");
        return false;
    }
    int32_t offset = (int32_t)(word << 6) >> 4;   // imm26 * 4, signed
    uintptr_t stub = kp_main + move->site + offset;
    if (stub < kp_main + 8 || stub >= kp_main + kp_build->size || *(const uint64_t *)(stub - 8) != TAG) {
        kp_log("hook points off: the movement update is patched by something else");
        return false;
    }
    void (**slots)(void *) = (void (**)(void *))(kp_main + kp_build->hook_slots);
    slots[move->slot] = on_move;
    kp_event_on[KP_EV_ACTOR_MOVE] = true;
    kp_log("hook point in place: Actor.MoveUpdate");
    return true;
}
