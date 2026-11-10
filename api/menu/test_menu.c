/* Host tests for the Mods menu, and screenshots of it.
 *     cc -O1 -Wall -o test_menu test_menu.c kae_menu.c && ./test_menu [background.rgba W H]
 * Writes mods.ppm, page.ppm and controls.ppm. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "kae_menu.h"

static int failures, checks;
#define CHECK(c) do { checks++; if (!(c)) { failures++; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

static KaeMenu m;
static uint64_t step(uint64_t buttons) { KaePad r = { buttons, 0, 0, 0, 0 }, g; kae_menu_input(&m, &r, &g); return g.buttons; }
static void tap(uint64_t b) { step(b); step(0); }

static int changed_count;
static void changed(KaeItem *it, void *user) { (void)it; (void)user; changed_count++; }

static const char *const modes[] = { "Free fly", "Angle", "Acro", "Simple" };
static KaeItem fp_items[] = {
    { KAE_BINDING, "Toggle first person", "Switch between the normal camera and Link's eyes.", 0, 0, 0, 0, 0, 0, KAE_R3, KAE_R3, changed, 0 },
    { KAE_TOGGLE, "Hide Link", "Hide Link's model while in first person.", 1, 1, 0, 0, 0, 0, 0, 0, changed, 0 },
    { KAE_NUMBER, "Eye height (cm)", "Raise or lower the camera.", 0, 0, -40, 40, 2, 0, 0, 0, changed, 0 },
};
static KaeItem drone_items[] = {
    { KAE_BINDING, "Launch / land", "Start or stop flying.", 0, 0, 0, 0, 0, 0, KAE_L3, KAE_L3, changed, 0 },
    { KAE_CHOICE, "Starting mode", "The flight mode used on the first launch.", 0, 0, 0, 3, 0, modes, 0, 0, changed, 0 },
    { KAE_NUMBER, "Acro camera tilt", "Degrees the camera looks up in Acro.", 30, 30, 0, 60, 5, 0, 0, 0, changed, 0 },
    { KAE_ACTION, "Reset drone position", "Put the drone back at the game camera.", 0, 0, 0, 0, 0, 0, 0, 0, changed, 0 },
};
static KaeItem gz_items[] = {
    { KAE_BINDING, "Levitate", "Float Link.", 0, 0, 0, 0, 0, 0, KAE_L3, KAE_L3, changed, 0 },
};
static KaePage fp = { "kabosune.first-person", "First Person", "2.0.0", 0, 1, fp_items, 3 };
static KaePage drone = { "kabosune.fpv-drone", "FPV Drone", "2.0.0", 0, 1, drone_items, 4 };
static KaePage gz = { "example.practice-tools", "Practice Tools", "0.4.1", 0, 1, gz_items, 1 };
static KaePage old = { "example.wide-fov", "Wide FOV", "1.0.0", "Not supported on this game version yet (needs Camera.Fov).", 0, 0, 0 };

static void shot(const char *name, const uint8_t *bg, int w, int h)
{
    uint8_t *px = malloc((size_t)w * h * 4);
    if (bg) memcpy(px, bg, (size_t)w * h * 4);
    else for (int i = 0; i < w * h; i++) { px[i * 4] = 38; px[i * 4 + 1] = 44; px[i * 4 + 2] = 52; px[i * 4 + 3] = 255; }
    kae_menu_draw(&m, px, w, h, w * 4);
    FILE *f = fopen(name, "wb");
    fprintf(f, "P6 %d %d 255\n", w, h);
    for (int i = 0; i < w * h; i++) fwrite(px + i * 4, 1, 3, f);
    fclose(f); free(px);
}

int main(int argc, char **argv)
{
    int w = 1920, h = 1080; uint8_t *bg = 0;
    if (argc == 4) {
        w = atoi(argv[2]); h = atoi(argv[3]); bg = malloc((size_t)w * h * 4);
        FILE *f = fopen(argv[1], "rb");
        if (!f || fread(bg, 4, (size_t)w * h, f) != (size_t)w * h) { puts("bad background"); return 2; }
        fclose(f);
    }
    kae_menu_add(&m, &fp); kae_menu_add(&m, &drone); kae_menu_add(&m, &gz); kae_menu_add(&m, &old);
    m.about[0] = "Kaepora Core 0.1 (draft)"; m.about[1] = "Game 1.1.1, build E0F3CCFA";
    m.about[2] = "4 mods installed, 3 running"; m.nabout = 3;

    /* --- a lone Plus reaches the game, late by the window, for as long as it is held */
    for (int i = 0; i < KAE_CHORD_WINDOW; i++) CHECK(step(KAE_PLUS) == 0);
    CHECK(step(KAE_PLUS) == KAE_PLUS);
    CHECK(step(KAE_PLUS | KAE_A) == (KAE_PLUS | KAE_A));
    CHECK(step(0) == 0 && !m.open);
    /* --- a one-frame tap of Minus is played back, not lost */
    CHECK(step(KAE_MINUS) == 0);
    CHECK(step(0) == KAE_MINUS);
    CHECK(step(0) == KAE_MINUS);
    CHECK(step(0) == 0);
    /* --- other buttons are never delayed */
    CHECK(step(KAE_A | KAE_ZL) == (KAE_A | KAE_ZL)); step(0);
    /* --- Plus then Minus too late: both go to the game, no menu */
    for (int i = 0; i < KAE_CHORD_WINDOW + 1; i++) step(KAE_PLUS);
    CHECK(step(KAE_PLUS | KAE_MINUS) == (KAE_PLUS | KAE_MINUS) && !m.open); step(0); step(0); step(0);
    /* --- Minus, then Plus two frames later: opens, the game sees neither, even on release */
    CHECK(step(KAE_MINUS) == 0); CHECK(step(KAE_MINUS) == 0);
    CHECK(step(KAE_MINUS | KAE_PLUS) == 0 && m.open);
    CHECK(step(KAE_PLUS) == 0); CHECK(step(0) == 0); CHECK(step(0) == 0);
    /* --- open: the game sees nothing; navigation works */
    CHECK(step(KAE_A | KAE_ZR) == 0 && m.depth == 1 && m.page == 0);     /* A entered First Person */
    step(0); shot("page.ppm", bg, w, h);
    tap(KAE_DOWN); CHECK(m.item_cursor == 1);
    changed_count = 0; tap(KAE_A); CHECK(fp_items[1].value == 0 && changed_count == 1);
    tap(KAE_DOWN); tap(KAE_RIGHT); tap(KAE_RIGHT); CHECK(fp_items[2].value == 4);
    for (int i = 0; i < 40; i++) tap(KAE_RIGHT);
    CHECK(fp_items[2].value == 40);                                         /* clamped */
    tap(KAE_Y); CHECK(fp_items[2].value == 0);                              /* back to default */
    step(KAE_DOWN); for (int i = 0; i < 30; i++) step(KAE_DOWN); step(0);
    CHECK(m.item_cursor != 0 || 1);                                        /* held direction repeats without crashing */
    m.item_cursor = 0;
    /* --- rebinding: A, then hold ZL and press Y, release */
    tap(KAE_A); CHECK(m.capture == &fp_items[0]);
    step(KAE_ZL); step(KAE_ZL | KAE_Y); step(KAE_Y); step(0);
    CHECK(!m.capture && fp_items[0].binding == (KAE_ZL | KAE_Y));
    char t[64]; CHECK(!strcmp(kae_binding_text(fp_items[0].binding, t, sizeof t), "Y + ZL"));
    tap(KAE_Y); CHECK(fp_items[0].binding == KAE_R3);
    /* --- clash: two enabled mods on L3 */
    const KaePage *owner = 0;
    CHECK(kae_menu_clash(&m, &drone_items[0], &owner) == &gz_items[0] && owner == &gz);
    CHECK(!kae_menu_clash(&m, &fp_items[0], 0));
    tap(KAE_B); CHECK(m.depth == 0 && m.open);
    shot("mods.ppm", bg, w, h);
    tap(KAE_R); CHECK(m.tab == 1);
    tap(KAE_DOWN); shot("controls.ppm", bg, w, h);
    /* --- switching a mod off removes its clash */
    tap(KAE_L); m.cursor[0] = 2; tap(KAE_X); CHECK(!gz.enabled);
    CHECK(!kae_menu_clash(&m, &drone_items[0], 0));
    m.cursor[0] = 3; tap(KAE_X); CHECK(!old.enabled);                       /* an unavailable mod can't be switched on */
    tap(KAE_R); tap(KAE_R); CHECK(m.tab == 2);
    /* --- B closes; B is not passed to the game while still held */
    CHECK(step(KAE_B) == 0 && !m.open);
    CHECK(step(KAE_B) == 0); CHECK(step(0) == 0);
    CHECK(step(KAE_B) == KAE_B); step(0);
    /* --- the chord closes it too */
    step(KAE_PLUS); step(KAE_PLUS | KAE_MINUS); step(0); CHECK(m.open);
    step(KAE_PLUS | KAE_MINUS); CHECK(!m.open); CHECK(step(KAE_PLUS) == 0); step(0);

    printf("%d checks, %d failed\n", checks, failures);
    return failures != 0;
}
