// Adventure Log: the game's own play log (the one 1.1.1 keeps for Zelda Notes), shown in the game.
//
// Game version 1.1.1 keeps a rolling log of 1,024 events in memory (and in option.sav), even with
// Zelda Notes never set up and offline. This mod reads it each frame and shows it on screen: counts
// by kind, and the newest entries with their names. It can also write each new entry to the log, so
// the rest of the kinds can be named by doing one thing at a time.
//
// The log (1.1.1, main 0x4E6B718 holds the recorder; found 17 Nov 2026 from the function that copies
// it into the save, 0x587E80, and the one that adds an entry, 0xE46590):
//   recorder + 0x0000  1,024 entries of 24 bytes: u32 time, u32 kind, u32 name1, u32 name2, s32 value1, s32 value2
//   recorder + 0x6000  u32 next slot to write, u32 number of entries (up to 1,024)
// Times are seconds since 1 January 2026, UTC. Actor names are CRC32 of the name, scene and event
// names MurmurHash3 (names.c holds the game's actor, scene and event flow names).
// 1.0.0 has no log, so the mod does nothing there.
//
// Jumps, rolls and sword swings since the file began: the game keeps them as Int64 GameData fields
// (found 19 Nov 2026 by a save diff; their names aren't known, only their hashes). Read from the
// GameData manager (Core's name GameDataMgrPtr): each field type has a 0x60-byte block in it, at
// 0x10 + type * 0x60; Int64 is type 22, so +0x850: u32 count, records at +0x858 (0x30 bytes each,
// the value at +0x20), a {u32 hash, u32 index} map at +0x860 with its size at +0x86C (open
// addressing from hash % size, as the game's own getters do).
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
#define HIGHLIGHTS    4

typedef struct {
    uint32_t time, kind, name1, name2;
    int32_t value1, value2;
} Entry;

// What each kind is. From two saves and a test round (19 Nov 2026: one thing at a time, logged);
// '?' = still a guess. Jumps and rolls aren't logged (their totals are Int64 fields in the save).
static const char *kind_name(uint32_t kind) {
    switch (kind) {
    case 1:  return "Link hurt";             // by name1; value2 = damage in quarter hearts
    case 2:  return "Link defeated";         // by name1 (Game Over follows)
    case 3:  return "enemy defeated";        // Link, the enemy
    case 4:  return "Z-target";              // the target; no name = let go
    case 5:  return "item readied?";         // value1 = the item's kind
    case 7:  return "item used";             // value1: 3 bomb, 6 bow, 8 hookshot...
    case 8:  return "sword swing";
    case 11: return "picked up";
    case 14: return "talk line";             // who; value1 = the message
    case 16: return "event";                 // no name = it ended (chests, ocarina, falls are events)
    case 17: return "file loaded";          // value1 = the slot
    case 23: return "lift";
    case 24: return "throw / put down";
    case 25: return "area change";           // from, to; values = the two positions
    case 26: return "game saved";           // value1 = the slot
    case 27: return "equip change";          // old, new; value1 = the slot
    case 28: return "hit";                   // target, attacker
    case 30: return "song played";           // the song (Item_Melody_*)
    case 32: return "appeared?";             // enemies and shots coming into play
    case 33: return "removed";               // broken, collected or opened away
    case 34: return "room change";           // values = old and new floor / room
    case 37: return "Link hurt (world)";     // falls, fire, grabs; value2 = damage
    case 38: return "dropped item";          // who dropped it, what
    case 39: return "life / magic";          // value1 = max << 16 | life (quarter hearts), value2 the same for magic
    default: return "?";
    }
}

// Events (kind 16) worth counting by name: MurmurHash3 of the event's name.
#define EV_CHEST_BIG   0x7494876Fu        // Dm_SY_Treasurebox
#define EV_CHEST_SMALL 0x92126ED4u        // Dm_SY_TreasureboxSmall
#define EV_OCARINA     0x956E2065u        // Dm_SY_Ocarina

static const char *const size_names[] = { "Small", "Medium", "Large" };
static const char *const style_names[] = { "Simple", "Detailed" };

enum { SHOW, STYLE, TOGGLE, SIZE, RECENT, CLOCK, LOG_NEW };
static KaeItem settings[] = {
    [SHOW]    = { KAE_TOGGLE, "Show on screen", "The log panel in the top left corner.", 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 },
    [STYLE]   = { KAE_CHOICE, "Panel", "Simple: the highlights. Detailed: every count and the raw log.", 0, 0, 0, 1, 0, style_names, 0, 0, 0, 0 },
    [TOGGLE]  = { KAE_BINDING, "Show / hide", "Buttons or a key to switch the panel on and off.", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [SIZE]    = { KAE_CHOICE, "Text size", 0, 0, 0, 0, 2, 0, size_names, 0, 0, 0, 0 },
    [RECENT]  = { KAE_NUMBER, "Newest entries shown", "On the detailed panel.", 10, 10, 0, RECENT_MAX, 1, 0, 0, 0, 0, 0 },
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

typedef struct {
    uint32_t kinds[KINDS];
    uint32_t chests, ocarina, hurt_quarters;
} Tally;

static void tally_add(Tally *t, const Entry *e) {
    if (e->kind < KINDS)
        t->kinds[e->kind]++;
    if (e->kind == 16 && (e->name1 == EV_CHEST_BIG || e->name1 == EV_CHEST_SMALL))
        t->chests++;
    if (e->kind == 16 && e->name1 == EV_OCARINA)
        t->ocarina++;
    if ((e->kind == 1 || e->kind == 37) && e->value2 > 0 && e->value2 < 1000)
        t->hurt_quarters += (uint32_t)e->value2;
}

static struct {                      // left for the render thread
    int state;                       // 0 no recorder yet, 1 reading, 2 something looks wrong
    uint32_t count;                  // entries in the game's log
    uint32_t session;                // entries added since the mod started
    uint32_t newest_time;
    int32_t life;                    // the newest kind 39's value1, -1 if none
    Tally in_session, in_log, today;
    Entry recent[RECENT_MAX];
    int recent_n;
    uint32_t area;                   // the newest area change's "to" scene (MurmurHash3), 0 if none
    Entry highlight[HIGHLIGHTS];     // the newest entries worth a line on the simple panel
    int highlight_n;
} shown = { .life = -1 };

static int panel_on = -1;            // -1: follow the setting

// ---- the game's own numbers in GameData ----
// Each field type has a 0x60-byte block in the manager at 0x10 + type * 0x60: u32 count, records,
// a {u32 hash, u32 index} map and its size at +0x1C. Records: Int 0x28 bytes (value at +0x1C),
// Int64 0x30 bytes (value at +0x20).
typedef struct { uint32_t block, stride, value; } GdType;
static const GdType GD_INT = { 0xD0, 0x28, 0x1C }, GD_INT64 = { 0x850, 0x30, 0x20 };

enum { T_JUMPS, T_ROLLS, T_SWINGS, T_RUN, T_WALK, TOTALS };
static const uint32_t total_hash[TOTALS] = { 0xA6454431u, 0x4AC3FF5Du, 0x2A24450Au, 0x3EEAFADDu, 0xCE97845Eu };
static const char *const total_name[TOTALS] = { "jumps", "rolls", "sword swings", "metres run", "metres walked" };
// Int fields by their names (MurmurHash3): PlayerStatus.CurrentRupee, .Life, .MaxLife,
// PouchData.Item_Token_Gold.StockNum, PouchData.Obj_Heart_Piece.StockNum
enum { S_RUPEES, S_LIFE, S_MAX_LIFE, S_TOKENS, S_PIECES, STATS };
static const uint32_t stat_hash[STATS] = { 0xA77921D7u, 0x31AB5580u, 0xFBE01DA1u, 0x04735978u, 0x51EC97B3u };
static uintptr_t gdm_slot;           // where main keeps the GameData manager pointer

static struct {                      // left for the render thread
    int state;                       // 0 not read yet, 1 read, 2 the layout doesn't look right
    int64_t now[TOTALS], start[TOTALS];
    int have_stats;
    int32_t stat[STATS];
} totals;

// One field by hash; 1 if found.
static int gd_read(uintptr_t mgr, const GdType *t, uint32_t hash, int64_t *out) {
    uintptr_t b = mgr + t->block;
    if (!kae_readable((const void *)b, 0x20))
        return 0;
    uint32_t count = *(const uint32_t *)b;
    uintptr_t recs = *(const uintptr_t *)(b + 8);
    uintptr_t map = *(const uintptr_t *)(b + 0x10);
    uint32_t size = *(const uint32_t *)(b + 0x1C);
    if (!map || !recs || !size || size > 0x100000 || !count || count > 0x100000)
        return 0;
    if (!kae_readable((const void *)map, (size_t)size * 8) ||
        !kae_readable((const void *)recs, (size_t)count * t->stride))
        return 0;
    const uint32_t *m = (const uint32_t *)map;
    uint32_t start = hash % size, i = start;
    do {
        uint32_t h = m[2 * i];
        if (h == hash) {
            uint32_t index = m[2 * i + 1];
            if (index >= count)
                return 0;
            uintptr_t v = recs + (uintptr_t)index * t->stride + t->value;
            *out = t->stride == 0x30 ? *(const int64_t *)v : *(const int32_t *)v;
            return 1;
        }
        if (!h)
            return 0;
        i = i + 1 < size ? i + 1 : 0;
    } while (i != start);
    return 0;
}

// The records of a type all start with the same pointer (their class): checks the stride.
static int gd_type_ok(uintptr_t mgr, const GdType *t) {
    uintptr_t b = mgr + t->block;
    if (!kae_readable((const void *)b, 0x20))
        return 0;
    uint32_t count = *(const uint32_t *)b;
    uintptr_t recs = *(const uintptr_t *)(b + 8);
    if (count < 2 || !recs || !kae_readable((const void *)recs, 2 * t->stride))
        return 0;
    return *(const uintptr_t *)recs == *(const uintptr_t *)(recs + t->stride);
}

// Every few frames: the totals and the stats.
static void read_totals(void) {
    if (!gdm_slot || totals.state == 2 || !kae_readable((const void *)gdm_slot, 8))
        return;
    uintptr_t mgr = *(const uintptr_t *)gdm_slot;
    if (!mgr)
        return;
    if (totals.state == 0 && !(gd_type_ok(mgr, &GD_INT64) && gd_type_ok(mgr, &GD_INT))) {
        uintptr_t b = mgr + GD_INT64.block;
        if (kae_readable((const void *)b, 0x20) && *(const uint32_t *)b >= 2) {
            KAE_LOG("adventure log: the game's GameData fields don't look as expected: no totals");
            totals.state = 2;
        }
        return;
    }
    int64_t v[TOTALS];
    for (int k = 0; k < TOTALS; k++)
        if (!gd_read(mgr, &GD_INT64, total_hash[k], &v[k]))
            return;                  // not there yet or gone: try again later
    if (!v[T_JUMPS] && !v[T_ROLLS] && !v[T_SWINGS])
        return;                      // all 0: the title screen, before a file is loaded
    int64_t st[STATS];
    int have = 1;
    for (int k = 0; k < STATS; k++)
        if (!gd_read(mgr, &GD_INT, stat_hash[k], &st[k]))
            have = 0;
    if (have)
        for (int k = 0; k < STATS; k++)
            totals.stat[k] = (int32_t)st[k];
    int first_stats = have && !totals.have_stats;
    totals.have_stats |= have;
    if (totals.state == 0) {
        for (int k = 0; k < TOTALS; k++)
            totals.start[k] = totals.now[k] = v[k];
        totals.state = 1;
        KAE_LOG("adventure log: totals: %lld jumps, %lld rolls, %lld sword swings, %lld m run, %lld m walked",
                (long long)v[T_JUMPS], (long long)v[T_ROLLS], (long long)v[T_SWINGS], (long long)v[T_RUN],
                (long long)v[T_WALK]);
    } else {
        for (int k = 0; k < TOTALS; k++) {
            if (v[k] == totals.now[k])
                continue;
            if (v[k] < totals.now[k] || v[k] > totals.now[k] + 100000)    // another file loaded
                totals.start[k] = v[k];
            if (settings[LOG_NEW].value && k < T_RUN)       // distances change every step: see walk_log
                KAE_LOG("adventure log: %s %lld (was %lld)", total_name[k], (long long)v[k], (long long)totals.now[k]);
            totals.now[k] = v[k];
        }
    }
    if (first_stats)
        KAE_LOG("adventure log: %d rupees, life %d / %d (quarter hearts), %d Gold Skulltulas, %d heart pieces",
                totals.stat[S_RUPEES], totals.stat[S_LIFE], totals.stat[S_MAX_LIFE], totals.stat[S_TOKENS],
                totals.stat[S_PIECES]);
}

// ---- distance the mod measures itself (a check on the game's two distance counters) ----
#define RATE 30.0f                   // Link's movement updates a second
static float walked_m;               // along the ground, this session
static float walk_last[3];
static int walk_have, walk_away = 1000;
static uint64_t frames_seen;

static float root(float v) {
    float r;
    __asm__("fsqrt %s0, %s1" : "=w"(r) : "w"(v));
    return r;
}

static void player_move(const KaePlayer *link, void *user) {
    (void)user;
    const float *p = link->position;
    if (walk_away > 2)
        walk_have = 0;
    walk_away = 0;
    if (walk_have) {
        float dx = p[0] - walk_last[0], dz = p[2] - walk_last[2];
        float d = root(dx * dx + dz * dz);
        if (d < 2.0f)                // more than 2 m in one update (60 m/s): a warp or a reload
            walked_m += d;
    }
    for (int k = 0; k < 3; k++)
        walk_last[k] = p[k];
    walk_have = 1;
}

// Every 5 seconds, if Link moved: the mod's distance next to the game's two counters.
static void walk_log(void) {
    static float logged = 0;
    if (!settings[LOG_NEW].value || totals.state != 1 || walked_m - logged < 1.0f)
        return;
    logged = walked_m;
    KAE_LOG("adventure log: distance: %.1f m measured by the mod this session; the game's counters: run +%lld m, walked +%lld m",
            (double)walked_m, (long long)(totals.now[T_RUN] - totals.start[T_RUN]),
            (long long)(totals.now[T_WALK] - totals.start[T_WALK]));
}

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

// The entries the simple panel tells about.
static int is_highlight(const Entry *e) {
    switch (e->kind) {
    case 2: case 3: case 11: case 25: case 26: case 30:
        return 1;
    case 16:
        return e->name1 == EV_CHEST_BIG || e->name1 == EV_CHEST_SMALL;
    default:
        return 0;
    }
}

static void snapshot(uint32_t head, uint32_t count) {
    Tally t = { 0 };
    for (uint32_t i = 0; i < count; i++)
        tally_add(&t, entry_at(i));
    shown.in_log = t;
    for (uint32_t k = 0; k < count; k++) {        // newest life / magic
        const Entry *e = entry_at((head + LOG_SIZE - 1 - k) % LOG_SIZE);
        if (e->kind == 39) {
            shown.life = e->value1;
            break;
        }
    }
    int n = settings[RECENT].value;
    if (n > RECENT_MAX) n = RECENT_MAX;
    if ((uint32_t)n > count) n = (int)count;
    for (int k = 0; k < n; k++)               // newest first
        shown.recent[k] = *entry_at((head + LOG_SIZE - 1 - (uint32_t)k) % LOG_SIZE);
    shown.recent_n = n;
    shown.count = count;
    shown.newest_time = count ? entry_at((head + LOG_SIZE - 1) % LOG_SIZE)->time : 0;

    // today (by the clock setting): the entries on the newest entry's day
    long long offset = (long long)settings[CLOCK].value * 3600;
    long long today = ((long long)shown.newest_time + offset) / 86400;
    Tally d = { 0 };
    shown.area = 0;
    shown.highlight_n = 0;
    for (uint32_t k = 0; k < count; k++) {        // newest first
        const Entry *e = entry_at((head + LOG_SIZE - 1 - k) % LOG_SIZE);
        if (((long long)e->time + offset) / 86400 == today)
            tally_add(&d, e);
        if (!shown.area && e->kind == 25 && e->name2)
            shown.area = e->name2;
        if (shown.highlight_n < HIGHLIGHTS && is_highlight(e))
            shown.highlight[shown.highlight_n++] = *e;
    }
    shown.today = d;
}

static void frame(void *user) {
    (void)user;
    if (kae_binding_pressed(&settings[TOGGLE]))
        panel_on = !(panel_on < 0 ? settings[SHOW].value : panel_on);
    static int tick;
    frames_seen++;
    if (walk_away < 1000)
        walk_away++;
    if (++tick % 10 == 0)
        read_totals();
    if (tick % 150 == 0)
        walk_log();

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
            tally_add(&shown.in_session, e);
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

// The lines of the summary: a label and how to count it.
enum { R_DEFEATED, R_HURT, R_HEARTS, R_GAME_OVER, R_AREAS, R_ROOMS, R_CHESTS, R_PICKED, R_TALK, R_ITEMS,
       R_OCARINA, R_SONGS, ROWS };
static const char *const row_label[ROWS] = {
    "Enemies defeated", "Times hurt", "Hearts lost", "Game Overs", "Areas entered", "Rooms entered",
    "Chests opened", "Things picked up", "Lines of talk", "Items used", "Ocarina taken out", "Songs played",
};

static uint32_t row_value(const Tally *t, int row) {   // hearts lost: in quarter hearts
    switch (row) {
    case R_DEFEATED:  return t->kinds[3];
    case R_HURT:      return t->kinds[1] + t->kinds[37];
    case R_HEARTS:    return t->hurt_quarters;
    case R_GAME_OVER: return t->kinds[2];
    case R_AREAS:     return t->kinds[25];
    case R_ROOMS:     return t->kinds[34];
    case R_CHESTS:    return t->chests;
    case R_PICKED:    return t->kinds[11];
    case R_TALK:      return t->kinds[14];
    case R_ITEMS:     return t->kinds[7];
    case R_OCARINA:   return t->ocarina;
    case R_SONGS:     return t->kinds[30];
    }
    return 0;
}

// A count, or for hearts quarter hearts as "3.25"
static char *put_row_value(char *out, int row, uint32_t v) {
    if (row != R_HEARTS)
        return put_int(out, v, 0);
    out = put_int(out, v / 4, 0);
    static const char *const quarter[] = { "", ".25", ".5", ".75" };
    return put(out, quarter[v % 4]);
}

static void draw_simple(const KaeFrame *f);

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    int on = panel_on < 0 ? settings[SHOW].value : panel_on;
    if (!on || kae_menu_open())
        return;
    if (settings[STYLE].value == 0) {
        draw_simple(f);
        return;
    }
    int s = settings[SIZE].value + 1;
    int line = 18 * s, pad = 8 * s;
    int recent = shown.state == 1 ? shown.recent_n : 0;
    int lines = 3 + (shown.state == 1 ? ROWS + 3 + (recent ? 1 + recent : 0) : 0);
    int width = 112 * 8 * s + 2 * pad;
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
    if (shown.life >= 0) {
        uint32_t life = (uint32_t)shown.life & 0xFFFF, max = (uint32_t)shown.life >> 16;
        p = put(p, "    life ");
        p = put_row_value(p, R_HEARTS, life);
        p = put(p, " / ");
        p = put_row_value(p, R_HEARTS, max);
        p = put(p, " hearts");
    }
    kae_draw_text(x, y, s, LIT, text);
    y += line;
    // the game's own totals since the file began, and this session's part of them
    p = put(text, "Since the file began: ");
    if (totals.state == 1) {
        static const char *const label[TOTALS] = { " jumps", " rolls", " sword swings", " m run", " m walked" };
        for (int k = 0; k < TOTALS; k++) {
            p = put_int(p, totals.now[k], 0);
            p = put(p, label[k]);
            p = put(p, " (+");
            p = put_int(p, totals.now[k] - totals.start[k], 0);
            p = put(p, k + 1 < TOTALS ? ")  " : ")");
        }
    } else {
        put(p, totals.state == 2 ? "can't read them (see the log)" : "-");
    }
    kae_draw_text(x, y, s, totals.state == 1 ? LIT : LABEL, text);
    y += line;
    kae_draw_text(x, y, s, DIM, "                          session    log");
    y += line;
    for (int row = 0; row < ROWS; row++) {
        p = put(text, row_label[row]);
        while (p < text + 26)
            *p++ = ' ';
        *p = 0;
        uint32_t now = row_value(&shown.in_session, row);
        char num[16];
        char *end = put_row_value(num, row, now);
        for (int pad_n = 7 - (int)(end - num); pad_n > 0; pad_n--)
            *p++ = ' ';
        p = put(p, num);
        p = put(p, "   ");
        put_row_value(p, row, row_value(&shown.in_log, row));
        kae_draw_text(x, y, s, now ? LIT : LABEL, text);
        y += line;
    }
    // every kind seen this session, as "kind:count"
    p = put(text, "All kinds this session: ");
    int any = 0;
    for (int k = 0; k < KINDS && p < text + 140; k++) {
        if (!shown.in_session.kinds[k])
            continue;
        p = put_int(p, k, 0);
        *p++ = ':';
        p = put_int(p, shown.in_session.kinds[k], 0);
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

// ---- the simple panel ----
static int same(const char *a, const char *b) {
    while (*a && *a == *b)
        a++, b++;
    return *a == *b;
}

// A friendlier name: "Enemy_Keese_Fire" -> "Keese Fire", "HyruleField_Child" -> "Hyrule Field",
// "Item_Melody_ZeldaLullaby" -> "Zelda Lullaby". Unknown names -> `unknown`.
static char *put_nice(char *out, uint32_t hash, const char *unknown, int max) {
    const char *n = name_of(hash);
    if (!n || !hash)
        return put(out, unknown);
    static const char *const prefixes[] = { "Item_Melody_", "Enemy_", "Obj_", "Item_", "Npc_", "Weapon_", "Armor_",
                                            "Animal_", "Player_" };
    for (unsigned k = 0; k < sizeof prefixes / sizeof *prefixes; k++) {
        const char *a = prefixes[k], *b = n;
        while (*a && *a == *b)
            a++, b++;
        if (!*a) {
            n = b;
            break;
        }
    }
    char *start = out;
    if (n[0] == 'R' && n[1] == 'u' && n[2] == 'p' && n[3] == 'e' && n[4] == 'e' && n[5] == '_' && n[6]) {
        out = put(out, n + 6);                  // "Rupee_Green" -> "Green Rupee"
        return put(out, " Rupee");
    }
    for (const char *c = n; *c && out - start < max; c++) {
        if (*c == '_') {
            // drop the age / scene variant at the end ("_Child", "_Adult", "_FireTemple", "_001")
            const char *rest = c + 1;
            int tail = 1;
            for (const char *r = rest; *r; r++)
                if (*r == '_')
                    tail = 0;
            if (tail && (rest[0] == 'C' || rest[0] == 'A' || (rest[0] >= '0' && rest[0] <= '9')) && out > start &&
                (same(rest, "Child") || same(rest, "Adult") || (rest[0] >= '0' && rest[0] <= '9')))
                break;
            if (out > start && out[-1] != ' ')
                *out++ = ' ';
            continue;
        }
        if (c > n && *c >= 'A' && *c <= 'Z' && c[-1] >= 'a' && c[-1] <= 'z' && out > start && out[-1] != ' ')
            *out++ = ' ';
        *out++ = *c;
    }
    *out = 0;
    return out;
}

// What a highlight entry says.
static char *put_event(char *out, const Entry *e) {
    switch (e->kind) {
    case 2:  out = put(out, "Game Over");
             if (e->name1 && name_of(e->name1) && !same(name_of(e->name1), "internal")) {
                 out = put(out, " (");
                 out = put_nice(out, e->name1, "?", 24);
                 out = put(out, ")");
             }
             return out;
    case 3:  out = put(out, "Defeated ");   return put_nice(out, e->name2, "an enemy", 28);
    case 11: out = put(out, "Picked up ");  return put_nice(out, e->name1, "something", 28);
    case 25: out = put(out, "Entered ");    return put_nice(out, e->name2, "a new area", 28);
    case 26: return put(out, "Saved the game");
    case 30: out = put(out, "Played ");     return put_nice(out, e->name1, "a song", 28);
    case 16: return put(out, "Opened a chest");
    }
    return put(out, kind_name(e->kind));
}

// Little pictures, drawn with kae_draw_image. '#' = the colour, '.' = left out.
static const char heart_rows[6][8] = { ".##.##.", "#######", "#######", ".#####.", "..###..", "...#..." };
static const char rupee_rows[7][6] = { "..#..", ".###.", "#####", "#####", "#####", ".###.", "..#.." };
static const char token_rows[7][8] = { "...#...", "..###..", "#######", ".#####.", "..###..", ".##.##.", "##...##" };

static void draw_picture(int x, int y, int w, int h, const char *rows, int stride, uint32_t argb, uint32_t argb2,
                         int split, int scale) {
    uint32_t px[64];
    for (int r = 0; r < h; r++)
        for (int c = 0; c < w; c++)
            px[r * w + c] = rows[r * stride + c] == '#' ? (c < split ? argb : argb2) : 0;
    kae_draw_image(x, y, w, h, px, scale);
}

enum { CARD = 0x0E1418, CARD_TOP = 0x1A2630, HEART = 0xFFE8384A, HEART_OFF = 0xFF3A2A30, RUPEE = 0xFF40D070,
       TOKEN = 0xFFF0C040 };

// "1 song", "2 songs"
static char *put_count(char *out, long long n, const char *one, const char *many) {
    out = put_int(out, n, 0);
    *out++ = ' ';
    return put(out, n == 1 ? one : many);
}

// "1.23 km", or "456 m" under one kilometre
static char *put_km(char *out, long long metres) {
    if (metres < 1000) {
        out = put_int(out, metres, 0);
        return put(out, " m");
    }
    out = put_int(out, metres / 1000, 0);
    *out++ = '.';
    out = put_int(out, (metres % 1000) / 10, 2);
    return put(out, " km");
}

static void draw_simple(const KaeFrame *f) {
    int s = settings[SIZE].value + 1;
    int line = 18 * s, pad = 8 * s, icon = 2 * s;
    int width = 64 * 8 * s + 2 * pad;
    if (width > f->width - 20)
        width = f->width - 20;
    int rows = 1 + 1 + 3 + (shown.state == 1 ? shown.highlight_n : 0);
    int height = rows * line + 2 * pad + 6 * s;
    int x0 = f->width / 60, y0 = f->height / 30, x = x0 + pad, y = y0 + pad;
    kae_draw_rect(x0, y0, width, height, CARD);
    kae_draw_rect(x0, y0, width, pad + line + 2 * s, CARD_TOP);
    char text[160], *p;

    // the title, and where Link is
    kae_draw_text(x, y, s, GOLD, "ADVENTURE LOG");
    if (shown.state == 1 && shown.area) {
        put_nice(text, shown.area, "", 30);
        kae_draw_text(x0 + width - pad - kae_text_width(s, text), y, s, LIT, text);
    }
    y += line + 6 * s;

    // hearts, rupees, Gold Skulltulas
    int life = -1, max = -1;
    if (totals.have_stats) {
        life = totals.stat[S_LIFE];
        max = totals.stat[S_MAX_LIFE];
    } else if (shown.life >= 0) {
        life = shown.life & 0xFFFF;
        max = (int)((uint32_t)shown.life >> 16);
    }
    int px = x;
    if (max > 0) {
        int hearts = (max + 3) / 4;
        if (hearts > 20)
            hearts = 20;
        for (int h = 0; h < hearts; h++) {
            int q = life - h * 4;              // quarters of this heart
            int split = q >= 4 ? 7 : q <= 0 ? 0 : (q * 7 + 2) / 4;
            draw_picture(px, y + 2 * s, 7, 6, &heart_rows[0][0], 8, HEART, HEART_OFF, split, icon);
            px += 8 * icon;
        }
        px += 10 * s;
    }
    if (totals.have_stats) {
        draw_picture(px, y + s, 5, 7, &rupee_rows[0][0], 6, RUPEE, RUPEE, 5, icon);
        px += 6 * icon;
        put_int(text, totals.stat[S_RUPEES], 0);
        px = kae_draw_text(px, y, s, LIT, text) + 10 * s;
        draw_picture(px, y + s, 7, 7, &token_rows[0][0], 8, TOKEN, TOKEN, 7, icon);
        px += 8 * icon;
        put_int(text, totals.stat[S_TOKENS], 0);
        px = kae_draw_text(px, y, s, LIT, text) + 10 * s;
        if (totals.stat[S_PIECES] % 4) {
            p = put_int(text, totals.stat[S_PIECES] % 4, 0);
            put(p, "/4 heart piece");
            kae_draw_text(px, y, s, LABEL, text);
        }
    }
    y += line;

    // today, this session, the whole file
    const Tally *t = &shown.today;
    p = put_count(text, t->kinds[3], "enemy", "enemies");  p = put(p, "   ");
    p = put_count(p, t->chests, "chest", "chests");          p = put(p, "   ");
    p = put_count(p, t->kinds[25], "area", "areas");         p = put(p, "   ");
    p = put_count(p, t->kinds[30], "song", "songs");
    kae_draw_text(x, y, s, DIM, "TODAY");
    kae_draw_text(x + 10 * 8 * s, y, s, shown.state == 1 ? LIT : LABEL, shown.state == 1 ? text : "-");
    y += line;

    kae_draw_text(x, y, s, DIM, "SESSION");
    if (totals.state == 1) {
        p = put_count(text, totals.now[T_JUMPS] - totals.start[T_JUMPS], "jump", "jumps");  p = put(p, "   ");
        p = put_count(p, totals.now[T_ROLLS] - totals.start[T_ROLLS], "roll", "rolls");     p = put(p, "   ");
        p = put_count(p, totals.now[T_SWINGS] - totals.start[T_SWINGS], "swing", "swings"); p = put(p, "   ");
        p = put_km(p, totals.now[T_RUN] - totals.start[T_RUN] + totals.now[T_WALK] - totals.start[T_WALK]);
        p = put(p, "   ");
        uint64_t secs = frames_seen / 30;
        p = put_int(p, (long long)(secs / 3600), 0); p = put(p, "h ");
        p = put_int(p, (long long)(secs / 60 % 60), 2); put(p, "m");
    } else {
        put(text, "-");
    }
    kae_draw_text(x + 10 * 8 * s, y, s, totals.state == 1 ? LIT : LABEL, text);
    y += line;

    kae_draw_text(x, y, s, DIM, "ALL TIME");
    if (totals.state == 1) {
        p = put_int(text, totals.now[T_JUMPS], 0);  p = put(p, " jumps   ");
        p = put_int(p, totals.now[T_ROLLS], 0);     p = put(p, " rolls   ");
        p = put_int(p, totals.now[T_SWINGS], 0);    p = put(p, " swings   ");
        p = put_km(p, totals.now[T_RUN] + totals.now[T_WALK]);
        put(p, " on foot");
    } else {
        put(text, "-");
    }
    kae_draw_text(x + 10 * 8 * s, y, s, totals.state == 1 ? LIT : LABEL, text);
    y += line;

    // the newest highlights
    if (shown.state != 1)
        return;
    for (int k = 0; k < shown.highlight_n; k++) {
        const Entry *e = &shown.highlight[k];
        kae_draw_rect(x + 2 * s, y + 6 * s, 3 * s, 3 * s, k == 0 ? 0x80E090 : 0x56645C);
        put_event(text, e);
        kae_draw_text(x + 10 * s, y, s, k == 0 ? LIT : LABEL, text);
        put_clock(text, e->time);
        text[5] = 0;                           // hh:mm
        kae_draw_text(x0 + width - pad - kae_text_width(s, text), y, s, DIM, text);
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
    gdm_slot = (uintptr_t)kae_sym("GameDataMgrPtr");
    if (!gdm_slot)
        KAE_LOG("adventure log: no GameDataMgrPtr in Core's names: no totals");
    if (kae_on_frame(frame, 0, 0) != KAE_OK || kae_on_draw(draw, 0, 0) != KAE_OK)
        return 2;
    if (kae_on_player_move(player_move, 0, 0) != KAE_OK)
        KAE_LOG("adventure log: no player_move event in this game: no distance of its own");
    kae_settings("Adventure Log", settings, sizeof settings / sizeof *settings);
    KAE_LOG("adventure log 0.4.0 on game 1.1.1, %u names", notes_name_count);
    return 0;
}

KAE_MOD("kabosune.adventure-log", "0.4.0", start, 0);
