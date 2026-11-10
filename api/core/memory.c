// Checking that memory can be read before reading it (svcQueryMemory).
#include "core.h"

typedef struct {
    uint64_t base, size;
    uint32_t state, attributes, permission, ipc, device, pad;
} region_t;

static region_t cached;

static int query(region_t *out, uintptr_t address) {
    register uintptr_t x0 __asm__("x0") = (uintptr_t)out;
    register uintptr_t x1 __asm__("x1");
    register uintptr_t x2 __asm__("x2") = address;
    __asm__ volatile("svc #0x6" : "+r"(x0), "=r"(x1), "+r"(x2) : : "x3", "x4", "x5", "x6", "x7", "memory");
    return (int)x0;
}

bool kp_readable(uintptr_t address, size_t size) {
    if (address < 0x10000 || address + size < address)
        return false;
    if (!(cached.size && address >= cached.base && address + size <= cached.base + cached.size)) {
        if (query(&cached, address) != 0) {
            cached.size = 0;
            return false;
        }
    }
    return cached.state != 0 && (cached.permission & 1) && address + size <= cached.base + cached.size;
}
