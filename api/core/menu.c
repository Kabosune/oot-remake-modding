// The Mods menu inside Core: the shared screen (opened with - and + together) that lists every
// mod, switches mods off and on, and shows each mod's settings (kae_settings).
//
// The menu itself (its state, what each button does, how it is laid out) is ../menu/kae_menu.c,
// which is also built and tested on the PC. This file gives it Core's mods, the controller once a
// frame, and Core's rectangles and text to draw with.
//
// The controller is read many times a frame (per controller, per style), the menu steps once a
// frame. So each frame the menu sees every button that any read of the last frame reported, and
// what it decides (hide everything while open; hold a lone - or + back for a moment) is applied to
// every read of the next frame.
#include "core.h"

#define KAE_MENU_ON_CORE
#include "../menu/kae_menu.c"

#define MAX_PAGES KAE_MAX_PAGES

static KaeMenu menu;
static KaePage pages[MAX_PAGES];
static const KaeMod *owners[MAX_PAGES];
static int page_count;
static bool on;

static uint64_t seen_buttons;       // every button reported since the last frame
static uint64_t hide, press;        // what to take from, and add to, the game's reads this frame
static bool hide_all;

static KaePage *page_of(const KaeMod *mod) {
    for (int i = 0; i < page_count; i++)
        if (owners[i] == mod)
            return &pages[i];
    return 0;
}

void kp_menu_add_mod(const KaeMod *mod, const char *status) {
    KaePage *page = page_of(mod);
    if (!page) {
        if (page_count == MAX_PAGES)
            return;
        owners[page_count] = mod;
        page = &pages[page_count++];
        *page = (KaePage){ mod->id, mod->id, mod->version ? mod->version : "?", 0, 1, 0, 0 };
        kae_menu_add(&menu, page);
    }
    page->status = status;
}

bool kp_mod_off(const KaeMod *mod) {
    const KaePage *page = page_of(mod);
    return page && !page->enabled;
}

int kae_settings(const char *name, KaeItem *items, int count) {
    KaePage *page = page_of(kp_mod_starting());
    if (!page || count < 0 || (count && !items))
        return KAE_ERR_ARGUMENT;
    if (name && name[0])
        page->name = name;
    page->items = items;
    page->count = count;
    return KAE_OK;
}

int kae_menu_open(void) { return menu.open; }

void kp_menu_start(void) {
    static const char *const about[] = {
        "Kaepora Core: a shared base for Ocarina of Time mods.",
        "github.com/Kabosune/oot-remake-modding",
        "",
        "Open and close this menu with Minus and Plus together.",
        "Settings are not saved between runs yet.",
    };
    for (unsigned i = 0; i < sizeof about / sizeof *about; i++)
        menu.about[menu.nabout++] = about[i];
    on = kp_event_on[KP_EV_INPUT] && kp_event_on[KP_EV_FRAME] && kp_event_on[KP_EV_DRAW];
    if (!on)
        kp_log("Mods menu off: it needs the controller, the frame and drawing");
}

bool kp_menu_on(void) { return on; }

// Once a frame, before the mods' frame functions.
void kp_menu_frame(void) {
    if (!on)
        return;
    KaePad real = { seen_buttons, 0, 0, 0, 0 }, game;
    seen_buttons = 0;
    bool was_open = menu.open;
    kae_menu_input(&menu, &real, &game);
    hide_all = menu.open || was_open;      // the press that closes the menu isn't the game's either
    hide = real.buttons & ~game.buttons;
    press = game.buttons & ~real.buttons;
    if (menu.open != was_open)
        kp_log(menu.open ? "Mods menu opened" : "Mods menu closed");
}

// Every controller read, before the mods' input functions.
void kp_menu_input(KaeInput *seen, const KaeInput *real) {
    if (!on || !real->connected)
        return;
    seen_buttons |= real->buttons & 0xFFFF;
    if (hide_all) {
        seen->buttons = 0;
        seen->lx = seen->ly = seen->rx = seen->ry = 0;
    } else {
        seen->buttons = (seen->buttons & ~hide) | press;
    }
}

// The menu has the last word while it is open: a mod can't press buttons for the game then.
void kp_menu_input_done(KaeInput *seen) {
    if (on && hide_all) {
        seen->buttons = 0;
        seen->lx = seen->ly = seen->rx = seen->ry = 0;
    }
}

// Inside Core's draw, after the mods have drawn.
void kp_menu_draw(int width, int height) {
    if (on)
        kae_menu_draw_core(&menu, width, height);
}
