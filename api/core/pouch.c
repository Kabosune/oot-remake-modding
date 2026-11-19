// The pouch (0.9): the pouch_equip event and taking items off.
//
// Hook point Pouch.Equip is the second instruction of the game's PouchEquip (PouchMgr*, name,
// mode, flag), the function the pause menu and the game's own code (area loads, events) call to
// put an item into one of Link's PlayerStatus.Equip... slots. Core tells mods about the call, with
// whether it came from the pause menu (its return address lies in the hook point's `menu` range)
// and whether the item is already the one in its slot; a mod that returns 1 makes the game skip
// its own equip. kae_pouch_unequip calls the menu's own PouchUnequip.
#include "core.h"

typedef int (*is_equipped_fn)(void *pouch, void *name);
typedef void (*unequip_fn)(void *pouch, void *name, int flag);

static is_equipped_fn is_equipped;
static unequip_fn unequip;
static void **pouch_ptr;          // PouchMgrPtr: the variable holding the PouchMgr
static uintptr_t menu_lo, menu_hi;

// The game's string as these functions take it: a pointer to the text, then the buffer's size.
// They may write the terminator at top[size - 1], so hand them a copy in a buffer of our own.
typedef struct {
    char *top;
    int32_t size;
    char buf[0x44];
} game_string_t;

static int make_string(game_string_t *s, const char *name) {
    size_t n = 0;
    while (name[n]) {
        if (++n >= sizeof s->buf)
            return 0;
    }
    for (size_t i = 0; i <= n; i++)
        s->buf[i] = name[i];
    s->top = s->buf;
    s->size = (int32_t)sizeof s->buf;
    return 1;
}

// xpaclri (hint #7) works on x30 only, and is a no-op where pointers aren't signed (in the hint
// space, unlike xpaci, so it runs on any CPU).
static uintptr_t strip_pac(uintptr_t p) {
    uintptr_t out;
    __asm__ volatile("mov x30, %1\n\thint #7\n\tmov %0, x30" : "=r"(out) : "r"(p) : "x30");
    return out;
}

bool kp_pouch_start(void) {
    is_equipped = (is_equipped_fn)kae_sym("PouchIsEquipped");
    unequip = (unequip_fn)kae_sym("PouchUnequip");
    pouch_ptr = (void **)kae_sym("PouchMgrPtr");
    for (uint32_t i = 0; i < kp_build->hookpoint_count; i++) {
        const kp_hookpoint_t *h = &kp_build->hookpoints[i];
        if (h->menu_hi) {
            menu_lo = kp_main + h->menu_lo;
            menu_hi = kp_main + h->menu_hi;
        }
    }
    if (!is_equipped || !unequip || !pouch_ptr) {
        kp_log("pouch off: this game version's symbols don't have the pouch functions");
        return false;
    }
    return true;
}

int kp_pouch_entry(void *pouch, void *name, int mode, int flag, uintptr_t lr) {
    (void)flag;
    if (!kp_wants_pouch_equip())
        return 0;
    const char *text = 0;
    if (name && kp_readable((uintptr_t)name, 8))
        text = *(const char **)name;
    if (!text || !kp_readable((uintptr_t)text, 1))
        return 0;
    uintptr_t ret = strip_pac(lr);
    KaePouchEquip e = {
        .size = sizeof e,
        .name = text,
        .from_menu = menu_hi && ret >= menu_lo && ret < menu_hi,
        .equipped = is_equipped(pouch, name) & 1,
        .mode = mode,
        .pouch = pouch,
    };
    return kp_fire_pouch_equip(&e);
}

static void *the_pouch(void) {
    if (!pouch_ptr || !kp_readable((uintptr_t)pouch_ptr, 8))
        return 0;
    return *pouch_ptr;
}

int kae_pouch_is_equipped(const char *name) {
    void *pouch = the_pouch();
    game_string_t s;
    if (!is_equipped || !pouch)
        return KAE_ERR_UNAVAILABLE;
    if (!name || !make_string(&s, name))
        return KAE_ERR_ARGUMENT;
    return is_equipped(pouch, &s) & 1;
}

int kae_pouch_unequip(const char *name) {
    void *pouch = the_pouch();
    game_string_t s;
    if (!unequip || !pouch)
        return KAE_ERR_UNAVAILABLE;
    if (!name || !make_string(&s, name))
        return KAE_ERR_ARGUMENT;
    unequip(pouch, &s, 0);
    return KAE_OK;
}
