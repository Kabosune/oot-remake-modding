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

// settings.c: the pages' values kept between runs.
void kp_settings_load(KaePage **pages, int count);
void kp_settings_save(KaePage **pages, int count);
bool kp_settings_on(void);
static int saved_line;   // the line of the About text that says whether settings are saved

static KaeMenu menu;
static KaePage pages[MAX_PAGES];
static const KaeMod *owners[MAX_PAGES];
static int page_count;
static bool on;

// Keys (0.7): each page's items' keys, what kae_binding_pressed saw last time it was asked, and
// whether the mod reads the item with kae_binding_held / _pressed (then it gets no buttons for it).
static unsigned char page_keys[MAX_PAGES][KAE_MAX_KEYED], page_held[MAX_PAGES][KAE_MAX_KEYED];
static bool page_read[MAX_PAGES][KAE_MAX_KEYED];
static bool keys_bound;              // some enabled binding has a key: worth reading the keyboard
static uint64_t injected;            // buttons added for older mods' keys in this controller read

// Core's own settings, on the About tab and in the settings file as [kaegae.core].
static void keyboard_changed(KaeItem *item, void *user) {
    (void)user;
    kp_keyboard_switch(item->value != 0);
}
static KaeItem core_items[] = {
    { KAE_TOGGLE, "Keyboard", "Mods' keys (the Keyboard column). Off: Core never reads the keyboard.",
      1, 1, 0, 0, 0, 0, 0, 0, keyboard_changed, 0 },
};
static KaePage core_page = { "kaegae.core", "KaeGae Core", KP_STR(KAE_API_MAJOR) "." KP_STR(KAE_API_MINOR), 0, 1,
                             core_items, sizeof core_items / sizeof *core_items, 0 };

// The settings file's pages: the mods' and Core's own.
static int all_pages(KaePage **out) {
    int n = 0;
    for (int i = 0; i < menu.npages; i++)
        out[n++] = menu.pages[i];
    out[n++] = &core_page;
    return n;
}

static void count_keys(void) {
    keys_bound = false;
    for (int i = 0; i < page_count; i++)
        for (int j = 0; pages[i].enabled && pages[i].keys && j < pages[i].count && j < KAE_MAX_KEYED; j++)
            if (pages[i].items[j].type == KAE_BINDING && pages[i].keys[j])
                keys_bound = true;
}

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
        *page = (KaePage){ mod->id, mod->id, mod->version ? mod->version : "?", 0, 1, 0, 0, 0 };
        kae_menu_add(&menu, page);
    }
    page->status = status;
}

bool kp_mod_off(const KaeMod *mod) {
    const KaePage *page = page_of(mod);
    return page && !page->enabled;
}

// Mods built before 0.6: their KaeItem is this Core's KaeItem.
int (kae_settings)(const char *name, KaeItem *items, int count) {
    return kae_settings_sized(name, items, count, sizeof(KaeItem));
}

int kae_settings_sized(const char *name, KaeItem *items, int count, uint32_t item_size) {
    KaePage *page = page_of(kp_mod_starting());
    // Only this Core's KaeItem so far. When it grows, an older, smaller one will be read through a
    // copy here instead of being refused.
    if (!page || count < 0 || (count && !items) || item_size != sizeof(KaeItem))
        return KAE_ERR_ARGUMENT;
    if (name && name[0])
        page->name = name;
    page->items = items;
    page->count = count;
    page->keys = page_keys[page - pages];
    return KAE_OK;
}

int kae_menu_open(void) { return menu.open; }

void kp_menu_start(void) {
    static const char *const about[] = {
        "KaeGae Core: a shared base for Ocarina of Time mods.",
        "github.com/Kabosune/oot-remake-modding",
        "",
        "Open and close this menu with Minus and Plus together.",
        "Settings are not saved between runs.",
    };
    for (unsigned i = 0; i < sizeof about / sizeof *about; i++)
        menu.about[menu.nabout++] = about[i];
    saved_line = menu.nabout - 1;
    if (kp_keyboard_present()) {
        menu.core_items = core_items;
        menu.ncore = core_page.count;
    } else {
        kp_log("keyboard: the system has no keyboard functions, so mods get no keys");
    }
    on = kp_event_on[KP_EV_INPUT] && kp_event_on[KP_EV_FRAME] && kp_event_on[KP_EV_DRAW];
    if (!on)
        kp_log("Mods menu off: it needs the controller, the frame and drawing");
}

bool kp_menu_on(void) { return on; }

// Once a frame, before the mods' frame functions.
void kp_menu_frame(void) {
    if (!on)
        return;
    static bool loaded;
    KaePage *all[MAX_PAGES + 1];
    int all_count = all_pages(all);
    if (!loaded) {
        loaded = true;
        kp_settings_load(all, all_count);
        if (kp_settings_on())
            menu.about[saved_line] = "Settings are saved on the SD card: kaegae/settings.txt.";
        count_keys();
    }
    menu.keyboard = kp_keyboard_on();
    if (!menu.open || !kp_keyboard_read(menu.keys))   // only the open menu reads keys (to capture them)
        for (int i = 0; i < 4; i++)
            menu.keys[i] = 0;
    KaePad real = { seen_buttons, 0, 0, 0, 0 }, game;
    seen_buttons = 0;
    bool was_open = menu.open;
    kae_menu_input(&menu, &real, &game);
    hide_all = menu.open || was_open;      // the press that closes the menu isn't the game's either
    hide = real.buttons & ~game.buttons;
    press = game.buttons & ~real.buttons;
    if (menu.open != was_open) {
        kp_log(menu.open ? "Mods menu opened" : "Mods menu closed");
        if (!menu.open) {
            kp_settings_save(all, all_count);
            count_keys();
        }
    }
}

static int key_held(const uint64_t keys[4], int key) { return key > 0 && key < 256 && (int)(keys[key >> 6] >> (key & 63) & 1); }

// The buttons of every binding whose key is held, unless its mod reads it with kae_binding_held or
// kae_binding_pressed: mods written before 0.7 look at the controller's buttons themselves, so they
// get the buttons instead. Other mods see them too.
static uint64_t old_mods_keys(void) {
    uint64_t keys[4], buttons = 0;
    if (!keys_bound || !kp_keyboard_read(keys))
        return 0;
    for (int i = 0; i < page_count; i++) {
        const KaePage *page = &pages[i];
        if (!page->enabled || !page->keys)
            continue;
        for (int j = 0; j < page->count && j < KAE_MAX_KEYED; j++)
            if (page->items[j].type == KAE_BINDING && !page_read[i][j] && key_held(keys, page->keys[j]))
                buttons |= page->items[j].binding;
    }
    return buttons;
}

// Every controller read, before the mods' input functions.
void kp_menu_input(KaeInput *seen, KaeInput *real) {
    injected = 0;
    if (!on || !real->connected)
        return;
    seen_buttons |= real->buttons & KAE_BINDING_MASK;
    if (hide_all) {
        seen->buttons = 0;
        seen->lx = seen->ly = seen->rx = seen->ry = 0;
    } else {
        seen->buttons = (seen->buttons & ~hide) | press;
        injected = old_mods_keys() & ~real->buttons;
        seen->buttons |= injected;
        real->buttons |= injected;
    }
}

// The menu has the last word while it is open: a mod can't press buttons for the game then. And
// the buttons added for keys never reach the game.
void kp_menu_input_done(KaeInput *seen) {
    if (on && hide_all) {
        seen->buttons = 0;
        seen->lx = seen->ly = seen->rx = seen->ry = 0;
    }
    seen->buttons &= ~injected;
    injected = 0;
}

// ---- kae_binding_held / kae_binding_pressed ----

static KaePage *page_of_item(const KaeItem *item, int *index) {
    for (int i = 0; i < page_count; i++)
        if (pages[i].items && item >= pages[i].items && item < pages[i].items + pages[i].count) {
            *index = (int)(item - pages[i].items);
            return &pages[i];
        }
    return 0;
}

int kae_binding_held(const KaeItem *item) {
    if (!item || item->type != KAE_BINDING || (on && menu.open))
        return 0;
    int index = 0;
    const KaePage *page = page_of_item(item, &index);
    if (page && index < KAE_MAX_KEYED)
        page_read[page - pages][index] = true;
    if (page && !page->enabled)
        return 0;
    uint64_t mask = item->binding & KAE_BINDING_MASK;
    if (mask && (kp_input_live() & mask) == mask)
        return 1;
    int key = page && page->keys && index < KAE_MAX_KEYED ? page->keys[index] : 0;
    uint64_t keys[4];
    return key && kp_keyboard_read(keys) && key_held(keys, key);
}

int kae_binding_pressed(const KaeItem *item) {
    static struct { const KaeItem *item; unsigned char held; } loose[16];   // items not on a page
    int index = 0, held = kae_binding_held(item);
    KaePage *page = item ? page_of_item(item, &index) : 0;
    unsigned char *was = 0;
    if (page && index < KAE_MAX_KEYED) {
        was = &page_held[page - pages][index];
    } else if (item) {
        for (int i = 0; i < 16 && !was; i++)
            if (loose[i].item == item || !loose[i].item) {
                loose[i].item = item;
                was = &loose[i].held;
            }
    }
    if (!was)
        return 0;
    int pressed = held && !*was;
    *was = (unsigned char)held;
    return pressed;
}

// Inside Core's draw, after the mods have drawn.
void kp_menu_draw(int width, int height) {
    if (on)
        kae_menu_draw_core(&menu, width, height);
}
