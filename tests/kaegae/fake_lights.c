// A stand-in for the game's LocationalLight manager, for Flashlight & Lantern's module test. Linked
// at fixed addresses (tests/test_kaegae_modules.py): light_register / light_lookup inside main where
// the real ones sit, the rest in its own region. Same layout as the game's as far as the mod uses it:
// pools at mgr + 0x58 (vtable slot 2 takes a light, slot 3 gives it back), lights with vtable slot 9
// setting the position, the named-light map at mgr + 0xD0E0 (16-byte entries {u32 hash, ptr}, count
// at + 8, capacity at + 0xC, open addressing from hash % capacity).
#include <stdint.h>

#define KINDS 5
#define PER_KIND 4
#define LIGHT_SIZE 0x200

typedef struct { uint32_t hash, pad; void *light; } Entry;

__attribute__((section(".fake_reg"))) int light_register(uint8_t *mgr, void *light, uint32_t hash) {
    if (!hash)
        return 0;
    uint32_t cap = *(uint32_t *)(mgr + 0xD0EC);
    Entry *t = *(Entry **)(mgr + 0xD0E0);
    uint32_t start = hash % cap, i = start;
    do {
        if (!t[i].hash) {
            t[i].hash = hash;
            t[i].light = light;
            (*(uint32_t *)(mgr + 0xD0E8))++;
            return 1;
        }
        if (t[i].hash == hash)
            return 0;
        i = i + 1 >= cap ? 0 : i + 1;
    } while (i != start);
    return 0;
}

__attribute__((section(".fake_lookup"))) void *light_lookup(uint8_t *mgr, uint32_t hash) {
    uint32_t cap = *(uint32_t *)(mgr + 0xD0EC);
    if (!hash || !cap)
        return 0;
    Entry *t = *(Entry **)(mgr + 0xD0E0);
    uint32_t start = hash % cap, i = start;
    do {
        if (t[i].hash == hash)
            return t[i].light;
        if (!t[i].hash)
            return 0;
        i = i + 1 >= cap ? 0 : i + 1;
    } while (i != start);
    return 0;
}

// The game's Navi pool keeps its own lights' count at + 0x28 and a pointer to them at + 0x30
// (0x170 bytes each); the fake keeps them there for every pool and fills them in for pool 3.
typedef struct Pool { void **vt; int kind; int used[PER_KIND]; uint8_t pad[0x28 - 0x1C]; int32_t count, pad2; void *lights; } Pool;

uint8_t fake_navi_lights[2][0x170] __attribute__((aligned(16)));

uint8_t fake_light_mem[KINDS][PER_KIND][LIGHT_SIZE] __attribute__((aligned(16)));
int fake_light_setpos_calls;
int fake_light_frees;

static void light_setpos(uint8_t *l, float x, float y, float z) {
    float *p = (float *)(l + 0x40);      // where the fake keeps it (the mod never reads it back)
    p[0] = x; p[1] = y; p[2] = z;
    fake_light_setpos_calls++;
}

static void *light_vt[12] = { 0, 0, 0, 0, 0, 0, 0, 0, 0, (void *)light_setpos, 0, 0 };

static void *pool_alloc(Pool *pool) {
    for (int i = 0; i < PER_KIND; i++)
        if (!pool->used[i]) {
            pool->used[i] = 1;
            // Navi's pool hands out its own lights (the game's are inside its array)
            uint8_t *l = pool->kind == 3 && i < 2 ? fake_navi_lights[i] : fake_light_mem[pool->kind][i];
            for (int k = 0; k < (pool->kind == 3 && i < 2 ? 0x170 : LIGHT_SIZE); k++)
                l[k] = 0;
            *(void ***)l = light_vt;
            return l;
        }
    return 0;
}

static void pool_free(Pool *pool, uint8_t *l) {
    for (int i = 0; i < PER_KIND; i++)
        if (fake_light_mem[pool->kind][i] == l || (pool->kind == 3 && i < 2 && fake_navi_lights[i] == l))
            pool->used[i] = 0;
    fake_light_frees++;
}

static void *pool_vt[4] = { 0, 0, (void *)pool_alloc, (void *)pool_free };

Pool fake_light_pools[KINDS] = {
    { pool_vt, 0, { 0 }, { 0 }, 0, 0, 0 }, { pool_vt, 1, { 0 }, { 0 }, 0, 0, 0 }, { pool_vt, 2, { 0 }, { 0 }, 0, 0, 0 },
    { pool_vt, 3, { 1 }, { 0 }, 2, 0, fake_navi_lights }   /* light 0 is Navi's own */, { pool_vt, 4, { 0 }, { 0 }, 0, 0, 0 },
};

uint8_t fake_light_top[0x200] __attribute__((aligned(16)));
uint8_t fake_light_holder[0xC00] __attribute__((aligned(16)));
uint8_t fake_light_mgr[0xD100] __attribute__((aligned(16)));
Entry fake_light_map[64];
