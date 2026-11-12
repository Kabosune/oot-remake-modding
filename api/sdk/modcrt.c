// Start of a mod built as its own module: hand the mod (KAE_MOD) to Core.
//
// rtld calls this once the module is loaded and linked. A mod's references to Core are weak
// (kaegae.h), so a mod installed without Core, or loaded by something that doesn't link it to
// Core, finds kae_register missing here and does nothing instead of crashing the game.
#include "kaegae.h"

__attribute__((visibility("hidden"))) extern KaeMod *__kae_mods_start[], *__kae_mods_end[];

static void debug_out(const char *s, size_t n) {
    register const char *x0 __asm__("x0") = s;
    register uint64_t x1 __asm__("x1") = n;
    __asm__ volatile("svc #0x27" : "+r"(x0), "+r"(x1) : : "x2", "x3", "x4", "x5", "x6", "x7", "memory");
}

void kae_module_init(void) {
    if (!kae_register) {
        static const char text[] = "kaegae mod: KaeGae Core isn't loaded (or this module wasn't linked to it); doing nothing";
        debug_out(text, sizeof text - 1);
        return;
    }
    for (KaeMod **m = __kae_mods_start; m < __kae_mods_end; m++)
        kae_register(*m);
}
