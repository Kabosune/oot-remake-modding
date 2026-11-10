// Input probe for the mouse-grab mod (Ocarina of Time, Switch 2, main build E0F3CCFA).
//
// Twice a second it reads the mouse through the game's own nn::hid::GetMouseStates import and
// writes one line to the debug log (svcOutputDebugString): "MGP" and 32 words in hex.
//
//   word 0      polls seen (calls of GetNpadStyleSet)
//   word 1      the game's own GetMouseStates calls
//   word 2      the game's GetSixAxisSensorStates calls that returned a state
//   word 3      states returned by the probe's GetMouseStates call
//   words 4-13  nn::hid::MouseState (0x28 bytes)
//   words 14-31 the newest nn::hid::SixAxisSensorState from +0x10 on: acceleration, angular
//               velocity, angle (3 floats each), then the direction matrix (9 floats)

#include <stdint.h>

typedef struct {
    uint64_t next;         // +0x00 system tick of the next line
    uint32_t polls;        // +0x08
    uint32_t game_mouse;   // +0x0c probe.S counts here
    uint32_t six;          // +0x10
    uint32_t got;          // +0x14
    uint32_t mouse[10];    // +0x18
    uint32_t motion[18];   // +0x40
} probe_t;                 // 0x88 bytes

_Static_assert(__builtin_offsetof(probe_t, game_mouse) == 0x0c, "probe.S");
_Static_assert(sizeof(probe_t) <= 0x100, "claimed 0x100 bytes");

extern probe_t PROBE_STATE;
int PLT_GETMOUSESTATES(void *states, int count);

#define WORDS 32
#define TICKS_PER_LINE 9600000   // system ticks are 19.2 MHz

void probe_tick(void) {
    probe_t *p = &PROBE_STATE;
    p->polls++;
    register uint64_t now __asm__("x0");
    __asm__ volatile("svc #0x1e" : "=r"(now) : : "memory");   // svcGetSystemTick
    if (now < p->next)
        return;
    p->next = now + TICKS_PER_LINE;
    p->got = (uint32_t)PLT_GETMOUSESTATES(p->mouse, 1);

    char line[3 + WORDS * 9];
    char *o = line;
    *o++ = 'M'; *o++ = 'G'; *o++ = 'P';
    const uint32_t *w = &p->polls;
    for (int i = 0; i < WORDS; i++) {
        uint32_t v = w[i];
        *o++ = ' ';
        for (int s = 28; s >= 0; s -= 4) {
            uint32_t d = (v >> s) & 15;
            *o++ = (char)(d + (d < 10 ? '0' : 'a' - 10));
        }
    }
    register const char *x0 __asm__("x0") = line;
    register uint64_t x1 __asm__("x1") = sizeof line;
    __asm__ volatile("svc #0x27" : "+r"(x0), "+r"(x1) : : "x2", "x3", "x4", "x5", "x6", "x7", "memory");   // svcOutputDebugString
}

void probe_six(const uint32_t *state, int count) {
    probe_t *p = &PROBE_STATE;
    if (count <= 0)
        return;
    p->six++;
    for (int i = 0; i < 18; i++)
        p->motion[i] = state[4 + i];
}
