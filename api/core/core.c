// Module start: find main, start the services, take in the mods linked into this module.
#include "core.h"

extern void nnMain(void);   // exported by main

uintptr_t kp_main;
const kp_build_t *kp_build;

void kp_module_init(void) {
#ifdef KAE_LOAD_ONLY
    return;   // hardware test build: the module is loaded and does nothing at all
#endif
    uintptr_t nnmain = (uintptr_t)&nnMain;
    for (unsigned i = 0; i < kp_build_count; i++) {
        uintptr_t base = nnmain - kp_builds[i].nnmain;
        // nnMain's offset gives a page-aligned base only for the right build; then check MOD0
        if ((base & 0xFFF) == 0 && *(const uint32_t *)(base + 4) == kp_builds[i].mod0 &&
            *(const uint32_t *)(base + kp_builds[i].mod0) == 0x30444F4D) {
            kp_main = base;
            kp_build = &kp_builds[i];
            break;
        }
    }
    for (KaeMod **m = __kae_mods_start; m < __kae_mods_end; m++)
        kae_register(*m);
    if (!kp_main) {
        kp_logf("Core %d.%d.%d: unknown game build, doing nothing. nnMain at %p", KAE_API_MAJOR, KAE_API_MINOR, KAE_CORE_PATCH,
                (void *)nnmain);
        kp_mods_ready();   // nothing will run: say so for each mod, now and as they register
        return;
    }
    kp_logf("Core %d.%d.%d loaded, game %s, main at %p", KAE_API_MAJOR, KAE_API_MINOR, KAE_CORE_PATCH, kp_build->version,
            (void *)kp_main);
    if (!kp_draw_start())
        kp_log("drawing off: main's nvnBootstrapLoader import wasn't found");
    if (!kp_input_start())
        kp_log("input off: main's GetNpadStates imports weren't found");
    if (!kp_motion_start())
        kp_log("motion off: main's GetSixAxisSensorStates import wasn't found");
    if (kp_hooks_start() && !kp_player_start())
        kp_log("player off: this build's symbol pack doesn't say where Link is");
    kp_menu_start();
}
