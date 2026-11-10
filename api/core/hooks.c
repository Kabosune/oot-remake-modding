// Kaepora hook points: the module's side. See hookpoints.S for the patch to main.
#include "core.h"

#define HOOK_SLOTS   0x4E9FB00   // module offset of KP_HOOK_SLOTS
#define MOVE_SITE    0x2C215E4   // module offset of the movement update's second instruction
#define TAG          0x31304B4F4F48504BULL   // "KPHOOK01"

static void (*mod_move)(void *actor);

static void on_move(void *actor) {
    if (mod_move)
        mod_move(actor);
}

bool kp_hooks_start(void (*move)(void *actor)) {
    uint32_t site = *(const uint32_t *)(kp_main + MOVE_SITE);
    if ((site & 0xFC000000) != 0x14000000) {   // a b instruction
        kp_log("hooks off: main isn't patched (the mod's .ips is missing)");
        return false;
    }
    int32_t offset = (int32_t)(site << 6) >> 4;   // imm26 * 4, signed
    uintptr_t stub = kp_main + MOVE_SITE + offset;
    if (*(const uint64_t *)(stub - 8) != TAG) {
        kp_log("hooks off: the movement update is patched by something else");
        return false;
    }
    mod_move = move;
    *(void (**)(void *))(kp_main + HOOK_SLOTS) = on_move;
    kp_log("hook point in place: movement update");
    return true;
}
