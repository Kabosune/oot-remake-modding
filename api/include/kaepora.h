/* Kaepora Core API 0.2. See ../DESIGN.md for the rules behind it and ../CHANGELOG.md for changes.
 *
 * A mod is plain C (or anything that can call C). The whole of a small mod:
 *
 *     #include <kaepora.h>
 *
 *     static void draw(const KaeFrame *frame, void *user) {
 *         kae_draw_rect(20, 20, 40, 40, 0x40C0FF);
 *     }
 *
 *     static int start(void) {
 *         KAE_LOG("hello, game version %s", kae_game_version());
 *         return kae_on_draw(draw, 0, 0);          // 0 = fine, anything else switches the mod off
 *     }
 *
 *     KAE_MOD("author.mod-name", "1.0.0", start, 0);
 *
 * Until API 1.0, Core only runs mods built against exactly its own version (0.x may still change).
 */
#ifndef KAEPORA_H
#define KAEPORA_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KAE_API_MAJOR 0
#define KAE_API_MINOR 2

/* In a mod every Core function is a weak import: if Core isn't installed the mod's module still
   loads, finds kae_register missing and does nothing. */
#ifdef KAE_BUILDING_CORE
#define KAE_API __attribute__((visibility("default")))
#else
#define KAE_API __attribute__((weak))
#endif

/* Errors are negative; 0 is success. */
enum {
    KAE_OK              = 0,
    KAE_ERR_ARGUMENT    = -1,   /* a null function, an unknown name */
    KAE_ERR_FULL        = -2,   /* no room for another subscriber */
    KAE_ERR_UNAVAILABLE = -3,   /* Core can't offer this in the running game (see kae_has) */
};

/* ---- the mod ---------------------------------------------------------------------------- */

typedef struct KaeMod KaeMod;

/* What a mod hands to Core. Grows at the end only; `size` says how much the mod knows about. */
struct KaeMod {
    uint32_t    size;                 /* sizeof(KaeMod) when the mod was built */
    uint16_t    api_major, api_minor; /* KAE_API_MAJOR / KAE_API_MINOR when the mod was built */
    const char *id;                   /* "author.mod-name", same as the manifest */
    const char *version;              /* semver */
    int       (*start)(void);         /* called once, after every module is loaded; 0 = ok */
    void      (*stop)(void);          /* may be null; called if Core switches the mod off after start */
    KaeMod     *next;                 /* Core's; leave null */
};

/* Defines the mod. Use once per mod, at file scope. The mod's build puts it where Core finds it. */
#define KAE_MOD(id_, version_, start_, stop_)                                                         \
    __attribute__((visibility("hidden")))                                                             \
    KaeMod kae_this_mod = { sizeof(KaeMod), KAE_API_MAJOR, KAE_API_MINOR, id_, version_, start_, stop_, 0 }; \
    __attribute__((used, section(".kae_mods"))) static KaeMod *kae_this_mod_entry = &kae_this_mod

__attribute__((visibility("hidden"))) extern KaeMod kae_this_mod;

/* Adds a mod to Core's list and nothing else, so it is safe whichever module starts first.
   KAE_MOD and the mod's build call it for you. */
KAE_API void kae_register(KaeMod *mod);

/* ---- queries ---------------------------------------------------------------------------- */

KAE_API uint32_t    kae_api_version(void);         /* (major << 16) | minor of the running Core */
KAE_API int         kae_has(const char *feature);  /* 1 if Core offers it in this game, else 0. Features:
                                                      "event.frame" "event.draw" "event.input" "event.actor_move"
                                                      "draw.rect" "motion" "symbols" "alloc" */
KAE_API const char *kae_game_version(void);        /* "1.1.1"; "" if the game's build isn't known */
KAE_API const char *kae_game_build(void);          /* main's build ID as 40 hex digits; "" if not known */

/* Things inside the game, by name, from the symbol pack of the running build. */
KAE_API void       *kae_sym(const char *name);     /* a function, global or "vtable.<Name>"; null if not known */
KAE_API int64_t     kae_field(const char *name);   /* a field's offset, e.g. "Actor.position"; -1 if not known */

/* The address main is loaded at (it changes from run to run); 0 if the build isn't known.
   For research builds that still use raw offsets. A released mod asks kae_sym instead. */
KAE_API uintptr_t   kae_game_base(void);

/* 1 if `size` bytes at `p` are mapped and readable. For following pointers that aren't understood yet. */
KAE_API int         kae_readable(const void *p, size_t size);

/* ---- events ----------------------------------------------------------------------------- */
/* Any number of mods can subscribe to an event. priority: lower runs first; 0 is normal; equal
   priorities run in the order they subscribed. `user` is handed back to the function. */

/* frame: once per game frame, on the thread that reads the controllers, before they are read. */
typedef void (*KaeFrameFn)(void *user);
KAE_API int kae_on_frame(KaeFrameFn fn, void *user, int priority);

/* input: each time the game reads a controller. `real` is what the controller reports;
   `seen_by_game` starts as a copy (already changed by earlier subscribers) and is what the game gets.
   Clear buttons in it to hide them from the game, set them to press them. */
typedef struct {
    uint32_t size;
    uint32_t controller;       /* 0 = player 1 ... ; 0x20 = handheld */
    uint64_t buttons;          /* bit 0 A, 1 B, 2 X, 3 Y, 4 L3, 5 R3, 6 L, 7 R, 8 ZL, 9 ZR, 10 +, 11 -,
                                  12 left, 13 up, 14 right, 15 down */
    int32_t  lx, ly, rx, ry;   /* sticks, -32767..32767 */
    uint32_t style;            /* 0 FullKey (Pro Controller), 1 handheld, 2 Joy-Con pair, 3 left, 4 right */
    uint32_t connected;
} KaeInput;
typedef void (*KaeInputFn)(KaeInput *seen_by_game, const KaeInput *real, void *user);
KAE_API int kae_on_input(KaeInputFn fn, void *user, int priority);

/* draw: on the game's render thread, just before each frame is shown. */
typedef struct {
    uint32_t size;
    int32_t  width, height;    /* the picture's size in pixels */
    uint64_t number;           /* counts frames shown */
} KaeFrame;
typedef void (*KaeDrawFn)(const KaeFrame *frame, void *user);
KAE_API int  kae_on_draw(KaeDrawFn fn, void *user, int priority);
/* Fills a rectangle of the picture; (0, 0) is the top left. Only inside a draw function. */
KAE_API void kae_draw_rect(int x, int y, int w, int h, uint32_t rgb);

/* actor_move: the movement update of every physics actor, every frame, on the game's thread,
   before the game moves it. Needs Core's patch to main (kae_has("event.actor_move")). */
typedef void (*KaeActorFn)(void *actor, void *user);
KAE_API int kae_on_actor_move(KaeActorFn fn, void *user, int priority);

/* ---- services --------------------------------------------------------------------------- */

/* The controller's motion sensor: the newest direction matrix (3x3, rows). Returns how many
   readings there have been so far (0: none yet, `out` is all zeros). */
KAE_API uint64_t kae_motion_direction(float out[9]);

/* One log for every mod (an emulator shows it in its own log). Formats: %s %c %d %i %u %x %X %p %f %%,
   with l / ll / z, a width and 0 padding (%08x), and a precision for %f (%.2f; 3 without). */
KAE_API void kae_logf(const KaeMod *mod, const char *format, ...) __attribute__((format(printf, 2, 3)));
#define KAE_LOG(...) kae_logf(&kae_this_mod, __VA_ARGS__)

/* Memory from Core's own pool, 16-byte aligned. kae_alloc returns null when it is full. */
KAE_API void *kae_alloc(size_t size);
KAE_API void  kae_free(void *p);

/* Planned, not in 0.2 (see DESIGN.md): kae_hook (any hook point by name, with the registers),
   input bindings (kae_action, kae_pressed, kae_held, kae_capture), config, text drawing, the
   view and player events. A mod can't use them by accident: its build refuses any kae_ function
   Core doesn't export. */

#ifdef __cplusplus
}
#endif
#endif
