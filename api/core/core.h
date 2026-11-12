// KaeGae Core: what Core's own source files share. Mods use ../include/kaegae.h instead.
#pragma once
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "kaegae.h"

// Hardware test switches (tools/kaemod.py --define NAME), off in normal builds:
//   KAE_NO_DEBUG_OUT  the log writes nothing (no svcOutputDebugString)
//   KAE_LOAD_ONLY     the module's start returns at once: Core and its mods do nothing

// ---- log (svcOutputDebugString; shows up in an emulator's log) ----
void kp_log(const char *text);
void kp_logf(const char *format, ...) __attribute__((format(printf, 1, 2)));
void kp_log_hex(const char *text, uint64_t value);                  // "text 0x1234"
void kp_log_2(const char *text, int64_t a, int64_t b);              // "text 12 34"
// Writes at most cap - 1 characters and a 0; returns the length written.
size_t kp_vformat(char *out, size_t cap, const char *format, va_list args);

// ---- the system (platform.c; the tests swap in their own) ----
void kp_debug_out(const char *text, size_t length);
bool kp_readable(uintptr_t address, size_t size);   // mapped and readable

// ---- locks (two threads call into Core: the game's and its render thread) ----
typedef volatile char kp_lock_t;
static inline void kp_lock(kp_lock_t *l) { while (__atomic_test_and_set(l, __ATOMIC_ACQUIRE)) {} }
static inline void kp_unlock(kp_lock_t *l) { __atomic_clear(l, __ATOMIC_RELEASE); }

// ---- the game: one entry per symbol pack (generated, see tools/kaegae_symbols.py) ----
typedef struct { const char *name; uint32_t offset; } kp_sym_t;
typedef struct { const char *name; uint32_t site; uint32_t slot; } kp_hookpoint_t;
typedef struct {
    const char *version;     // "1.1.1"
    const char *build_id;    // 40 hex digits
    uint32_t nnmain;         // module offset of nnMain
    uint32_t mod0;           // module offset of MOD0
    uint32_t size;           // mapped size of main
    uint32_t hook_slots;     // module offset of the hook slots (function pointers)
    const kp_sym_t *syms;    // sorted by name
    uint32_t sym_count;
    const kp_sym_t *fields;  // sorted by name
    uint32_t field_count;
    const kp_hookpoint_t *hookpoints;
    uint32_t hookpoint_count;
} kp_build_t;

extern const kp_build_t kp_builds[];
extern const unsigned kp_build_count;

extern uintptr_t kp_main;            // main's base address, 0 if the build isn't known
extern const kp_build_t *kp_build;

// The address of the GOT slot through which `module` calls the import `name`, or 0.
uintptr_t *kp_import_slot(uintptr_t module, const char *name);
// Puts `wrapper` in main's slot for the import `name`. Returns the function to call instead:
// whatever another module had put there, or `own`, Core's own import of the same function.
// Null, and nothing changed, if main doesn't import it or there would be nothing to call.
void *kp_wrap_import(const char *name, void *wrapper, void *own);

// ---- mods ----
// Starts every registered mod, once; later calls do nothing. Every entry from the game calls it.
void kp_mods_ready(void);
// The mod whose start function is running, or null.
KaeMod *kp_mod_starting(void);

// ---- events ----
enum { KP_EV_FRAME, KP_EV_INPUT, KP_EV_DRAW, KP_EV_ACTOR_MOVE, KP_EV_PLAYER_MOVE, KP_EV_COUNT };
extern bool kp_event_on[KP_EV_COUNT];   // set by the service that feeds the event

void kp_fire_frame(void);
void kp_fire_input(KaeInput *seen, const KaeInput *real);
void kp_fire_draw(const KaeFrame *frame);
void kp_fire_actor_move(void *actor);
bool kp_wants_player_move(void);                 // someone subscribed: worth looking for Link
void kp_fire_player_move(const KaePlayer *link);
void kp_unsubscribe_mod(const KaeMod *mod);

// ---- the Mods menu (menu.c) ----
void kp_menu_start(void);                                   // after the other services
void kp_menu_add_mod(const KaeMod *mod, const char *status); // status: null, or why the mod is off
bool kp_mod_off(const KaeMod *mod);                         // switched off in the menu: gets no events
bool kp_menu_on(void);
void kp_menu_frame(void);
void kp_menu_input(KaeInput *seen, const KaeInput *real);
void kp_menu_input_done(KaeInput *seen);                    // after the mods' input functions
void kp_menu_draw(int width, int height);

// ---- services, each started once from kp_module_init; false = off in this game ----
bool kp_draw_start(void);
bool kp_motion_start(void);
bool kp_input_start(void);
bool kp_hooks_start(void);
bool kp_player_start(void);                      // after kp_hooks_start
extern bool kp_player_on;
extern bool kp_motion_on;

// Mods linked into Core's own module (bundle builds); empty otherwise.
extern KaeMod *__kae_mods_start[], *__kae_mods_end[];
