// FPV drone for The Legend of Zelda: Ocarina of Time (Switch 2), main build E0F3CCFA.
//
// fpv_input() runs after each of the game's own GetNpadStates calls (npad_wrap in fpv.S). It takes
// player 1's / handheld's sticks and buttons, flies the drone one step, writes the drone camera's
// view matrix into DRONE_STATE, and, while the drone is on, blanks the controller the game sees so
// Link stands still. fpv_view_hook in fpv.S copies that matrix over the gameplay view each frame.
//
// fpv_actor() runs at the start of the game's movement update for physics actors (fpv_actor_hook
// in fpv.S, only while carrying). For Link, it moves his character controller to the drone
// with the game's own ChangePosition, the call behind the OneShotPhysicsCctChangePosition script
// command (Hookshot's flight cheat moves Link the same way).
//
// The drone's attitude is three unit vectors in world space: right, up, back (the same convention
// as the rows of the game's view matrix; the drone faces -back).
//
// Tunables come from params.inc, written by build.py. The code is built for size (one constant
// table, one base register for the state) and split over the padding between the game's functions.

#include <stdint.h>
#include "params.inc"

typedef struct {
    uint32_t on;           // +0x00 drone flying
    uint32_t mode;         // +0x04 MODE_FREE (0: the mode at boot) / ANGLE / ACRO / SIMPLE
    uint32_t prev;         // +0x08 buttons at the last read (for presses)
    uint32_t carrying;     // +0x0c on and carry: fpv_actor_hook reads this first
    uint64_t tick;         // +0x10 system tick of the last step
    uint32_t seen;         // +0x18 reads since the gameplay view was last built (fpv.S zeroes it)
    uint32_t carry;        // +0x1c carry Link (toggled with the carry button)
    float    eye[3];       // +0x20 the game camera's eye, kept by fpv.S every frame
    float    gback[3];     // +0x2c the game camera's back axis, kept by fpv.S every frame
    float    mat[12];      // +0x38 the drone camera's view matrix, copied over the game's by fpv.S
    float    p[3];         // +0x68 position
    float    v[3];         // +0x74 velocity
    float    r[3][3];      // +0x80 right, up, back
    float    carry_at[3];  // +0xa4 where carried Link's feet go: behind the camera, at its height
} drone_t;                 // 0xb0 bytes

_Static_assert(__builtin_offsetof(drone_t, carrying) == 0x0c, "fpv.S");
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
extern char VT_ACTOR[], VT_PLAYER[], VT_CCT[];
void CCT_CHANGE_POSITION(char *controller, const float *position);   // f_806d2530

typedef struct {
    float deadzone, dz_scale, dt_max, tick_s, tilt_cos, tilt_sin;
    float yaw_center, yaw_extra, rate_center, rate_extra, level_gain, max_tilt_sin;
    float gravity, climb_gain, climb_rate, brake, thrust_max, drag, min_up;
    float free_speed, free_turn, max_look, carry_drop, carry_back;
} params_t;

static const params_t PARAMS = {
    DEADZONE, 1.0f / (1.0f - DEADZONE), DT_MAX, 1.0f / 19200000.0f, UPTILT_COS, UPTILT_SIN,
    YAW_CENTER, YAW_MAX - YAW_CENTER, RATE_CENTER, RATE_MAX - RATE_CENTER, LEVEL_GAIN, TILT_SIN,
    GRAVITY, CLIMB_GAIN, CLIMB_RATE, SIMPLE_BRAKE, THRUST_MAX, DRAG, 0.3f,
    FREE_SPEED, FREE_TURN, 0.97f, CARRY_DROP, CARRY_BACK,
};

enum { MODE_FREE = 0, MODE_ANGLE = 1, MODE_ACRO = 2, MODE_SIMPLE = 3 };   // state is zero at boot

#define BTN(bit) (1u << (bit))
#define BTN_ZL 8
#define BTN_ZR 9
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

// Point the frame along back = (bx, by, bz) with no roll: right stays level.
static void aim(float *r, float bx, float by, float bz)
{
    static const float world_up[3] = { 0.0f, 1.0f, 0.0f };
    float n = __builtin_sqrtf(bx * bx + bz * bz);
    if (n < 1e-3f) {                            // straight up or down: pick any heading
        bx = 0.0f;
        bz = 1.0f;
    }
    float m = 1.0f / __builtin_sqrtf(bx * bx + by * by + bz * bz);
    r[6] = bx * m;
    r[7] = by * m;
    r[8] = bz * m;
    cross_n(r, world_up, r + 6);                // right = world up x back
    cross_n(r + 3, r + 6, r);                   // up = back x right
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

    // svcGetSystemTick (0x1e): 19.2 MHz ticks. Not mrs cntvct_el0 / cntfrq_el0: Lichii's CPU
    // emulator (dynarmic) doesn't implement those and stops the game.
    register uint64_t now __asm__("x0");
    __asm__ volatile("svc #0x1e" : "=r"(now) : : "memory");
    float dt = 0.0f;
    if (d->tick)
        dt = (float)(now - d->tick) * k->tick_s;
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
    if (press & BTN(BTN_CARRY))
        d->carry ^= 1;
    if (!d->on)
        d->carry = 0;                           // leaving the drone lets go of Link
    d->carrying = d->carry;
    if (!d->on)
        return;

    float *right = d->r[0], *up = d->r[1], *back = d->r[2];
    if (press & BTN(BTN_RESET)) {
        for (int i = 0; i < 3; i++) {
            d->p[i] = d->eye[i];
            d->v[i] = 0.0f;
        }
        aim(right, d->gback[0], 0.0f, d->gback[2]);
    }
    uint32_t mode = d->mode;
    if (press & BTN(BTN_ACRO))
        mode = MODE_ACRO;
    if (press & BTN(BTN_ANGLE))
        mode = MODE_ANGLE;
    if (press & BTN(BTN_SIMPLE))
        mode = MODE_SIMPLE;
    if (press & BTN(BTN_FREE))
        mode = MODE_FREE;
    if (mode != d->mode && mode != MODE_ACRO)   // into a levelled mode: start level
        aim(right, back[0], 0.0f, back[2]);
    d->mode = mode;

    float in[4];
    for (int i = 0; i < 4; i++) {
        float x = (float)st->stick[i] * (1.0f / 32767.0f);
        float a = __builtin_fabsf(x) - k->deadzone;
        a = a < 0.0f ? 0.0f : a * k->dz_scale;
        in[i] = __builtin_copysignf(a > 1.0f ? 1.0f : a, x);
    }
    float tc = k->tilt_cos, ts = k->tilt_sin;

    if (mode == MODE_FREE) {
        // Noclip camera: right stick looks (yaw about world up, pitch), left stick moves where
        // you look, ZL / ZR down / up. No physics, no roll, no camera uptilt.
        float turn = k->free_turn * dt, yaw = -in[2] * turn, look = in[3] * turn;
        float bx = back[0] + yaw * back[2] - look * up[0];
        float by = back[1] - look * up[1];
        float bz = back[2] - yaw * back[0] - look * up[2];
        float m = 1.0f / __builtin_sqrtf(bx * bx + by * by + bz * bz);
        bx *= m;
        by *= m;
        bz *= m;
        if (__builtin_fabsf(by) > k->max_look) {    // stop short of straight up / down
            float h = __builtin_sqrtf((1.0f - k->max_look * k->max_look) / (bx * bx + bz * bz));
            bx *= h;
            bz *= h;
            by = __builtin_copysignf(k->max_look, by);
        }
        aim(right, bx, by, bz);
        float vert = (float)((b >> BTN_ZR) & 1) - (float)((b >> BTN_ZL) & 1);
        for (int i = 0; i < 3; i++) {
            d->v[i] = (right[i] * in[0] - back[i] * in[1] + (i == 1 ? vert : 0.0f)) * k->free_speed;
            d->p[i] += d->v[i] * dt;
        }
        tc = 1.0f;
        ts = 0.0f;
    } else {
        // Mode 2: left stick throttle (y) / yaw (x), right stick pitch (y) / roll (x).
        float yaw = in[0], thr = in[1], roll = in[2], pitch = in[3];

        // Body rates (rad/s): wx about right (nose up), wy about up (turn left), wz about back
        // (roll left). Rate curve: center + extra * x^2, fine near the middle, fast at full stick.
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
            // Height hold: the throttle stick asks for a climb rate. Centred sticks stop the drone.
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
    }

    // View = the drone frame tilted up about its right axis (the camera's uptilt);
    // translation = -(row . eye).
    float cam[3][3];
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

    // Carried Link: feet CARRY_DROP below the camera, CARRY_BACK behind it (along the level part of
    // its back axis), so he's out of view and turns with it.
    float h = __builtin_sqrtf(back[0] * back[0] + back[2] * back[2]);
    h = h > 1e-3f ? k->carry_back / h : 0.0f;
    d->carry_at[0] = d->p[0] + back[0] * h;
    d->carry_at[1] = d->p[1] - k->carry_drop;
    d->carry_at[2] = d->p[2] + back[2] * h;

blank:
    // While flying, the game sees centred sticks and no buttons (except + and -), so Link waits.
    if (d->on) {
        for (int i = 0; i < n; i++) {
            st[i].buttons &= BTN(BTN_PLUS) | BTN(BTN_MINUS);
            st[i].stick[0] = st[i].stick[1] = st[i].stick[2] = st[i].stick[3] = 0;
        }
    }
}

// The movement update of a physics actor is starting. If it's Link and we carry him, move his
// character controller to carry_at (ChangePosition takes the actor position: his feet).
void fpv_actor(char *actor)
{
    drone_t *d = &DRONE_STATE;
    if (!d->carrying || *(char **)actor != VT_ACTOR)
        return;
    char *components = *(char **)(actor + 0x270);
    if (!components)
        return;
    char *movement = *(char **)(components + 0x320);
    if (!movement || *(char **)(movement + 0x18) != actor)
        return;
    char *player = movement - 0x1d50;           // Link's player object holds the movement component
    if (*(char **)player != VT_PLAYER)
        return;
    char *res = *(char **)(player + 0x10);      // resource name must be "Player"
    if (!res || *(uint32_t *)(res + 0x58) != 0x79616c50 || *(uint16_t *)(res + 0x5c) != 0x7265 ||
        res[0x5e])
        return;
    // components -> character controller, the chain OneShotPhysicsCctChangePosition follows.
    char *controller = components;
    static const uint8_t chain[4] = { 80, 32, 16, 8 };
    for (int i = 0; i < 4; i++) {
        controller = *(char **)(controller + chain[i]);
        if (!controller)
            return;
    }
    if (*(char **)controller != VT_CCT)
        return;
    float to[4] = { d->carry_at[0], d->carry_at[1], d->carry_at[2], 0.0f };
    CCT_CHANGE_POSITION(controller, to);
}
