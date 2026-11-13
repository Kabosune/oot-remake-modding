// The view event (0.8): the gameplay camera's view, right after the game has built it.
//
// The hook point "Camera.View" sits in f_804e48c0 just after it has written a view's matrix (the
// place First Person 1.x patched). That function builds every view, menus and previews too, so the
// gameplay one is picked out the way First Person and FPV Drone did: the view object's vtable, and
// camera 0 of the camera manager pointing at it.
//
// The field of view: the view holds a sead PerspectiveProjection (docs/sloperina-findings.md):
// the vertical angle and its half's sine, cosine and tangent, the aspect, its two "dirty" flags
// and the matrices worked out from them. Changing it is setFovy done by hand: the four numbers,
// the two flags (so the game works the matrices out again), and the x / y scales of both matrices
// scaled by the change, in case they are read before that. Not checked against main yet.
#include "core.h"

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))

static struct {
    void *vt_view, **manager_slot;
    int64_t matrix, eye, target, projection, fovy, aspect;
    bool fov;
} k;

bool kp_view_start(void) {
    k.vt_view = kae_sym("vtable.View");
    k.manager_slot = (void **)kae_sym("CameraManagerSlot");
    k.matrix = kae_field("View.matrix");
    k.eye = kae_field("View.position");
    k.target = kae_field("View.look_at");
    if (!k.vt_view || !k.manager_slot || k.matrix < 0 || k.eye < 0 || k.target < 0)
        return false;
    k.projection = kae_field("View.projection");
    k.fovy = kae_field("View.fovy");
    k.aspect = kae_field("View.aspect");
    k.fov = k.projection >= 0 && k.fovy >= 0 && k.aspect >= 0;
    return true;
}

bool kp_view_fov(void) { return k.fov && kp_event_on[KP_EV_VIEW]; }

// Gameplay view: [[slot]] = manager; +0x20 count; [[manager+0x28]] = camera 0; [camera 0 + 0x78] = view.
static bool gameplay(void *view) {
    if (!view || AT(view, 0, void *) != k.vt_view)
        return false;
    void **cell = *k.manager_slot;
    void *manager = cell && kp_readable((uintptr_t)cell, 8) ? *cell : 0;
    if (!manager || !kp_readable((uintptr_t)manager, 0x30) || !AT(manager, 0x20, uint32_t))
        return false;
    void **cameras = AT(manager, 0x28, void **);
    if (!cameras || !kp_readable((uintptr_t)cameras, 8) || !cameras[0] ||
        !kp_readable((uintptr_t)cameras[0] + 0x78, 8))
        return false;
    return AT(cameras[0], 0x78, void *) == view;
}

// sin and cos of x in [0, pi/2] (half a field of view), to 1e-7: enough for a camera.
static void half_sincos(float x, float *s, float *c) {
    float x2 = x * x;
    *s = x * (1 - x2 / 6 * (1 - x2 / 20 * (1 - x2 / 42 * (1 - x2 / 72 * (1 - x2 / 110)))));
    *c = 1 - x2 / 2 * (1 - x2 / 12 * (1 - x2 / 30 * (1 - x2 / 56 * (1 - x2 / 90 * (1 - x2 / 132)))));
}

static bool fov_readable(void *view) {
    if (!k.fov || !kp_readable((uintptr_t)view + k.projection, (size_t)(k.aspect - k.projection) + 4))
        return false;
    float fovy = AT(view, k.fovy, float), aspect = AT(view, k.aspect, float);
    return fovy > 0.1f && fovy < 3.0f && aspect > 0.5f && aspect < 4.0f;
}

static void set_fovy(void *view, float fovy) {
    if (fovy < 0.05f)
        fovy = 0.05f;
    if (fovy > 3.0f)
        fovy = 3.0f;
    char *p = (char *)view + k.projection;
    float s, c;
    half_sincos(fovy / 2, &s, &c);
    float old_tan = AT(view, k.fovy + 12, float), tan = s / c;
    AT(view, k.fovy, float) = fovy;
    AT(view, k.fovy + 4, float) = s;
    AT(view, k.fovy + 8, float) = c;
    AT(view, k.fovy + 12, float) = tan;
    p[8] = 1;   // the matrix and the device matrix are out of date
    p[9] = 1;
    // sead::Projection: matrix (4x4) at +0xC, device matrix at +0x4C. Their [0][0] and [1][1].
    if (old_tan > 1e-4f && old_tan < 100.0f) {
        float scale = old_tan / tan;
        static const int cells[4] = { 0xC, 0xC + 0x14, 0x4C, 0x4C + 0x14 };
        for (int i = 0; i < 4; i++)
            AT(p, cells[i], float) *= scale;
    }
}

void kp_view(void *view, void *camera) {
    (void)camera;
    kp_mods_ready();
    if (!kp_event_on[KP_EV_VIEW] || !gameplay(view) ||
        !kp_readable((uintptr_t)view + k.matrix, 12 * 4) || !kp_readable((uintptr_t)view + k.eye, 12) ||
        !kp_readable((uintptr_t)view + k.target, 12))
        return;
    KaeView v = { .size = sizeof v, .camera = view };
    float *matrix = &AT(view, k.matrix, float);
    for (int i = 0; i < 12; i++)
        v.matrix[i] = matrix[i];
    for (int i = 0; i < 3; i++) {
        v.eye[i] = AT(view, k.eye + 4 * i, float);
        v.target[i] = AT(view, k.target + 4 * i, float);
    }
    bool fov = fov_readable(view);
    if (fov) {
        v.fovy = AT(view, k.fovy, float);
        v.aspect = AT(view, k.aspect, float);
    }
    float fovy = v.fovy;
    kp_fire_view(&v);
    for (int i = 0; i < 12; i++)
        if (v.matrix[i] == v.matrix[i])   // not NaN
            matrix[i] = v.matrix[i];
    if (fov && v.fovy != fovy && v.fovy == v.fovy)
        set_fovy(view, v.fovy);
}
