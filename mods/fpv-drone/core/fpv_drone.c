// FPV Drone 2 on KaeGae Core: a free camera or an FPV quadcopter, and Link carried along if you like.
//
// The flying is FPV Drone 1.x's (../fpv.c), unchanged in how it flies; Core does the patching and
// every number and button is a setting in the Mods menu:
//   input        the first read of player 1 / the handheld each frame flies one step; while the
//                drone is up the game sees centred sticks and no buttons (but + and -)
//   view         the gameplay view is replaced by the drone's camera (priority 10: after First
//                Person, so the drone wins when both are on). Also the FOV.
//   frame        counts frames since the last gameplay view (menus, loading: the drone stands by)
//   player_move  a carried Link is put under the drone with the game's own controller move
//
// The drone's attitude is three unit vectors in world space: right, up, back (the rows of the game's
// view matrix; the drone faces -back).
#include <kaegae.h>

#include "kmath.h"

static const char *const FOVS[] = { "The game's", "70°", "80°", "90°", "100°", "110°", "120°", "130°", "140°" };
static const int FOV_DEGREES[] = { 0, 70, 80, 90, 100, 110, 120, 130, 140 };
static const char *const THROTTLES[] = { "Centre = hover", "Centre = half thrust" };

#define BIND(label, help, buttons) { KAE_BINDING, label, help, 0, 0, 0, 0, 0, 0, buttons, buttons, 0, 0 }
#define NUM(label, help, def, lo, hi, step) { KAE_NUMBER, label, help, def, def, lo, hi, step, 0, 0, 0, 0, 0 }

enum {
    TOGGLE, RESET, FREE, ANGLE, ACRO, SIMPLE, CARRY, UP, DOWN,
    FOV, FREE_SPEED, FREE_TURN, UPTILT, ACRO_UPTILT, ACRO_RATE, YAW_RATE, MAX_TILT, THRUST, TOP_SPEED,
    CLIMB, THROTTLE, DEADZONE, CARRY_BACK, CARRY_DROP, COUNT
};
static KaeItem settings[] = {
    [TOGGLE]      = BIND("Drone on / off", "Takes off from where the game camera is.", KAE_L3),
    [RESET]       = BIND("Back to the game camera", 0, KAE_A),
    [FREE]        = BIND("Free fly mode", "A noclip camera: left stick moves where you look, right stick looks.", KAE_L),
    [ANGLE]       = BIND("Angle mode", "Self-levelling: the right stick sets the tilt.", KAE_Y),
    [ACRO]        = BIND("Acro mode", "The right stick sets how fast it rotates. Flips, rolls.", KAE_X),
    [SIMPLE]      = BIND("Simple mode", "Self-levelling and holds its height; stops when you let go.", KAE_B),
    [CARRY]       = BIND("Carry / drop Link", "He flies along behind the camera. Drop him low.", KAE_R),
    [UP]          = BIND("Free fly: up", 0, KAE_ZR),
    [DOWN]        = BIND("Free fly: down", 0, KAE_ZL),
    [FOV]         = { KAE_CHOICE, "Field of view", "Horizontal, while flying. The game's own is about 80°.", 0, 0, 0, 8, 0, FOVS, 0, 0, 0, 0 },
    [FREE_SPEED]  = NUM("Free fly speed (m/s)", "At full stick.", 8, 1, 60, 1),
    [FREE_TURN]   = NUM("Free fly look speed (°/s)", "At full stick.", 120, 30, 360, 10),
    [UPTILT]      = NUM("Camera tilt, Angle / Simple (°)", "How far the camera points up from the drone's body.", 20, 0, 60, 5),
    [ACRO_UPTILT] = NUM("Camera tilt, Acro (°)", "Racers fly 40 to 55.", 30, 0, 70, 5),
    [ACRO_RATE]   = NUM("Acro rate (°/s)", "Pitch and roll at full stick (200 near the middle).", 670, 200, 1500, 10),
    [YAW_RATE]    = NUM("Yaw rate (°/s)", "At full stick (120 near the middle).", 300, 120, 1000, 10),
    [MAX_TILT]    = NUM("Angle / Simple: max tilt (°)", "Tilt at full stick.", 50, 10, 80, 5),
    [THRUST]      = NUM("Thrust (% of gravity)", "Full throttle. 100 only just hovers.", 350, 120, 1000, 10),
    [TOP_SPEED]   = NUM("Top speed (m/s)", "Sets the air drag: about the fastest it flies level.", 29, 5, 100, 1),
    [CLIMB]       = NUM("Simple: climb speed (m/s)", "At full throttle stick.", 4, 1, 20, 1),
    [THROTTLE]    = { KAE_CHOICE, "Throttle stick", "Half thrust at the centre is closer to a real radio.", 0, 0, 0, 1, 0, THROTTLES, 0, 0, 0, 0 },
    [DEADZONE]    = NUM("Stick dead zone (%)", 0, 6, 0, 30, 1),
    [CARRY_BACK]  = NUM("Carried Link: behind (cm)", "Behind the camera, out of view.", 100, 0, 500, 10),
    [CARRY_DROP]  = NUM("Carried Link: below (cm)", "His feet below the camera.", 0, -200, 500, 10),
};

#define GRAVITY 9.81f
#define DT_MAX 0.05f
#define LEVEL_GAIN 8.0f
#define CLIMB_GAIN 3.0f
#define BRAKE 1.5f
#define MIN_UP 0.3f
#define MAX_LOOK 0.97f
#define RATE_CENTER 200.0f
#define YAW_CENTER 120.0f
#define STANDBY_FRAMES 4    // frames without a gameplay view (menus, loading): stand by
#define TICK_S (1.0f / 19200000.0f)

enum { MODE_FREE, MODE_ANGLE, MODE_ACRO, MODE_SIMPLE };   // Free fly is the mode at boot

static struct {
    int on, mode, carry, stepped;
    volatile int since_view;   // frames since the last gameplay view
    uint64_t tick;
    int have_game;             // eye / gback hold the game camera
    float eye[3], gback[3];    // the view as it was before the drone (for taking off)
    float mat[12];             // the drone camera
    float p[3], v[3], r[9];    // position, velocity, right / up / back
    float carry_at[3];
} d;

static int pressed(int item) { return kae_binding_pressed(&settings[item]); }
static int held(int item) { return kae_binding_held(&settings[item]); }

static void cross_n(float *out, const float *a, const float *b) {
    float x = a[1] * b[2] - a[2] * b[1], y = a[2] * b[0] - a[0] * b[2], z = a[0] * b[1] - a[1] * b[0];
    float k = 1.0f / ksqrt(x * x + y * y + z * z);
    out[0] = x * k, out[1] = y * k, out[2] = z * k;
}

// Point the frame along back = (bx, by, bz) with no roll: right stays level.
static void aim(float *r, float bx, float by, float bz) {
    static const float world_up[3] = { 0, 1, 0 };
    if (ksqrt(bx * bx + bz * bz) < 1e-3f)
        bx = 0, bz = 1;
    float m = 1.0f / ksqrt(bx * bx + by * by + bz * bz);
    r[6] = bx * m, r[7] = by * m, r[8] = bz * m;
    cross_n(r, world_up, r + 6);
    cross_n(r + 3, r + 6, r);
}

static float stick(int32_t raw) {
    float x = (float)raw * (1.0f / 32767.0f), dz = (float)settings[DEADZONE].value / 100.0f;
    float a = __builtin_fabsf(x) - dz;
    a = a < 0 ? 0 : a / (1.0f - dz);
    return __builtin_copysignf(a > 1 ? 1 : a, x);
}

static void step(const KaeInput *in) {
    uint64_t now = 0;
#if defined(__aarch64__)
    register uint64_t x0 __asm__("x0");
    __asm__ volatile("svc #0x1e" : "=r"(x0) : : "x1", "x2", "x3", "x4", "x5", "x6", "x7", "memory");
    now = x0;   // svcGetSystemTick: 19.2 MHz
#endif
    float dt = d.tick ? (float)(now - d.tick) * TICK_S : 0;
    d.tick = now;
    if (dt > DT_MAX)
        dt = DT_MAX;

    int reset = 0;
    if (pressed(TOGGLE)) {
        d.on = !d.on;
        reset = 1;
        KAE_LOG("fpv drone %s", d.on ? "on" : "off");
    }
    if ((in->buttons & (KAE_PLUS | KAE_MINUS)) && d.on) {   // menus need the buttons: leave the drone
        d.on = 0;
        KAE_LOG("fpv drone off (+ or -)");
    }
    if (pressed(CARRY) && d.on)
        d.carry = !d.carry;
    if (!d.on) {
        d.carry = 0;
        return;
    }
    float *right = d.r, *up = d.r + 3, *back = d.r + 6;
    if (pressed(RESET))
        reset = 1;
    if (reset) {
        for (int i = 0; i < 3; i++)
            d.p[i] = d.eye[i], d.v[i] = 0;
        aim(d.r, d.gback[0], 0, d.gback[2]);
    }
    int mode = d.mode;
    if (pressed(ACRO))
        mode = MODE_ACRO;
    if (pressed(ANGLE))
        mode = MODE_ANGLE;
    if (pressed(SIMPLE))
        mode = MODE_SIMPLE;
    if (pressed(FREE))
        mode = MODE_FREE;
    if (mode != d.mode && mode != MODE_ACRO)   // into a levelled mode: start level
        aim(d.r, back[0], 0, back[2]);
    d.mode = mode;

    float lx = stick(in->lx), ly = stick(in->ly), rx = stick(in->rx), ry = stick(in->ry);
    float tilt = krad((float)settings[mode == MODE_ACRO ? ACRO_UPTILT : UPTILT].value);
    float tc = kcos(tilt), ts = ksin(tilt);

    if (mode == MODE_FREE) {
        float turn = krad((float)settings[FREE_TURN].value) * dt, yaw = -rx * turn, look = ry * turn;
        float bx = back[0] + yaw * back[2] - look * up[0];
        float by = back[1] - look * up[1];
        float bz = back[2] - yaw * back[0] - look * up[2];
        float m = 1.0f / ksqrt(bx * bx + by * by + bz * bz);
        bx *= m, by *= m, bz *= m;
        if (__builtin_fabsf(by) > MAX_LOOK) {   // stop short of straight up / down
            float h = ksqrt((1.0f - MAX_LOOK * MAX_LOOK) / (bx * bx + bz * bz));
            bx *= h, bz *= h;
            by = __builtin_copysignf(MAX_LOOK, by);
        }
        aim(d.r, bx, by, bz);
        float vert = (float)held(UP) - (float)held(DOWN), speed = (float)settings[FREE_SPEED].value;
        for (int i = 0; i < 3; i++) {
            d.v[i] = (right[i] * lx - back[i] * ly + (i == 1 ? vert : 0)) * speed;
            d.p[i] += d.v[i] * dt;
        }
        tc = 1, ts = 0;
    } else {
        // Mode 2: left stick throttle (y) / yaw (x), right stick pitch (y) / roll (x).
        float yaw = lx, thr = ly, roll = rx, pitch = ry;
        float rate_extra = krad((float)settings[ACRO_RATE].value - RATE_CENTER);
        float yaw_extra = krad((float)settings[YAW_RATE].value - YAW_CENTER);
        float wx, wz, wy = -yaw * (krad(YAW_CENTER) + yaw_extra * yaw * yaw);
        if (mode == MODE_ACRO) {
            wx = -pitch * (krad(RATE_CENTER) + rate_extra * pitch * pitch);
            wz = -roll * (krad(RATE_CENTER) + rate_extra * roll * roll);
        } else {
            float max_tilt = ksin(krad((float)settings[MAX_TILT].value));
            wx = LEVEL_GAIN * (back[1] - pitch * max_tilt);
            wz = LEVEL_GAIN * (-roll * max_tilt - right[1]);
        }
        float g = GRAVITY, thrust_max = (float)settings[THRUST].value / 100.0f * g, thrust, brake = 0;
        if (mode == MODE_SIMPLE) {
            float uy = up[1] > MIN_UP ? up[1] : MIN_UP;
            thrust = (g + CLIMB_GAIN * (thr * (float)settings[CLIMB].value - d.v[1])) / uy;
            brake = BRAKE;
        } else if (settings[THROTTLE].value == 0) {
            thrust = g + thr * (thr >= 0 ? thrust_max - g : g);   // centre = hover
        } else {
            thrust = (thr + 1) * 0.5f * thrust_max;               // centre = half throttle
        }
        thrust = kclamp(thrust, 0, thrust_max);
        for (int i = 0; i < 3; i++) {
            float r0 = right[i], u0 = up[i], b0 = back[i];
            right[i] = r0 + dt * (wz * u0 - wy * b0);
            up[i] = u0 + dt * (wx * b0 - wz * r0);
            back[i] = b0 + dt * (wy * r0 - wx * u0);
        }
        cross_n(right, up, back);
        cross_n(back, right, up);
        cross_n(up, back, right);
        // Quadratic drag set from the top speed: thrust_max = drag * top^2.
        float top = (float)settings[TOP_SPEED].value;
        float drag = thrust_max / (top * top) * ksqrt(d.v[0] * d.v[0] + d.v[1] * d.v[1] + d.v[2] * d.v[2]);
        for (int i = 0; i < 3; i++) {
            float a = up[i] * thrust - drag * d.v[i] - (i == 1 ? g : brake * d.v[i]);
            d.v[i] += a * dt;
            d.p[i] += d.v[i] * dt;
        }
    }

    // The camera: the drone frame tilted up about its right axis; translation = -(row . eye).
    float cam[9];
    for (int i = 0; i < 3; i++) {
        cam[i] = right[i];
        cam[3 + i] = up[i] * tc + back[i] * ts;
        cam[6 + i] = back[i] * tc - up[i] * ts;
    }
    for (int row = 0; row < 3; row++) {
        float *o = d.mat + 4 * row, *a = cam + 3 * row;
        o[0] = a[0], o[1] = a[1], o[2] = a[2];
        o[3] = -(a[0] * d.p[0] + a[1] * d.p[1] + a[2] * d.p[2]);
    }
    // Carried Link: behind the camera along the level part of its back axis, and below it.
    float h = ksqrt(back[0] * back[0] + back[2] * back[2]);
    h = h > 1e-3f ? (float)settings[CARRY_BACK].value / 100.0f / h : 0;
    d.carry_at[0] = d.p[0] + back[0] * h;
    d.carry_at[1] = d.p[1] - (float)settings[CARRY_DROP].value / 100.0f;
    d.carry_at[2] = d.p[2] + back[2] * h;
}

static int standing_by(void) { return d.since_view > STANDBY_FRAMES || !d.have_game || kae_menu_open(); }

static void frame(void *user) {
    (void)user;
    if (d.since_view <= STANDBY_FRAMES)
        d.since_view++;
    d.stepped = 0;
}

static void input(KaeInput *seen, const KaeInput *real, void *user) {
    (void)user;
    if (standing_by()) {
        d.tick = 0;
        return;
    }
    if (!d.stepped && real->connected && (real->controller == 0 || real->controller == 0x20)) {
        d.stepped = 1;
        step(real);
    }
    if (d.on) {   // the game sees centred sticks and no buttons (except + and -), so Link waits
        seen->buttons &= KAE_PLUS | KAE_MINUS;
        seen->lx = seen->ly = seen->rx = seen->ry = 0;
    }
}

static void view(KaeView *v, void *user) {
    (void)user;
    d.since_view = 0;
    if (!d.on) {
        // Keep the view as it is now (First Person's, if that is on) for the next take-off:
        // eye = -(R^T t), back = row 2.
        const float *m = v->matrix;
        for (int i = 0; i < 3; i++) {
            d.eye[i] = -(m[i] * m[3] + m[4 + i] * m[7] + m[8 + i] * m[11]);
            d.gback[i] = m[8 + i];
        }
        d.have_game = 1;
        return;
    }
    for (int i = 0; i < 12; i++)
        v->matrix[i] = d.mat[i];
    int fov = FOV_DEGREES[settings[FOV].value];
    if (fov && v->fovy > 0 && v->aspect > 0)
        v->fovy = kfovy_from_horizontal((float)fov, v->aspect);
}

static void player_move(const KaePlayer *link, void *user) {
    (void)user;
    if (d.on && d.carry)
        kae_player_move(link, d.carry_at);
}

static int start(void) {
    if (kae_on_view(view, 0, 10) != KAE_OK) {
        KAE_LOG("fpv drone: no view event (Core older than 0.8, or its patch to main is missing or replaced): doing nothing");
        return 2;
    }
    if (kae_on_frame(frame, 0, 0) != KAE_OK || kae_on_input(input, 0, 10) != KAE_OK)
        return 2;
    if (kae_on_player_move(player_move, 0, 0) != KAE_OK)
        KAE_LOG("fpv drone: Link can't be carried in this game version");
    kae_settings("FPV Drone", settings, COUNT);
    KAE_LOG("fpv drone 2.0.0 on Core");
    return 0;
}

KAE_MOD("kabosune.fpv-drone", "2.0.0", start, 0);
