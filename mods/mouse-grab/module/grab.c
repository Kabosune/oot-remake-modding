// Mouse Grab, step three: hold the left button on Link to pick him up, move the mouse to carry
// him, let go to throw him (he ragdolls as he flies).
//
// - The cursor becomes a ray through the gameplay camera: camera = [[CAMERA_SLOT]+0x68], position
//   +0x38, look-at +0x44, tan(half vertical FOV) +0x13c, aspect +0x140 (sloperina's notes).
// - Grabbing works when the ray passes within the grab radius (a setting) of Link's middle. He is held at the same
//   distance along the ray, so the mouse moves him across the screen.
// - Moving: he's a ragdoll while held. Every frame the ragdoll's bodies get a velocity that takes
//   him to the held point (Link's actor position follows the ragdoll). Middle click switches
//   between pulling every body (stiff) and pulling only the first one, so the rest dangles.
// - Throwing: on release every ragdoll body gets the velocity the held point had.
// - Other characters (no ragdoll; only Link has one): the cursor picks whichever character's middle
//   the ray passes closest to. They're carried stiff by their character controller (ChangePosition
//   with velocity zeroed, in their own movement update) and thrown by the controller body's velocity.
#include "core.h"
#include "input.h"

#define CAMERA_SLOT    0x4E98068
#define F_SET_VELOCITY 0x12DBE0    // f_8014dbe0(body, float vel[3])
#define BODY_VT        0x4C34658
#define F_HOLDER       0x837620
#define MIDDLE         0.8f        // Link's middle above his feet (m)
#define MAX_BODIES     32
#define F_CHANGE_POS   0x6B2530    // f_806d2530(controller, float pos[4])
#define VT_CCT         0x4C34F10   // CharacterProperty, the character controller
#define BODY_VT        0x4C34658   // the controller's body
#define MAX_CANDIDATES 96
// Depth works like a mouse: turning the controller moves him, holding it still keeps him where
// he is, and slow turns below the gyro deadzone (a setting) don't count, so you can turn back slowly and flick again.
#define DEPTH_PER_RAD  1.5f        // metres of depth per radian of pitch, at slow speed, at 100 %
// The grab radius, pull, top speed, throw, and the gyro's speed, deadzone and smoothing are
// settings (settings.h).
#define GYRO_ACCEL     0.25f       // faster turns go further: gain * (1 + GYRO_ACCEL * rad/s)
#define MIN_DEPTH      0.8f
#define MAX_DEPTH      40.0f
#define TICK_HZ        19200000.0f

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))

bool ragdoll_is_down(void *actor);
void ragdoll_start(void *actor);
void ragdoll_stop(void *actor);
int ragdoll_bodies(void *actor, void **out, int max);
void *actor_holder(void *actor);
void link_voice(void *actor, const char *command);

typedef struct { float x, y, z; } v3;
static v3 add(v3 a, v3 b) { return (v3){ a.x + b.x, a.y + b.y, a.z + b.z }; }
static v3 sub(v3 a, v3 b) { return (v3){ a.x - b.x, a.y - b.y, a.z - b.z }; }
static v3 mul(v3 a, float k) { return (v3){ a.x * k, a.y * k, a.z * k }; }
static float dot(v3 a, v3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static v3 cross(v3 a, v3 b) { return (v3){ a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x }; }
static float root(float x) { float r; __asm__("fsqrt %s0, %s1" : "=w"(r) : "w"(x)); return r; }
static v3 unit(v3 a) { float l = root(dot(a, a)); return l > 1e-6f ? mul(a, 1.0f / l) : a; }

// The controller's pitch (radians, up positive) from its direction matrix; false without data.
static float asin_approx(float x) {   // good to ~0.01 rad over -1..1
    if (x > 1) x = 1;
    if (x < -1) x = -1;
    float ax = x < 0 ? -x : x;
    float r = 1.5707963f - root(1 - ax) * (1.5707288f + ax * (-0.2121144f + ax * (0.0742610f - 0.0187293f * ax)));
    return x < 0 ? -r : r;
}

static bool controller_pitch(float *pitch) {
    float d[9];
    if (!kp_motion_direction(d))
        return false;
    *pitch = asin_approx(d[7]);   // y of the third row (the axis out of the controller's face)
    return true;
}

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

// Characters seen in the last frames that can be carried: their controller and middle.
static struct { void *actor; v3 middle; uint32_t frame; } candidates[MAX_CANDIDATES];
static int next_candidate;

static void *controller_of(void *actor) {
    void *holder = actor_holder(actor);
    void *c = holder ? AT(holder, 8, void *) : 0;
    return c && kp_readable((uintptr_t)c, 0x28) && AT(c, 0, uintptr_t) == kp_main + VT_CCT ? c : 0;
}

static void *body_of(void *controller) {
    void *b = controller ? AT(controller, 0x20, void *) : 0;
    return b && kp_readable((uintptr_t)b, 8) && AT(b, 0, uintptr_t) == kp_main + BODY_VT ? b : 0;
}

static struct {
    void *target;         // what's held: Link or another actor
    void *link;
    bool throw_pending;   // another actor was let go: throw it in its next update
    bool held_button, grabbing, held_middle, one_body;
    float depth;          // distance along the ray when grabbed
    float last_pitch;     // controller pitch last frame (radians)
    float depth_velocity; // smoothed depth change per frame
    bool have_pitch;
    v3 point, last_point; // held point (Link's middle)
    v3 velocity;
    uint64_t last_tick;
    uint32_t frames, frame;
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
    bool left = got > 0 && (m.attributes & 2) && (m.buttons & 1) && (g.grabbing || !kae_menu_open());
    bool pressed = left && !g.held_button, released = !left && g.held_button;
    bool middle_button = got > 0 && (m.attributes & 2) && (m.buttons & 4) && !kae_menu_open();
    if (middle_button && !g.held_middle) {
        g.one_body = !g.one_body;
        kp_log_2("grab: pull only the first body:", g.one_body, 0);
    }
    g.held_middle = middle_button;
    g.held_button = left;
    uint64_t now = ticks();
    float dt = g.last_tick ? (float)(now - g.last_tick) / TICK_HZ : 1.0f / 30;
    g.last_tick = now;
    if (dt <= 0.001f || dt > 0.5f)
        dt = 1.0f / 30;

    v3 from, dir;
    bool ray = got > 0 && mouse_ray(&m, &from, &dir);
    v3 middle = add(AT(actor, 0x31c, v3), (v3){ 0, MIDDLE, 0 });

    g.link = actor;
    g.frame++;
    if (pressed && ray) {
        // the closest character to the ray, Link included
        void *best = 0;
        float best_miss = (float)MG(MG_GRAB_RADIUS) / 100.0f, best_along = 0;
        v3 best_middle = middle;
        for (int i = -1; i < MAX_CANDIDATES; i++) {
            void *who = i < 0 ? actor : candidates[i].actor;
            v3 mid = i < 0 ? middle : candidates[i].middle;
            if (!who || (i >= 0 && (!MG(MG_GRAB_OTHERS) || g.frame - candidates[i].frame > 2)))
                continue;
            float along = dot(sub(mid, from), dir);
            v3 off = sub(mid, add(from, mul(dir, along)));
            float miss = root(dot(off, off));
            if (along > 0.3f && miss < best_miss) {
                best = who;
                best_miss = miss;
                best_along = along;
                best_middle = mid;
            }
        }
        kp_log_2("grab: pressed. picked Link, miss (cm):", best == actor, best ? (int64_t)(best_miss * 100) : -1);
        if (best) {
            if (best == actor && !ragdoll_is_down(actor))
                ragdoll_start(actor);
            if (best == actor)
                link_voice(actor, "VoiceDamageKidnapped");
            g.target = best;
            g.grabbing = true;
            g.throw_pending = false;
            g.depth = best_along;
            g.point = g.last_point = best_middle;
            g.velocity = (v3){ 0, 0, 0 };
            g.frames = 0;
            g.have_pitch = controller_pitch(&g.last_pitch);
            g.depth_velocity = 0;
            if (best != actor) {
                const char *name = AT(best, 0x20, const char *);
                kp_log(name && kp_readable((uintptr_t)name, 1) ? name : "grab: holding a character");
            } else {
                kp_log_2("grab: holding Link. pitch known, pitch (mrad):", g.have_pitch, (int64_t)(g.last_pitch * 1000));
            }
        }
    }
    if (g.grabbing && left && ray) {
        float pitch, turned = 0;
        if (controller_pitch(&pitch)) {
            if (g.have_pitch) {
                turned = pitch - g.last_pitch;
                float rate = (turned < 0 ? -turned : turned) / dt;
                float gain = DEPTH_PER_RAD * (float)MG(MG_GYRO_SPEED) / 100.0f * (MG(MG_GYRO_INVERT) ? -1.0f : 1.0f);
                float step = rate > (float)MG(MG_GYRO_DEADZONE) / 10.0f ? turned * gain * (1 + GYRO_ACCEL * rate) : 0;
                // tilting the controller's face towards you brings him closer (KaboWabo, build f;
                // the direction matrix's sign is the other way round from what the name says)
                g.depth_velocity += (step - g.depth_velocity) * (float)MG(MG_GYRO_SMOOTHING) / 100.0f;
                g.depth += g.depth_velocity;
            }
            g.last_pitch = pitch;
            g.have_pitch = true;
        }
        if (g.depth < MIN_DEPTH)
            g.depth = MIN_DEPTH;
        if (g.depth > MAX_DEPTH)
            g.depth = MAX_DEPTH;
        float depth = g.depth;
        g.point = add(from, mul(dir, depth));
        v3 v = mul(sub(g.point, g.last_point), 1.0f / dt);
        g.velocity = add(mul(g.velocity, 0.5f), mul(v, 0.5f));   // smoothed over a few frames
        g.last_point = g.point;
        if (g.target != actor)
            goto logged;   // another actor: moved in its own update (grab_other)
        // velocity that closes the gap to the held point, on top of the point's own motion
        v3 gap = sub(g.point, middle);
        v3 pull = add(mul(gap, (float)MG(MG_PULL)), g.velocity);
        float speed = root(dot(pull, pull)), top = (float)MG(MG_MAX_SPEED);
        if (speed > top)
            pull = mul(pull, top / speed);
        void *bodies[MAX_BODIES];
        int n = ragdoll_bodies(actor, bodies, MAX_BODIES);
        float vel[3] = { pull.x, pull.y, pull.z };
        for (int i = 0; i < (g.one_body ? (n > 0) : n); i++)
            KP_FN(void (*)(void *, const float *, int), F_SET_VELOCITY)(bodies[i], vel, 0);
        if (g.frames == 0)
            kp_log_2("grab: ragdoll bodies, pulling only the first:", n, g.one_body);
    logged:
        if (g.frames++ % 30 == 0) {
            log_v3("grab: held point (cm x, z)", g.point);
            log_v3("  Link's actor position", AT(actor, 0x31c, v3));
            kp_log_2("  depth (cm), pitch (mrad):", (int64_t)(depth * 100), (int64_t)(g.last_pitch * 1000));
        }
    }
    if (g.grabbing && released) {
        g.grabbing = false;
        g.velocity = mul(g.velocity, (float)MG(MG_THROW) / 100.0f);
        if (g.target == actor) {
            void *bodies[MAX_BODIES];
            int n = ragdoll_bodies(actor, bodies, MAX_BODIES);
            float v[3] = { g.velocity.x, g.velocity.y, g.velocity.z };
            for (int i = 0; i < n; i++)
                KP_FN(void (*)(void *, const float *, int), F_SET_VELOCITY)(bodies[i], v, 0);
            if (dot(g.velocity, g.velocity) > 4.0f * 4.0f)
                link_voice(actor, "VoiceFallDanger");   // thrown hard
        } else {
            g.throw_pending = true;
        }
        log_v3("grab: thrown, velocity (cm/s x, z)", g.velocity);
    }
}

// Every other physics actor, in its own movement update.
void grab_other(void *actor) {
    if (g.target == actor && (g.grabbing || g.throw_pending)) {
        void *c = controller_of(actor);
        void *body = body_of(c);
        if (g.grabbing && c) {
            float to[4] = { g.point.x, g.point.y - MIDDLE, g.point.z, 0 };
            KP_FN(void (*)(void *, const float *), F_CHANGE_POS)(c, to);
            static const float still[3] = { 0, 0, 0 };
            if (body)
                KP_FN(void (*)(void *, const float *, int), F_SET_VELOCITY)(body, still, 0);
        } else if (g.throw_pending) {
            g.throw_pending = false;
            float v[3] = { g.velocity.x, g.velocity.y, g.velocity.z };
            if (body)
                KP_FN(void (*)(void *, const float *, int), F_SET_VELOCITY)(body, v, 0);
        }
        return;
    }
    // remember carriable characters, at most once per frame each
    for (int i = 0; i < MAX_CANDIDATES; i++)
        if (candidates[i].actor == actor) {
            if (candidates[i].frame != g.frame) {
                candidates[i].frame = g.frame;
                candidates[i].middle = add(AT(actor, 0x31c, v3), (v3){ 0, MIDDLE, 0 });
            }
            return;
        }
    if (!controller_of(actor))
        return;
    const char *name = AT(actor, 0x20, const char *);
    if (name && kp_readable((uintptr_t)name, 9) && name[0] == 'N' && name[1] == 'p' && name[2] == 'c' &&
        name[3] == '_' && name[4] == 'N' && name[5] == 'a' && name[6] == 'v' && name[7] == 'i' && !name[8])
        return;   // Navi flies next to Link and would steal clicks meant for him
    int i = next_candidate;
    next_candidate = (next_candidate + 1) % MAX_CANDIDATES;
    candidates[i].actor = actor;
    candidates[i].frame = g.frame;
    candidates[i].middle = add(AT(actor, 0x31c, v3), (v3){ 0, MIDDLE, 0 });
}
