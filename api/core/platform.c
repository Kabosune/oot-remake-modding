// What Core asks of the system directly: debug output and memory queries (supervisor calls).
#include "core.h"

void kp_debug_out(const char *s, size_t n) {
#ifdef KAE_NO_DEBUG_OUT
    // Hardware test build: no svcOutputDebugString at all, in case the game isn't allowed it.
    (void)s;
    (void)n;
    return;
#endif
    register const char *x0 __asm__("x0") = s;
    register uint64_t x1 __asm__("x1") = n;
    __asm__ volatile("svc #0x27" : "+r"(x0), "+r"(x1) : : "x2", "x3", "x4", "x5", "x6", "x7", "memory");
}

typedef struct {
    uint64_t base, size;
    uint32_t state, attributes, permission, ipc, device, pad;
} region_t;

static int query(region_t *out, uintptr_t address) {
    register uintptr_t x0 __asm__("x0") = (uintptr_t)out;
    register uintptr_t x1 __asm__("x1");
    register uintptr_t x2 __asm__("x2") = address;
    __asm__ volatile("svc #0x6" : "+r"(x0), "=r"(x1), "+r"(x2) : : "x3", "x4", "x5", "x6", "x7", "memory");
    return (int)x0;
}

// The last region asked about is remembered: mods check many addresses in the same region.
static region_t cached;
static kp_lock_t lock;

bool kp_readable(uintptr_t address, size_t size) {
    if (address < 0x10000 || address + size < address)
        return false;
    kp_lock(&lock);
    if (!(cached.size && address >= cached.base && address + size <= cached.base + cached.size)) {
        if (query(&cached, address) != 0)
            cached.size = 0;
    }
    bool ok = cached.size && cached.state != 0 && (cached.permission & 1) &&
              address + size <= cached.base + cached.size;
    kp_unlock(&lock);
    return ok;
}
