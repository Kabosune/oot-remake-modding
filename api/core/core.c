// Module start: find main, start the services, start the mod.
#include "core.h"

extern void nnMain(void);   // exported by main

static const kp_build_t builds[] = {
    { "1.1.1", 0x1202CD0, 0x3C4705C, 0x4EA0000 },   // main build E0F3CCFA
};

uintptr_t kp_main;
const kp_build_t *kp_build;

void kp_module_init(void) {
    uintptr_t nnmain = (uintptr_t)&nnMain;
    for (size_t i = 0; i < sizeof builds / sizeof *builds; i++) {
        uintptr_t base = nnmain - builds[i].nnmain;
        // nnMain's offset gives a page-aligned base only for the right build; then check MOD0
        if ((base & 0xFFF) == 0 && *(const uint32_t *)(base + 4) == builds[i].mod0 &&
            *(const uint32_t *)(base + builds[i].mod0) == 0x30444F4D) {
            kp_main = base;
            kp_build = &builds[i];
            break;
        }
    }
    if (!kp_main) {
        kp_log_hex("unknown game build, doing nothing. nnMain at", nnmain);
        return;
    }
    kp_log_hex("module loaded, main at", kp_main);
    if (!kp_draw_start())
        kp_log("drawing off: main's nvnBootstrapLoader import wasn't found");
    mod_init();
}
