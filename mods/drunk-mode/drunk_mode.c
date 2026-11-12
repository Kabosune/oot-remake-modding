// Drunk Mode: the controls go wrong on purpose. The movement stick wobbles (its direction sways
// back and forth over time), and sticks and buttons can be mirrored, flipped or swapped. On
// KaeGae Core: it only changes what the game is handed in the input event.
#include <kaegae.h>

enum { WOBBLE, WOBBLE_SPEED, WOBBLE_CAMERA, MIRROR_MOVE, FLIP_MOVE, MIRROR_CAMERA, FLIP_CAMERA, SWAP_STICKS, SWAP_AB };
static KaeItem settings[] = {
    [WOBBLE]        = { KAE_NUMBER, "Wobble (%)", "How far the stick's direction sways. 100 = a quarter turn.", 40, 40, 0, 100, 10, 0, 0, 0, 0, 0 },
    [WOBBLE_SPEED]  = { KAE_NUMBER, "Wobble speed", 0, 3, 3, 1, 10, 1, 0, 0, 0, 0, 0 },
    [WOBBLE_CAMERA] = { KAE_TOGGLE, "Wobble the camera too", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [MIRROR_MOVE]   = { KAE_TOGGLE, "Mirror movement", "Left on the stick is right.", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [FLIP_MOVE]     = { KAE_TOGGLE, "Flip movement", "Up on the stick is down.", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [MIRROR_CAMERA] = { KAE_TOGGLE, "Mirror camera", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [FLIP_CAMERA]   = { KAE_TOGGLE, "Flip camera", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [SWAP_STICKS]   = { KAE_TOGGLE, "Swap sticks", "Move with the right stick, look with the left.", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    [SWAP_AB]       = { KAE_TOGGLE, "Swap A and B", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
};

#define PI  3.14159265f
#define TAU 6.28318531f

static float phase;   // the wobble's clock, kept within one turn

static float sine(float x) {   // any angle in radians; the mod's angles are only a few turns at most
    while (x > PI)
        x -= TAU;
    while (x < -PI)
        x += TAU;
    if (x > PI / 2)
        x = PI - x;
    else if (x < -PI / 2)
        x = -PI - x;
    float x2 = x * x;
    return x * (1 - x2 / 6 * (1 - x2 / 20 * (1 - x2 / 42 * (1 - x2 / 72))));
}

static float cosine(float x) { return sine(x + PI / 2); }

static void frame(void *user) {
    (void)user;
    phase += 0.015f * (float)settings[WOBBLE_SPEED].value;
    if (phase >= TAU)
        phase -= TAU;
}

static int32_t clamp(float v) {
    return v > 32767 ? 32767 : v < -32767 ? -32767 : (int32_t)v;
}

// Turns a stick by `angle` (radians); its length stays.
static void turn(int32_t *x, int32_t *y, float angle) {
    float c = cosine(angle), s = sine(angle), fx = (float)*x, fy = (float)*y;
    *x = clamp(fx * c - fy * s);
    *y = clamp(fx * s + fy * c);
}

static void input(KaeInput *in, const KaeInput *real, void *user) {
    (void)user;
    if (!real->connected || kae_menu_open())
        return;
    if (settings[SWAP_STICKS].value) {
        int32_t lx = in->lx, ly = in->ly;
        in->lx = in->rx; in->ly = in->ry;
        in->rx = lx; in->ry = ly;
    }
    if (settings[MIRROR_MOVE].value)   in->lx = -in->lx;
    if (settings[FLIP_MOVE].value)     in->ly = -in->ly;
    if (settings[MIRROR_CAMERA].value) in->rx = -in->rx;
    if (settings[FLIP_CAMERA].value)   in->ry = -in->ry;

    if (settings[WOBBLE].value) {
        // two sways at different speeds, so it doesn't feel like a metronome
        float sway = 0.7f * sine(phase) + 0.3f * sine(phase * 2.3f + 1.0f);
        float angle = sway * (PI / 2) * (float)settings[WOBBLE].value / 100.0f;
        turn(&in->lx, &in->ly, angle);
        if (settings[WOBBLE_CAMERA].value)
            turn(&in->rx, &in->ry, -angle);
    }
    if (settings[SWAP_AB].value) {
        uint64_t b = in->buttons, a = b & KAE_A, bb = b & KAE_B;
        in->buttons = (b & ~(uint64_t)(KAE_A | KAE_B)) | (a ? KAE_B : 0) | (bb ? KAE_A : 0);
    }
}

static int start(void) {
    if (kae_on_frame(frame, 0, 0) != KAE_OK || kae_on_input(input, 0, 0) != KAE_OK)
        return 2;
    kae_settings("Drunk Mode", settings, sizeof settings / sizeof *settings);
    KAE_LOG("drunk mode 0.1.0: wobble, mirrored and swapped controls");
    return 0;
}

KAE_MOD("kabosune.drunk-mode", "0.1.0", start, 0);
