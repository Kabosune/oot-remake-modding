// Hello: the smallest Kaepora mod. A small square in the top left corner that turns green while
// A is held, and a log line every 300 frames. It is also Core's test mod: its log lines show
// which parts of Core work in the running game.
#include <kaepora.h>

static uint64_t frames, inputs, moves;
static int a_held;

static void frame(void *user) {
    (void)user;
    frames++;
    if (frames % 300 == 1)
        KAE_LOG("alive: %llu frames, %llu controller reads, %llu actor moves", (unsigned long long)frames,
                (unsigned long long)inputs, (unsigned long long)moves);
}

static void input(KaeInput *seen_by_game, const KaeInput *real, void *user) {
    (void)seen_by_game;
    (void)user;
    inputs++;
    if (real->connected)
        a_held = (real->buttons & 1) != 0;
}

static void actor_move(void *actor, void *user) {
    (void)actor;
    (void)user;
    moves++;
}

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    int unit = f->height / 90;
    kae_draw_rect(unit * 2 - 2, unit * 2 - 2, unit * 3 + 4, unit * 3 + 4, 0x000000);
    kae_draw_rect(unit * 2, unit * 2, unit * 3, unit * 3, a_held ? 0x40E060 : 0x40C0FF);
}

static int start(void) {
    KAE_LOG("hello from its own start. Core API %u.%u, game %s", kae_api_version() >> 16,
            kae_api_version() & 0xFFFF, kae_game_version());
    static const char *const features[] = { "event.frame", "event.input", "event.draw", "event.actor_move", "motion" };
    for (unsigned i = 0; i < sizeof features / sizeof *features; i++)
        KAE_LOG("  %s: %s", features[i], kae_has(features[i]) ? "yes" : "no");
    KAE_LOG("  CctChangePosition at %p, Actor.position at +0x%llx", kae_sym("CctChangePosition"),
            (unsigned long long)kae_field("Actor.position"));
    void *p = kae_alloc(64);
    KAE_LOG("  kae_alloc(64): %p", p);
    kae_free(p);
    // Each event is optional here: the mod shows what it can.
    kae_on_frame(frame, 0, 0);
    kae_on_input(input, 0, 0);
    kae_on_actor_move(actor_move, 0, 0);
    kae_on_draw(draw, 0, 0);
    return 0;
}

KAE_MOD("kaepora.hello", "0.2.0", start, 0);
