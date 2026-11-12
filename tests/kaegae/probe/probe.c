// The test's mod. See mod.toml.
#include <kaegae.h>

typedef struct {
    int64_t sample;
    int32_t x, y, dx, dy, wheel_x, wheel_y;
    uint32_t buttons, attributes;
} mouse_state_t;
int _ZN2nn3hid14GetMouseStatesEPNS0_10MouseStateEi(mouse_state_t *states, int count);

static int frames, moves, draws, inputs;
static void *last_actor;

static void frame(void *user) { frames += (int)(uintptr_t)user; }

// Hides B from the game, presses X while A is held, and takes over the left stick.
static void input(KaeInput *seen, const KaeInput *real, void *user) {
    (void)user;
    inputs++;
    seen->buttons &= ~2ull;
    if (real->buttons & 1)
        seen->buttons |= 4;
    seen->lx = 111;
    seen->ly = -222;
}

static void actor_move(void *actor, void *user) {
    (void)user;
    moves++;
    last_actor = actor;
}

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    draws++;
    kae_draw_rect(10, 20, 30, 40, 0x112233);
    kae_draw_rect(-5, 700, 20, 100, 0xFFFFFF);          // clipped to the picture
    kae_draw_rect(5000, 5000, 10, 10, 0xFF0000);        // outside it: dropped
    if (f->number == 2) {
        float d[9];
        uint64_t n = kae_motion_direction(d);
        mouse_state_t m;
        int got = _ZN2nn3hid14GetMouseStatesEPNS0_10MouseStateEi(&m, 1);
        KAE_LOG("report: frames %d inputs %d moves %d draws %d actor %p size %dx%d", frames, inputs, moves, draws,
                last_actor, f->width, f->height);
        KAE_LOG("report: motion %llu %.1f %.1f mouse %d %d,%d", (unsigned long long)n, d[0], d[8], got, m.x, m.y);
    }
}

static int start(void) {
    char *a = kae_alloc(100), *b = kae_alloc(100);
    KAE_LOG("start: api %x game %s build %s base %p", kae_api_version(), kae_game_version(), kae_game_build(),
            (void *)kae_game_base());
    KAE_LOG("start: sym %p alias %p vtable %p field %lld unknown %p %lld", kae_sym("CctChangePosition"),
            kae_sym("f_806d2530"), kae_sym("vtable.Actor"), (long long)kae_field("Actor.position"),
            kae_sym("NoSuchThing"), (long long)kae_field("No.such"));
    KAE_LOG("start: has %d%d%d%d%d%d%d", kae_has("event.frame"), kae_has("event.input"), kae_has("event.draw"),
            kae_has("event.actor_move"), kae_has("motion"), kae_has("symbols"), kae_has("nothing"));
    KAE_LOG("start: alloc %d readable %d%d", a && b && a != b && ((uintptr_t)a & 15) == 0,
            kae_readable(a, 100), kae_readable((void *)0x10000000, 8));
    kae_free(a);
    kae_free(b);
    int r1 = kae_on_frame(frame, (void *)1, 0);
    int r2 = kae_on_input(input, 0, -5);
    int r3 = kae_on_actor_move(actor_move, 0, 0);
    int r4 = kae_on_draw(draw, 0, 10);
    KAE_LOG("start: subscribed %d %d %d %d", r1, r2, r3, r4);
    return 0;
}

KAE_MOD("kaegae.test-probe", "1.2.3", start, 0);
