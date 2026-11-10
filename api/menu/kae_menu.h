/* The Mods menu: model, input handling and a CPU renderer. Portable C with no dependencies, so the
 * same code runs inside the game (drawn into the frame by Kaepora Core) and in the host tests.
 * Draft 0.1: see ../MODS-MENU.md. */
#ifndef KAE_MENU_H
#define KAE_MENU_H
#include <stdint.h>

/* Controller buttons: the system's bit numbers. */
enum {
    KAE_A = 1 << 0, KAE_B = 1 << 1, KAE_X = 1 << 2, KAE_Y = 1 << 3, KAE_L3 = 1 << 4, KAE_R3 = 1 << 5,
    KAE_L = 1 << 6, KAE_R = 1 << 7, KAE_ZL = 1 << 8, KAE_ZR = 1 << 9, KAE_PLUS = 1 << 10,
    KAE_MINUS = 1 << 11, KAE_LEFT = 1 << 12, KAE_UP = 1 << 13, KAE_RIGHT = 1 << 14, KAE_DOWN = 1 << 15,
};
#define KAE_OPEN_CHORD   (KAE_PLUS | KAE_MINUS)
#define KAE_CHORD_WINDOW 4       /* frames a lone + or - is held back, waiting for the other */

typedef struct { uint64_t buttons; int32_t lx, ly, rx, ry; } KaePad;

typedef enum { KAE_TOGGLE, KAE_CHOICE, KAE_NUMBER, KAE_BINDING, KAE_ACTION } KaeItemType;

typedef struct KaeItem KaeItem;
struct KaeItem {
    KaeItemType type;
    const char *label;
    const char *help;                 /* one line shown under the list; may be null */
    int value, def;                   /* toggle 0/1, choice index, number */
    int min, max, step;               /* number */
    const char *const *choices;       /* choice: `max + 1` names */
    uint64_t binding, def_binding;    /* binding: button mask, 0 = unbound */
    void (*changed)(KaeItem *item, void *user);   /* after any change; for an action, on A */
    void *user;
};

typedef struct {
    const char *id, *name, *version;
    const char *status;               /* null, or why Core switched the mod off */
    int enabled;
    KaeItem *items;
    int count;
} KaePage;

#define KAE_MAX_PAGES 32
#define KAE_MAX_ABOUT 16

typedef struct {
    KaePage *pages[KAE_MAX_PAGES];
    int npages;
    const char *about[KAE_MAX_ABOUT];
    int nabout;
    /* state */
    int open, tab, depth, page, cursor[3], item_cursor, scroll;
    KaeItem *capture; int capture_stage, capture_frames; uint64_t capture_mask;
    uint64_t prev, pending, replay; int pending_frames, replay_frames, swallow;
    int repeat_frames; uint64_t repeat_button;
} KaeMenu;

void kae_menu_add(KaeMenu *m, KaePage *page);
/* Once per frame. `real` is the controller; `game` receives what the game should see. */
void kae_menu_input(KaeMenu *m, const KaePad *real, KaePad *game);
/* Draws the menu, if open, over an RGBA8 picture (bytes R, G, B, A). */
void kae_menu_draw(const KaeMenu *m, uint8_t *rgba, int width, int height, int stride);
/* Another enabled mod's item bound to the same buttons, or null. */
const KaeItem *kae_menu_clash(const KaeMenu *m, const KaeItem *item, const KaePage **owner);
/* "L3", "Minus + Plus", "none". Returns `out`. */
char *kae_binding_text(uint64_t mask, char *out, int size);

#endif
