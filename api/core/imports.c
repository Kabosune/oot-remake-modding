// Finding the GOT slot a module calls an import through, from the module's own dynamic section.
#include "core.h"

typedef struct { int64_t tag; uint64_t value; } dyn_t;
typedef struct { uint32_t name; uint8_t info, other; uint16_t section; uint64_t value, size; } sym_t;
typedef struct { uint64_t where, info; int64_t addend; } rela_t;

enum { TAG_END = 0, TAG_PLT_SIZE = 2, TAG_STRINGS = 5, TAG_SYMBOLS = 6, TAG_RELA = 7, TAG_RELA_SIZE = 8, TAG_PLT_RELA = 23 };
enum { REL_ABS64 = 257, REL_GLOB_DAT = 1025, REL_JUMP_SLOT = 1026 };

static bool equal(const char *a, const char *b) {
    for (; *a == *b; a++, b++)
        if (!*a)
            return true;
    return false;
}

// A dynamic entry holds an offset before rtld relocates it and an address after.
static uint64_t offset_of(uintptr_t module, uint64_t v) {
    return v >= module ? v - module : v;
}

static uintptr_t *search(uintptr_t module, uint64_t table, uint64_t bytes, const sym_t *symbols, const char *strings,
                         const char *name) {
    const rela_t *r = (const rela_t *)(module + table);
    for (uint64_t i = 0; table && i < bytes / sizeof *r; i++) {
        uint32_t type = (uint32_t)r[i].info, index = (uint32_t)(r[i].info >> 32);
        if (!index || (type != REL_JUMP_SLOT && type != REL_GLOB_DAT && type != REL_ABS64))
            continue;
        if (symbols[index].section == 0 && equal(strings + symbols[index].name, name))
            return (uintptr_t *)(module + r[i].where);
    }
    return 0;
}

uintptr_t *kp_import_slot(uintptr_t module, const char *name) {
    uintptr_t mod0 = module + *(const uint32_t *)(module + 4);
    if (*(const uint32_t *)mod0 != 0x30444F4D)   // "MOD0"
        return 0;
    const dyn_t *d = (const dyn_t *)(mod0 + *(const int32_t *)(mod0 + 4));
    uint64_t symbols = 0, strings = 0, rela = 0, rela_size = 0, plt = 0, plt_size = 0;
    for (int i = 0; i < 128 && d[i].tag != TAG_END; i++) {
        switch (d[i].tag) {
        case TAG_SYMBOLS:   symbols = offset_of(module, d[i].value); break;
        case TAG_STRINGS:   strings = offset_of(module, d[i].value); break;
        case TAG_RELA:      rela = offset_of(module, d[i].value); break;
        case TAG_PLT_RELA:  plt = offset_of(module, d[i].value); break;
        case TAG_RELA_SIZE: rela_size = d[i].value; break;
        case TAG_PLT_SIZE:  plt_size = d[i].value; break;
        }
    }
    if (!symbols || !strings)
        return 0;
    const sym_t *s = (const sym_t *)(module + symbols);
    const char *str = (const char *)(module + strings);
    uintptr_t *slot = search(module, plt, plt_size, s, str, name);
    return slot ? slot : search(module, rela, rela_size, s, str, name);
}
