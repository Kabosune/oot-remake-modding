// Mouse Grab, step two (test): right click drops Link into ragdoll, right click again gets him up.
//
// What the game's ExecuteEventPlayerImmediateRagdollDown node does on entering (f_826d3ec0), and
// what is copied here:
//   holder  = f_80857620(actor)          [[[actor+0x270]+0x50]+0x20]+0x10
//   ragdoll = f_806188c0(holder)         a component of holder, looked up by type
//   f_83238d30(ragdoll, &request)        request {actor, 1.0, 0, 0, 0, 0, 1, 2, 0, 0}; it builds the
//                                        name "ImmediateDown" and starts that ragdoll
// and on leaving (f_826d42c0):
//   f_83239090(ragdoll, &{actor, false})  ends it (clears ragdoll+0x17c, which the start sets to 3)
//   player[0x1c3e] |= 1                   player = [[actor+0x270]+0x358]
// Before the request the node also prepares Link's player object (player = [[actor+0x270]+0x358]):
//   f_809539f0(player, 0.0)
//   f_80992a40(player, ZERO, 0), f_8094fde0(player, ZERO, 0)    ZERO = [0x84c9ddc0], (0, 0, 0, 1)
//   player+0x1030 = 0
//   f_80953270(player, 0, NAMES, 15, 0)                        NAMES = [0x84c9f168]: "SlippingDown",
//                                                               "SlippingDownLand"
// Without that (first builds) a ragdoll started in the air only showed once he landed. The node's
// per-frame update (f_826d3fb0) isn't copied: he stays down until right click.
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
#define F_PREP_SPEED      0x9339F0    // f_809539f0
#define F_PREP_A          0x972A40    // f_80992a40
#define F_PREP_B          0x92FDE0    // f_8094fde0
#define F_PREP_STATE      0x933270    // f_80953270
#define G_ZERO            0x4C7DDC0   // [0x84c9ddc0]
#define G_NAMES           0x4C7F168   // [0x84c9f168]
#define F_RAGDOLL_END     0x3219090   // f_83239090(ragdoll, end request)
#define RAGDOLL_STATE     0x17c       // in the ragdoll component: 3 while down, 0 otherwise
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

typedef struct {
    void *actor;
    uint8_t flag;         // 0 in the node
    uint8_t pad[7];
} ragdoll_end_t;

static uint32_t down_frames;
void survey2(void *actor, void *holder, int pass);

static bool held;
static bool requested;
static void *ragdoll_of(void *actor) {
    void *holder = KP_FN(void *(*)(void *), F_HOLDER)(actor);
    return holder ? KP_FN(void *(*)(void *), F_FIND_RAGDOLL)(holder) : 0;
}

static uint32_t frames;
static int64_t last_rd_b0 = -1, last_rd_f0 = -1, last_reaction = -1;
static void *link;

static void report(void *actor, const char *why) {
    char *physics = physics_of(actor);
    char *rd = physics ? AT(physics, 0x1c8, char *) : 0;
    void *ragdoll = ragdoll_of(actor);
    int64_t b0 = ragdoll ? AT(ragdoll, RAGDOLL_STATE, int32_t) : -1, f0 = rd ? AT(rd, 0xf0, int32_t) : -1;
    void *reaction = KP_FN(void *(*)(void *), F_REACTION)(actor);
    int64_t active = reaction ? (int64_t)KP_FN(bool (*)(void *), F_REACTION_ACTIVE)(reaction) : -1;
    if (why || b0 != last_rd_b0 || f0 != last_rd_f0 || active != last_reaction) {
        kp_log(why ? why : "ragdoll state changed");
        kp_log_2("  ragdoll state (3 = down), physics +0xf0:", b0, f0);
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
    char *components = AT(actor, 0x270, char *);
    char *player = components ? AT(components, 0x358, char *) : 0;
    if (player && AT(player, 0x18, void *) == actor) {
        void *zero = AT(kp_main + G_ZERO, 0, void *);
        void *names = AT(kp_main + G_NAMES, 0, void *);
        KP_FN(void (*)(void *, float), F_PREP_SPEED)(player, 0.0f);
        KP_FN(void (*)(void *, void *, int), F_PREP_A)(player, zero, 0);
        KP_FN(void (*)(void *, void *, int), F_PREP_B)(player, zero, 0);
        AT(player, 0x1030, uint32_t) = 0;
        KP_FN(void (*)(void *, void *, void *, int, int), F_PREP_STATE)(player, 0, names, 15, 0);
    } else {
        kp_log("ragdoll: player object not as expected, skipping the preparation");
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
    void *ragdoll = ragdoll_of(actor);
    if (ragdoll) {
        ragdoll_end_t e = { actor, 0, { 0 } };
        KP_FN(void (*)(void *, ragdoll_end_t *), F_RAGDOLL_END)(ragdoll, &e);
        char *components = AT(actor, 0x270, char *);
        char *player = components ? AT(components, 0x358, char *) : 0;
        if (player)
            player[0x1c3e] |= 1;
    }
    requested = false;
    report(actor, ragdoll ? "ragdoll: end requested" : "ragdoll: no ragdoll component to end");
}

// The ragdoll's bodies, found in f_83237d70 (which the start request calls to hand the controller's
// velocity to every ragdoll body): set = [ragdoll+0x40], count [set+0x60] - 1, entries of 0x138
// bytes from [set+0x68], body (the same wrapper class as the controller's body) at entry+0x38.
#define BODY_VT 0x4C34658
int ragdoll_bodies(void *actor, void **out, int max) {
    char *r = ragdoll_of(actor);
    char *set = r ? AT(r, 0x40, char *) : 0;
    if (!set || !kp_readable((uintptr_t)set, 0x70))
        return 0;
    int count = AT(set, 0x60, int32_t) - 1;
    char *entries = AT(set, 0x68, char *);
    int n = 0;
    for (int i = 0; i < count && n < max; i++) {
        char *e = entries + 0x138 * i;
        if (!kp_readable((uintptr_t)e + 0x38, 8))
            break;
        void *body = AT(e, 0x38, void *);
        if (body && kp_readable((uintptr_t)body, 8) && AT(body, 0, uintptr_t) == kp_main + BODY_VT)
            out[n++] = body;
    }
    return n;
}

bool ragdoll_is_down(void *actor) {
    void *r = ragdoll_of(actor);
    return r && AT(r, RAGDOLL_STATE, int32_t) != 0;
}

void ragdoll_start(void *actor) {
    ragdoll_down(actor);
}

void ragdoll_stop(void *actor) {
    ragdoll_end(actor);
}

void grab_move(void *actor);

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
        void *ragdoll = ragdoll_of(actor);
        bool down = ragdoll && AT(ragdoll, RAGDOLL_STATE, int32_t) != 0;
        if (!down)
            ragdoll_down(actor);
        else
            ragdoll_end(actor);
    }
    held = right;
    grab_move(actor);
    void *rd = ragdoll_of(actor);
    if (rd && AT(rd, RAGDOLL_STATE, int32_t) != 0) {
        ++down_frames;
        if (down_frames == 40 || down_frames == 50)
            survey2(actor, KP_FN(void *(*)(void *), F_HOLDER)(actor), down_frames == 50);
    } else {
        down_frames = 0;
    }
    if (requested || frames % 120 == 0)
        report(actor, 0);
}
