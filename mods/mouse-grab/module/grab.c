// Mouse Grab, step three: hold the left button on Link to pick him up, move the mouse to carry
// him, let go to throw him (he ragdolls as he flies).
//
// - The cursor becomes a ray through the gameplay camera: camera = [[CAMERA_SLOT]+0x68], position
//   +0x38, look-at +0x44, tan(half vertical FOV) +0x13c, aspect +0x140 (sloperina's notes).
// - Grabbing works when the ray passes within GRAB_RADIUS of Link's middle. He is held at the same
//   distance along the ray, so the mouse moves him across the screen.
// - Moving: his character controller is put at the held point every frame (ChangePosition, as
//   FPV Drone's carry), with its velocity zeroed so he doesn't build up a fall. A ragdoll doesn't
//   follow the controller (tested: the game pulls the controller back to the ragdoll), so while
//   he's held he is out of ragdoll.
// - Throwing: on release the controller body gets the velocity the held point had, then he
//   ragdolls.
#include "core.h"
#include "input.h"

#define CAMERA_SLOT    0x4E98068
#define F_CHANGE_POS   0x6B2530    // f_806d2530(controller, float pos[4])
#define F_SET_VELOCITY 0x12DBE0    // f_8014dbe0(body, float vel[3])
#define VT_CCT         0x4C34F10
#define BODY_VT        0x4C34658
#define F_HOLDER       0x837620
#define GRAB_RADIUS    1.2f
#define MIDDLE         0.8f        // Link's middle above his feet (m)
#define TICK_HZ        19200000.0f

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))

bool ragdoll_is_down(void *actor);
void ragdoll_start(void *actor);
void ragdoll_stop(void *actor);

typedef struct { float x, y, z; } v3;
static v3 add(v3 a, v3 b) { return (v3){ a.x + b.x, a.y + b.y, a.z + b.z }; }
static v3 sub(v3 a, v3 b) { return (v3){ a.x - b.x, a.y - b.y, a.z - b.z }; }
static v3 mul(v3 a, float k) { return (v3){ a.x * k, a.y * k, a.z * k }; }
static float dot(v3 a, v3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static v3 cross(v3 a, v3 b) { return (v3){ a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x }; }
static float root(float x) { float r; __asm__("fsqrt %s0, %s1" : "=w"(r) : "w"(x)); return r; }
static v3 unit(v3 a) { float l = root(dot(a, a)); return l > 1e-6f ? mul(a, 1.0f / l) : a; }

static uint64_t ticks(void) {
    register uint64_t x0 __asm__("x0");
    __asm__ volatile("svc #0x1e" : "=r"(x0) : : "memory");
    return x0;
}

// The ray under the mouse. False if there's no camera.
static bool mouse_ray(const mouse_state_t *m, v3 *from, v3 *dir) {
    char *slot = AT(kp_main + CAMERA_SLOT, 0, char *);
    char *camera = slot && kp_readable((uintptr_t)slot + 0x68, 8) ? AT(slot, 0x68, char *) : 0;
    if (!camera || !kp_readable((uintptr_t)camera, 0x150))
        return false;
    v3 eye = AT(camera, 0x38, v3), at = AT(camera, 0x44, v3);
    float t = AT(camera, 0x13c, float), aspect = AT(camera, 0x140, float);
    if (!(t > 0.01f && t < 10.0f) || !(aspect > 0.1f && aspect < 10.0f))
        return false;
    v3 f = unit(sub(at, eye));
    v3 r = unit(cross(f, (v3){ 0, 1, 0 }));
    v3 u = cross(r, f);
    float nx = (float)m->x / 640.0f - 1.0f, ny = 1.0f - (float)m->y / 360.0f;
    *from = eye;
    *dir = unit(add(f, add(mul(r, nx * t * aspect), mul(u, ny * t))));
    return true;
}

static void *controller_of(void *actor) {
    void *holder = KP_FN(void *(*)(void *), F_HOLDER)(actor);
    void *c = holder ? AT(holder, 8, void *) : 0;
    return c && AT(c, 0, uintptr_t) == kp_main + VT_CCT ? c : 0;
}

static struct {
    bool held_button, grabbing;
    float depth;          // distance along the ray
    v3 point, last_point; // held point (Link's middle)
    v3 velocity;
    uint64_t last_tick;
    uint32_t frames;
} g;

static void log_v3(const char *what, v3 p) {
    kp_log_2(what, (int64_t)(p.x * 100), (int64_t)(p.z * 100));
    kp_log_2("    height (cm), -", (int64_t)(p.y * 100), 0);
}

void grab_move(void *actor) {
    mouse_state_t m;
    m.buttons = 0;
    m.attributes = 0;
    int got = _ZN2nn3hid14GetMouseStatesEPNS0_10MouseStateEi(&m, 1);
    bool left = got > 0 && (m.attributes & 2) && (m.buttons & 1);
    bool pressed = left && !g.held_button, released = !left && g.held_button;
    g.held_button = left;
    uint64_t now = ticks();
    float dt = g.last_tick ? (float)(now - g.last_tick) / TICK_HZ : 1.0f / 30;
    g.last_tick = now;
    if (dt <= 0.001f || dt > 0.5f)
        dt = 1.0f / 30;

    v3 from, dir;
    bool ray = got > 0 && mouse_ray(&m, &from, &dir);
    v3 middle = add(AT(actor, 0x31c, v3), (v3){ 0, MIDDLE, 0 });

    if (pressed && ray) {
        float along = dot(sub(middle, from), dir);
        v3 closest = add(from, mul(dir, along));
        v3 off = sub(middle, closest);
        float miss = root(dot(off, off));
        kp_log_2("grab: pressed. distance along ray, miss (cm):", (int64_t)(along * 100), (int64_t)(miss * 100));
        if (along > 0.3f && miss < GRAB_RADIUS) {
            if (ragdoll_is_down(actor))
                ragdoll_stop(actor);
            g.grabbing = true;
            g.depth = along;
            g.point = g.last_point = middle;
            g.velocity = (v3){ 0, 0, 0 };
            g.frames = 0;
            kp_log("grab: holding Link");
        }
    }
    if (g.grabbing && left && ray) {
        g.point = add(from, mul(dir, g.depth));
        v3 v = mul(sub(g.point, g.last_point), 1.0f / dt);
        g.velocity = add(mul(g.velocity, 0.5f), mul(v, 0.5f));   // smoothed over a few frames
        g.last_point = g.point;
        void *c = controller_of(actor);
        void *body = c ? AT(c, 0x20, void *) : 0;
        if (c) {
            float to[4] = { g.point.x, g.point.y - MIDDLE, g.point.z, 0 };
            KP_FN(void (*)(void *, const float *), F_CHANGE_POS)(c, to);
        }
        if (body && AT(body, 0, uintptr_t) == kp_main + BODY_VT) {
            static const float still[3] = { 0, 0, 0 };
            KP_FN(void (*)(void *, const float *), F_SET_VELOCITY)(body, still);
        }
        if (g.frames++ % 30 == 0) {
            log_v3("grab: held point (cm x, z)", g.point);
            log_v3("  Link's actor position", AT(actor, 0x31c, v3));
        }
    }
    if (g.grabbing && released) {
        g.grabbing = false;
        ragdoll_start(actor);   // first: its preparation stops Link
        void *c = controller_of(actor);
        void *body = c ? AT(c, 0x20, void *) : 0;
        if (body && AT(body, 0, uintptr_t) == kp_main + BODY_VT) {
            float v[3] = { g.velocity.x, g.velocity.y, g.velocity.z };
            KP_FN(void (*)(void *, const float *), F_SET_VELOCITY)(body, v);
        }
        log_v3("grab: thrown, velocity (cm/s x, z)", g.velocity);
    }
}
