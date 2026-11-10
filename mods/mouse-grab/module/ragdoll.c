// Mouse Grab, step two (test): right click drops Link into ragdoll, the next right click tries to
// end it. Everything it does is logged, since none of it is known to work yet.
//
// What the game's ExecuteEventPlayerImmediateRagdollDown node does on entering (f_826d3ec0), and
// what is copied here:
//   holder  = f_80857620(actor)          [[[actor+0x270]+0x50]+0x20]+0x10
//   ragdoll = f_806188c0(holder)         a component of holder, looked up by type
//   f_83238d30(ragdoll, &request)        request {actor, 1.0, 0, 0, 0, 0, 1, 2, 0, 0}; it builds the
//                                        name "ImmediateDown" and starts that ragdoll
// The node also changes Link's state (f_80953270 with "SlippingDown" / "SlippingDownLand") and runs
// an update every frame (f_826d3fb0); neither is copied, so Link may not get up by himself.
#include "core.h"
#include "input.h"

typedef struct {
    void *actor;          // +0x00
    float weight;         // +0x08  1.0
    uint32_t zero[4];     // +0x0c .. +0x1b
    uint32_t one;         // +0x1c  1
    uint32_t two;         // +0x20  2
    uint32_t zero2[2];    // +0x24 .. +0x2b
    uint32_t pad;
} ragdoll_request_t;
_Static_assert(sizeof(ragdoll_request_t) == 0x30, "request");

#define VT_ACTOR          0x4B25E18   // physics actor
#define VT_PLAYER         0x4B4C460   // player-type object
#define F_HOLDER          0x837620    // f_80857620(actor)
#define F_FIND_RAGDOLL    0x5F88C0    // f_806188c0(holder)
#define F_RAGDOLL_DOWN    0x3218D30   // f_83238d30(ragdoll, request)
#define F_REACTION        0x2C1D670   // f_82c3d670(actor): ragdoll reaction component, [components+0x390]
#define F_REACTION_ACTIVE 0x2E94110   // f_82eb4110(reaction): QueryIsNowRagdoll's test
#define F_REACTION_END    0x2E92F80   // f_82eb2f80(reaction): OneShotRagdollReactionEnd

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))

static bool is_link(void *actor) {
    if (AT(actor, 0, uintptr_t) != kp_main + VT_ACTOR)
        return false;
    char *components = AT(actor, 0x270, char *);
    if (!components)
        return false;
    char *movement = AT(components, 0x320, char *);
    if (!movement || AT(movement, 0x18, void *) != actor)
        return false;
    char *player = movement - 0x1d50;
    if (AT(player, 0, uintptr_t) != kp_main + VT_PLAYER)
        return false;
    char *res = AT(player, 0x10, char *);
    return res && AT(res, 0x58, uint32_t) == 0x79616c50 && AT(res, 0x5c, uint16_t) == 0x7265 && !res[0x5e];   // "Player"
}

static void *physics_of(void *actor) {
    char *c = AT(actor, 0x270, char *);
    c = c ? AT(c, 0x50, char *) : 0;
    return c ? AT(c, 0x20, void *) : 0;
}

static bool held;
static bool requested;
static uint32_t frames;
static int64_t last_rd_b0 = -1, last_rd_f0 = -1, last_reaction = -1;
static void *link;

static void report(void *actor, const char *why) {
    char *physics = physics_of(actor);
    char *rd = physics ? AT(physics, 0x1c8, char *) : 0;
    int64_t b0 = rd ? AT(rd, 0xb0, int32_t) : -1, f0 = rd ? AT(rd, 0xf0, int32_t) : -1;
    void *reaction = KP_FN(void *(*)(void *), F_REACTION)(actor);
    int64_t active = reaction ? (int64_t)KP_FN(bool (*)(void *), F_REACTION_ACTIVE)(reaction) : -1;
    if (why || b0 != last_rd_b0 || f0 != last_rd_f0 || active != last_reaction) {
        kp_log(why ? why : "ragdoll state changed");
        kp_log_2("  physics ragdoll +0xb0, +0xf0:", b0, f0);
        kp_log_2("  reaction component present, active:", reaction != 0, active);
        last_rd_b0 = b0; last_rd_f0 = f0; last_reaction = active;
    }
}

static void ragdoll_down(void *actor) {
    void *holder = KP_FN(void *(*)(void *), F_HOLDER)(actor);
    void *ragdoll = holder ? KP_FN(void *(*)(void *), F_FIND_RAGDOLL)(holder) : 0;
    kp_log_hex("ragdoll: holder", (uintptr_t)holder);
    kp_log_hex("ragdoll: ragdoll component", (uintptr_t)ragdoll);
    if (!ragdoll) {
        kp_log("ragdoll: no ragdoll component, nothing done");
        return;
    }
    ragdoll_request_t r = { 0 };
    r.actor = actor;
    r.weight = 1.0f;
    r.one = 1;
    r.two = 2;
    KP_FN(void (*)(void *, ragdoll_request_t *), F_RAGDOLL_DOWN)(ragdoll, &r);
    requested = true;
    report(actor, "ragdoll: ImmediateDown requested");
}

static void ragdoll_end(void *actor) {
    void *reaction = KP_FN(void *(*)(void *), F_REACTION)(actor);
    if (reaction)
        KP_FN(void (*)(void *), F_REACTION_END)(reaction);
    requested = false;
    report(actor, reaction ? "ragdoll: reaction end called" : "ragdoll: no reaction component to end");
}

void ragdoll_move(void *actor) {
    if (actor != link) {
        if (!is_link(actor))
            return;
        link = actor;
        kp_log_hex("found Link's actor", (uintptr_t)actor);
        report(actor, "ragdoll: state at start");
    }
    frames++;
    mouse_state_t m;
    m.buttons = 0;
    m.attributes = 0;
    int got = _ZN2nn3hid14GetMouseStatesEPNS0_10MouseStateEi(&m, 1);
    bool right = got > 0 && (m.attributes & 2) && (m.buttons & 2);
    if (right && !held) {
        if (!requested)
            ragdoll_down(actor);
        else
            ragdoll_end(actor);
    }
    held = right;
    if (requested || frames % 120 == 0)
        report(actor, 0);
}
