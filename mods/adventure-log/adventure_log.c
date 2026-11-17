// Adventure Log: the game's own play log (the one 1.1.1 keeps for Zelda Notes), shown in the game.
//
// Game version 1.1.1 keeps a rolling log of 1,024 events in memory (and in option.sav), even with
// Zelda Notes never set up and offline. This mod reads it each frame and shows it on screen: counts
// by kind, and the newest entries with their names. It can also write each new entry to the log, so
// the kinds can be named by doing one thing at a time (test 0.1.0).
//
// The log (1.1.1, main 0x4E6B718 holds the recorder; found 17 Nov 2026 from the function that copies
// it into the save, 0x587E80, and the one that adds an entry, 0xE46590):
//   recorder + 0x0000  1,024 entries of 24 bytes: u32 time, u32 kind, u32 name1, u32 name2, s32 value1, s32 value2
//   recorder + 0x6000  u32 next slot to write, u32 number of entries (up to 1,024)
// Times are seconds since 1 January 2026, UTC. Actor names are CRC32 of the name, scene and event
// names MurmurHash3 (names.c holds the game's actor, scene and event flow names).
// 1.0.0 has no log, so the mod does nothing there.
#include <kaegae.h>

extern const uint32_t notes_name_count;
extern const uint32_t notes_name_hash[];
extern const uint32_t notes_name_off[];
extern const char notes_name_blob[];

#define RECORDER_SLOT 0x4E6B718u      // 1.1.1: pointer to the recorder (raw offset: 1.1.1 only)
#define LOG_SIZE      1024
#define HEAD_OFFSET   0x6000
#define RECENT_MAX    20
#define KINDS         64

typedef struct {
    uint32_t time, kind, name1, name2;
    int32_t value1, value2;
} Entry;

// What each kind seems to be, from one save (17 Nov 2026). '?' = a guess, to be checked.
static const char *kind_name(uint32_t kind) {
    switch (kind) {
    case 2:  return "enemy hit Link?";
    case 3:  return "Link hit something?";
    case 4:  return "Z-target?";
    case 5:  return "cucco flight?";
    case 11: return "picked up";
    case 14: return "talk line";
    case 16: return "event (blank = end)";
    case 23: return "lift";
    case 24: return "throw / put down";
    case 25: return "area change";
    case 27: return "equip change";
    case 28: return "was hit by?";
    case 30: return "learned song";
    case 33: return "object gone?";
    case 37: return "defeated?";
    case 38: return "dropped item";
    default: return "?";
    }
}

static const char *const size_names[] = { "Small", "Medium", "Large" };

enum { SHOW, TOGGLE, SIZE, RECENT, CLOCK, LOG_NEW };
static KaeItem settings[] = {
    [SHOW]    = { KAE_TOGGLE, "Show on screen", "The log panel in the top left corner.", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
    [TOGGLE]  = { KAE_BINDING, "Show / hide", "Buttons or a key to switch the panel on and off.", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [SIZE]    = { KAE_CHOICE, "Text size", 0, 0, 0, 0, 2, 0, size_names, 0, 0, 0, 0 },
    [RECENT]  = { KAE_NUMBER, "Newest entries shown", 0, 10, 10, 0, RECENT_MAX, 1, 0, 0, 0, 0, 0 },
    [CLOCK]   = { KAE_NUMBER, "Clock: hours from UTC", "-8 is US Pacific time in winter.", -8, -8, -12, 14, 1, 0, 0, 0, 0, 0 },
    [LOG_NEW] = { KAE_TOGGLE, "Write new entries to the log", "Each new entry as a line in the emulator's log.", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
};

// ---- names ----
static const char *name_of(uint32_t hash) {
    if (!hash)
        return "-";
    uint32_t lo = 0, hi = notes_name_count;
    while (lo < hi) {
        uint32_t mid = (lo + hi) / 2;
        if (notes_name_hash[mid] < hash)
            lo = mid + 1;
        else
            hi = mid;
    }
    if (lo < notes_name_count && notes_name_hash[lo] == hash)
        return notes_name_blob + notes_name_off[lo];
    return 0;
}

// ---- reading the game's log, on the game's thread ----
static uintptr_t slot;               // where main keeps the recorder pointer
static uintptr_t recorder;           // the recorder, once the game has made it
static uint32_t last_head;
static int synced;

static struct {                      // left for the render thread
    int state;                       // 0 no recorder yet, 1 reading, 2 something looks wrong
    uint32_t count;                  // entries in the game's log
    uint32_t session;                // entries added since the mod started
    uint32_t newest_time;
    uint32_t kinds_session[KINDS], kinds_log[KINDS];
    Entry recent[RECENT_MAX];
    int recent_n;
} shown;

static int panel_on = -1;            // -1: follow the setting

static const Entry *entry_at(uint32_t i) { return (const Entry *)(recorder + (uintptr_t)i * sizeof(Entry)); }

static void log_entry(const Entry *e) {
    const char *a = name_of(e->name1), *b = name_of(e->name2);
    char ha[12], hb[12];
    if (!a) {
        static const char hex[] = "0123456789abcdef";
        for (int k = 0; k < 8; k++) ha[k] = hex[(e->name1 >> (28 - 4 * k)) & 15];
        ha[8] = 0;
        a = ha;
    }
    if (!b) {
        static const char hex[] = "0123456789abcdef";
        for (int k = 0; k < 8; k++) hb[k] = hex[(e->name2 >> (28 - 4 * k)) & 15];
        hb[8] = 0;
        b = hb;
    }
    KAE_LOG("adventure log: t=%u kind %u (%s) %s %s %d %d", e->time, e->kind, kind_name(e->kind), a, b,
            e->value1, e->value2);
}

static void snapshot(uint32_t head, uint32_t count) {
    for (int k = 0; k < KINDS; k++)
        shown.kinds_log[k] = 0;
    for (uint32_t i = 0; i < count; i++) {
        uint32_t kind = entry_at(i)->kind;
        if (kind < KINDS)
            shown.kinds_log[kind]++;
    }
    int n = settings[RECENT].value;
    if (n > RECENT_MAX) n = RECENT_MAX;
    if ((uint32_t)n > count) n = (int)count;
    for (int k = 0; k < n; k++)               // newest first
        shown.recent[k] = *entry_at((head + LOG_SIZE - 1 - (uint32_t)k) % LOG_SIZE);
    shown.recent_n = n;
    shown.count = count;
    shown.newest_time = count ? entry_at((head + LOG_SIZE - 1) % LOG_SIZE)->time : 0;
}

static void frame(void *user) {
    (void)user;
    if (kae_binding_pressed(&settings[TOGGLE]))
        panel_on = !(panel_on < 0 ? settings[SHOW].value : panel_on);

    if (!kae_readable((const void *)slot, 8))
        return;
    uintptr_t r = *(const uintptr_t *)slot;
    if (r != recorder) {
        recorder = r;
        synced = 0;
        if (r)
            KAE_LOG("adventure log: the game's recorder is at %p", (void *)r);
    }
    if (!recorder) {
        shown.state = 0;
        return;
    }
    if (!kae_readable((const void *)recorder, HEAD_OFFSET + 8)) {
        shown.state = 2;
        return;
    }
    const uint32_t *h = (const uint32_t *)(recorder + HEAD_OFFSET);
    uint32_t head = h[0], count = h[1];
    if (head >= LOG_SIZE || count > LOG_SIZE) {
        if (shown.state != 2)
            KAE_LOG("adventure log: the log looks wrong (next %u, count %u): not reading it", head, count);
        shown.state = 2;
        return;
    }
    shown.state = 1;
    if (!synced) {
        synced = 1;
        last_head = head;
        KAE_LOG("adventure log: the game's log has %u entries, next slot %u", count, head);
        snapshot(head, count);
        return;
    }
    if (head == last_head)
        return;
    uint32_t added = (head + LOG_SIZE - last_head) % LOG_SIZE;
    if (added > 64) {   // far more than a frame's worth: the game read the log back from a save
        KAE_LOG("adventure log: %u entries at once (the log was read back from the save?): not counted", added);
    } else {
        for (uint32_t k = 0; k < added; k++) {
            const Entry *e = entry_at((last_head + k) % LOG_SIZE);
            shown.session++;
            if (e->kind < KINDS)
                shown.kinds_session[e->kind]++;
            if (settings[LOG_NEW].value)
                log_entry(e);
        }
    }
    last_head = head;
    snapshot(head, count);
}

// ---- drawing, on the render thread ----
static char *put(char *out, const char *s) {
    while (*s)
        *out++ = *s++;
    *out = 0;
    return out;
}

static char *put_n(char *out, const char *s, int max) {
    int n = 0;
    while (s[n] && n < max)
        n++;
    for (int k = 0; k < n; k++)
        *out++ = s[k];
    if (s[n]) {             // cut: show it was
        out[-1] = '~';
    }
    *out = 0;
    return out;
}

static char *put_int(char *out, long long v, int width) {
    char d[24];
    int n = 0, neg = v < 0;
    unsigned long long u = neg ? (unsigned long long)-v : (unsigned long long)v;
    do
        d[n++] = (char)('0' + u % 10);
    while (u /= 10);
    if (neg)
        d[n++] = '-';
    while (n < width)
        d[n++] = '0';
    while (n)
        *out++ = d[--n];
    *out = 0;
    return out;
}

static char *put_hash(char *out, uint32_t hash) {
    const char *n = name_of(hash);
    if (n)
        return put_n(out, n, 34);
    static const char hex[] = "0123456789abcdef";
    *out++ = '#';
    for (int k = 0; k < 8; k++)
        *out++ = hex[(hash >> (28 - 4 * k)) & 15];
    *out = 0;
    return out;
}

static char *put_clock(char *out, uint32_t time) {
    long long t = (long long)time + (long long)settings[CLOCK].value * 3600;
    long long day = t % 86400;
    if (day < 0)
        day += 86400;
    out = put_int(out, day / 3600, 2);
    *out++ = ':';
    out = put_int(out, day / 60 % 60, 2);
    *out++ = ':';
    return put_int(out, day % 60, 2);
}

enum { PLATE = 0x101820, LIT = 0xFFFFFF, DIM = 0x7A8A80, LABEL = 0x9AA79F, GOLD = 0xFFD040, GREEN = 0x80E090 };

// The kinds worth a line of their own, in this order.
static const uint8_t headline[] = { 37, 2, 3, 25, 11, 14, 30, 4, 23 };

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    int on = panel_on < 0 ? settings[SHOW].value : panel_on;
    if (!on || kae_menu_open())
        return;
    int s = settings[SIZE].value + 1;
    int line = 18 * s, pad = 8 * s;
    int recent = shown.state == 1 ? shown.recent_n : 0;
    int lines = 3 + (shown.state == 1 ? (int)(sizeof headline) + 2 + (recent ? 1 + recent : 0) : 0);
    int width = 74 * 8 * s + 2 * pad;
    if (width > f->width - 20)
        width = f->width - 20;
    int x = f->width / 60, y = f->height / 30;
    kae_draw_rect(x, y, width, lines * line + 2 * pad, PLATE);
    x += pad;
    y += pad;
    char text[160];

    kae_draw_text(x, y, s, GOLD, "Adventure Log");
    kae_draw_text(x + 15 * 8 * s, y, s, DIM, "the game's own log (kept for Zelda Notes)");
    y += line;
    if (shown.state != 1) {
        kae_draw_text(x, y, s, LABEL, shown.state == 0 ? "Waiting for the game's log (it starts with a save loaded)."
                                                       : "The game's log doesn't look right: see the emulator log.");
        return;
    }
    char *p = put(text, "This session: ");
    p = put_int(p, shown.session, 0);
    p = put(p, "    In the log: ");
    p = put_int(p, shown.count, 0);
    p = put(p, " of 1024");
    if (shown.newest_time) {
        p = put(p, "    newest ");
        p = put_clock(p, shown.newest_time);
    }
    kae_draw_text(x, y, s, LIT, text);
    y += line;
    kae_draw_text(x, y, s, DIM, "                          session    log");
    y += line;
    for (unsigned k = 0; k < sizeof headline; k++) {
        int kind = headline[k];
        p = put(text, kind_name((uint32_t)kind));
        while (p < text + 26)
            *p++ = ' ';
        *p = 0;
        char num[16];
        char *end = put_int(num, shown.kinds_session[kind], 0);
        for (int pad_n = 7 - (int)(end - num); pad_n > 0; pad_n--)
            *p++ = ' ';
        p = put(p, num);
        p = put(p, "   ");
        p = put_int(p, shown.kinds_log[kind], 0);
        kae_draw_text(x, y, s, shown.kinds_session[kind] ? LIT : LABEL, text);
        y += line;
    }
    // every kind seen this session, as "kind:count"
    p = put(text, "All kinds this session: ");
    int any = 0;
    for (int k = 0; k < KINDS && p < text + 140; k++) {
        if (!shown.kinds_session[k])
            continue;
        p = put_int(p, k, 0);
        *p++ = ':';
        p = put_int(p, shown.kinds_session[k], 0);
        *p++ = ' ';
        *p = 0;
        any = 1;
    }
    if (!any)
        put(p, "none yet");
    kae_draw_text(x, y, s, LABEL, text);
    y += line;
    if (!recent)
        return;
    kae_draw_text(x, y, s, DIM, "Newest:");
    y += line;
    for (int k = 0; k < recent; k++) {
        const Entry *e = &shown.recent[k];
        p = put_clock(text, e->time);
        p = put(p, "  ");
        p = put_int(p, e->kind, 2);
        *p++ = ' ';
        p = put_n(p, kind_name(e->kind), 20);
        while (p < text + 34)
            *p++ = ' ';
        *p = 0;
        if (e->name1 || e->name2) {
            p = put_hash(p, e->name1);
            if (e->name2) {
                p = put(p, " > ");
                p = put_hash(p, e->name2);
            }
        }
        if ((e->value1 || e->value2) && e->kind != 14 && e->kind != 25 && p < text + 130) {
            p = put(p, "  (");
            p = put_int(p, e->value1, 0);
            p = put(p, ", ");
            p = put_int(p, e->value2, 0);
            p = put(p, ")");
        }
        kae_draw_text(x, y, s, k == 0 ? GREEN : LIT, text);
        y += line;
    }
}

static int start(void) {
    const char *v = kae_game_version();
    if (v[0] != '1' || v[1] != '.' || v[2] != '1' || v[3] != '.' || v[4] != '1' || v[5]) {
        KAE_LOG("adventure log: game %s has no play log (only 1.1.1 does): doing nothing", v[0] ? v : "unknown");
        return 2;
    }
    uintptr_t base = kae_game_base();
    if (!base)
        return 2;
    slot = base + RECORDER_SLOT;
    if (kae_on_frame(frame, 0, 0) != KAE_OK || kae_on_draw(draw, 0, 0) != KAE_OK)
        return 2;
    kae_settings("Adventure Log", settings, sizeof settings / sizeof *settings);
    KAE_LOG("adventure log 0.1.0 on game 1.1.1, %u names", notes_name_count);
    return 0;
}

KAE_MOD("kabosune.adventure-log", "0.1.0", start, 0);
