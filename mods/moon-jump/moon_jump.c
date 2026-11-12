// Moon Jump: low gravity, bigger jumps and a hold-to-fly button, on KaeGae Core.
//
// It only touches Link's velocity, through Core (kae_player_velocity / kae_player_set_velocity), once
// per movement update. Gravity isn't a number the mod knows: it sees how much Link's upward speed
// dropped since its last update and lets only part of that drop through. Rises (a jump, a ledge
// hop) pass through whole, or boosted when they are a jump's kick. No game address is written here.
#include <kaegae.h>

enum { GRAVITY, JUMP_BOOST, MOON, MOON_SPEED, MAX_FALL };
static KaeItem settings[] = {
    [GRAVITY]    = { KAE_NUMBER, "Gravity (%)", "How hard Link falls. 100 is the game's own.", 40, 40, 10, 100, 5, 0, 0, 0, 0, 0 },
    [JUMP_BOOST] = { KAE_NUMBER, "Jump boost (%)", "How much higher a jump starts. 100 is the game's own.", 130, 130, 100, 300, 10, 0, 0, 0, 0, 0 },
    [MOON]       = { KAE_BINDING, "Moon jump (hold)", "Link flies up while the buttons are held.", 0, 0, 0, 0, 0, 0, KAE_L | KAE_A, KAE_L | KAE_A, 0, 0 },
    [MOON_SPEED] = { KAE_NUMBER, "Moon jump speed", "Metres a second upward while held.", 6, 6, 1, 20, 1, 0, 0, 0, 0, 0 },
    [MAX_FALL]   = { KAE_NUMBER, "Top falling speed", "Metres a second. 0 = no limit (the game's own).", 0, 0, 0, 40, 2, 0, 0, 0, 0, 0 },
};

// A rise this much faster than last update, in one update, is taken as a jump's kick (m/s).
#define KICK 2.0f

static int have_last;         // last_vy is from Link's previous update
static float last_vy;         // his upward speed as the mod left it
static int frames_away = 1000; // frames since his last movement update, capped
static int moon_held;
static int velocity_result = 1;  // what reading his velocity last returned, to log a change once

static void frame(void *user) {
    (void)user;
    if (frames_away < 1000)
        frames_away++;
}

static int held(uint64_t buttons, const KaeItem *item) {
    return item->binding && (buttons & item->binding) == item->binding;
}

static void input(KaeInput *seen_by_game, const KaeInput *real, void *user) {
    (void)user;
    if (!real->connected)
        return;
    if (kae_menu_open()) {
        moon_held = 0;
        return;
    }
    moon_held = held(real->buttons, &settings[MOON]);
    if (moon_held)
        seen_by_game->buttons &= ~settings[MOON].binding;   // the game doesn't also act on the combination
}

static void player_move(const KaePlayer *link, void *user) {
    (void)user;
    if (frames_away > 2)       // a new area, a cutscene, a reload: start over
        have_last = 0;
    frames_away = 0;

    float v[3];
    int result = kae_player_velocity(link, v);
    if (result != velocity_result) {
        velocity_result = result;
        KAE_LOG(result == KAE_OK ? "moon jump: Link's velocity found" : "moon jump: Link's velocity is out of reach here (%d)", result);
    }
    if (result != KAE_OK) {
        have_last = 0;
        return;
    }

    float vy = v[1], out = vy;
    if (moon_held) {
        out = (float)settings[MOON_SPEED].value;
    } else if (have_last) {
        float change = vy - last_vy;
        if (change < 0)                                          // gravity (or anything pulling down)
            out = last_vy + change * (float)settings[GRAVITY].value / 100.0f;
        else if (change > KICK && vy > 0)                        // a jump starting
            out = vy * (float)settings[JUMP_BOOST].value / 100.0f;
    }
    float limit = (float)settings[MAX_FALL].value;
    if (limit > 0 && out < -limit)
        out = -limit;
    if (out != vy) {
        v[1] = out;
        kae_player_set_velocity(link, v);
    }
    last_vy = out;
    have_last = 1;
}

static int start(void) {
    if (kae_on_player_move(player_move, 0, 0) != KAE_OK) {
        KAE_LOG("moon jump: no player_move event in this game: doing nothing");
        return 2;
    }
    if (kae_on_frame(frame, 0, 0) != KAE_OK || kae_on_input(input, 0, 0) != KAE_OK)
        return 2;
    kae_settings("Moon Jump", settings, sizeof settings / sizeof *settings);
    KAE_LOG("moon jump 0.1.0: gravity, jump boost, hold to fly");
    return 0;
}

KAE_MOD("kabosune.moon-jump", "0.1.0", start, 0);
