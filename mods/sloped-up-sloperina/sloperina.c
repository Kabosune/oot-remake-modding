// Sloped Up Sloperina: practice tools on KaeGae Core. The first slice: an input display, a position
// watch, save / load position and levitate. Its settings and buttons are a page of the Mods menu.
//
// Everything it asks of the game goes through Core by name (kae_sym, kae_field), except the walk
// from an actor to Link's player object and character controller, whose offsets are still written
// out here (finding Link belongs in Core; see the README).
#include <kaegae.h>

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))

// ---- settings: a page of the Mods menu ----
static void save_now(KaeItem *item, void *user);
static void load_now(KaeItem *item, void *user);

enum { INPUT_DISPLAY, POSITION_WATCH, HUD_SIZE, SAVE, LOAD, LEVITATE, LEVITATE_SPEED, SAVE_NOW, LOAD_NOW };
static KaeItem settings[] = {
    [INPUT_DISPLAY]  = { KAE_TOGGLE, "Input display", "Shows the buttons and sticks the controller reports.", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
    [POSITION_WATCH] = { KAE_TOGGLE, "Position watch", "Shows Link's position and speed.", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
    [HUD_SIZE]       = { KAE_NUMBER, "Display size", "The size of the display's text.", 2, 2, 1, 4, 1, 0, 0, 0, 0, 0 },
    [SAVE]           = { KAE_BINDING, "Save position", "Remembers where Link stands.", 0, 0, 0, 0, 0, 0, KAE_L | KAE_LEFT, KAE_L | KAE_LEFT, 0, 0 },
    [LOAD]           = { KAE_BINDING, "Load position", "Puts Link back where he was saved.", 0, 0, 0, 0, 0, 0, KAE_L | KAE_RIGHT, KAE_L | KAE_RIGHT, 0, 0 },
    [LEVITATE]       = { KAE_BINDING, "Levitate (hold)", "Lifts Link while the buttons are held.", 0, 0, 0, 0, 0, 0, KAE_L | KAE_UP, KAE_L | KAE_UP, 0, 0 },
    [LEVITATE_SPEED] = { KAE_NUMBER, "Levitate speed", "Centimetres a frame.", 10, 10, 2, 50, 2, 0, 0, 0, 0, 0 },
    [SAVE_NOW]       = { KAE_ACTION, "Save position now", "The same as the Save position buttons.", 0, 0, 0, 0, 0, 0, 0, 0, save_now, 0 },
    [LOAD_NOW]       = { KAE_ACTION, "Load position now", "The same as the Load position buttons.", 0, 0, 0, 0, 0, 0, 0, 0, load_now, 0 },
};

// ---- what the game's thread leaves for the render thread to show ----
static struct {
    uint64_t buttons;
    int32_t lx, ly, rx, ry;
    float position[3], speed;      // speed: metres a second, from frame to frame
    int link_seen;                 // frames since Link's movement update last ran, capped
    int has_save;
    int note_frames;               // how long the note below stays up
    const char *note;
} shown = { .link_seen = 1000 };

// ---- the game ----
static void *vt_actor, *vt_player, *vt_cct;
static void (*change_position)(void *controller, const float position[4]);
static int64_t position_offset;

static float saved[3];
static int want_save, want_load, levitating;
static uint64_t held_before;

static void note(const char *text) {
    shown.note = text;
    shown.note_frames = 120;
}

static void save_now(KaeItem *item, void *user) { (void)item; (void)user; want_save = 1; }
static void load_now(KaeItem *item, void *user) { (void)item; (void)user; want_load = 1; }

// Link's character controller if `actor` is Link's physics actor, else null. The walk FPV Drone
// and Mouse Grab use, tested in the game on 1.1.1: the actor's movement component sits inside
// Link's player object, whose resource is named "Player".
static void *links_controller(void *actor) {
    if (!kae_readable(actor, 0x340) || AT(actor, 0, void *) != vt_actor)
        return 0;
    char *components = AT(actor, 0x270, char *);
    if (!components || !kae_readable(components, 0x328))
        return 0;
    char *movement = AT(components, 0x320, char *);
    if (!movement || !kae_readable(movement - 0x1d50, 0x1d70) || AT(movement, 0x18, void *) != actor)
        return 0;
    char *player = movement - 0x1d50;
    if (AT(player, 0, void *) != vt_player)
        return 0;
    char *resource = AT(player, 0x10, char *);
    if (!resource || !kae_readable(resource, 0x60) || AT(resource, 0x58, uint32_t) != 0x79616c50 ||
        AT(resource, 0x5c, uint16_t) != 0x7265 || resource[0x5e])       // "Player"
        return 0;
    char *controller = components;
    static const uint8_t chain[4] = { 0x50, 0x20, 0x10, 0x08 };
    for (int i = 0; i < 4; i++) {
        if (!kae_readable(controller + chain[i], 8))
            return 0;
        controller = AT(controller, chain[i], char *);
        if (!controller)
            return 0;
    }
    return kae_readable(controller, 8) && AT(controller, 0, void *) == vt_cct ? controller : 0;
}

static float root(float v) {
    if (v <= 0)
        return 0;
    float r = v > 1 ? v : 1;
    for (int i = 0; i < 20; i++)
        r = 0.5f * (r + v / r);
    return r;
}

// Every physics actor's movement update, on the game's thread. Link's is where he can be moved.
static void actor_move(void *actor, void *user) {
    (void)user;
    void *controller = links_controller(actor);
    if (!controller)
        return;
    float *position = &AT(actor, position_offset, float);
    float d[3] = { position[0] - shown.position[0], position[1] - shown.position[1], position[2] - shown.position[2] };
    // the game's own rate is 30 updates a second on this game; shown as distance per update x 30
    shown.speed = shown.link_seen == 0 ? root(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) * 30.0f : 0;
    for (int i = 0; i < 3; i++)
        shown.position[i] = position[i];
    shown.link_seen = 0;

    if (want_save) {
        want_save = 0;
        for (int i = 0; i < 3; i++)
            saved[i] = position[i];
        shown.has_save = 1;
        note("position saved");
    }
    float to[4] = { position[0], position[1], position[2], 0 };
    int move = 0;
    if (want_load) {
        want_load = 0;
        if (shown.has_save) {
            for (int i = 0; i < 3; i++)
                to[i] = saved[i];
            move = 1;
            note("position loaded");
        } else {
            note("no position saved yet");
        }
    }
    if (levitating) {
        to[1] += (float)settings[LEVITATE_SPEED].value / 100.0f;
        move = 1;
    }
    if (move)
        change_position(controller, to);
}

static int held(uint64_t buttons, const KaeItem *item) {
    return item->binding && (buttons & item->binding) == item->binding;
}

// Every controller read, on the game's thread.
static void input(KaeInput *seen_by_game, const KaeInput *real, void *user) {
    (void)user;
    if (!real->connected)
        return;
    shown.buttons = real->buttons;
    shown.lx = real->lx; shown.ly = real->ly; shown.rx = real->rx; shown.ry = real->ry;
    if (shown.link_seen < 1000)
        shown.link_seen++;
    if (kae_menu_open()) {
        levitating = 0;
        held_before = real->buttons;
        return;
    }
    uint64_t now = real->buttons, hide = 0;
    if (held(now, &settings[SAVE])) {
        if (!held(held_before, &settings[SAVE]))
            want_save = 1;
        hide |= settings[SAVE].binding;
    }
    if (held(now, &settings[LOAD])) {
        if (!held(held_before, &settings[LOAD]))
            want_load = 1;
        hide |= settings[LOAD].binding;
    }
    levitating = held(now, &settings[LEVITATE]);
    if (levitating)
        hide |= settings[LEVITATE].binding;
    seen_by_game->buttons &= ~hide;       // the game doesn't also act on a combination that was used here
    held_before = now;
}

// ---- drawing, on the render thread ----
static char *put(char *out, const char *text) {
    while (*text)
        *out++ = *text++;
    *out = 0;
    return out;
}

// A number with two decimals, right-aligned in `width` characters.
static char *put_fixed(char *out, float value, int width) {
    char digits[24];
    int n = 0, negative = value < 0;
    double v = negative ? -(double)value : (double)value;
    if (v > 9999999.0)
        v = 9999999.0;
    uint64_t hundredths = (uint64_t)(v * 100.0 + 0.5);
    for (int i = 0; i < 2 || hundredths; i++) {
        if (i == 2)
            digits[n++] = '.';
        digits[n++] = (char)('0' + hundredths % 10);
        hundredths /= 10;
    }
    if (n == 2)
        digits[n++] = '.';
    if (digits[n - 1] == '.')
        digits[n++] = '0';
    if (negative)
        digits[n++] = '-';
    for (int i = n; i < width; i++)
        *out++ = ' ';
    while (n)
        *out++ = digits[--n];
    *out = 0;
    return out;
}

static char *put_int(char *out, int value, int width) {
    char digits[12];
    int n = 0, negative = value < 0;
    unsigned v = negative ? 0u - (unsigned)value : (unsigned)value;
    do
        digits[n++] = (char)('0' + v % 10);
    while (v /= 10);
    if (negative)
        digits[n++] = '-';
    for (int i = n; i < width; i++)
        *out++ = ' ';
    while (n)
        *out++ = digits[--n];
    *out = 0;
    return out;
}

enum { PLATE = 0x101820, LIT = 0xFFFFFF, DIM = 0x56645C, LABEL = 0x9AA79F, GOLD = 0xFFD040 };

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    if (kae_menu_open())
        return;
    int scale = settings[HUD_SIZE].value, line = 18 * scale, pad = 6 * scale;
    int lines = (settings[INPUT_DISPLAY].value ? 2 : 0) + (settings[POSITION_WATCH].value ? 2 : 0) + (shown.note_frames > 0);
    if (!lines)
        return;
    int width = 44 * 8 * scale + 2 * pad, height = lines * line + 2 * pad;
    int x = f->height / 45, y = f->height - f->height / 45 - height;
    kae_draw_rect(x, y, width, height, PLATE);
    x += pad;
    y += pad;
    char text[96];
    if (settings[INPUT_DISPLAY].value) {
        static const struct { const char *name; uint64_t bit; } buttons[] = {
            { "A", KAE_A }, { "B", KAE_B }, { "X", KAE_X }, { "Y", KAE_Y }, { "L", KAE_L }, { "R", KAE_R },
            { "ZL", KAE_ZL }, { "ZR", KAE_ZR }, { "+", KAE_PLUS }, { "-", KAE_MINUS }, { "<", KAE_LEFT },
            { "^", KAE_UP }, { ">", KAE_RIGHT }, { "v", KAE_DOWN }, { "L3", KAE_L3 }, { "R3", KAE_R3 },
        };
        int pen = x;
        for (unsigned i = 0; i < sizeof buttons / sizeof *buttons; i++)
            pen = kae_draw_text(pen, y, scale, shown.buttons & buttons[i].bit ? LIT : DIM, buttons[i].name) + 8 * scale;
        y += line;
        char *end = put(text, "L ");
        end = put_int(end, shown.lx, 6);
        end = put_int(end, shown.ly, 7);
        end = put(end, "   R ");
        end = put_int(end, shown.rx, 6);
        put_int(end, shown.ry, 7);
        kae_draw_text(x, y, scale, LABEL, text);
        y += line;
    }
    if (settings[POSITION_WATCH].value) {
        if (shown.link_seen < 30) {
            char *end = put(text, "pos ");
            for (int i = 0; i < 3; i++)
                end = put_fixed(end, shown.position[i], 11);
            kae_draw_text(x, y, scale, LIT, text);
            end = put(text, "speed ");
            end = put_fixed(end, shown.speed, 7);
            put(end, shown.has_save ? " m/s   saved" : " m/s");
            kae_draw_text(x, y + line, scale, LABEL, text);
        } else {
            kae_draw_text(x, y, scale, DIM, "pos  (Link isn't moving in the world)");
        }
        y += 2 * line;
    }
    if (shown.note_frames > 0) {
        shown.note_frames--;
        kae_draw_text(x, y, scale, GOLD, shown.note);
    }
}

static int start(void) {
    vt_actor = kae_sym("vtable.Actor");
    vt_player = kae_sym("vtable.Player");
    vt_cct = kae_sym("vtable.Cct");
    change_position = (void (*)(void *, const float *))kae_sym("CctChangePosition");
    position_offset = kae_field("Actor.position");
    if (!vt_actor || !vt_player || !vt_cct || !change_position || position_offset < 0) {
        KAE_LOG("this game version's symbols are missing: not starting");
        return 1;
    }
    if (kae_on_input(input, 0, 0) != KAE_OK || kae_on_draw(draw, 0, 0) != KAE_OK)
        return 2;
    if (kae_on_actor_move(actor_move, 0, 0) != KAE_OK)
        KAE_LOG("no actor_move event: the position watch, save / load and levitate are off");
    kae_settings("Sloped Up Sloperina", settings, sizeof settings / sizeof *settings);
    KAE_LOG("sloped up sloperina 0.1.0: input display, position watch, save / load position, levitate");
    return 0;
}

KAE_MOD("kabosune.sloped-up-sloperina", "0.1.0", start, 0);
