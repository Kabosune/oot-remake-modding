// Core's memory pool: a first-fit list of blocks in one fixed array, so mods never touch the
// game's heaps. Every block starts with a 16-byte header; blocks are 16-byte aligned.
#include "core.h"

#ifndef KP_POOL_BYTES
#define KP_POOL_BYTES (1u << 20)
#endif

typedef struct {
    uint64_t size;   // of the whole block, header included
    uint64_t used;
} block_t;

static _Alignas(16) uint8_t pool[KP_POOL_BYTES];
static bool ready;
static kp_lock_t lock;

#define FIRST ((block_t *)pool)
#define END   ((block_t *)(pool + KP_POOL_BYTES))
#define NEXT(b) ((block_t *)((uint8_t *)(b) + (b)->size))

void *kae_alloc(size_t size) {
    if (!size || size > KP_POOL_BYTES)
        return 0;
    uint64_t need = ((uint64_t)size + 15) / 16 * 16 + sizeof(block_t);
    void *result = 0;
    kp_lock(&lock);
    if (!ready) {
        FIRST->size = KP_POOL_BYTES;
        FIRST->used = 0;
        ready = true;
    }
    for (block_t *b = FIRST; b < END; b = NEXT(b)) {
        if (b->used)
            continue;
        while (NEXT(b) < END && !NEXT(b)->used)   // join the free blocks that follow
            b->size += NEXT(b)->size;
        if (b->size < need)
            continue;
        if (b->size - need >= sizeof(block_t) + 16) {   // split off what's left
            block_t *rest = (block_t *)((uint8_t *)b + need);
            rest->size = b->size - need;
            rest->used = 0;
            b->size = need;
        }
        b->used = 1;
        result = b + 1;
        break;
    }
    kp_unlock(&lock);
    return result;
}

void kae_free(void *p) {
    if (!p)
        return;
    block_t *b = (block_t *)p - 1;
    if ((uint8_t *)b < pool || (uint8_t *)b >= pool + KP_POOL_BYTES || ((uintptr_t)b & 15))
        return;   // not from this pool
    kp_lock(&lock);
    b->used = 0;
    kp_unlock(&lock);
}
