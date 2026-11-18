// Equip Anything: child and adult Link can equip every item, and picking an equipped one again
// in the pause menu takes it off. A core mod (KaeGae Core 0.9).
//
// Any age: the pause menu reads which age may use an item from its table (UI/Pouch/PouchTable),
// as the game parsed it: every item has IsUsableChild and IsUsableAdult, each with a "set here"
// byte. The mod sets both, in memory, on every item of the menu's pages, keeping what it found so
// that switching the setting off puts it back. It looks again every second, in case the table
// was loaded anew.
//
// Taking off: Core's pouch_equip event says when the menu equips an item that already is in its
// slot; the mod empties the slot instead (kae_pouch_unequip) and the game's equip is skipped.
#include <kaegae.h>

enum { ANY_AGE, TAKE_OFF, ITEMS };
static KaeItem settings[ITEMS] = {
    [ANY_AGE]  = { KAE_TOGGLE, "Any age can equip", "Child and adult Link can pick every item and piece of equipment.",
                   1, 1, 0, 1, 1, 0, 0, 0, 0, 0 },
    [TAKE_OFF] = { KAE_TOGGLE, "Pick again to take off", "Picking an equipped sword, shield or tunic again takes it off.",
                   1, 1, 0, 1, 1, 0, 0, 0, 0, 0 },
};

#define PAGES 8           // arrays of 0x28 bytes from PouchTable.pages
#define PAGE_SIZE 0x28
#define HIDDEN_PAGE 2     // +0x88: not one of the menu's seven pages (none of its page getters returns it)
#define MAX_ITEMS 256

typedef struct {
    uint8_t *item;
    uint8_t child, adult, child_set, adult_set;
} saved_t;

static void **pouch_ptr;
static int64_t f_ui, f_table, f_pages, f_items, f_name, f_child, f_adult;
static saved_t saved[MAX_ITEMS];
static int saved_count;
static void *table_done;      // the table the flags were set in (0: not set / put back)
static int frames;

// An array of the game's: count at +8, pointer to the elements at +0x10.
static int array_at(const uint8_t *array, void ***elements) {
    if (!kae_readable(array, 0x18))
        return 0;
    uint32_t count = *(const uint32_t *)(array + 8);
    void **data = *(void ***)(array + 0x10);
    if (!count || count > 128 || !kae_readable(data, count * sizeof(void *)))
        return 0;
    *elements = data;
    return (int)count;
}

static void *find_table(void) {
    if (!pouch_ptr || !kae_readable(pouch_ptr, 8))
        return 0;
    uint8_t *pouch = *pouch_ptr;
    if (!pouch || !kae_readable(pouch + f_ui, 8))
        return 0;
    uint8_t *ui = *(uint8_t **)(pouch + f_ui);
    if (!ui || !kae_readable(ui + f_table, 8))
        return 0;
    uint8_t *table = *(uint8_t **)(ui + f_table);
    if (!table || !kae_readable(table + f_pages, PAGES * PAGE_SIZE))
        return 0;
    return table;
}

static int is_name(const char *s) {
    if (!kae_readable(s, 2))
        return 0;
    return (s[0] >= 'A' && s[0] <= 'Z') || (s[0] >= 'a' && s[0] <= 'z');
}

static void put_back(void) {
    for (int i = 0; i < saved_count; i++) {
        uint8_t *it = saved[i].item;
        if (!kae_readable(it + f_child, 4))
            continue;
        it[f_child] = saved[i].child;
        it[f_adult] = saved[i].adult;
        it[f_child + 3] = saved[i].child_set;
        it[f_adult + 3] = saved[i].adult_set;
    }
    saved_count = 0;
    table_done = 0;
}

// Sets both flags on every item. Returns how many items it changed.
static int unlock(uint8_t *table) {
    int changed = 0, seen = 0;
    for (int p = 0; p < PAGES; p++) {
        if (p == HIDDEN_PAGE)
            continue;
        void **buttons;
        int n = array_at(table + f_pages + p * PAGE_SIZE, &buttons);
        for (int b = 0; b < n; b++) {
            uint8_t *button = buttons[b];
            void **items;
            int m = button ? array_at(button + f_items, &items) : 0;
            for (int i = 0; i < m; i++) {
                uint8_t *it = items[i];
                if (!it || !kae_readable(it + f_name, 8) || !kae_readable(it + f_child, 4) || !is_name(*(const char **)(it + f_name)))
                    continue;
                seen++;
                if (it[f_child] == 1 && it[f_adult] == 1 && it[f_child + 3] == 1 && it[f_adult + 3] == 1)
                    continue;
                if (saved_count < MAX_ITEMS)
                    saved[saved_count++] = (saved_t){ it, it[f_child], it[f_adult], it[f_child + 3], it[f_adult + 3] };
                it[f_child] = it[f_adult] = 1;
                it[f_child + 3] = it[f_adult + 3] = 1;
                changed++;
            }
        }
    }
    if (seen == 0)
        return -1;
    return changed;
}

static void frame(void *user) {
    (void)user;
    if (frames++ % 60)
        return;
    void *table = find_table();
    if (!settings[ANY_AGE].value) {
        if (table_done)
            put_back();
        return;
    }
    if (!table)
        return;
    if (table != table_done)
        saved_count = 0;      // a new table: what was saved belongs to the old one
    int changed = unlock(table);
    if (changed < 0)
        return;
    if (table != table_done || changed)
        KAE_LOG("equip anything: every age can use %d more items (table at %p)", changed, table);
    table_done = table;
}

static void any_age_changed(KaeItem *item, void *user) {
    (void)item;
    (void)user;
    frames = 0;               // act on the next frame
}

static int on_equip(KaePouchEquip *e, void *user) {
    (void)user;
    if (!settings[TAKE_OFF].value || !e->from_menu || !e->equipped || e->handled)
        return 0;
    int result = kae_pouch_unequip(e->name);
    KAE_LOG("equip anything: took off %s (%d)", e->name, result);
    return result == KAE_OK;
}

static int start(void) {
    pouch_ptr = kae_sym("PouchMgrPtr");
    f_ui = kae_field("PouchMgr.ui");
    f_table = kae_field("PouchUi.table");
    f_pages = kae_field("PouchTable.pages");
    f_items = kae_field("PouchButton.items");
    f_name = kae_field("PouchItem.name");
    f_child = kae_field("PouchItem.usable_child");
    f_adult = kae_field("PouchItem.usable_adult");
    settings[ANY_AGE].changed = any_age_changed;
    kae_settings("Equip Anything", settings, ITEMS);
    int ok_age = pouch_ptr && f_ui >= 0 && f_table >= 0 && f_pages >= 0 && f_items >= 0 && f_name >= 0 && f_child >= 0 && f_adult == f_child + 1;
    int ok_off = kae_has("event.pouch_equip");
    KAE_LOG("equip anything 1.0.0 (game %s): any age %s, take off %s", kae_game_version(),
            ok_age ? "ready" : "unavailable (names missing)", ok_off ? "ready" : "unavailable (Core's Pouch.Equip hook point is off)");
    if (ok_age)
        kae_on_frame(frame, 0, 0);
    if (ok_off)
        kae_on_pouch_equip(on_equip, 0, 0);
    return ok_age || ok_off ? 0 : 1;
}

KAE_MOD("kabosune.equip-anything", "1.0.0", start, 0);
