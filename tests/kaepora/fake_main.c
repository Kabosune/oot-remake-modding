// A stand-in for the game's main, for tests/test_kaepora_modules.py. It has the few things Core
// looks for in the real one at the same places (nnMain, MOD0, the movement update, the import
// slots) and behaves like the game where Core hooks it. Nothing here comes from the game.
#include <stddef.h>
#include <stdint.h>

#define EXPORT __attribute__((visibility("default")))

typedef struct {
    int64_t sample;
    uint64_t buttons;
    int32_t lx, ly, rx, ry;
    uint32_t attributes, pad;
} npad_state_t;

void *nvnBootstrapLoader(const char *name);
uint32_t _ZN2nn3hid15GetNpadStyleSetERKj(const uint32_t *id);
int _ZN2nn3hid13GetNpadStatesEPNS0_16NpadFullKeyStateEiRKj(npad_state_t *, int, const uint32_t *);
int _ZN2nn3hid13GetNpadStatesEPNS0_17NpadHandheldStateEiRKj(npad_state_t *, int, const uint32_t *);
int _ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyDualStateEiRKj(npad_state_t *, int, const uint32_t *);
int _ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyLeftStateEiRKj(npad_state_t *, int, const uint32_t *);
int _ZN2nn3hid13GetNpadStatesEPNS0_17NpadJoyRightStateEiRKj(npad_state_t *, int, const uint32_t *);
int _ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE(void *, int, const uint32_t *);

__attribute__((section(".text_nnmain"))) EXPORT void nnMain(void) {}

static _Alignas(0x1000) uint8_t heap[0x300000];
static size_t heap_used;
EXPORT size_t game_heap_limit = sizeof heap;   // a test lowers it to play a game short of memory
EXPORT void *aligned_alloc(size_t align, size_t size) {
    size_t at = (heap_used + align - 1) / align * align;
    if (at + size > game_heap_limit)
        return 0;
    heap_used = at + size;
    return heap + at;
}

// ---- what the test reads back ----
EXPORT npad_state_t game_states[2][4];   // [0] player 1, [1] handheld: the states the game was handed
EXPORT int game_state_count[2];
EXPORT void *game_moved_actor;
EXPORT int game_moves;

// ---- graphics start, as the game does it: everything by name through the bootstrap loader ----
typedef void *(*getproc_fn)(void *device, const char *name);
static uint8_t device[64], queue[64], window[64], builder[64], texture_a[64], texture_b[64];
static void (*present)(void *queue, void *window, int index);

EXPORT void game_boot(void) {
    getproc_fn getproc = (getproc_fn)nvnBootstrapLoader("nvnDeviceGetProcAddress");
    int (*init)(void *, const void *) = (int (*)(void *, const void *))getproc(0, "nvnDeviceInitialize");
    init(device, builder);
    void (*set)(void *, int, void *const *) = (void (*)(void *, int, void *const *))getproc(device, "nvnWindowBuilderSetTextures");
    void *const textures[2] = { texture_a, texture_b };
    set(builder, 2, textures);
    present = (void (*)(void *, void *, int))getproc(device, "nvnQueuePresentTexture");
}

EXPORT void game_present(int index) { present(queue, window, index); }

// ---- controller polling: player 1 as a Pro Controller, then the handheld ----
EXPORT void game_poll(int ask_style_set) {
    uint32_t id = 0;
    if (ask_style_set)
        _ZN2nn3hid15GetNpadStyleSetERKj(&id);
    game_state_count[0] = _ZN2nn3hid13GetNpadStatesEPNS0_16NpadFullKeyStateEiRKj(game_states[0], 4, &id);
    id = 0x20;
    if (ask_style_set)
        _ZN2nn3hid15GetNpadStyleSetERKj(&id);
    game_state_count[1] = _ZN2nn3hid13GetNpadStatesEPNS0_17NpadHandheldStateEiRKj(game_states[1], 4, &id);
}

// The other three styles are imported, as in the game, and not called by this test.
EXPORT void *game_unused_imports(int which) {
    return which == 0 ? (void *)_ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyDualStateEiRKj
         : which == 1 ? (void *)_ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyLeftStateEiRKj
                      : (void *)_ZN2nn3hid13GetNpadStatesEPNS0_17NpadJoyRightStateEiRKj;
}

EXPORT void game_read_motion(void) {
    static uint8_t states[0x60];
    uint32_t handle = 0x20000010;
    _ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE(states, 1, &handle);
}

// ---- the movement update (fake_main_move.S) ----
void move_update(void *actor);
__attribute__((visibility("hidden"))) void record_move(void *actor) {
    game_moved_actor = actor;
    game_moves++;
}
EXPORT void game_move(void *actor) { move_update(actor); }
