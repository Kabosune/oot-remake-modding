// Emotes: hold a button to open a list of Link's animations, pick one, he plays it. On KaeGae Core.
//
// The animations are commands of Link's animation sequencer (AS) graph (AS/Player_Child.root.asb and
// AS/Player_Adult.root.asb have the same 471 commands). They are played the way Mouse Grab plays his
// face: f_802222a0 with a 0x30-byte request (see mods/mouse-grab/module/face.c for its layout).
//
// The button: held for "Hold time" frames, the list opens; a shorter tap is handed back to the
// game, a few frames late ("While the list is open" with "Tap goes to the game" on). While the
// list is up: up / down (D-pad or left stick) to choose, A to play, release the button to close.
#include <kaegae.h>

#define F_AS_PLAY 0x2022A0   // f_802222a0(request), game 1.1.1
#define PARTIAL_MOUTH 6

typedef struct {
    void *actor;
    const char *command;
    int32_t partial;
    float rate;
    float minus_one[2];
    uint8_t ignore_same;
    uint8_t whole_body;   // +0x21: 1 takes the other branch (f_7000202610, no partial); every caller seen leaves it 0
    uint8_t zero[6];
    void *node;
} as_request_t;
_Static_assert(sizeof(as_request_t) == 0x30, "AS request");

typedef struct { const char *name, *command, *voice; } Emote;
static const Emote emotes[] = {
    { "Stop",                  "Wait",                  0 },
    { "Wave",                  "EvtTalkHello",          0 },
    { "Nod (yes)",             "EvtTalkYes",            "VoiceEvtTalkYes" },
    { "Shake head (no)",       "EvtTalkNo",             0 },
    { "Wonder",                "EvtTalkWonder",         0 },
    { "Talking",               "EvtTalkingL",           0 },
    { "Surprised",             "EvtSurprise",           0 },
    { "Surprised (small)",     "EvtSurpriseS",          0 },
    { "Turn around surprised", "EvtTurnAroundSurprise", "VoiceEvtTurnAroundSurprise" },
    { "Notice",                "EvtNotice",             0 },
    { "Caution",               "EvtCaution",            0 },
    { "Look around",           "EvtLookAround",         0 },
    { "Stretch",               "EvtStretch",            "VoiceEvtStretch" },
    { "Flinch",                "EvtFlinch",             0 },
    { "Unsteady",              "EvtUnsteady",           0 },
    { "Off balance",           "EvtUnbalance",          0 },
    { "Step back",             "EvtStepBack",           0 },
    { "Item get",              "DemoGet",               0 },
    { "Item get (smile)",      "DemoGet_Smile",         0 },
    { "Show item",             "EvtShowItemSuccess",    0 },
    { "Show item (wrong)",     "EvtShowItemFailure",    0 },
    { "Bottle pose",           "EvtPoseBottle",         0 },
    { "Drink",                 "DemoDrinkBottle",       0 },
    { "Read letter",           "DemoReadLetter",        0 },
    { "Ocarina",               "DemoOcarina",           0 },
    { "Plant beans",           "EvtBeansPlant",         "VoiceEvtBeansPlant" },
    { "Backflip",              "BackFlip",              "VoiceBackFlip" },
    { "Sidestep",              "SideStep",              "VoiceSideStep" },
};
#define N_EMOTES ((int)(sizeof emotes / sizeof *emotes))

enum { BUTTON, BLOCK, TAP, HOLD, VOICE, KEEP, KEEP_FOR, ROWS, SLOT, WHOLE, UPPER, DEBUG, N_SETTINGS };
enum { BLOCK_OFF, BLOCK_WHILE_OPEN, BLOCK_ALWAYS };
static const char *const block_names[] = { "Off", "While the list is open", "Always" };
enum { KEEP_OFF, KEEP_BEFORE, KEEP_AFTER };
static const char *const keep_names[] = { "Off", "Before Link's update", "After Link's update" };
static KaeItem settings[] = {
    [BUTTON] = { KAE_BINDING, "Emote list (hold)", "Hold to open the list. Up / down to choose, A to play.", 0, 0, 0, 0, 0, 0, KAE_L, KAE_L, 0, 0 },
    [BLOCK]  = { KAE_CHOICE, "Hide the button from the game", "Always: the game never gets it (L / R lose their own use: shield, targeting).", BLOCK_WHILE_OPEN, BLOCK_WHILE_OPEN, 0, 2, 1, block_names, 0, 0, 0, 0 },
    [TAP]    = { KAE_TOGGLE, "Tap goes to the game", "With \"While the list is open\": a short tap still does the button's own thing.", 1, 1, 0, 1, 1, 0, 0, 0, 0, 0 },
    [HOLD]   = { KAE_NUMBER, "Hold time (frames)", "How long to hold before the list opens. 60 frames = 1 second.", 10, 10, 2, 40, 1, 0, 0, 0, 0, 0 },
    [VOICE]  = { KAE_TOGGLE, "Voice", "Link's voice with the emotes that have one.", 1, 1, 0, 1, 1, 0, 0, 0, 0, 0 },
    [KEEP]   = { KAE_CHOICE, "Keep it playing (test)", "Asks for the emote again every frame so the game's own animation doesn't replace it. Try both.", KEEP_OFF, KEEP_OFF, 0, 2, 1, keep_names, 0, 0, 0, 0 },
    [KEEP_FOR] = { KAE_NUMBER, "Keep it for (frames)", "How long, at most. Moving the stick or pressing a button ends it sooner. 0 = until then.", 180, 180, 0, 600, 30, 0, 0, 0, 0, 0 },
    [ROWS]   = { KAE_NUMBER, "List rows", "How many emotes the list shows at once.", 10, 10, 4, 20, 1, 0, 0, 0, 0, 0 },
    [SLOT]   = { KAE_NUMBER, "Body slot (test)", "Animation slot the emote plays in: 0 whole body?, 1 upper body, 4 face. For testing.", 0, 0, 0, 8, 1, 0, 0, 0, 0, 0 },
    [WHOLE]  = { KAE_TOGGLE, "Whole-body flag (test)", "Sets the request's +0x21 byte: the game's other way of playing an animation.", 1, 1, 0, 1, 1, 0, 0, 0, 0, 0 },
    [UPPER]  = { KAE_TOGGLE, "Also on the upper body (test)", "Plays the emote on slot 1 (upper body) as well.", 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
    [DEBUG]  = { KAE_TOGGLE, "Debug log", "Logs every emote played and the list's state.", 1, 1, 0, 1, 1, 0, 0, 0, 0, 0 },
};

#define LOG(...) do { if (settings[DEBUG].value) KAE_LOG(__VA_ARGS__); } while (0)

// ---- state: written on the game's thread, read by draw on the render thread ----
enum { IDLE, PENDING, OPEN, REPLAY, WAIT_RELEASE };
static volatile int state = IDLE;
static volatile int cursor, top;
static int held_frames;         // frames the button has been held (PENDING) / the tap lasted (REPLAY)
static int replay_left;
static uint32_t press_controller;
static volatile int play_index = -1;   // set by frame(), played and cleared by player_move()

// What the controllers did since the last frame (input can come several times a frame).
static uint64_t frame_buttons, prev_buttons;
static int frame_ly, frame_lx, prev_dir;

// The emote being kept playing (KEEP): asked for again every frame until it ends or Link moves.
static int keep_index = -1, keep_frames;
static void *link_actor;        // from Link's last movement update
static int frames_since_link = 1000;
static int frame_bound;          // the button combination was fully held on some controller
static uintptr_t game_base;

static int bound(uint64_t buttons) {
    uint64_t b = settings[BUTTON].binding;
    return b && (buttons & b) == b;
}

static void close_list(void) {
    state = settings[BUTTON].binding ? WAIT_RELEASE : IDLE;
}

static void as_play(void *actor, const char *command, int partial);
static void emote_play(void *actor, const char *command);

static void stop_keeping(const char *why) {
    if (keep_index >= 0) LOG("emotes: %s ended after %d frames (%s)", emotes[keep_index].name, keep_frames, why);
    keep_index = -1;
}

// Once a frame, on the game's thread between two of Link's updates ("After Link's update").
static void keep(uint64_t pressed, int lx, int ly) {
    if (keep_index < 0)
        return;
    const uint64_t buttons = KAE_A | KAE_B | KAE_X | KAE_Y | KAE_ZL | KAE_ZR | KAE_L3 | KAE_R3 | KAE_L | KAE_R;
    if (state == OPEN || state == PENDING) return;            // choosing another one: hold still
    if (pressed & buttons & ~settings[BUTTON].binding) { stop_keeping("a button"); return; }
    if ((lx || ly) && keep_frames >= 15) { stop_keeping("the stick"); return; }   // a grace for the thumb that chose it
    if (frames_since_link > 2 || !link_actor) { stop_keeping("Link went away"); return; }
    int most = settings[KEEP_FOR].value;
    if (most && keep_frames >= most) { stop_keeping("time"); return; }
    keep_frames++;
    if (settings[KEEP].value == KEEP_AFTER)
        emote_play(link_actor, emotes[keep_index].command);
}

static void frame(void *user) {
    (void)user;
    uint64_t now = frame_buttons, pressed = now & ~prev_buttons;
    int dir = frame_ly > 16000 ? 1 : frame_ly < -16000 ? -1 : 0;   // stick up = 1
    int on = frame_bound, lx = frame_lx, ly = frame_ly;
    frame_buttons = 0, frame_ly = 0, frame_lx = 0, frame_bound = 0;
    if (frames_since_link < 1000) frames_since_link++;
    keep(pressed, lx, ly);

    if (kae_menu_open()) {
        state = IDLE, held_frames = 0;
        prev_buttons = now, prev_dir = dir;
        return;
    }
    int tap = settings[BLOCK].value == BLOCK_WHILE_OPEN && settings[TAP].value;
    switch (state) {
    case IDLE:
        if (on) {
            held_frames = 1;
            if (!tap || held_frames >= settings[HOLD].value) {
                state = OPEN;
                LOG("emotes: list open");
            } else {
                state = PENDING;
            }
        }
        break;
    case PENDING:
        if (!on) {                  // a tap: give it back to the game
            replay_left = held_frames < 2 ? 2 : held_frames;
            state = REPLAY;
        } else if (++held_frames >= settings[HOLD].value) {
            state = OPEN;
            LOG("emotes: list open");
        }
        break;
    case REPLAY:
        if (--replay_left <= 0)
            state = on ? WAIT_RELEASE : IDLE;
        break;
    case OPEN: {
        if (!on) { state = IDLE; break; }
        int step = 0;
        if (pressed & KAE_UP) step = -1;
        if (pressed & KAE_DOWN) step = 1;
        if (dir && dir != prev_dir) step = -dir;
        if (step) {
            int c = (cursor + step + N_EMOTES) % N_EMOTES, rows = settings[ROWS].value;
            if (c < top) top = c;
            if (c >= top + rows) top = c - rows + 1;
            cursor = c;
        }
        if (pressed & KAE_A) {
            play_index = cursor;
            close_list();
        } else if (pressed & KAE_B) {
            close_list();
        }
        break;
    }
    case WAIT_RELEASE:   // closed by A or B with the button still held: wait before it can open again
        if (!on) state = IDLE;
        break;
    }
    prev_buttons = now, prev_dir = dir;
}

static void input(KaeInput *seen_by_game, const KaeInput *real, void *user) {
    (void)user;
    if (!real->connected || kae_menu_open())
        return;
    uint64_t b = settings[BUTTON].binding;
    frame_buttons |= real->buttons;
    if (real->ly > 16000 || real->ly < -16000) frame_ly = real->ly;
    if (real->lx > 16000 || real->lx < -16000) frame_lx = real->lx;
    if (bound(real->buttons)) {
        if (!frame_bound) press_controller = real->controller;
        frame_bound = 1;
    }
    int block = settings[BLOCK].value;
    switch (state) {
    case OPEN:
        if (block != BLOCK_OFF) seen_by_game->buttons &= ~b;
        // the list's own controls never reach the game
        seen_by_game->buttons &= ~(uint64_t)(KAE_A | KAE_B | KAE_UP | KAE_DOWN);
        seen_by_game->lx = seen_by_game->ly = 0;
        break;
    case PENDING:
    case WAIT_RELEASE:
        if (block != BLOCK_OFF) seen_by_game->buttons &= ~b;
        if (state == WAIT_RELEASE) seen_by_game->buttons &= ~(uint64_t)(KAE_A | KAE_B);
        break;
    case REPLAY:
        if (real->controller == press_controller) seen_by_game->buttons |= b;
        break;
    default:
        if (block == BLOCK_ALWAYS) seen_by_game->buttons &= ~b;
        else if (block == BLOCK_WHILE_OPEN && bound(real->buttons))
            seen_by_game->buttons &= ~b;   // a press frame() hasn't seen yet: held back (a tap is replayed)
        break;
    }
}

static void as_request(void *actor, const char *command, int partial, int whole) {
    static _Alignas(16) uint8_t stand_in_node[0x200];
    // IsIgnoreSameCommand = 1: asking again for what is already playing doesn't restart it
    as_request_t r = { actor, command, partial, 1.0f, { -1.0f, -1.0f }, 1, (uint8_t)whole, { 0 }, stand_in_node };
    ((void (*)(as_request_t *))(game_base + F_AS_PLAY))(&r);
}

static void as_play(void *actor, const char *command, int partial) {
    as_request(actor, command, partial, 0);
}

// An emote: with the test settings, on the whole-body branch and / or the upper body as well.
static void emote_play(void *actor, const char *command) {
    as_request(actor, command, settings[SLOT].value, settings[WHOLE].value);
    if (settings[UPPER].value && settings[SLOT].value != 1)
        as_request(actor, command, 1, 0);
}

static void player_move(const KaePlayer *link, void *user) {
    (void)user;
    link_actor = link->actor, frames_since_link = 0;
    if (keep_index >= 0 && settings[KEEP].value == KEEP_BEFORE && link->actor)
        emote_play(link->actor, emotes[keep_index].command);
    int i = play_index;
    if (i < 0 || i >= N_EMOTES || !link->actor)
        return;
    play_index = -1;
    keep_index = (i == 0 || settings[KEEP].value == KEEP_OFF) ? -1 : i, keep_frames = 0;   // "Stop" isn't kept
    const Emote *e = &emotes[i];
    emote_play(link->actor, e->command);
    if (e->voice && settings[VOICE].value)
        as_play(link->actor, e->voice, PARTIAL_MOUTH);
    LOG("emotes: played %s (%s) in slot %d, whole-body flag %d, upper body too %d", e->name, e->command,
        settings[SLOT].value, settings[WHOLE].value, settings[UPPER].value);
}

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    if (state != OPEN)
        return;
    int scale = f->height >= 900 ? 2 : 1;
    int line = 18 * scale, pad = 8 * scale, rows = settings[ROWS].value;
    if (rows > N_EMOTES) rows = N_EMOTES;
    int w = 26 * 8 * scale + 2 * pad, h = (rows + 1) * line + 2 * pad;
    int x = f->width / 20, y = (f->height - h) / 2;
    int c = cursor, t = top;
    if (t > N_EMOTES - rows) t = N_EMOTES - rows;
    if (t < 0) t = 0;

    kae_draw_rect(x, y, w, h, 0x101820);
    kae_draw_rect(x, y, w, 2 * scale, 0x40C0FF);
    kae_draw_text(x + pad, y + pad, scale, 0x40C0FF, "Emotes");
    for (int r = 0; r < rows; r++) {
        int i = t + r, ry = y + pad + (r + 1) * line;
        if (i == c) kae_draw_rect(x + pad / 2, ry - scale, w - pad, line, 0x2C4C6C);
        kae_draw_text(x + pad, ry, scale, i == c ? 0xFFFFFF : 0xB0B8C0, emotes[i].name);
    }
    if (t > 0) kae_draw_text(x + w - pad - 8 * scale, y + pad + line, scale, 0x40C0FF, "^");
    if (t + rows < N_EMOTES) kae_draw_text(x + w - pad - 8 * scale, y + pad + rows * line, scale, 0x40C0FF, "v");
}

static int same(const char *a, const char *b) {
    while (*a && *a == *b) a++, b++;
    return *a == *b;
}

static int start(void) {
    game_base = kae_game_base();
    if (!game_base || !same(kae_game_version(), "1.1.1")) {
        KAE_LOG("emotes: needs game version 1.1.1 (this is \"%s\"): doing nothing", kae_game_version());
        return 2;
    }
    if (kae_on_player_move(player_move, 0, 0) != KAE_OK) {
        KAE_LOG("emotes: no player_move event in this game: doing nothing");
        return 2;
    }
    if (kae_on_frame(frame, 0, 0) != KAE_OK || kae_on_input(input, 0, 0) != KAE_OK || kae_on_draw(draw, 0, 0) != KAE_OK)
        return 2;
    kae_settings("Emotes", settings, N_SETTINGS);
    KAE_LOG("emotes 0.1.2: %d emotes, hold the button to open the list", N_EMOTES);
    return 0;
}

KAE_MOD("kabosune.emotes", "0.1.2", start, 0);
