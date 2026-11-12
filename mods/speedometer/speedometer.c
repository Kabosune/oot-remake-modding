// Speedometer: how fast Link is going, as a big number and a bar, with his top speed and how fast
// he is rising or falling. On KaeGae Core.
//
// Speed comes from how far Link moved between two of his movement updates, times 30: the game
// runs 30 updates a second (the same rate Slopped Up Sloperina's position watch uses). No game
// address is written here.
#include <kaegae.h>

static void reset_top(KaeItem *item, void *user);

static const char *const unit_names[] = { "m/s", "km/h", "mph" };
static const float unit_scale[] = { 1.0f, 3.6f, 2.236936f };
static const char *const corner_names[] = { "Bottom right", "Bottom left", "Top right", "Top left" };

enum { UNITS, CORNER, SIZE, BAR_FULL, WITH_FALL, SHOW_TOP, SHOW_VERTICAL, RESET_TOP };
static KaeItem settings[] = {
    [UNITS]         = { KAE_CHOICE, "Units", 0, 1, 1, 0, 2, 0, unit_names, 0, 0, 0, 0 },
    [CORNER]        = { KAE_CHOICE, "Corner", "Where on the screen it sits.", 0, 0, 0, 3, 0, corner_names, 0, 0, 0, 0 },
    [SIZE]          = { KAE_NUMBER, "Size", 0, 2, 2, 1, 4, 1, 0, 0, 0, 0, 0 },
    [BAR_FULL]      = { KAE_NUMBER, "Bar full at (m/s)", "The speed that fills the bar.", 12, 12, 2, 40, 1, 0, 0, 0, 0, 0 },
    [WITH_FALL]     = { KAE_TOGGLE, "Count falling", "Off: only speed along the ground.", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [SHOW_TOP]      = { KAE_TOGGLE, "Show top speed", 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
    [SHOW_VERTICAL] = { KAE_TOGGLE, "Show rise / fall", 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
    [RESET_TOP]     = { KAE_ACTION, "Reset top speed", 0, 0, 0, 0, 0, 0, 0, 0, 0, reset_top, 0 },
};

#define RATE 30.0f        // Link's movement updates a second
#define JUMP 50.0f        // metres in one update: a warp or a reload, not running

static float root(float v) {
    float r;
    __asm__("fsqrt %s0, %s1" : "=w"(r) : "w"(v));
    return r;
}

// ---- the game's thread ----
static float last[3];
static int have_last;
static int frames_away = 1000;
static int want_reset;

// what it leaves for the render thread
static struct {
    float speed;       // m/s, smoothed
    float top;         // m/s
    float vertical;    // m/s, up is positive
    int seen;          // Link moved in the world recently
} shown;

static void reset_top(KaeItem *item, void *user) { (void)item; (void)user; want_reset = 1; }

static void frame(void *user) {
    (void)user;
    if (frames_away < 1000)
        frames_away++;
    shown.seen = frames_away < 30;
}

static void player_move(const KaePlayer *link, void *user) {
    (void)user;
    const float *p = link->position;
    if (want_reset) {
        want_reset = 0;
        shown.top = 0;
    }
    if (frames_away > 2)
        have_last = 0;
    frames_away = 0;
    if (have_last) {
        float dx = p[0] - last[0], dy = p[1] - last[1], dz = p[2] - last[2];
        float ground = dx * dx + dz * dz, all = ground + dy * dy;
        if (all < JUMP * JUMP) {
            float now = root(settings[WITH_FALL].value ? all : ground) * RATE;
            shown.speed += (now - shown.speed) * 0.35f;          // a little smoothing against jitter
            if (shown.speed < 0.05f)
                shown.speed = 0;
            if (now > shown.top)
                shown.top = now;
            shown.vertical += (dy * RATE - shown.vertical) * 0.35f;
        }
    }
    for (int i = 0; i < 3; i++)
        last[i] = p[i];
    have_last = 1;
}

// ---- drawing, on the render thread ----
static char *put(char *out, const char *text) {
    while (*text)
        *out++ = *text++;
    *out = 0;
    return out;
}

// One decimal. Negative numbers get a '-'.
static char *put_tenths(char *out, float value) {
    if (value < 0) {
        *out++ = '-';
        value = -value;
    }
    if (value > 99999.0f)
        value = 99999.0f;
    unsigned tenths = (unsigned)(value * 10.0f + 0.5f);
    char digits[12];
    int n = 0;
    digits[n++] = (char)('0' + tenths % 10);
    digits[n++] = '.';
    tenths /= 10;
    do
        digits[n++] = (char)('0' + tenths % 10);
    while (tenths /= 10);
    while (n)
        *out++ = digits[--n];
    *out = 0;
    return out;
}

enum { PLATE = 0x101820, LIT = 0xFFFFFF, DIM = 0x56645C, LABEL = 0x9AA79F, GOLD = 0xFFD040, TRACK = 0x2A3530 };

// green, through yellow, to red as the bar fills
static uint32_t bar_colour(float fill) {
    if (fill < 0.5f) {
        unsigned r = (unsigned)(0x40 + fill * 2 * (0xFF - 0x40));
        return r << 16 | 0xD040;
    }
    unsigned g = (unsigned)(0xD0 - (fill - 0.5f) * 2 * (0xD0 - 0x40));
    return 0xFF0000 | g << 8 | 0x40;
}

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    if (kae_menu_open())
        return;
    int s = settings[SIZE].value, pad = 6 * s, line = 18 * s;
    int width = 14 * 8 * s + 2 * pad;
    int lines_small = (settings[SHOW_TOP].value || settings[SHOW_VERTICAL].value) ? 1 : 0;
    int height = 2 * pad + 16 * 2 * s + 4 * s + 8 * s + 4 * s + lines_small * line;
    int margin = f->height / 45;
    int corner = settings[CORNER].value;
    int x = (corner == 0 || corner == 2) ? f->width - margin - width : margin;
    int y = (corner == 0 || corner == 1) ? f->height - margin - height : margin;
    kae_draw_rect(x, y, width, height, PLATE);
    x += pad;
    y += pad;

    int unit = settings[UNITS].value;
    float scale = unit_scale[unit];
    char text[48];
    if (shown.seen) {
        put_tenths(text, shown.speed * scale);
        int at = shown.top > 0.5f && shown.speed >= shown.top * 0.98f ? GOLD : LIT;
        int end = kae_draw_text(x, y, 2 * s, at, text);
        kae_draw_text(end + 4 * s, y + 16 * s, s, LABEL, unit_names[unit]);
    } else {
        int end = kae_draw_text(x, y, 2 * s, DIM, "--");
        kae_draw_text(end + 4 * s, y + 16 * s, s, DIM, unit_names[unit]);
    }
    y += 16 * 2 * s + 4 * s;

    // the bar
    int bar_w = width - 2 * pad, bar_h = 8 * s;
    float fill = shown.seen ? shown.speed / (float)settings[BAR_FULL].value : 0;
    if (fill > 1)
        fill = 1;
    kae_draw_rect(x, y, bar_w, bar_h, TRACK);
    int filled = (int)(fill * (float)bar_w);
    if (filled > 0)
        kae_draw_rect(x, y, filled, bar_h, bar_colour(fill));
    y += bar_h + 4 * s;

    if (lines_small) {
        int pen = x;
        if (settings[SHOW_TOP].value) {
            char *end = put(text, "top ");
            put_tenths(end, shown.top * scale);
            pen = kae_draw_text(pen, y, s, LABEL, text) + 16 * s;
        }
        if (settings[SHOW_VERTICAL].value && shown.seen) {
            float v = shown.vertical * scale;
            char *end = put(text, v > 0.05f ? "^ " : v < -0.05f ? "v " : "  ");
            put_tenths(end, v < 0 ? -v : v);
            kae_draw_text(pen, y, s, v < -0.05f ? 0x80B0FF : LABEL, text);
        }
    }
}

static int start(void) {
    if (kae_on_player_move(player_move, 0, 0) != KAE_OK) {
        KAE_LOG("speedometer: no player_move event in this game: doing nothing");
        return 2;
    }
    if (kae_on_frame(frame, 0, 0) != KAE_OK || kae_on_draw(draw, 0, 0) != KAE_OK)
        return 2;
    kae_settings("Speedometer", settings, sizeof settings / sizeof *settings);
    KAE_LOG("speedometer 0.1.0");
    return 0;
}

KAE_MOD("kabosune.speedometer", "0.1.0", start, 0);
