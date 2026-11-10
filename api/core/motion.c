// The controller's motion sensor, as the game reads it.
//
// Core swaps main's GOT slot for nn::hid::GetSixAxisSensorStates and keeps the newest state of the
// first sensor that reports a non-zero acceleration (the game reads one per controller style; with
// one controller only one of them moves).
#include "core.h"

typedef struct {
    int64_t delta_time;
    int64_t sample;
    float acceleration[3];
    float angular_velocity[3];
    float angle[3];
    float direction[9];
    uint32_t attributes;
    uint32_t pad;
} six_axis_state_t;
_Static_assert(sizeof(six_axis_state_t) == 0x60, "nn::hid::SixAxisSensorState");

int _ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE(six_axis_state_t *,
                                                                                               int, const uint32_t *);
#define REAL _ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE
#define NAME "_ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE"

static int (*real)(six_axis_state_t *, int, const uint32_t *);
static float direction[9];
static uint64_t updates;
static uint32_t chosen;
static bool have_chosen;

static int wrap(six_axis_state_t *states, int count, const uint32_t *handle) {
    int n = real(states, count, handle);
    if (n > 0 && handle) {
        const float *a = states[0].acceleration;
        bool moving = a[0] != 0 || a[1] != 0 || a[2] != 0;
        if (!have_chosen && moving) {
            have_chosen = true;
            chosen = *handle;
            kp_log_hex("motion: using sensor", chosen);
        }
        if (have_chosen && *handle == chosen) {
            for (int i = 0; i < 9; i++)
                direction[i] = states[0].direction[i];
            updates++;
        }
    }
    return n;
}

uint64_t kae_motion_direction(float out[9]) {
    for (int i = 0; i < 9; i++)
        out[i] = direction[i];
    return updates;
}

bool kp_motion_on;

bool kp_motion_start(void) {
    void *r = kp_wrap_import(NAME, (void *)wrap, (void *)REAL);
    if (!r)
        return false;
    real = (int (*)(six_axis_state_t *, int, const uint32_t *))r;
    kp_motion_on = true;
    return true;
}
