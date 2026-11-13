// The view event (0.8): the gameplay camera's view, right after the game has built it.
//
// The hook point "Camera.View" sits in f_804e48c0 just after it has written a view's matrix (the
// place First Person 1.x patched). That function builds every view, menus and previews too, so the
// gameplay one is picked out the way First Person and FPV Drone did: the view object's vtable, and
// camera 0 of the camera manager pointing at it.
//
// The field of view (0.8.1): the camera's own (camera +0x13C, aspect +0x140). Later in the same
// function (0x804e52d4..0x804e5348) the game copies the camera's near, far, fovy, aspect and offset
// into the sead PerspectiveProjection, with the sine, cosine and tangent and its dirty flag. So
// Core changes the camera's value and the game does the rest. (0.8.0 wrote the projection, at the
// view's +0x130: the game overwrote it a few instructions later, so the setting did nothing.)
#include "core.h"

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))

static struct {
    void *vt_view, **manager_slot;
    int64_t matrix, eye, target, fovy, aspect;
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
    k.fovy = kae_field("Camera.fovy");
    k.aspect = kae_field("Camera.aspect");
    k.fov = k.fovy >= 0 && k.aspect >= 0;
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

static bool fov_readable(void *camera) {
    if (!k.fov || !camera || !kp_readable((uintptr_t)camera + k.fovy, 4) || !kp_readable((uintptr_t)camera + k.aspect, 4))
        return false;
    float fovy = AT(camera, k.fovy, float), aspect = AT(camera, k.aspect, float);
    return fovy > 0.1f && fovy < 3.0f && aspect > 0.5f && aspect < 4.0f;
}

void kp_view(void *view, void *camera) {
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
    bool fov = fov_readable(camera);
    if (fov) {
        v.fovy = AT(camera, k.fovy, float);
        v.aspect = AT(camera, k.aspect, float);
    }
    float fovy = v.fovy;
    kp_fire_view(&v);
    for (int i = 0; i < 12; i++)
        if (v.matrix[i] == v.matrix[i])   // not NaN
            matrix[i] = v.matrix[i];
    if (fov && v.fovy != fovy && v.fovy == v.fovy)
        AT(camera, k.fovy, float) = v.fovy < 0.05f ? 0.05f : v.fovy > 3.0f ? 3.0f : v.fovy;
}
