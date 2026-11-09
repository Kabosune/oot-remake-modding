// FPV drone for The Legend of Zelda: Ocarina of Time (Switch 2), main build E0F3CCFA.
//
// fpv_input() runs after each of the game's own GetNpadStates calls (npad_wrap in fpv.S). It takes
// player 1's / handheld's sticks and buttons, flies the drone one step, writes the drone camera's
// view matrix into DRONE_STATE, and, while the drone is on, blanks the controller the game sees so
// Link stands still. fpv_view_hook in fpv.S copies that matrix over the gameplay view each frame.
//
// The drone's attitude is three unit vectors in world space: right, up, back (the same convention
// as the rows of the game's view matrix; the drone faces -back).
//
// Tunables come from params.inc, written by build.py. All of this has to fit the shared code cave,
// so it is written for size: one constant table, one base register for the state, few helpers.

#include <stdint.h>
#include "params.inc"

typedef struct {
    uint32_t on;           // +0x00 drone flying
    uint32_t mode;         // +0x04 MODE_ANGLE / MODE_ACRO / MODE_SIMPLE
    uint32_t prev;         // +0x08 buttons at the last read (for presses)
    uint32_t pad0;         // +0x0c
    uint64_t tick;         // +0x10 system tick of the last step
    uint32_t seen;         // +0x18 reads since the gameplay view was last built (fpv.S zeroes it)
    uint32_t pad;          // +0x1c
    float    eye[3];       // +0x20 the game camera's eye, kept by fpv.S every frame
    float    gback[3];     // +0x2c the game camera's back axis, kept by fpv.S every frame
    float    mat[12];      // +0x38 the drone camera's view matrix, copied over the game's by fpv.S
    float    p[3];         // +0x68 position
    float    v[3];         // +0x74 velocity
    float    r[3][3];      // +0x80 right, up, back
} drone_t;                 // 0xa4 bytes

_Static_assert(__builtin_offsetof(drone_t, seen) == 0x18, "fpv.S");
_Static_assert(__builtin_offsetof(drone_t, eye) == 0x20, "fpv.S");
_Static_assert(__builtin_offsetof(drone_t, gback) == 0x2c, "fpv.S");
_Static_assert(__builtin_offsetof(drone_t, mat) == 0x38, "fpv.S");
_Static_assert(sizeof(drone_t) <= 0x100, "claimed 0x100 bytes");

// nn::hid NpadFullKeyState / NpadHandheldState / NpadJoyDualState / ...: all 0x28 bytes.
typedef struct {
    int64_t  sampling;
    uint64_t buttons;
    int32_t  stick[4];     // left x, left y, right x, right y
    uint32_t attributes;   // bit 0: connected
    uint32_t reserved;
} npad_t;

extern drone_t DRONE_STATE;

typedef struct {
    float deadzone, dz_scale, dt_max, tilt_cos, tilt_sin;
    float yaw_center, yaw_extra, rate_center, rate_extra, level_gain, max_tilt_sin;
    float gravity, climb_gain, climb_rate, brake, thrust_max, drag, min_up;
} params_t;

static const params_t PARAMS = {
    DEADZONE, 1.0f / (1.0f - DEADZONE), DT_MAX, UPTILT_COS, UPTILT_SIN,
    YAW_CENTER, YAW_MAX - YAW_CENTER, RATE_CENTER, RATE_MAX - RATE_CENTER, LEVEL_GAIN, TILT_SIN,
    GRAVITY, CLIMB_GAIN, CLIMB_RATE, SIMPLE_BRAKE, THRUST_MAX, DRAG, 0.3f,
};

enum { MODE_ANGLE = 0, MODE_ACRO = 1, MODE_SIMPLE = 2 };

#define BTN(bit) (1u << (bit))
#define BTN_PLUS 10
#define BTN_MINUS 11

// out = normalize(a x b)
static void cross_n(float *out, const float *a, const float *b)
{
    float x = a[1] * b[2] - a[2] * b[1];
    float y = a[2] * b[0] - a[0] * b[2];
    float z = a[0] * b[1] - a[1] * b[0];
    float k = 1.0f / __builtin_sqrtf(x * x + y * y + z * z);
    out[0] = x * k;
    out[1] = y * k;
    out[2] = z * k;
}

// Level the drone, keeping the heading of (bx, ?, bz).
static void level(float *r, float bx, float bz)
{
    float n = __builtin_sqrtf(bx * bx + bz * bz);
    if (n < 1e-3f) {
        bx = 0.0f;
        bz = n = 1.0f;
    }
    bx /= n;
    bz /= n;
    r[0] = bz;   r[1] = 0.0f; r[2] = -bx;    // right = up x back
    r[3] = 0.0f; r[4] = 1.0f; r[5] = 0.0f;   // up
    r[6] = bx;   r[7] = 0.0f; r[8] = bz;     // back
}

void fpv_input(npad_t *st, int n, const uint32_t *idp)
{
    drone_t *d = &DRONE_STATE;
    const params_t *k = &PARAMS;
    __asm__("" : "+r"(d), "+r"(k));             // keep both addresses in one register each

    uint32_t id = *idp;
    if (n <= 0 || (id != 0 && id != 0x20) || !(st->attributes & 1))
        goto blank;
    if (++d->seen > PAUSE_READS) {              // no gameplay view lately (menus, loading): stand by
        d->tick = 0;
        return;
    }

    uint64_t now, freq;
    __asm__ volatile("mrs %0, cntvct_el0" : "=r"(now));
    __asm__ volatile("mrs %0, cntfrq_el0" : "=r"(freq));
    float dt = 0.0f;
    if (d->tick && freq)
        dt = (float)(now - d->tick) / (float)freq;
    d->tick = now;
    if (dt > k->dt_max)                         // first step after standing by: a short one
        dt = k->dt_max;

    uint32_t b = (uint32_t)st->buttons;
    uint32_t press = b & ~d->prev;
    d->prev = b;

    if (press & BTN(TOGGLE_BIT)) {
        d->on ^= 1;
        press |= BTN(BTN_RESET);                // switching on starts at the game camera
    }
    if (press & (BTN(BTN_PLUS) | BTN(BTN_MINUS)))   // menus need the buttons: leave the drone
        d->on = 0;
    if (!d->on)
        return;

    float *right = d->r[0], *up = d->r[1], *back = d->r[2];
    if (press & BTN(BTN_RESET)) {
        for (int i = 0; i < 3; i++) {
            d->p[i] = d->eye[i];
            d->v[i] = 0.0f;
        }
        level(right, d->gback[0], d->gback[2]);
    }
    uint32_t mode = d->mode;
    if (press & BTN(BTN_ACRO))
        mode = MODE_ACRO;
    if (press & BTN(BTN_ANGLE))
        mode = MODE_ANGLE;
    if (press & BTN(BTN_SIMPLE))
        mode = MODE_SIMPLE;
    if (mode != d->mode && mode != MODE_ACRO)   // into a self-levelling mode: start level
        level(right, back[0], back[2]);
    d->mode = mode;

    // Mode 2: left stick throttle (y) / yaw (x), right stick pitch (y) / roll (x).
    float in[4];
    for (int i = 0; i < 4; i++) {
        float x = (float)st->stick[i] * (1.0f / 32767.0f);
        float a = __builtin_fabsf(x) - k->deadzone;
        a = a < 0.0f ? 0.0f : a * k->dz_scale;
        in[i] = __builtin_copysignf(a > 1.0f ? 1.0f : a, x);
    }
    float yaw = in[0], thr = in[1], roll = in[2], pitch = in[3];

    // Body rates (rad/s): wx about right (nose up), wy about up (turn left), wz about back (roll left).
    // Rate curve: center + extra * x^2, so fine near the middle and fast at full stick.
    float wx, wz;
    float wy = -yaw * (k->yaw_center + k->yaw_extra * yaw * yaw);
    if (mode == MODE_ACRO) {
        wx = -pitch * (k->rate_center + k->rate_extra * pitch * pitch);
        wz = -roll * (k->rate_center + k->rate_extra * roll * roll);
    } else {
        // Self-levelling: the stick sets the sine of the tilt; steer towards it.
        wx = k->level_gain * (back[1] - pitch * k->max_tilt_sin);
        wz = k->level_gain * (-roll * k->max_tilt_sin - right[1]);
    }

    float g = k->gravity, thrust, brake = 0.0f;
    if (mode == MODE_SIMPLE) {
        // Height hold: the throttle stick asks for a climb rate. Centered sticks stop the drone.
        float uy = up[1] > k->min_up ? up[1] : k->min_up;
        thrust = (g + k->climb_gain * (thr * k->climb_rate - d->v[1])) / uy;
        brake = k->brake;
    } else {
#if THROTTLE_HOVER_CENTER
        thrust = g + thr * (thr >= 0.0f ? k->thrust_max - g : g);   // centre = hover
#else
        thrust = (thr + 1.0f) * 0.5f * k->thrust_max;                // centre = half throttle
#endif
    }
    thrust = thrust < 0.0f ? 0.0f : thrust > k->thrust_max ? k->thrust_max : thrust;

    // Rotate the frame by the body rates, then make it orthonormal again.
    for (int i = 0; i < 3; i++) {
        float r0 = right[i], u0 = up[i], b0 = back[i];
        right[i] = r0 + dt * (wz * u0 - wy * b0);
        up[i]    = u0 + dt * (wx * b0 - wz * r0);
        back[i]  = b0 + dt * (wy * r0 - wx * u0);
    }
    cross_n(right, up, back);
    cross_n(back, right, up);
    cross_n(up, back, right);

    // Thrust along up, gravity, quadratic drag, and in Simple mode a linear brake sideways.
    float drag = k->drag * __builtin_sqrtf(d->v[0] * d->v[0] + d->v[1] * d->v[1] + d->v[2] * d->v[2]);
    for (int i = 0; i < 3; i++) {
        float a = up[i] * thrust - drag * d->v[i] - (i == 1 ? g : brake * d->v[i]);
        d->v[i] += a * dt;
        d->p[i] += d->v[i] * dt;
    }

    // View = the drone frame tilted up about its right axis (the camera's uptilt);
    // translation = -(row . eye).
    float cam[3][3], tc = k->tilt_cos, ts = k->tilt_sin;
    for (int i = 0; i < 3; i++) {
        cam[0][i] = right[i];
        cam[1][i] = up[i] * tc + back[i] * ts;
        cam[2][i] = back[i] * tc - up[i] * ts;
    }
    for (int row = 0; row < 3; row++) {
        float *o = d->mat + 4 * row, *a = cam[row];
        o[0] = a[0];
        o[1] = a[1];
        o[2] = a[2];
        o[3] = -(a[0] * d->p[0] + a[1] * d->p[1] + a[2] * d->p[2]);
    }

blank:
    // While flying, the game sees centered sticks and no buttons (except + and -), so Link waits.
    if (d->on) {
        for (int i = 0; i < n; i++) {
            st[i].buttons &= BTN(BTN_PLUS) | BTN(BTN_MINUS);
            st[i].stick[0] = st[i].stick[1] = st[i].stick[2] = st[i].stick[3] = 0;
        }
    }
}
