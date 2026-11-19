// For tests/test_kaegae_modules.py: logs every pouch_equip, and takes an item picked again in the
// menu off (what Equip Anything does).
#include <kaegae.h>

static int on_equip(KaePouchEquip *e, void *user) {
    (void)user;
    KAE_LOG("pouch: %s menu %d equipped %d mode %d handled %d", e->name, e->from_menu, e->equipped, e->mode, e->handled);
    if (e->from_menu && e->equipped) {
        KAE_LOG("pouch: unequip %d, still equipped %d", kae_pouch_unequip(e->name), kae_pouch_is_equipped(e->name));
        return 1;
    }
    return 0;
}

static int start(void) {
    KAE_LOG("pouch: has %d %d", kae_has("event.pouch_equip"), kae_has("pouch"));
    return kae_on_pouch_equip(on_equip, 0, 0);
}

KAE_MOD("kaegae.pouch-test", "1.0.0", start, 0);
