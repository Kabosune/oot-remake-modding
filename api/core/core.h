// Kaepora Core, first skeleton: what the modules linked into this slot share.
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// ---- log (svcOutputDebugString; shows up in an emulator's log) ----
void kp_log(const char *text);
void kp_log_hex(const char *text, uint64_t value);                  // "text 0x1234"
void kp_log_2(const char *text, int64_t a, int64_t b);              // "text 12 34"
void kp_log_floats(const char *text, const float *values, int count); // in thousandths, up to 12

// ---- memory ----
bool kp_readable(uintptr_t address, size_t size);   // mapped and readable

// ---- the game ----
typedef struct {
    const char *name;        // "1.1.1"
    uint32_t nnmain;         // module offset of nnMain
    uint32_t mod0;           // module offset of MOD0
    uint32_t size;           // mapped size of main
} kp_build_t;

extern uintptr_t kp_main;            // main's base address, 0 if the build isn't known
extern const kp_build_t *kp_build;

// The address of the GOT slot through which `module` calls the import `name`, or 0.
uintptr_t *kp_import_slot(uintptr_t module, const char *name);

// ---- drawing over the game's picture ----
// Called on the game's render thread just before each frame is presented. Inside it, kp_draw_rect
// fills a rectangle of the picture about to be shown; (0, 0) is the top left.
typedef struct {
    int width, height;       // size of the picture in pixels
    uint64_t number;         // counts presented frames
} kp_frame_t;

void kp_draw_rect(int x, int y, int w, int h, uint32_t rgb);
bool kp_draw_start(void);            // hooks the game's NVN; false if main's import wasn't found

// ---- motion sensor ----
bool kp_motion_start(void);
// The newest direction matrix (3x3, rows) of the controller; returns how many updates so far (0: none).
uint64_t kp_motion_direction(float out[9]);

// ---- hook points (need the mod's patch to main) ----
// move(actor) runs on the game's thread for every physics actor, every frame.
bool kp_hooks_start(void (*move)(void *actor));

// ---- the game's own functions ----
// The address of a function of main by its module offset (address in symbols/ minus 0x80020000).
#define KP_FN(type, offset) ((type)(kp_main + (offset)))

// ---- the mod linked into this module ----
void mod_init(void);
void mod_draw(const kp_frame_t *frame);
