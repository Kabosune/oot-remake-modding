// Hello: a small KaeGae mod. A square in the top left corner that turns green while A is held, a
// line of text and a small picture next to it, a log line every 300 frames, and a page of settings
// in the Mods menu (- and + together) that change what it draws. It is also Core's test mod: its log lines show
// which parts of Core work in the running game.
#include <kaegae.h>

static uint64_t frames, inputs, moves;
static int a_held, combo_held;

static void say_hello(KaeItem *item, void *user) {
    (void)item;
    (void)user;
    KAE_LOG("the menu's action was chosen after %llu frames", (unsigned long long)frames);
}

enum { SHOW_SQUARE, TEXT_COLOUR, TEXT_SIZE, COMBO, SAY_HELLO };
static const char *const colours[] = { "White", "Gold", "Sky" };
static const uint32_t colour_rgb[] = { 0xFFFFFF, 0xFFD040, 0x80D0FF };
static KaeItem settings[] = {
    [SHOW_SQUARE] = { KAE_TOGGLE, "Show the square", "The square that turns green while A is held.", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
    [TEXT_COLOUR] = { KAE_CHOICE, "Text colour", "The colour of Hello's line of text.", 0, 0, 0, 2, 0, colours, 0, 0, 0, 0 },
    [TEXT_SIZE]   = { KAE_NUMBER, "Text size", "1 is the font's own size, 8 x 16 pixels.", 2, 2, 1, 4, 1, 0, 0, 0, 0, 0 },
    [COMBO]       = { KAE_BINDING, "Flash the diamond", "While these buttons are held the diamond is drawn bigger.", 0, 0, 0, 0, 0, 0, KAE_L3, KAE_L3, 0, 0 },
    [SAY_HELLO]   = { KAE_ACTION, "Write a line to the log", "Shows that a mod's function runs when chosen.", 0, 0, 0, 0, 0, 0, 0, 0, say_hello, 0 },
};

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
    if (real->connected && !kae_menu_open()) {
        a_held = (real->buttons & KAE_A) != 0;
        uint64_t combo = settings[COMBO].binding;
        combo_held = combo && (real->buttons & combo) == combo;
    }
}

static void actor_move(void *actor, void *user) {
    (void)actor;
    (void)user;
    moves++;
}

// An 8 x 8 picture: a yellow diamond with a white middle. 0 is see-through.
#define Y_ 0xFFFFD040
#define W_ 0xFFFFFFFF
static const uint32_t diamond[8 * 8] = {
    0,  0,  0,  Y_, Y_, 0,  0,  0,
    0,  0,  Y_, Y_, Y_, Y_, 0,  0,
    0,  Y_, Y_, W_, W_, Y_, Y_, 0,
    Y_, Y_, W_, W_, W_, W_, Y_, Y_,
    Y_, Y_, W_, W_, W_, W_, Y_, Y_,
    0,  Y_, Y_, W_, W_, Y_, Y_, 0,
    0,  0,  Y_, Y_, Y_, Y_, 0,  0,
    0,  0,  0,  Y_, Y_, 0,  0,  0,
};

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    int unit = f->height / 90;
    if (settings[SHOW_SQUARE].value) {
        kae_draw_rect(unit * 2 - 2, unit * 2 - 2, unit * 3 + 4, unit * 3 + 4, 0x000000);
        kae_draw_rect(unit * 2, unit * 2, unit * 3, unit * 3, a_held ? 0x40E060 : 0x40C0FF);
    }
    // text on a dark plate so it reads over anything
    int scale = settings[TEXT_SIZE].value;
    const char *text = a_held ? "KaeGae Core 0.5: A is held" : "KaeGae Core 0.5: - and + open Mods";
    int x = unit * 7, y = unit * 2;
    kae_draw_rect(x - 4, y - 4, kae_text_width(scale, text) + 8 * scale * 3 + 12, kae_text_height(scale, text) + 8, 0x101820);
    x = kae_draw_text(x, y, scale, colour_rgb[settings[TEXT_COLOUR].value], text);
    kae_draw_image(x + 4 * scale, y + 4 * scale - (combo_held ? 4 * scale : 0), 8, 8, diamond, combo_held ? scale * 2 : scale);
}

static int start(void) {
    KAE_LOG("hello from its own start. Core API %u.%u, game %s", kae_api_version() >> 16,
            kae_api_version() & 0xFFFF, kae_game_version());
    static const char *const features[] = { "event.frame", "event.input", "event.draw", "event.actor_move", "motion",
                                            "draw.text", "draw.image", "menu" };
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
    kae_settings("Hello", settings, sizeof settings / sizeof *settings);
    return 0;
}

KAE_MOD("kaegae.hello", "0.5.0", start, 0);
