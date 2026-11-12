// Controllers: the frame and input events.
//
// The game polls its controllers once per frame: for each one it calls nn::hid::GetNpadStyleSet,
// then nn::hid::GetNpadStates for each style present (docs/address-map.md, f_834893d0). Core swaps
// main's GOT slots for those imports, found by name, so this needs nothing build-specific.
//
//   frame   the GetNpadStyleSet call for player 1, the first call of each poll
//   input   every GetNpadStates call that returns a state
#include "core.h"

// nn::hid::NpadFullKeyState and the other styles' states share this layout (docs/structures.md).
typedef struct {
    int64_t sample;
    uint64_t buttons;
    int32_t lx, ly, rx, ry;
    uint32_t attributes;
    uint32_t pad;
} npad_state_t;
_Static_assert(sizeof(npad_state_t) == 0x28, "NpadCommonState");

typedef int (*states_fn)(npad_state_t *, int, const uint32_t *);

enum { STYLES = 5 };
static states_fn real_states[STYLES];
void *kp_real_style_set;         // the real GetNpadStyleSet; input_wrap.S jumps to it
void kp_style_set_wrap(void);    // input_wrap.S
static bool frame_from_states;   // no GetNpadStyleSet import: count frames from player 1's states
static int frame_style = -1;

static int states(int style, npad_state_t *out, int count, const uint32_t *id) {
    if (frame_from_states && id && *id == 0) {
        if (frame_style < 0)
            frame_style = style;
        if (style == frame_style)
            kp_fire_frame();
    }
    int n = real_states[style](out, count, id);
    if (n <= 0 || !out || !id)
        return n;
    KaeInput real = { sizeof real, *id, out[0].buttons, out[0].lx, out[0].ly, out[0].rx, out[0].ry,
                      (uint32_t)style, out[0].attributes & 1 };
    KaeInput seen = real;
    kp_fire_input(&seen, &real);
    // The game keeps every state it is handed, not only the newest: change them all the same way.
    uint64_t released = real.buttons & ~seen.buttons, pressed = seen.buttons & ~real.buttons;
    bool left = seen.lx != real.lx || seen.ly != real.ly, right = seen.rx != real.rx || seen.ry != real.ry;
    if (released || pressed || left || right) {
        for (int i = 0; i < n && i < count; i++) {
            out[i].buttons = (out[i].buttons & ~released) | pressed;
            if (left) {
                out[i].lx = seen.lx;
                out[i].ly = seen.ly;
            }
            if (right) {
                out[i].rx = seen.rx;
                out[i].ry = seen.ry;
            }
        }
    }
    return n;
}

// Called by the wrapper on GetNpadStyleSet before the real function runs.
void kp_before_style_set(const uint32_t *id) {
    if (id && *id == 0)
        kp_fire_frame();
}

// One wrapper per style: each is a different function of the system's, with its own slot in main.
// Core's own imports of them are weak: a name the system doesn't export leaves that style unhooked
// instead of leaving Core with an import that can't be resolved.
#define STYLE(index, type)                                                                              \
    __attribute__((weak)) int _ZN2nn3hid13GetNpadStatesEPNS0_##type##EiRKj(npad_state_t *, int, const uint32_t *); \
    static int wrap_##index(npad_state_t *out, int count, const uint32_t *id) { return states(index, out, count, id); }
STYLE(0, 16NpadFullKeyState)
STYLE(1, 17NpadHandheldState)
STYLE(2, 16NpadJoyDualState)
STYLE(3, 16NpadJoyLeftState)
STYLE(4, 17NpadJoyRightState)
__attribute__((weak)) uint32_t _ZN2nn3hid15GetNpadStyleSetERKj(const uint32_t *);

#define NAME(type) "_ZN2nn3hid13GetNpadStatesEPNS0_" #type "EiRKj"

bool kp_input_start(void) {
    static const struct { const char *name; states_fn wrap, own; } styles[STYLES] = {
        { NAME(16NpadFullKeyState), wrap_0, _ZN2nn3hid13GetNpadStatesEPNS0_16NpadFullKeyStateEiRKj },
        { NAME(17NpadHandheldState), wrap_1, _ZN2nn3hid13GetNpadStatesEPNS0_17NpadHandheldStateEiRKj },
        { NAME(16NpadJoyDualState), wrap_2, _ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyDualStateEiRKj },
        { NAME(16NpadJoyLeftState), wrap_3, _ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyLeftStateEiRKj },
        { NAME(17NpadJoyRightState), wrap_4, _ZN2nn3hid13GetNpadStatesEPNS0_17NpadJoyRightStateEiRKj },
    };
    int found = 0;
    for (int i = 0; i < STYLES; i++) {
        real_states[i] = (states_fn)kp_wrap_import(styles[i].name, (void *)styles[i].wrap, (void *)styles[i].own);
        if (real_states[i])
            found++;
        else
            real_states[i] = styles[i].own;   // never called: main has no slot for it
    }
    // Set before the slot is swapped: the wrapper may run as soon as it is in place.
    kp_real_style_set = (void *)_ZN2nn3hid15GetNpadStyleSetERKj;
    void *real_style = kp_wrap_import("_ZN2nn3hid15GetNpadStyleSetERKj", (void *)kp_style_set_wrap, kp_real_style_set);
    if (real_style)
        kp_real_style_set = real_style;
    frame_from_states = !real_style;
    kp_event_on[KP_EV_INPUT] = found > 0;
    kp_event_on[KP_EV_FRAME] = real_style || found > 0;
    kp_logf("input: %d of %d controller styles hooked, frames from %s", found, STYLES,
            real_style ? "GetNpadStyleSet" : found ? "GetNpadStates" : "nothing");
    return found > 0;
}

uint64_t kp_input_live(void) {
    static uint64_t last_tick, last;
    uint64_t now = kp_tick();
    if (last_tick && now >= last_tick && now - last_tick < KP_TICKS_PER_MS)
        return last;
    static const uint32_t player1 = 0, handheld = 0x20;
    static const struct { states_fn fn; const uint32_t *id; } reads[] = {
        { _ZN2nn3hid13GetNpadStatesEPNS0_16NpadFullKeyStateEiRKj, &player1 },
        { _ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyDualStateEiRKj, &player1 },
        { _ZN2nn3hid13GetNpadStatesEPNS0_17NpadHandheldStateEiRKj, &handheld },
    };
    uint64_t buttons = 0;
    for (unsigned i = 0; i < sizeof reads / sizeof *reads; i++) {
        npad_state_t state = { 0 };
        if (reads[i].fn && reads[i].fn(&state, 1, reads[i].id) > 0 && (state.attributes & 1))
            buttons |= state.buttons;
    }
    last = buttons;
    last_tick = now ? now : 1;
    return buttons;
}
