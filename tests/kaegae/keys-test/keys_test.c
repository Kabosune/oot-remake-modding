// The test's mod. See mod.toml.
#include <kaegae.h>

static KaeItem settings[] = {
    { KAE_BINDING, "Jump", "Held from the controller or the keyboard.", 0, 0, 0, 0, 0, 0, KAE_ZR, KAE_ZR, 0, 0 },
};
static int presses;
static uint64_t saw;   // every button the mod was handed

static void frame(void *user) {
    (void)user;
    int held = kae_binding_held(&settings[0]);
    presses += kae_binding_pressed(&settings[0]);
    KAE_LOG("keys: held %d presses %d saw 0x%llx keyboard %d", held, presses, (unsigned long long)saw, kae_has("keyboard"));
    saw = 0;
}

static void input(KaeInput *seen, const KaeInput *real, void *user) {
    (void)seen;
    (void)user;
    saw |= real->buttons;
}

static int start(void) {
    if (kae_on_frame(frame, 0, 0) || kae_on_input(input, 0, 0))
        return -1;
    return kae_settings("Keys Test", settings, 1);
}

KAE_MOD("kaegae.keys-test", "1.0.0", start, 0);
