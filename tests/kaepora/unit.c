// Host tests of Core's portable parts (mod list, events, symbols, format, pool), built for the PC
// and run by tests/test_kaepora_unit.py. Each scenario runs in its own process: Core keeps its
// state in statics, as it does in the game.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "core.h"

#define CHECK(x) do { if (!(x)) { printf("FAILED %s:%d: %s\n", __FILE__, __LINE__, #x); exit(1); } } while (0)

// ---- what the system layer and the other services provide in the game ----
static char logged[64][256];
static int log_count;
void kp_debug_out(const char *text, size_t n) {
    CHECK(log_count < 64 && n < 256);
    memcpy(logged[log_count], text, n);
    logged[log_count++][n] = 0;
}
bool kp_readable(uintptr_t address, size_t size) { (void)size; return address != 0; }
uintptr_t kp_main;
const kp_build_t *kp_build;
bool kp_motion_on;
KaeMod *__kae_mods_start[1], *__kae_mods_end[1];

static bool logged_line(const char *part) {
    for (int i = 0; i < log_count; i++)
        if (strstr(logged[i], part))
            return true;
    return false;
}

static void known_game(void) {
    kp_main = 0x80000000;
    kp_build = &kp_builds[0];
    for (int e = 0; e < KP_EV_COUNT; e++)
        kp_event_on[e] = true;
}

static char *fmt(const char *format, ...) {
    static char out[128];
    va_list a;
    va_start(a, format);
    kp_vformat(out, sizeof out, format, a);
    va_end(a);
    return out;
}

// ---- format ----
static void test_format(void) {
    CHECK(!strcmp(fmt("plain"), "plain"));
    CHECK(!strcmp(fmt("%d %i %u", -12, 34, 56u), "-12 34 56"));
    CHECK(!strcmp(fmt("%lld %llu %zu", -5000000000LL, 18446744073709551615ULL, (size_t)7), "-5000000000 18446744073709551615 7"));
    CHECK(!strcmp(fmt("%x %X %08x %4d|%-d", 0xbeef, 0xBEEF, 0x1234, 7, 3), "beef BEEF 00001234    7|%-d"));
    CHECK(!strcmp(fmt("%05d", -42), "-0042"));
    CHECK(!strcmp(fmt("%s %c %%", "text", 'z'), "text z %"));
    CHECK(!strcmp(fmt("%s", (char *)0), "(null)"));
    CHECK(!strcmp(fmt("%p", (void *)0x1234), "0x1234"));
    CHECK(!strcmp(fmt("%f %.2f %.0f %f", 1.5, -2.345, 2.5, 0.0005), "1.500 -2.35 3 0.001"));
    CHECK(!strcmp(fmt("%f %f", 0.0 / 0.0 * 0 + (0.0 / 0.0), 1e30), "nan inf") || !strcmp(fmt("%f", 1e30), "inf"));
    CHECK(!strcmp(fmt("%.3f", 0.9996), "1.000"));
    CHECK(!strcmp(fmt("100%"), "100"));
    char small[8];
    va_list none;
    memset(&none, 0, sizeof none);
    CHECK(kp_vformat(small, sizeof small, "0123456789", none) == 7 && !strcmp(small, "0123456"));
    kae_logf(0, "x %d", 1);
    CHECK(!strcmp(logged[0], "kaepora [?]: x 1"));
    kp_logf("core %s", "line");
    CHECK(!strcmp(logged[1], "kaepora: core line"));
}

// ---- mods ----
static char order[64];
static int frames_a, frames_b;
static void frame_a(void *user) { (void)user; frames_a++; }
static void frame_b(void *user) { (void)user; frames_b++; }
static int start_a(void) { strcat(order, "a"); CHECK(kp_mod_starting()); return kae_on_frame(frame_a, 0, 0); }
static int start_b(void) { strcat(order, "b"); return 0; }
static int start_c(void) { strcat(order, "c"); return 0; }
static int start_fails(void) { strcat(order, "f"); kae_on_frame(frame_b, 0, 0); return 7; }
#define MOD(id, start) { sizeof(KaeMod), KAE_API_MAJOR, KAE_API_MINOR, id, "1.0.0", start, 0, 0 }

static void test_mods(void) {
    known_game();
    static KaeMod a = MOD("t.a", start_a), b = MOD("t.b", start_b), c = MOD("t.c", start_c);
    static KaeMod fails = MOD("t.fails", start_fails), twin = MOD("t.a", start_c), no_id = MOD("", start_c);
    static KaeMod old = { sizeof(KaeMod), KAE_API_MAJOR, KAE_API_MINOR - 1, "t.old", "1", start_c, 0, 0 };
    static KaeMod newer = { sizeof(KaeMod), KAE_API_MAJOR, KAE_API_MINOR + 1, "t.newer", "1", start_c, 0, 0 };
    static KaeMod major = { sizeof(KaeMod), KAE_API_MAJOR + 1, 0, "t.major", "1", start_c, 0, 0 };
    static KaeMod tiny = { 8, KAE_API_MAJOR, KAE_API_MINOR, "t.tiny", "1", start_c, 0, 0 };
    kae_register(&a);
    kae_register(&fails);
    kae_register(&b);
    kae_register(&twin);
    kae_register(&no_id);
    kae_register(&old);
    kae_register(&newer);
    kae_register(&major);
    kae_register(&tiny);
    kae_register(0);
    CHECK(!order[0]);                      // registering starts nothing
    kp_fire_frame();                       // the first entry from the game starts the mods, in order
    CHECK(!strcmp(order, "afb"));
    CHECK(frames_a == 1 && frames_b == 0); // the failed mod's subscription was taken back
    CHECK(logged_line("mod t.a 1.0.0 started") && logged_line("mod t.b 1.0.0 started"));
    CHECK(logged_line("mod t.fails 1.0.0 is off: its start returned 7"));
    CHECK(logged_line("mod t.a 1.0.0 is off: a mod with the same id is already loaded"));
    CHECK(logged_line("mod (no id) 1.0.0 is off: it has no id"));
    CHECK(logged_line("mod t.old 1 is off: it was built for an older 0.x API"));
    CHECK(logged_line("mod t.newer 1 is off: it was built for a newer Core"));
    CHECK(logged_line("mod t.major 1 is off: it was built for a different major version"));
    CHECK(logged_line("mod t.tiny 1 is off: its descriptor is smaller"));
    kp_mods_ready();
    CHECK(!strcmp(order, "afb"));          // only once
    kae_register(&c);                      // late: started straight away
    CHECK(!strcmp(order, "afbc"));
    kp_fire_frame();
    CHECK(frames_a == 2);
}

static void test_unknown_game(void) {
    static KaeMod a = MOD("t.a", start_a), b = MOD("t.b", start_b);
    kae_register(&a);
    kp_mods_ready();                       // what Core's start does when it doesn't know the build
    kae_register(&b);
    CHECK(!order[0]);
    CHECK(logged_line("mod t.a 1.0.0 is off: this build of the game isn't known to Core"));
    CHECK(logged_line("mod t.b 1.0.0 is off: this build of the game isn't known to Core"));
    CHECK(kae_sym("CctChangePosition") == 0 && kae_field("Actor.position") == -1 && kae_game_base() == 0);
    CHECK(!strcmp(kae_game_version(), "") && !strcmp(kae_game_build(), ""));
    CHECK(!kae_has("symbols") && !kae_has("event.frame"));
}

// ---- events ----
static void note(void *user) { strcat(order, (const char *)user); }
static void press_a(KaeInput *seen, const KaeInput *real, void *user) { (void)user; CHECK(real->buttons == 2); seen->buttons |= 1; }
static void hide_b(KaeInput *seen, const KaeInput *real, void *user) { (void)real; (void)user; CHECK(seen->buttons == 3); seen->buttons &= ~2ull; }
static void draw_note(const KaeFrame *f, void *user) { CHECK(f->width == 1280 && f->size == sizeof *f); note(user); }
static void actor_note(void *actor, void *user) { CHECK(actor == (void *)0x1234); note(user); }
static void subscribes(void *user) { (void)user; CHECK(kae_on_frame(note, "+", 99) == KAE_OK); }

static void test_events(void) {
    known_game();
    CHECK(kae_on_frame(0, 0, 0) == KAE_ERR_ARGUMENT);
    CHECK(kae_on_frame(note, "2", 0) == KAE_OK);
    CHECK(kae_on_frame(note, "4", 10) == KAE_OK);
    CHECK(kae_on_frame(note, "1", -10) == KAE_OK);
    CHECK(kae_on_frame(note, "3", 0) == KAE_OK);    // same priority: after the earlier one
    kp_fire_frame();
    CHECK(!strcmp(order, "1234"));
    CHECK(kae_on_input(hide_b, 0, 5) == KAE_OK && kae_on_input(press_a, 0, 0) == KAE_OK);
    KaeInput real = { sizeof real, 0, 2, 0, 0, 0, 0, 0, 1 }, seen = real;
    kp_fire_input(&seen, &real);
    CHECK(seen.buttons == 1 && real.buttons == 2);
    order[0] = 0;
    KaeFrame f = { sizeof f, 1280, 720, 0 };
    CHECK(kae_on_draw(draw_note, "d", 0) == KAE_OK && kae_on_actor_move(actor_note, "m", 0) == KAE_OK);
    kp_fire_draw(&f);
    kp_fire_actor_move((void *)0x1234);
    CHECK(!strcmp(order, "dm"));
    order[0] = 0;
    CHECK(kae_on_frame(subscribes, 0, -100) == KAE_OK);   // subscribing from inside an event is fine
    kp_fire_frame();
    CHECK(!strcmp(order, "1234"));
    order[0] = 0;
    kp_fire_frame();
    CHECK(!strcmp(order, "1234+"));
    int result = KAE_OK;
    for (int i = 0; i < 40 && result == KAE_OK; i++)
        result = kae_on_draw(draw_note, "", 0);
    CHECK(result == KAE_ERR_FULL);
    kp_event_on[KP_EV_ACTOR_MOVE] = false;                // Core's patch missing
    CHECK(kae_on_actor_move(actor_note, "m", 0) == KAE_ERR_UNAVAILABLE);
    CHECK(kae_has("event.frame") && kae_has("draw.rect") && kae_has("draw.text") && kae_has("draw.image") && !kae_has("event.actor_move") && !kae_has("motion"));
    CHECK(!kae_has("no.such.thing") && !kae_has(0) && kae_has("alloc") && kae_has("symbols"));
}

// ---- symbols ----
static void test_symbols(void) {
    known_game();
    CHECK(kp_build_count >= 1);
    for (unsigned b = 0; b < kp_build_count; b++) {
        kp_build = &kp_builds[b];
        CHECK(strlen(kp_build->build_id) == 40);
        for (uint32_t i = 0; i < kp_build->sym_count; i++) {      // every entry is found by its name
            CHECK(kae_sym(kp_build->syms[i].name) == (void *)(kp_main + kp_build->syms[i].offset));
            CHECK(i == 0 || strcmp(kp_build->syms[i - 1].name, kp_build->syms[i].name) < 0);
        }
        for (uint32_t i = 0; i < kp_build->field_count; i++)
            CHECK(kae_field(kp_build->fields[i].name) == kp_build->fields[i].offset);
    }
    kp_build = &kp_builds[0];
    CHECK(kae_sym("CctChangePosition") == (void *)(0x80000000 + 0x6B2530));
    CHECK(kae_sym("f_806d2530") == kae_sym("CctChangePosition"));          // the Hookshot-style alias
    CHECK(kae_sym("vtable.Actor") == (void *)(0x80000000 + 0x4B25E18));
    CHECK(kae_field("Actor.position") == 0x31C);
    CHECK(!kae_sym("NoSuchThing") && !kae_sym("") && !kae_sym(0) && !kae_sym("CctChangePositio") && !kae_sym("CctChangePositionX"));
    CHECK(kae_field("Actor.nothing") == -1 && kae_field(0) == -1);
    CHECK(!strcmp(kae_game_version(), "1.1.1") && !strcmp(kae_game_build(), "E0F3CCFAF50065AE4EA01EB5AEB13B1A45DA3348"));
    CHECK(kae_api_version() == ((KAE_API_MAJOR << 16) | KAE_API_MINOR));
}

// ---- the pool (built with a small KP_POOL_BYTES) ----
static void test_alloc(void) {
    CHECK(!kae_alloc(0) && !kae_alloc(KP_POOL_BYTES + 1) && !kae_alloc(KP_POOL_BYTES));
    void *p[64];
    int n = 0;
    while (n < 64 && (p[n] = kae_alloc(100)))
        n++;
    CHECK(n == KP_POOL_BYTES / (112 + 16));             // 100 -> 112 bytes and a 16-byte header
    for (int i = 0; i < n; i++) {
        CHECK(((uintptr_t)p[i] & 15) == 0);
        memset(p[i], i, 100);
    }
    for (int i = 0; i < n; i++)
        for (int k = 0; k < 100; k++)
            CHECK(((unsigned char *)p[i])[k] == i);     // no two blocks overlap
    kae_free(p[1]);
    void *again = kae_alloc(50);
    CHECK(again == p[1]);                               // first fit: the hole is used again
    kae_free(again);
    kae_free(0);
    kae_free((void *)&n);                               // not from the pool: ignored
    for (int i = 0; i < n; i++)
        if (i != 1)
            kae_free(p[i]);
    void *all = kae_alloc(KP_POOL_BYTES - 16);          // everything joins back into one block
    CHECK(all == p[0]);
    CHECK(!kae_alloc(1));
    kae_free(all);
    CHECK(kae_alloc(1) == p[0]);
}

// ---- text and pictures: text.c turns them into rectangles; here the rectangles are painted ----
#include "font_gen.h"
#define CANVAS 96
static uint32_t canvas[CANVAS][CANVAS];   // 0 = untouched, else 0xFF000000 | rgb
static int rect_calls;
void kae_draw_rect(int x, int y, int w, int h, uint32_t rgb) {
    rect_calls++;
    CHECK(w > 0 && h > 0);
    for (int yy = y; yy < y + h; yy++)
        for (int xx = x; xx < x + w; xx++) {
            CHECK(xx >= 0 && yy >= 0 && xx < CANVAS && yy < CANVAS);
            CHECK(!canvas[yy][xx]);                       // nothing is painted twice
            canvas[yy][xx] = 0xFF000000 | rgb;
        }
}
static bool glyph_bit(uint32_t code, int col, int row) { return (kp_font_glyph(code)[row] >> (7 - col)) & 1; }
// The canvas from (x, y) shows `code` at `scale` in `rgb`, and nothing else in that cell.
static void check_glyph(int x, int y, int scale, uint32_t rgb, uint32_t code) {
    for (int row = 0; row < 16 * scale; row++)
        for (int col = 0; col < 8 * scale; col++)
            CHECK(canvas[y + row][x + col] == (glyph_bit(code, col / scale, row / scale) ? 0xFF000000 | rgb : 0));
}

static void test_text(void) {
    CHECK(kae_text_width(1, "abc") == 24 && kae_text_width(3, "ab\nabcd\na") == 96 && kae_text_width(1, "") == 0);
    CHECK(kae_text_height(1, "abc") == 16 && kae_text_height(2, "a\nb\n") == 96 && kae_text_width(0, "a") == 0);
    CHECK(kae_text_width(1, "\xC3\xA9t\xC3\xA9") == 24);          // "été": three characters, five bytes
    // one line, then a second one under it; the pen comes back
    CHECK(kae_draw_text(4, 2, 1, 0x112233, "Kp\n!") == 4 + 8);
    check_glyph(4, 2, 1, 0x112233, 'K');
    check_glyph(12, 2, 1, 0x112233, 'p');
    check_glyph(4, 18, 1, 0x112233, '!');
    CHECK(rect_calls < 40);                                         // runs, not single pixels
    // scaled, Latin-1, and what the font doesn't have
    memset(canvas, 0, sizeof canvas);
    CHECK(kae_draw_text(0, 0, 2, 0xABCDEF, "\xC3\xA9") == 16);       // U+00E9
    check_glyph(0, 0, 2, 0xABCDEF, 0xE9);
    memset(canvas, 0, sizeof canvas);
    CHECK(kae_draw_text(0, 0, 1, 1, "\xE2\x82\xAC\xFF\xC3") == 24);  // a euro sign, a stray byte, a cut-off sequence
    for (int i = 0; i < 3; i++)
        check_glyph(8 * i, 0, 1, 1, '?');
    CHECK(kae_draw_text(5, 5, 0, 1, "x") == 5 && kae_draw_text(5, 5, 1, 1, 0) == 5);
    // a space draws nothing
    memset(canvas, 0, sizeof canvas);
    rect_calls = 0;
    CHECK(kae_draw_text(0, 0, 1, 1, "   ") == 24 && rect_calls == 0);
}

static void test_image(void) {
    enum { R = 0xFFFF0000, G = 0x80008000, T = 0x7F123456, U = 0x00FFFFFF };   // T and U are see-through
    static const uint32_t picture[4 * 4] = {
        R, R, T, G,
        R, R, U, G,
        T, U, T, U,
        G, R, R, R,
    };
    kae_draw_image(10, 20, 4, 4, picture, 3);
    for (int row = 0; row < 4 * 3; row++)
        for (int col = 0; col < 4 * 3; col++) {
            uint32_t pixel = picture[(row / 3) * 4 + col / 3];
            CHECK(canvas[20 + row][10 + col] == ((pixel >> 24) >= 0x80 ? 0xFF000000 | (pixel & 0xFFFFFF) : 0));
        }
    CHECK(rect_calls == 4);     // rows 0 and 1 as one (R block, G bar), row 2 nothing, row 3 two runs
    kae_draw_image(0, 0, 0, 4, picture, 1);
    kae_draw_image(0, 0, 4, 4, 0, 1);
    kae_draw_image(0, 0, 4, 4, picture, 0);
    CHECK(rect_calls == 4);
}

int main(int argc, char **argv) {
    static const struct { const char *name; void (*run)(void); } tests[] = {
        { "format", test_format }, { "mods", test_mods }, { "unknown-game", test_unknown_game },
        { "events", test_events }, { "symbols", test_symbols }, { "alloc", test_alloc },
        { "text", test_text }, { "image", test_image },
    };
    for (size_t i = 0; i < sizeof tests / sizeof *tests; i++)
        if (argc == 2 && !strcmp(argv[1], tests[i].name)) {
            tests[i].run();
            printf("%s: ok\n", tests[i].name);
            return 0;
        }
    for (size_t i = 0; i < sizeof tests / sizeof *tests; i++)
        printf("%s\n", tests[i].name);
    return argc == 1 ? 0 : 1;
}
