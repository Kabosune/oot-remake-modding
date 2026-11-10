// A stand-in for the system's sdk module: the functions Core and the test mods import, with
// made-up behaviour the test can steer and read back. Nothing here comes from the system.
#include <stddef.h>
#include <stdint.h>

#define EXPORT __attribute__((visibility("default")))

static int same(const char *a, const char *b) {
    for (; *a == *b; a++, b++)
        if (!*a)
            return 1;
    return 0;
}

// ---- controllers ----
typedef struct {
    int64_t sample;
    uint64_t buttons;
    int32_t lx, ly, rx, ry;
    uint32_t attributes, pad;
} npad_state_t;

EXPORT uint64_t sdk_buttons;                     // what the controllers report
EXPORT int32_t sdk_lx, sdk_ly, sdk_rx, sdk_ry;
EXPORT int sdk_style_calls, sdk_state_calls;

static int fill(npad_state_t *out, int count) {
    sdk_state_calls++;
    int n = count < 3 ? count : 3;
    for (int i = 0; i < n; i++)
        out[i] = (npad_state_t){ 100 - i, sdk_buttons, sdk_lx, sdk_ly, sdk_rx, sdk_ry, 1, 0 };
    return n;
}

EXPORT int _ZN2nn3hid13GetNpadStatesEPNS0_16NpadFullKeyStateEiRKj(npad_state_t *o, int n, const uint32_t *id) { (void)id; return fill(o, n); }
EXPORT int _ZN2nn3hid13GetNpadStatesEPNS0_17NpadHandheldStateEiRKj(npad_state_t *o, int n, const uint32_t *id) { (void)id; return fill(o, n); }
EXPORT int _ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyDualStateEiRKj(npad_state_t *o, int n, const uint32_t *id) { (void)id; return fill(o, n); }
#ifndef OLD_SDK   // a system that lacks some of the names Core hopes for
EXPORT int _ZN2nn3hid13GetNpadStatesEPNS0_16NpadJoyLeftStateEiRKj(npad_state_t *o, int n, const uint32_t *id) { (void)id; return fill(o, n); }
EXPORT int _ZN2nn3hid13GetNpadStatesEPNS0_17NpadJoyRightStateEiRKj(npad_state_t *o, int n, const uint32_t *id) { (void)id; return fill(o, n); }
EXPORT uint32_t _ZN2nn3hid15GetNpadStyleSetERKj(const uint32_t *id) {
    sdk_style_calls++;
    return *id == 0x20 ? 2 : 1;
}
#endif

typedef struct {
    int64_t delta_time, sample;
    float acceleration[3], angular_velocity[3], angle[3], direction[9];
    uint32_t attributes, pad;
} six_axis_state_t;

EXPORT int _ZN2nn3hid22GetSixAxisSensorStatesEPNS0_18SixAxisSensorStateEiRKNS0_19SixAxisSensorHandleE(
        six_axis_state_t *out, int count, const uint32_t *handle) {
    (void)handle;
    if (count < 1)
        return 0;
    *out = (six_axis_state_t){ 0 };
    out->acceleration[2] = -1.0f;
    for (int i = 0; i < 9; i++)
        out->direction[i] = 0.5f + (float)i;
    return 1;
}

typedef struct {
    int64_t sample;
    int32_t x, y, dx, dy, wheel_x, wheel_y;
    uint32_t buttons, attributes;
} mouse_state_t;

EXPORT int _ZN2nn3hid14GetMouseStatesEPNS0_10MouseStateEi(mouse_state_t *out, int count) {
    if (count < 1)
        return 0;
    *out = (mouse_state_t){ 1, 640, 360, 0, 0, 0, 0, 0, 2 };
    return 1;
}

// ---- NVN: just enough to see what Core draws ----
typedef struct { int x, y, w, h; uint32_t rgb; } rect_t;
EXPORT rect_t sdk_rects[1024];          // the clears of the newest frame, with their scissor
EXPORT int sdk_rect_count, sdk_submits, sdk_presents, sdk_other_hook_calls;
static int scissor[4];

static void nothing(void) {}
static int yes(void) { return 1; }
// Command memory, counted the way NVN would: each clear with its scissor costs RECT_COST bytes.
#define RECT_COST 72
static size_t command_left;
EXPORT int sdk_overruns;               // clears recorded with no command memory left: must stay 0
static void add_command(void *cmd, const void *pool, long offset, size_t size) { (void)cmd; (void)pool; (void)offset; command_left = size; }
__attribute__((unused)) static size_t command_free(const void *cmd) { (void)cmd; return command_left; }
__attribute__((unused)) static size_t control_free(const void *cmd) { (void)cmd; return 0x800; }
static void set_scissor(void *cmd, int x, int y, int w, int h) {
    (void)cmd;
    scissor[0] = x; scissor[1] = y; scissor[2] = w; scissor[3] = h;
}
static void clear(void *cmd, int index, const float *rgba, int mask) {
    (void)cmd; (void)index; (void)mask;
    if (command_left < RECT_COST)
        sdk_overruns++;
    else
        command_left -= RECT_COST;
    if (sdk_rect_count < 1024)
        sdk_rects[sdk_rect_count++] = (rect_t){ scissor[0], scissor[1], scissor[2], scissor[3],
            ((uint32_t)(rgba[0] * 255.0f + 0.5f) << 16) | ((uint32_t)(rgba[1] * 255.0f + 0.5f) << 8) | (uint32_t)(rgba[2] * 255.0f + 0.5f) };
}
static void begin(void *cmd) { (void)cmd; sdk_rect_count = 0; }
static uint64_t end(void *cmd) { (void)cmd; return 0x1234; }
static void submit(void *queue, int count, const uint64_t *handles) { (void)queue; (void)count; (void)handles; sdk_submits++; }
static void present(void *queue, void *window, int index) { (void)queue; (void)window; (void)index; sdk_presents++; }
static int width(const void *t) { (void)t; return 1280; }
static int height(const void *t) { (void)t; return 720; }
static int origin(const void *d) { (void)d; return 0; }   // lower left, so Core has to flip y

static void *getproc(void *device, const char *name) {
    (void)device;
    static const struct { const char *name; void *fn; } table[] = {
        { "nvnDeviceInitialize", yes }, { "nvnWindowBuilderSetTextures", nothing }, { "nvnQueuePresentTexture", present },
        { "nvnMemoryPoolBuilderSetDefaults", nothing }, { "nvnMemoryPoolBuilderSetDevice", nothing },
        { "nvnMemoryPoolBuilderSetFlags", nothing }, { "nvnMemoryPoolBuilderSetStorage", nothing },
        { "nvnMemoryPoolInitialize", yes }, { "nvnCommandBufferInitialize", yes },
        { "nvnCommandBufferAddCommandMemory", add_command }, { "nvnCommandBufferAddControlMemory", nothing },
        { "nvnCommandBufferBeginRecording", begin }, { "nvnCommandBufferEndRecording", end },
        { "nvnCommandBufferSetRenderTargets", nothing }, { "nvnCommandBufferSetScissor", set_scissor },
        { "nvnCommandBufferClearColor", clear }, { "nvnQueueSubmitCommands", submit },
        #ifndef OLD_SDK
        { "nvnCommandBufferGetCommandMemoryFree", command_free }, { "nvnCommandBufferGetControlMemoryFree", control_free },
#endif
        { "nvnTextureGetWidth", width }, { "nvnTextureGetHeight", height }, { "nvnDeviceGetWindowOriginMode", origin },
    };
    for (size_t i = 0; i < sizeof table / sizeof *table; i++)
        if (same(name, table[i].name))
            return table[i].fn;
    return 0;
}

EXPORT void *nvnBootstrapLoader(const char *name) {
    return same(name, "nvnDeviceGetProcAddress") ? (void *)getproc : getproc(0, name);
}

// Another module's hook on main's nvnBootstrapLoader slot, in place before Core starts.
EXPORT void *sdk_other_hook(const char *name) {
    sdk_other_hook_calls++;
    return nvnBootstrapLoader(name);
}
