// The keyboard: what mods' keys (the Mods menu's Keyboard column) are read from.
//
// nn::hid::GetKeyboardState fills a KeyboardState of 0x30 bytes: the sample number, the modifiers
// and attributes (4 bytes each), then the keys as 256 bits at +0x10, bit n = USB HID usage n. The
// sdk's GetKeyboardState aborts the game if the keyboard wasn't set up first (its detail function
// returns an error, 0xa2ca, and the public one stops on any error: read in the game's sdk module,
// 11 Nov 2026). An emulator answers either way; a console may not. So Core calls
// nn::hid::InitializeKeyboard once, on the game's thread, before its first read.
//
// Nothing is set up or read until something needs a key: a binding with a key, or the Mods menu's
// key capture. The About tab's Keyboard switch (saved as [kaegae.core] Keyboard) turns it all off.
#include "core.h"

typedef struct {
    int64_t sample;
    uint32_t modifiers, attributes;
    uint64_t keys[4];
} keyboard_state_t;
_Static_assert(sizeof(keyboard_state_t) == 0x30, "KeyboardState");

__attribute__((weak)) void _ZN2nn3hid18InitializeKeyboardEv(void);
__attribute__((weak)) void _ZN2nn3hid16GetKeyboardStateEPNS0_13KeyboardStateE(keyboard_state_t *out);

static bool switched_on = true;   // the About tab's switch
static bool ready;                // InitializeKeyboard has been called
static uint64_t last_tick, last_keys[4];

bool kp_keyboard_present(void) {
    return _ZN2nn3hid18InitializeKeyboardEv && _ZN2nn3hid16GetKeyboardStateEPNS0_13KeyboardStateE;
}

bool kp_keyboard_on(void) { return switched_on && kp_keyboard_present(); }

void kp_keyboard_switch(bool on) {
    if (on != switched_on)
        kp_logf("keyboard: %s", on ? "on" : "off (Core won't read it)");
    switched_on = on;
}

// The keys held now: all zero (and false) if the keyboard is off. Read at most once a millisecond:
// many reads a frame (one per controller read, for older mods' keys) share one.
bool kp_keyboard_read(uint64_t keys[4]) {
    for (int i = 0; i < 4; i++)
        keys[i] = 0;
    if (!kp_keyboard_on())
        return false;
    if (!ready) {
        ready = true;
        _ZN2nn3hid18InitializeKeyboardEv();
        kp_log("keyboard: set up (nn::hid::InitializeKeyboard), reading it for mods' keys");
        last_tick = 0;
    }
    uint64_t now = kp_tick();
    if (!last_tick || now - last_tick >= KP_TICKS_PER_MS || now < last_tick) {
        keyboard_state_t state = { 0 };
        _ZN2nn3hid16GetKeyboardStateEPNS0_13KeyboardStateE(&state);
        for (int i = 0; i < 4; i++)
            last_keys[i] = state.keys[i];
        last_tick = now ? now : 1;
    }
    for (int i = 0; i < 4; i++)
        keys[i] = last_keys[i];
    return true;
}
