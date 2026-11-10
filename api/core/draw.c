// Drawing rectangles over the game's picture, through the game's own graphics library (NVN).
//
// The game asks nvnBootstrapLoader for nvnDeviceGetProcAddress and then fetches every NVN function
// by name through that. Core swaps main's GOT slot for nvnBootstrapLoader, so it can hand the game
// its own versions of three of those functions:
//
//   nvnDeviceInitialize          to learn the device
//   nvnWindowBuilderSetTextures  to learn the textures the game presents
//   nvnQueuePresentTexture       to draw just before each frame is shown
//
// A rectangle is drawn as a clear with a scissor on the texture about to be presented: no shaders
// and no pixel data. Function signatures and constants are NVN's as publicly documented for the
// first Switch; object storage is oversized in case the second one's objects are larger.
#include "core.h"

typedef struct nvn_device nvn_device;
typedef struct nvn_queue nvn_queue;
typedef struct nvn_window nvn_window;
typedef struct nvn_texture nvn_texture;
typedef struct { _Alignas(16) uint8_t bytes[0x800]; } nvn_object;   // builders, pools, command buffers
typedef void *(*getproc_fn)(nvn_device *, const char *);

extern void *nvnBootstrapLoader(const char *name);   // exported by sdk
void *aligned_alloc(size_t align, size_t size);      // exported by main

static struct {
    void (*pool_builder_defaults)(nvn_object *);
    void (*pool_builder_device)(nvn_object *, nvn_device *);
    void (*pool_builder_flags)(nvn_object *, int);
    void (*pool_builder_storage)(nvn_object *, void *, size_t);
    bool (*pool_init)(nvn_object *, const nvn_object *);
    bool (*cmd_init)(nvn_object *, nvn_device *);
    void (*cmd_add_command)(nvn_object *, const nvn_object *pool, ptrdiff_t offset, size_t size);
    void (*cmd_add_control)(nvn_object *, void *, size_t);
    void (*cmd_begin)(nvn_object *);
    uint64_t (*cmd_end)(nvn_object *);
    void (*cmd_targets)(nvn_object *, int count, nvn_texture *const *colors, const void *const *views,
                        const nvn_texture *depth, const void *depth_view);
    void (*cmd_scissor)(nvn_object *, int x, int y, int w, int h);
    void (*cmd_clear)(nvn_object *, int index, const float *rgba, int mask);
    void (*queue_submit)(nvn_queue *, int count, const uint64_t *handles);
    int (*texture_width)(const nvn_texture *);
    int (*texture_height)(const nvn_texture *);
    int (*origin_mode)(const nvn_device *);
} nvn;

static const char *const nvn_names[] = {
    "nvnMemoryPoolBuilderSetDefaults", "nvnMemoryPoolBuilderSetDevice", "nvnMemoryPoolBuilderSetFlags",
    "nvnMemoryPoolBuilderSetStorage", "nvnMemoryPoolInitialize", "nvnCommandBufferInitialize",
    "nvnCommandBufferAddCommandMemory", "nvnCommandBufferAddControlMemory", "nvnCommandBufferBeginRecording",
    "nvnCommandBufferEndRecording", "nvnCommandBufferSetRenderTargets", "nvnCommandBufferSetScissor",
    "nvnCommandBufferClearColor", "nvnQueueSubmitCommands", "nvnTextureGetWidth", "nvnTextureGetHeight",
    "nvnDeviceGetWindowOriginMode",
};
#define NVN_COUNT (sizeof nvn_names / sizeof *nvn_names)
_Static_assert(sizeof nvn == NVN_COUNT * sizeof(void *), "nvn table");

enum {
    POOL_CPU_UNCACHED = 0x02, POOL_GPU_CACHED = 0x20,
    ORIGIN_LOWER_LEFT = 0,
    CLEAR_RGBA = 0xF,
    SCISSOR_EVERYTHING = 65535,
};

// Command memory is used in turns: a frame's commands sit in one part, and that part is only
// written again SLOTS frames later, long after the GPU has run them.
#define SLOTS         8
#define COMMAND_BYTES 0x4000
#define CONTROL_BYTES 0x1000
#define MAX_RECTS     128
#define MAX_TEXTURES  8

static void *(*real_bootstrap)(const char *);
static getproc_fn real_getproc;
static void (*real_present)(nvn_queue *, nvn_window *, int);
static void (*real_set_textures)(void *builder, int count, nvn_texture *const *textures);
static bool (*real_device_init)(nvn_device *, const void *builder);

static nvn_device *device;
static nvn_texture *textures[MAX_TEXTURES];
static int texture_count;

static enum { NOT_SET_UP, READY, FAILED } state;
static nvn_object pool, commands;
static uint8_t *control_memory;
static bool lower_left;
static uint64_t frame_number;

static struct { int x, y, w, h; uint32_t rgb; } rects[MAX_RECTS];
static int rect_count;
static bool in_draw;
static int frame_width, frame_height;

static bool equal(const char *a, const char *b) {
    for (; *a == *b; a++, b++)
        if (!*a)
            return true;
    return false;
}

void kp_draw_rect(int x, int y, int w, int h, uint32_t rgb) {
    if (!in_draw || rect_count == MAX_RECTS)
        return;
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > frame_width) w = frame_width - x;
    if (y + h > frame_height) h = frame_height - y;
    if (w <= 0 || h <= 0)
        return;
    rects[rect_count].x = x; rects[rect_count].y = y;
    rects[rect_count].w = w; rects[rect_count].h = h;
    rects[rect_count].rgb = rgb;
    rect_count++;
}

static void set_up(void) {
    state = FAILED;
    void **table = (void **)&nvn;
    for (size_t i = 0; i < NVN_COUNT; i++) {
        table[i] = real_getproc(device, nvn_names[i]);
        if (!table[i]) {
            kp_log("drawing off: the game's NVN has no");
            kp_log(nvn_names[i]);
            return;
        }
    }
    void *command_memory = aligned_alloc(0x1000, SLOTS * COMMAND_BYTES);
    control_memory = aligned_alloc(0x1000, SLOTS * CONTROL_BYTES);
    if (!command_memory || !control_memory) {
        kp_log("drawing off: no memory");
        return;
    }
    nvn_object builder;
    nvn.pool_builder_defaults(&builder);
    nvn.pool_builder_device(&builder, device);
    nvn.pool_builder_flags(&builder, POOL_CPU_UNCACHED | POOL_GPU_CACHED);
    nvn.pool_builder_storage(&builder, command_memory, SLOTS * COMMAND_BYTES);
    if (!nvn.pool_init(&pool, &builder)) {
        kp_log("drawing off: memory pool");
        return;
    }
    if (!nvn.cmd_init(&commands, device)) {
        kp_log("drawing off: command buffer");
        return;
    }
    lower_left = nvn.origin_mode(device) == ORIGIN_LOWER_LEFT;
    state = READY;
    kp_log_2("drawing ready. swapchain textures, origin lower left:", texture_count, lower_left);
}

static void draw(nvn_queue *queue, nvn_texture *target) {
    frame_width = nvn.texture_width(target);
    frame_height = nvn.texture_height(target);
    if (frame_number == 0)
        kp_log_2("first frame, picture size", frame_width, frame_height);
    kp_frame_t frame = { frame_width, frame_height, frame_number };
    rect_count = 0;
    in_draw = true;
    mod_draw(&frame);
    in_draw = false;
    frame_number++;
    if (!rect_count)
        return;

    int slot = (int)(frame_number % SLOTS);
    nvn.cmd_add_command(&commands, &pool, (ptrdiff_t)slot * COMMAND_BYTES, COMMAND_BYTES);
    nvn.cmd_add_control(&commands, control_memory + slot * CONTROL_BYTES, CONTROL_BYTES);
    nvn.cmd_begin(&commands);
    nvn.cmd_targets(&commands, 1, &target, 0, 0, 0);
    for (int i = 0; i < rect_count; i++) {
        float rgba[4] = { (float)((rects[i].rgb >> 16) & 255) / 255.0f, (float)((rects[i].rgb >> 8) & 255) / 255.0f,
                          (float)(rects[i].rgb & 255) / 255.0f, 1.0f };
        int y = lower_left ? frame_height - rects[i].y - rects[i].h : rects[i].y;
        nvn.cmd_scissor(&commands, rects[i].x, y, rects[i].w, rects[i].h);
        nvn.cmd_clear(&commands, 0, rgba, CLEAR_RGBA);
    }
    nvn.cmd_scissor(&commands, 0, 0, SCISSOR_EVERYTHING, SCISSOR_EVERYTHING);
    uint64_t handle = nvn.cmd_end(&commands);
    nvn.queue_submit(queue, 1, &handle);
}

static int presents_seen;

static void my_present(nvn_queue *queue, nvn_window *window, int index) {
    if (presents_seen++ == 0)
        kp_log_2("first present. device known, textures:", device != 0, texture_count);
    if (state == NOT_SET_UP && device && real_getproc)
        set_up();
    if (state == READY && index >= 0 && index < texture_count && textures[index])
        draw(queue, textures[index]);
    real_present(queue, window, index);
}

static void my_set_textures(void *builder, int count, nvn_texture *const *list) {
    texture_count = count < 0 ? 0 : count > MAX_TEXTURES ? MAX_TEXTURES : count;
    kp_log_2("swapchain textures set:", count, 0);
    for (int i = 0; i < texture_count; i++)
        textures[i] = list[i];
    real_set_textures(builder, count, list);
}

static bool my_device_init(nvn_device *d, const void *builder) {
    bool ok = real_device_init(d, builder);
    if (ok)
        device = d;
    kp_log_2("device initialised:", ok, 0);
    return ok;
}

// The three functions Core wraps, whichever way the game asks for them (through
// nvnDeviceGetProcAddress or straight from nvnBootstrapLoader).
static void *wrap(const char *name, void *f) {
    if (!f || !name)
        return f;
    if (equal(name, "nvnQueuePresentTexture")) {
        real_present = f;
        kp_log("wrapped nvnQueuePresentTexture");
        return my_present;
    }
    if (equal(name, "nvnWindowBuilderSetTextures")) {
        real_set_textures = f;
        return my_set_textures;
    }
    if (equal(name, "nvnDeviceInitialize")) {
        real_device_init = f;
        return my_device_init;
    }
    return f;
}

static void *my_getproc(nvn_device *d, const char *name) {
    if (d && !device)
        device = d;   // the game passes its device when it fetches device functions
    return wrap(name, real_getproc(d, name));
}

static void *my_bootstrap(const char *name) {
    void *f = real_bootstrap(name);
    if (f && name && equal(name, "nvnDeviceGetProcAddress")) {
        real_getproc = f;
        kp_log("the game asked for NVN: drawing hooks in place");
        return my_getproc;
    }
    return wrap(name, f);
}

bool kp_draw_start(void) {
    uintptr_t *slot = kp_import_slot(kp_main, "nvnBootstrapLoader");
    if (!slot)
        return false;
    // The slot holds a pointer into main until the first call (the import is bound lazily): then
    // the real function is the one rtld gave this module. Anything else in the slot is another
    // module's hook, which stays in the chain.
    uintptr_t now = *slot;
    bool unbound = now >= kp_main && now < kp_main + kp_build->size;
    real_bootstrap = unbound || !now ? nvnBootstrapLoader : (void *(*)(const char *))now;
    *slot = (uintptr_t)my_bootstrap;
    return true;
}
