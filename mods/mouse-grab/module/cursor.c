// Mouse Grab, step one: a cursor at the mouse position.
#include "core.h"

#include "input.h"

enum { MOUSE_WIDTH = 1280, MOUSE_HEIGHT = 720, MOUSE_CONNECTED = 2 };
enum { BLACK = 0x000000, WHITE = 0xFFFFFF, HELD = 0xFFD040 };

// '#' outline, '.' fill
static const char *const arrow[] = {
    "#",
    "##",
    "#.#",
    "#..#",
    "#...#",
    "#....#",
    "#.....#",
    "#......#",
    "#.......#",
    "#........#",
    "#.........#",
    "#..........#",
    "#......#####",
    "#...#..#",
    "#..# #..#",
    "#.#  #..#",
    "##    #..#",
    "#     #..#",
    "       ##",
};
#define ARROW_ROWS ((int)(sizeof arrow / sizeof *arrow))

static bool logged_missing;

void ragdoll_move(void *actor);

uintptr_t mg_main;

static void on_draw(const KaeFrame *frame, void *user);
static void on_actor_move(void *actor, void *user) {
    (void)user;
    ragdoll_move(actor);
}

static int start(void) {
    kp_log("mouse grab: build 2026-11-10 g (on KaeGae Core 0.4)");
    mg_main = kae_game_base();
    if (kae_on_actor_move(on_actor_move, 0, 0) != KAE_OK)
        kp_log("mouse grab: no movement hook (Core's .ips is missing): the cursor works, grabbing doesn't");
    if (!kae_has("motion"))
        kp_log("motion off: main's GetSixAxisSensorStates import wasn't found");
    return kae_on_draw(on_draw, 0, 0);
}

KAE_MOD("kabosune.mouse-grab", "0.2.0", start, 0);

// One rectangle for each run of the same kind of cell in a row.
static void draw_arrow(int left, int top, int scale, uint32_t fill) {
    for (int row = 0; row < ARROW_ROWS; row++) {
        const char *s = arrow[row];
        for (int i = 0; s[i];) {
            int start = i;
            char kind = s[i];
            while (s[i] == kind)
                i++;
            if (kind != ' ')
                kp_draw_rect(left + start * scale, top + row * scale, (i - start) * scale, scale,
                             kind == '#' ? BLACK : fill);
        }
    }
}

static void on_draw(const KaeFrame *frame, void *user) {
    (void)user;
    mouse_state_t m;
    m.attributes = 0;
    int got = _ZN2nn3hid14GetMouseStatesEPNS0_10MouseStateEi(&m, 1);
    bool connected = got > 0 && (m.attributes & MOUSE_CONNECTED);
    if (!connected) {
        if (!logged_missing) {
            logged_missing = true;
            kp_log("mouse grab: no mouse connected (in the emulator, turn on the emulated mouse)");
        }
        return;
    }
    int scale = (frame->height + 360) / 720;
    if (scale < 1)
        scale = 1;
    int x = (int)((int64_t)m.x * frame->width / MOUSE_WIDTH);
    int y = (int)((int64_t)m.y * frame->height / MOUSE_HEIGHT);
    draw_arrow(x, y, scale, (m.buttons & 1) ? HELD : WHITE);
    if (frame->number % 300 == 0)
        kp_log_2("mouse grab: cursor at", m.x, m.y);
}
