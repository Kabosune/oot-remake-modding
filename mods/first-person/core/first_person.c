// First Person 2 on KaeGae Core: the game's camera seen from Link's eyes.
//
// The same idea as First Person 1.x (../first_person.S), with Core doing the patching:
//   player_move  remembers Link's actor and hides his model while first person is on
//   view         the gameplay camera's matrix is moved to his eyes; its rotation stays the game's,
//                so the right stick, Z-targeting and aiming still turn the view. Also the FOV.
//   frame        the on / off binding (a button or a key, from the Mods menu)
//   input        the look speed: the right stick the game sees, scaled while first person is on
//
// Every game address and offset comes from Core's symbol pack (kae_sym / kae_field).
#include <kaegae.h>

#include "kmath.h"

static const char *const FOVS[] = { "The game's", "70°", "80°", "90°", "100°", "110°", "120°" };
static const int FOV_DEGREES[] = { 0, 70, 80, 90, 100, 110, 120 };

enum { TOGGLE, FOV, EYE_HEIGHT, EYE_FORWARD, LOOK_SPEED, SHOW_LINK, COUNT };
static KaeItem settings[] = {
    [TOGGLE]      = { KAE_BINDING, "First person on / off", "Switches to Link's eyes and back. The game also sees it (R3 levels the camera).",
                      0, 0, 0, 0, 0, 0, KAE_R3, KAE_R3, 0, 0 },
    [FOV]         = { KAE_CHOICE, "Field of view", "Horizontal, while first person is on. The game's own is about 80°.",
                      0, 0, 0, 6, 0, FOVS, 0, 0, 0, 0 },
    [EYE_HEIGHT]  = { KAE_NUMBER, "Eye height (cm)", "Added to the height measured when you switch on (stand normally then).",
                      0, 0, -80, 80, 2, 0, 0, 0, 0, 0 },
    [EYE_FORWARD] = { KAE_NUMBER, "Eye forward (cm)", "How far in front of Link's face the eye sits, so his head stays behind it.",
                      15, 15, 0, 60, 1, 0, 0, 0, 0, 0 },
    [LOOK_SPEED]  = { KAE_NUMBER, "Look speed (%)", "The right stick while first person is on. 100 = the game's own.",
                      100, 100, 25, 300, 25, 0, 0, 0, 0, 0 },
    [SHOW_LINK]   = { KAE_TOGGLE, "Show Link", "Off: Link is hidden while first person is on (his sword and shield may still show).",
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
};

#define STALE_VIEWS 30            // views without a Link update (pause, loading): the normal camera comes back
#define HEIGHT_MIN 0.4f
#define HEIGHT_MAX 2.2f

static struct {
    void *vt_actor;
    int64_t position, components, model, visible, flags;
    int can_hide;
} k;

static volatile int on, measure;  // first person on; measure the eye height at the next view
static float height;              // eye height above Link's feet, measured at switching on
static void *volatile link_actor; // Link's physics actor, from his last movement update
static volatile unsigned moves;   // counts his movement updates
static unsigned moves_seen, stale;
static int hidden, was_visible;   // we hid him; his visible byte before that

static void frame(void *user) {
    (void)user;
    if (!kae_binding_pressed(&settings[TOGGLE]))
        return;
    on = !on;
    if (on) {
        measure = 1;
        stale = 0;
    }
    KAE_LOG("first person %s", on ? "on" : "off");
}

static void input(KaeInput *seen, const KaeInput *real, void *user) {
    (void)real, (void)user;
    int speed = settings[LOOK_SPEED].value;
    if (!on || speed == 100 || kae_menu_open())
        return;
    seen->rx = (int32_t)kclamp((float)seen->rx * (float)speed / 100.0f, -32767.0f, 32767.0f);
    seen->ry = (int32_t)kclamp((float)seen->ry * (float)speed / 100.0f, -32767.0f, 32767.0f);
}

// Hide or show his model the way the game's OneShotSetModelVisible does: the visible byte, then a
// flag so the model picks the change up. What the game had is put back when hiding stops.
static void hide(void *actor, int want) {
    if (!k.can_hide || want == hidden)
        return;
    char *components = *(char **)((char *)actor + k.components);
    char *model = components ? *(char **)(components + k.model) : 0;
    if (!model || !kae_readable(model, (size_t)k.flags + 4))
        return;
    if (want)
        was_visible = model[k.visible];
    model[k.visible] = want ? 0 : (char)was_visible;
    *(uint32_t *)(model + k.flags) |= 0x800;
    hidden = want;
}

static void player_move(const KaePlayer *link, void *user) {
    (void)user;
    link_actor = link->actor;
    moves++;
    hide(link->actor, on && !settings[SHOW_LINK].value);
}

static int link_position(float out[3]) {
    char *actor = link_actor;
    if (!actor || !kae_readable(actor, (size_t)k.position + 12) || *(void **)actor != k.vt_actor)
        return 0;
    const float *p = (const float *)(actor + k.position);
    out[0] = p[0], out[1] = p[1], out[2] = p[2];
    return 1;
}

static void view(KaeView *v, void *user) {
    (void)user;
    if (!on)
        return;
    unsigned m = moves;
    stale = m != moves_seen ? 0 : stale + 1;
    moves_seen = m;
    float p[3];
    if (stale > STALE_VIEWS || !link_position(p))
        return;
    if (measure) {
        height = kclamp(v->target[1] - p[1], HEIGHT_MIN, HEIGHT_MAX);
        measure = 0;
        KAE_LOG("first person: eye height %.2f m", height);
    }
    // Eye = Link + height, pushed forward along the level part of where the view faces (-back).
    float *back = v->matrix + 8;
    float eye[3] = { p[0], p[1] + height + (float)settings[EYE_HEIGHT].value / 100.0f, p[2] };
    float flat = ksqrt(back[0] * back[0] + back[2] * back[2]);
    if (flat > 1e-4f) {
        float f = (float)settings[EYE_FORWARD].value / 100.0f / flat;
        eye[0] -= back[0] * f;
        eye[2] -= back[2] * f;
    }
    for (int row = 0; row < 3; row++) {
        float *r = v->matrix + 4 * row;
        r[3] = -(r[0] * eye[0] + r[1] * eye[1] + r[2] * eye[2]);
    }
    int fov = FOV_DEGREES[settings[FOV].value];
    if (fov && v->fovy > 0 && v->aspect > 0)
        v->fovy = kfovy_from_horizontal((float)fov, v->aspect);
}

static int start(void) {
    k.vt_actor = kae_sym("vtable.Actor");
    k.position = kae_field("Actor.position");
    k.components = kae_field("Actor.components");
    k.model = kae_field("Components.model");
    k.visible = kae_field("Model.visible");
    k.flags = kae_field("Model.flags");
    k.can_hide = k.components >= 0 && k.model >= 0 && k.visible >= 0 && k.flags >= 0;
    if (!k.vt_actor || k.position < 0) {
        KAE_LOG("first person: this game version's symbols don't say where Link is: doing nothing");
        return 2;
    }
    if (kae_on_view(view, 0, 0) != KAE_OK) {
        KAE_LOG("first person: no view event (Core older than 0.8, or its patch to main is missing or replaced): doing nothing");
        return 2;
    }
    if (kae_on_player_move(player_move, 0, 0) != KAE_OK || kae_on_frame(frame, 0, 0) != KAE_OK ||
        kae_on_input(input, 0, 0) != KAE_OK)
        return 2;
    kae_settings("First Person", settings, COUNT);
    KAE_LOG("first person 2.0.0 on Core: %s", kae_has("view.fovy") ? "field of view can change" : "field of view is the game's");
    return 0;
}

KAE_MOD("kabosune.first-person", "2.0.0", start, 0);
