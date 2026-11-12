// Names for things inside the game, from the symbol pack of the running build, and kae_has.
#include "core.h"

#include "symbols_gen.h"

static int compare(const char *a, const char *b) {
    for (; *a && *a == *b; a++, b++) {}
    return (unsigned char)*a - (unsigned char)*b;
}

static const kp_sym_t *find(const kp_sym_t *table, uint32_t count, const char *name) {
    uint32_t low = 0, high = count;
    while (low < high) {
        uint32_t mid = low + (high - low) / 2;
        int c = compare(name, table[mid].name);
        if (c == 0)
            return &table[mid];
        if (c < 0)
            high = mid;
        else
            low = mid + 1;
    }
    return 0;
}

void *kae_sym(const char *name) {
    if (!kp_main || !name)
        return 0;
    const kp_sym_t *s = find(kp_build->syms, kp_build->sym_count, name);
    return s ? (void *)(kp_main + s->offset) : 0;
}

int64_t kae_field(const char *name) {
    if (!kp_build || !name)
        return -1;
    const kp_sym_t *s = find(kp_build->fields, kp_build->field_count, name);
    return s ? (int64_t)s->offset : -1;
}

uintptr_t kae_game_base(void) { return kp_main; }
const char *kae_game_version(void) { return kp_build ? kp_build->version : ""; }
const char *kae_game_build(void) { return kp_build ? kp_build->build_id : ""; }
uint32_t kae_api_version(void) { return ((uint32_t)KAE_API_MAJOR << 16) | KAE_API_MINOR; }
int kae_readable(const void *p, size_t size) { return kp_readable((uintptr_t)p, size); }

int kae_has(const char *feature) {
    static const struct { const char *name; int event; } events[] = {
        { "event.frame", KP_EV_FRAME }, { "event.input", KP_EV_INPUT }, { "event.draw", KP_EV_DRAW },
        { "event.actor_move", KP_EV_ACTOR_MOVE }, { "draw.rect", KP_EV_DRAW },
        { "draw.text", KP_EV_DRAW }, { "draw.image", KP_EV_DRAW },
    };
    if (!feature)
        return 0;
    for (size_t i = 0; i < sizeof events / sizeof *events; i++)
        if (compare(feature, events[i].name) == 0)
            return kp_event_on[events[i].event];
    if (compare(feature, "menu") == 0)
        return kp_menu_on();
    if (compare(feature, "motion") == 0)
        return kp_motion_on;
    if (compare(feature, "symbols") == 0)
        return kp_main != 0;
    if (compare(feature, "alloc") == 0)
        return 1;
    return 0;
}
