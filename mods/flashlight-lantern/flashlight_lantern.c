// Flashlight & Lantern: real dynamic lights that follow Link, on KaeGae Core.
//
// The game lights the world with its LocationalLight manager: point and spot lights placed in
// scenes, lights fixed to actors' bones ("rigs"), and its own pool for Navi's glow. An event action,
// OneshotCreateLocationalLight, makes a new one at run time; this mod does what that action's
// execute function does (1.1.1 0x295F8C0, 1.0.0 0x290D570) and then keeps the light next to Link:
//
//   holder = [[main + LIGHT_GLOBAL] + 0x1E8];  mgr = [holder + MGR_OFF]   (when holder byte + 0xE20 has bit 1)
//   pool   = [mgr + 0x58 + 8 * kind]        kinds: 0 point, 1 spot (the action writes spot fields
//                                            only for 1), 3 Navi's pool (Light_NaviNum), 2, 4 others
//   light  = pool->vtable[2](pool)           a free light from the pool (null if it's full)
//   light + 0xF8 = 0, + 0x108 = 7 (the tag the action's lights carry), byte + 0x132 |= 1
//   light->vtable[9](light, x, y, z)         its position
//   light + 0x18  f32 r, g, b, 1             colour, divided by its luminance (0.299, 0.587, 0.114)
//   light + 0x28  f32 intensity               the action makes 25; the game's files use ~1 to 500
//   light + 0x2C  f32 source radius (m)       0.1 by default
//   spot:  + 0x158 f32[3] direction (unit), + 0x164 inner angle, + 0x168 outer angle (radians), + 0x16C = 0
//   register(mgr, light, name hash)          the manager's map of named lights (mgr + 0xD0E0); 0 if
//                                            the name is taken. lookup(mgr, hash) finds one again.
//
// The manager frees every named light when it clears its lights (0xF09FA0 in 1.1.1), so each update
// the mod looks its light up by name: gone = make a new one. That keeps it safe across area loads.
// The game's map can't remove one name, so "off" sets the intensity to 0 (the light stays in its
// pool until the area changes).
//
// The addresses are each version's own (raw offsets; found 22 Nov 2026, see docs/lights.md): a test
// build. They go into Core's symbol packs at the next Core release.
#include <kaegae.h>

// ---- the game's light manager, per version ----

typedef struct {
    const char *version;
    uintptr_t global;      // main offset of the pointer the action reads first
    uint32_t  mgr_off;     // holder + this = the LocationalLight manager
    uintptr_t reg, lookup; // the named-light map's insert and find
} Addrs;

static const Addrs ADDRS[] = {
    { "1.1.1", 0x4E3E258, 0xBA0, 0x31C9A30, 0x31C9AA0 },
    { "1.0.0", 0x4DCE228, 0xBA8, 0x3173B20, 0x3173B90 },
};

#define HOLDER_OFF   0x1E8
#define READY_OFF    0xE20        // holder byte: bit 1 set once the lights are usable (the game's rig lights check it)
#define POOLS_OFF    0x58
#define MAP_OFF      0xD0E0       // u32 hash + pad + ptr, 16 bytes each; count +8, capacity +0xC
#define KINDS        5

typedef void *(*PoolAllocFn)(void *pool);
typedef void  (*PoolFreeFn)(void *pool, void *light);
typedef void  (*SetPosFn)(void *light, float x, float y, float z);
typedef int   (*RegisterFn)(void *mgr, void *light, uint32_t hash);
typedef void *(*LookupFn)(void *mgr, uint32_t hash);

static uintptr_t game;
static const Addrs *addrs;
static RegisterFn reg_light;
static LookupFn find_light;

// ---- settings ----

static const char *const lantern_colours[] = { "Warm", "White", "Navi blue", "Fairy green", "Fire red" };
static const float lantern_rgb[][3] = {
    { 1.00f, 0.78f, 0.52f }, { 1.0f, 1.0f, 1.0f }, { 0.62f, 0.80f, 1.00f }, { 0.70f, 1.00f, 0.62f }, { 1.00f, 0.45f, 0.25f },
};
static const char *const flash_colours[] = { "White", "Warm", "Cool" };
static const float flash_rgb[][3] = { { 1.0f, 1.0f, 1.0f }, { 1.00f, 0.86f, 0.68f }, { 0.82f, 0.90f, 1.00f } };
static const char *const kinds[] = { "Point light", "Navi's light (test)" };
static const char *const glows[] = { "Steady", "Candle flicker", "Navi pulse" };
static const char *const aims[] = { "Where Link faces", "Where the camera looks" };

enum {
    LANTERN, L_TOGGLE, L_BRIGHT, L_COLOUR, L_GLOW, L_HEIGHT, L_SIZE, L_KIND,
    FLASH, F_TOGGLE, F_BRIGHT, F_COLOUR, F_WIDTH, F_AIM, F_TILT, F_HEIGHT, F_FORWARD,
    STATUS,
    ITEMS
};
#define TOG(label_, help_, def_)                 { KAE_TOGGLE, label_, help_, def_, def_, 0, 1, 1, 0, 0, 0, 0, 0 }
#define NUM(label_, help_, def_, lo_, hi_, st_)  { KAE_NUMBER, label_, help_, def_, def_, lo_, hi_, st_, 0, 0, 0, 0, 0 }
#define CHO(label_, help_, def_, names_)         { KAE_CHOICE, label_, help_, def_, def_, 0, (int)(sizeof names_ / sizeof *names_) - 1, 0, names_, 0, 0, 0, 0 }
#define KEY(label_, help_)                       { KAE_BINDING, label_, help_, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
static KaeItem settings[ITEMS] = {
    [LANTERN]   = TOG("Lantern", "A light all around Link, like Navi's glow.", 1),
    [L_TOGGLE]  = KEY("Lantern on / off", "A button to switch the lantern while playing."),
    [L_BRIGHT]  = NUM("Lantern brightness", "The light's intensity (the game's torches use about 1 to 10).", 12, 1, 200, 1),
    [L_COLOUR]  = CHO("Lantern colour", 0, 0, lantern_colours),
    [L_GLOW]    = CHO("Lantern glow", "Steady, a candle's flicker, or a slow pulse like Navi.", 0, glows),
    [L_HEIGHT]  = NUM("Lantern height (cm)", "How far above Link's feet the light sits.", 110, 0, 300, 10),
    [L_SIZE]    = NUM("Lantern size (cm)", "The light's own radius: bigger is softer.", 30, 1, 200, 1),
    [L_KIND]    = CHO("Lantern light kind", "Point light, or a light from the pool the game keeps for Navi (a test).", 0, kinds),
    [FLASH]     = TOG("Flashlight", "A beam out of Link's chest.", 0),
    [F_TOGGLE]  = KEY("Flashlight on / off", "A button to switch the flashlight while playing."),
    [F_BRIGHT]  = NUM("Flashlight brightness", "The beam's intensity (the game's spot lights use about 10 to 200).", 80, 1, 1000, 5),
    [F_COLOUR]  = CHO("Flashlight colour", 0, 0, flash_colours),
    [F_WIDTH]   = NUM("Beam width (degrees)", "The beam's outer angle; its bright middle is 60 % of it.", 25, 5, 80, 1),
    [F_AIM]     = CHO("Flashlight aim", 0, 0, aims),
    [F_TILT]    = NUM("Beam tilt down (degrees)", "For \"Where Link faces\": how far the beam points down.", 10, -45, 60, 1),
    [F_HEIGHT]  = NUM("Flashlight height (cm)", "How far above Link's feet the beam starts.", 90, 0, 300, 10),
    [F_FORWARD] = NUM("Flashlight forward (cm)", "How far in front of Link the beam starts.", 30, 0, 200, 5),
    [STATUS]    = TOG("Show status", "A few lines on screen: whether each light exists, and its kind (for testing).", 0),
};

// ---- small maths ----

static float root(float x) {
    float r = 0.0f;
    if (x > 0.0f)
        __asm__("fsqrt %s0, %s1" : "=w"(r) : "w"(x));
    return r;
}
#define PI 3.14159265f
// sin for any x, good to ~0.001 (folds to [-pi, pi], then a parabola with a correction)
static float sine(float x) {
    float t = x * (1.0f / (2.0f * PI));
    t -= (float)(int)t;
    if (t < 0.0f) t += 1.0f;
    x = t * 2.0f * PI;
    if (x > PI) x -= 2.0f * PI;
    float y = 1.2732395f * x - 0.4052847f * x * (x < 0 ? -x : x);
    return 0.225f * (y * (y < 0 ? -y : y) - y) + y;
}

// MurmurHash3 x86_32, seed 0: the game hashes light names with it.
static uint32_t murmur3(const char *s) {
    uint32_t h = 0, len = 0, k;
    const uint8_t *p = (const uint8_t *)s;
    while (p[len]) len++;
    uint32_t i = 0;
    for (; i + 4 <= len; i += 4) {
        k = p[i] | p[i + 1] << 8 | p[i + 2] << 16 | (uint32_t)p[i + 3] << 24;
        k *= 0xCC9E2D51u; k = k << 15 | k >> 17; k *= 0x1B873593u;
        h ^= k; h = h << 13 | h >> 19; h = h * 5 + 0xE6546B64u;
    }
    k = 0;
    switch (len & 3) {
    case 3: k ^= (uint32_t)p[i + 2] << 16; // fall through
    case 2: k ^= (uint32_t)p[i + 1] << 8;  // fall through
    case 1: k ^= p[i]; k *= 0xCC9E2D51u; k = k << 15 | k >> 17; k *= 0x1B873593u; h ^= k;
    }
    h ^= len; h ^= h >> 16; h *= 0x85EBCA6Bu; h ^= h >> 13; h *= 0xC2B2AE35u; h ^= h >> 16;
    return h;
}

// ---- the lights ----

typedef struct {
    const char *name;   // for the log and the status lines
    int kind;           // pool: 0 point, 1 spot, 3 Navi's
    uint32_t hash;      // of the name we register it under (per kind)
    void *light, *mgr;  // as found on the last update
    int made, lost;     // counts, for the status lines
    const char *why;    // last reason it couldn't be made
} Lamp;

static Lamp lantern = { "lantern", 0, 0, 0, 0, 0, 0, 0 };
static Lamp flash = { "flashlight", 1, 0, 0, 0, 0, 0, 0 };

static void *read_ptr(uintptr_t at) {
    return kae_readable((const void *)at, sizeof(void *)) ? *(void **)at : 0;
}

static void *manager(void) {
    uintptr_t a = (uintptr_t)read_ptr(game + addrs->global);
    uintptr_t holder = a ? (uintptr_t)read_ptr(a + HOLDER_OFF) : 0;
    if (!holder || !kae_readable((const void *)(holder + READY_OFF), 1) || !(*(uint8_t *)(holder + READY_OFF) & 2))
        return 0;
    uintptr_t mgr = (uintptr_t)read_ptr(holder + addrs->mgr_off);
    if (!mgr || !kae_readable((const void *)(mgr + POOLS_OFF), 8 * KINDS) ||
        !kae_readable((const void *)(mgr + MAP_OFF), 16))
        return 0;
    // the named-light map must exist (the game's insert divides by its capacity)
    if (!*(uint32_t *)(mgr + MAP_OFF + 0xC) || !read_ptr(mgr + MAP_OFF))
        return 0;
    return (void *)mgr;
}

static void **vtable_of(void *obj, int slots) {
    void **vt = obj ? (void **)read_ptr((uintptr_t)obj) : 0;
    return vt && kae_readable(vt, sizeof(void *) * (size_t)slots) ? vt : 0;
}

static void set_colour(uint8_t *l, const float rgb[3]) {
    float lum = 0.299f * rgb[0] + 0.587f * rgb[1] + 0.114f * rgb[2];
    float k = lum > 0.0f ? 1.0f / lum : 0.0f;
    float *c = (float *)(l + 0x18);
    c[0] = rgb[0] * k; c[1] = rgb[1] * k; c[2] = rgb[2] * k; c[3] = 1.0f;
}

static uint32_t hash_for(const Lamp *lamp, int kind) {
    static const char *const names[2][KINDS] = {
        { "KaeGae_Lantern_Point", "KaeGae_Lantern_Spot", "KaeGae_Lantern_2", "KaeGae_Lantern_Navi", "KaeGae_Lantern_4" },
        { "KaeGae_Flashlight_Point", "KaeGae_Flashlight_Spot", "KaeGae_Flashlight_2", "KaeGae_Flashlight_Navi", "KaeGae_Flashlight_4" },
    };
    return murmur3(names[lamp == &flash][kind]);
}

// A new light from the pool, set up the way OneshotCreateLocationalLight does, and named.
static void *make(Lamp *lamp, void *mgr, const float pos[3]) {
    void *pool = read_ptr((uintptr_t)mgr + POOLS_OFF + 8 * (uintptr_t)lamp->kind);
    void **pvt = vtable_of(pool, 4);
    if (!pvt) { lamp->why = "no pool"; return 0; }
    uint8_t *l = ((PoolAllocFn)pvt[2])(pool);
    if (!l) { lamp->why = "pool full"; return 0; }
    void **lvt = vtable_of(l, 10);
    if (!lvt) { lamp->why = "odd light"; return 0; }
    *(uint64_t *)(l + 0xF8) = 0;
    *(uint32_t *)(l + 0x108) = 7;
    l[0x132] |= 1;
    ((SetPosFn)lvt[9])(l, pos[0], pos[1], pos[2]);
    static const float white[3] = { 1, 1, 1 };
    set_colour(l, white);
    *(float *)(l + 0x28) = 0.0f;      // dark until the first update sets it
    *(float *)(l + 0x2C) = 0.1f;
    if (lamp->kind == 1) {
        float *d = (float *)(l + 0x158);
        d[0] = 0; d[1] = -1; d[2] = 0;
        *(float *)(l + 0x164) = 0.2f;
        *(float *)(l + 0x168) = 0.4f;
        *(float *)(l + 0x16C) = 0.0f;
    }
    if (!reg_light(mgr, l, lamp->hash)) {
        // the name is taken (it shouldn't be: lookup came first): give it back like the action does
        l[0x132] &= 0xFE;
        ((PoolFreeFn)pvt[3])(pool, l);
        lamp->why = "name taken";
        return 0;
    }
    lamp->made++;
    lamp->why = 0;
    KAE_LOG("flashlight & lantern: made the %s: light %p (vtable +0x%lx) from pool %d at %p", lamp->name, (void *)l,
            (unsigned long)((uintptr_t)lvt - game), lamp->kind, pool);
    return l;
}

// Keeps one lamp in step: finds (or makes) its light, then places and lights it.
static void update(Lamp *lamp, int want, int kind, const float pos[3], const float dir[3], float intensity,
                   const float rgb[3], float radius, float outer) {
    void *mgr = manager();
    if (!mgr) {
        if (lamp->light) lamp->lost++;
        lamp->light = lamp->mgr = 0;
        lamp->why = "no light manager";
        return;
    }
    if (kind != lamp->kind) {
        // the old one can't be taken out of the map: darken it and start one of the new kind
        if (lamp->light && find_light(mgr, lamp->hash) == lamp->light)
            *(float *)((uint8_t *)lamp->light + 0x28) = 0.0f;
        lamp->kind = kind;
        lamp->hash = hash_for(lamp, kind);
        lamp->light = 0;
    }
    void *l = find_light(mgr, lamp->hash);
    if (!l && lamp->light) {
        lamp->lost++;
        KAE_LOG("flashlight & lantern: the %s's light is gone (the area changed?)", lamp->name);
    }
    lamp->light = l;
    lamp->mgr = mgr;
    if (!l) {
        if (!want)
            return;
        l = lamp->light = make(lamp, mgr, pos);
        if (!l)
            return;
    }
    uint8_t *b = l;
    void **lvt = vtable_of(l, 10);
    if (!lvt)
        return;
    if (!want) {
        *(float *)(b + 0x28) = 0.0f;
        return;
    }
    ((SetPosFn)lvt[9])(l, pos[0], pos[1], pos[2]);
    set_colour(b, rgb);
    *(float *)(b + 0x28) = intensity;
    *(float *)(b + 0x2C) = radius;
    if (kind == 1) {
        float *d = (float *)(b + 0x158);
        d[0] = dir[0]; d[1] = dir[1]; d[2] = dir[2];
        *(float *)(b + 0x168) = outer;
        *(float *)(b + 0x164) = outer * 0.6f;
        *(float *)(b + 0x16C) = 0.0f;
    }
}

// ---- events ----

static volatile float cam_look[3];
static volatile int cam_have;
static uint32_t ticks;
static uint32_t rng = 0x2545F491u;

static void on_view(KaeView *view, void *user) {
    (void)user;
    // rows: right, up, back; the camera looks along -back
    cam_look[0] = -view->matrix[8];
    cam_look[1] = -view->matrix[9];
    cam_look[2] = -view->matrix[10];
    cam_have = 1;
}

static float glow(void) {
    switch (settings[L_GLOW].value) {
    case 1: {                       // candle: a random walk around 85 %
        static float f = 1.0f;
        rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
        float target = 0.70f + 0.30f * (float)(rng & 0xFFFF) / 65535.0f;
        f += (target - f) * 0.25f;
        return f;
    }
    case 2:                         // Navi: a slow breath, ~2 s
        return 0.80f + 0.20f * sine((float)ticks * (2.0f * PI / 120.0f));
    default:
        return 1.0f;
    }
}

static void player_move(const KaePlayer *link, void *user) {
    (void)user;
    ticks++;
    if (kae_binding_pressed(&settings[L_TOGGLE]))
        settings[LANTERN].value = !settings[LANTERN].value;
    if (kae_binding_pressed(&settings[F_TOGGLE]))
        settings[FLASH].value = !settings[FLASH].value;

    const float *p = link->position;
    const uint8_t *a = link->actor;
    // Link's facing: his rotation's third column (+0x330, +0x33C, +0x348; yaw = atan2(+0x330, +0x348))
    float fx = 0, fz = 1;
    if (a && kae_readable(a + 0x328, 0x24)) {
        fx = *(const float *)(a + 0x330);
        fz = *(const float *)(a + 0x348);
        float n = root(fx * fx + fz * fz);
        if (n > 1e-4f) { fx /= n; fz /= n; } else { fx = 0; fz = 1; }
    }

    float lpos[3] = { p[0], p[1] + (float)settings[L_HEIGHT].value * 0.01f, p[2] };
    int lkind = settings[L_KIND].value ? 3 : 0;
    update(&lantern, settings[LANTERN].value, lkind, lpos, 0, (float)settings[L_BRIGHT].value * glow(),
           lantern_rgb[settings[L_COLOUR].value], (float)settings[L_SIZE].value * 0.01f, 0);

    float fwd = (float)settings[F_FORWARD].value * 0.01f;
    float fpos[3] = { p[0] + fx * fwd, p[1] + (float)settings[F_HEIGHT].value * 0.01f, p[2] + fz * fwd };
    float dir[3];
    if (settings[F_AIM].value == 1 && cam_have) {
        dir[0] = cam_look[0]; dir[1] = cam_look[1]; dir[2] = cam_look[2];
    } else {
        float t = (float)settings[F_TILT].value * (PI / 180.0f);
        float c = sine(t + PI / 2), s = sine(t);
        dir[0] = fx * c; dir[1] = -s; dir[2] = fz * c;
    }
    float n = root(dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]);
    if (n < 1e-4f) { dir[0] = fx; dir[1] = 0; dir[2] = fz; n = 1; }
    dir[0] /= n; dir[1] /= n; dir[2] /= n;
    update(&flash, settings[FLASH].value, 1, fpos, dir, (float)settings[F_BRIGHT].value,
           flash_rgb[settings[F_COLOUR].value], 0.05f, (float)settings[F_WIDTH].value * (PI / 180.0f));
}

// ---- the status lines ----

static char *put(char *o, const char *s) { while (*s) *o++ = *s++; return o; }
static char *put_int(char *o, int v) {
    char t[12]; int n = 0;
    if (v < 0) { *o++ = '-'; v = -v; }
    do t[n++] = (char)('0' + v % 10); while (v /= 10);
    while (n) *o++ = t[--n];
    return o;
}

static void status_line(char *o, const Lamp *lamp, int on) {
    o = put(o, lamp == &flash ? "Flashlight: " : "Lantern: ");
    o = put(o, on ? "on" : "off");
    o = put(o, lamp->light ? ", light made" : ", no light");
    if (lamp->why) { o = put(o, " ("); o = put(o, lamp->why); o = put(o, ")"); }
    o = put(o, ", kind ");
    o = put_int(o, lamp->kind);
    o = put(o, ", made ");
    o = put_int(o, lamp->made);
    o = put(o, ", lost ");
    o = put_int(o, lamp->lost);
    *o = 0;
}

static void draw(const KaeFrame *frame, void *user) {
    (void)user;
    if (!settings[STATUS].value || kae_menu_open())
        return;
    char line[128];
    int s = frame->height >= 1000 ? 2 : 1, y = frame->height - 3 * 18 * s;
    status_line(line, &lantern, settings[LANTERN].value);
    kae_draw_text(16 * s, y, s, 0xFFE0A0, line);
    status_line(line, &flash, settings[FLASH].value);
    kae_draw_text(16 * s, y + 18 * s, s, 0xC0E0FF, line);
}

static int start(void) {
    const char *v = kae_game_version();
    for (unsigned i = 0; i < sizeof ADDRS / sizeof *ADDRS; i++) {
        const char *a = ADDRS[i].version;
        int same = 1;
        for (int k = 0; same && (a[k] || v[k]); k++)
            same = a[k] == v[k];
        if (same)
            addrs = &ADDRS[i];
    }
    game = kae_game_base();
    if (!addrs || !game) {
        KAE_LOG("flashlight & lantern: game %s isn't one this build knows (1.0.0, 1.1.1): doing nothing", v[0] ? v : "unknown");
        return 2;
    }
    reg_light = (RegisterFn)(game + addrs->reg);
    find_light = (LookupFn)(game + addrs->lookup);
    lantern.hash = hash_for(&lantern, lantern.kind);
    flash.hash = hash_for(&flash, flash.kind);
    if (kae_on_player_move(player_move, 0, 0) != KAE_OK) {
        KAE_LOG("flashlight & lantern: no player_move event in this game: doing nothing");
        return 2;
    }
    if (kae_on_view(on_view, 0, 0) != KAE_OK)
        KAE_LOG("flashlight & lantern: no view event: the flashlight can only aim where Link faces");
    kae_on_draw(draw, 0, 0);
    kae_settings("Flashlight & Lantern", settings, ITEMS);
    KAE_LOG("flashlight & lantern 0.1.0 on game %s (light manager pointer at main+0x%lx)", v, (unsigned long)addrs->global);
    return 0;
}

KAE_MOD("kabosune.flashlight-lantern", "0.1.0", start, 0);
