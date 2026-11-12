/* The Mods menu: model, input handling and drawing. Portable C, so the same code runs inside
 * the game (built into KaeGae Core with KAE_MENU_ON_CORE) and in the host tests.
 * Draft 0.1: see ../MODS-MENU.md. */
#ifndef KAE_MENU_H
#define KAE_MENU_H
#include <stdint.h>

/* The buttons (KAE_A ...) and KaeItem are part of the public API. */
#include "kaegae.h"

#define KAE_OPEN_CHORD   (KAE_PLUS | KAE_MINUS)
#define KAE_CHORD_WINDOW 4       /* frames a lone + or - is held back, waiting for the other */

typedef struct { uint64_t buttons; int32_t lx, ly, rx, ry; } KaePad;

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
#ifdef KAE_MENU_ON_CORE
/* Draws the menu, if open, with Core's kae_draw_rect and kae_draw_text. Inside Core's draw. */
void kae_menu_draw_core(const KaeMenu *m, int width, int height);
#else
/* Draws the menu, if open, over an RGBA8 picture (bytes R, G, B, A): the host tests' renderer. */
void kae_menu_draw(const KaeMenu *m, uint8_t *rgba, int width, int height, int stride);
#endif
/* Another enabled mod's item bound to the same buttons, or null. */
const KaeItem *kae_menu_clash(const KaeMenu *m, const KaeItem *item, const KaePage **owner);
/* "L3", "Minus + Plus", "none". Returns `out`. */
char *kae_binding_text(uint64_t mask, char *out, int size);

#endif
