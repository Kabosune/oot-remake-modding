// Keep the up / down angle when first person is switched on.
//
// R3 is also the game's camera recenter: the camera swings behind Link and levels out to the
// follow camera's default pitch. In first person the swing is welcome but the levelling isn't, so
// the view keeps its own pitch: it follows every change the game makes to its pitch, except the
// ones right after first person is switched on, which are the recenter. Those are ignored until
// the game's pitch stops moving or the right stick is used (at most HOLD_MAX views).
//
// Pitch is kept as (sin, cos) of the back axis's angle above the horizon, so no trig is needed:
// changes are applied as small rotations and the matrix is rebuilt from the game's yaw and ours.
//
// The view matrix is rows of 4 floats: right, up, back, each with its translation last.
// Called from first_person.S (fp_view_hook) for the gameplay view only.
#include <stdint.h>
#include "params.inc"

typedef struct {
    uint32_t enabled;           // +0x00 first person on (the rest up to +0x38 is first_person.S's)
    uint8_t asm_fields[0x34];
    uint32_t have_prev;         // +0x38 the fields below are set up
    uint32_t hold;              // +0x3c views left of ignoring the game's pitch changes
    float prev_s, prev_c;       // +0x40 game pitch last view
    float our_s, our_c;         // +0x48 pitch shown in first person
    uint32_t seed;              // +0x50 set by the R3 toggle: start from the pitch before the press
} fp_t;

extern fp_t FP_STATE;

// Every gameplay view, after the R3 toggle. sticks = right stick y of the three controller types.
void fp_pitch_track(const float *m, const int32_t *sticks) {
    fp_t *s = &FP_STATE;
    float gs = m[9], gc = __builtin_sqrtf(m[8] * m[8] + m[10] * m[10]);
    if (!s->have_prev) {
        s->have_prev = 1;
        s->prev_s = s->our_s = gs;
        s->prev_c = s->our_c = gc;
    }
    float ps = s->prev_s, pc = s->prev_c;
    s->prev_s = gs;
    s->prev_c = gc;
    if (s->seed) {
        // Switched on this view: the recenter may already have taken its first step, so start
        // from the pitch of the view before the press.
        s->seed = 0;
        s->our_s = ps;
        s->our_c = pc;
        s->hold = HOLD_MAX;
        return;
    }
    if (!s->enabled)
        return;
    float ds = gs * pc - gc * ps, dc = gc * pc + gs * ps;   // game's change since last view
    if (s->hold) {
        int moved = 0;
        for (int i = 0; i < 3; i++)
            if (sticks[i] > DEADZONE || sticks[i] < -DEADZONE)
                moved = 1;
        if (!moved) {
            uint32_t left = --s->hold;
            if (HOLD_MAX - left < HOLD_MIN || ds > STILL || ds < -STILL)
                return;   // the recenter is (or may still be) moving the pitch: ignore it
        }
        s->hold = 0;
    }
    float os = s->our_s, oc = s->our_c;
    float ns = os * dc + oc * ds, nc = oc * dc - os * ds;
    float k = 1.0f / __builtin_sqrtf(ns * ns + nc * nc);
    ns *= k;
    nc *= k;
    if (nc < COS_MIN) {   // stop short of straight up / down
        nc = COS_MIN;
        ns = ns < 0 ? -SIN_MAX : SIN_MAX;
    }
    s->our_s = ns;
    s->our_c = nc;
}

// Rebuild the rotation from the game's yaw and our pitch (no roll), before the eye is placed.
void fp_pitch_apply(float *m) {
    fp_t *s = &FP_STATE;
    float bx = m[8], bz = m[10];
    float n = __builtin_sqrtf(bx * bx + bz * bz);
    if (!s->have_prev || n < 0.001f)
        return;
    float hx = bx / n, hz = bz / n, ps = s->our_s, pc = s->our_c;
    m[0] = hz;
    m[1] = 0;
    m[2] = -hx;
    m[4] = -ps * hx;
    m[5] = pc;
    m[6] = -ps * hz;
    m[8] = pc * hx;
    m[9] = ps;
    m[10] = pc * hz;
}
