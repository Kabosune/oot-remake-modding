/* Kaepora Core API, draft 0.1. A design sketch: Core does not exist yet. See ../DESIGN.md. */
#ifndef KAEPORA_H
#define KAEPORA_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KAE_API_MAJOR 0
#define KAE_API_MINOR 1

typedef struct KaeMod KaeMod;

/* What a mod hands to Core. Grows at the end only; `size` says how much the mod knows about. */
struct KaeMod {
    uint32_t    size;                 /* sizeof(KaeMod) when the mod was built */
    uint16_t    api_major, api_minor; /* KAE_API_MAJOR / KAE_API_MINOR when the mod was built */
    const char *id;                   /* "author.mod-name", same as the manifest */
    const char *version;              /* semver */
    int       (*start)(void);         /* called once, after every module is loaded; 0 = ok */
    void      (*stop)(void);          /* may be null */
    KaeMod     *next;                 /* Core's; leave null */
};

/* The only call allowed from a module's init function. Only links the mod into a list. */
void kae_register(KaeMod *mod);

/* ---- queries -------------------------------------------------------------------------- */

int         kae_has(const char *feature);          /* "draw.text", "event.view", ... */
const char *kae_game_build(void);                  /* main's build ID as hex text */
void       *kae_sym(const char *name);             /* a function or global by name; null if unknown */
int64_t     kae_field(const char *name);           /* a field offset by name; -1 if unknown */

/* ---- events --------------------------------------------------------------------------- */

typedef struct {
    uint32_t size;
    uint64_t buttons;          /* same bits as the system's controller state */
    int32_t  lx, ly, rx, ry;
    uint32_t controller;       /* 0 = player 1, 0x20 = handheld */
} KaeInput;

typedef struct {
    uint32_t size;
    float    matrix[3][4];     /* row 0 right, row 1 up, row 2 back; column 3 = -(row . eye) */
    double   eye[3], target[3];
} KaeView;

typedef void (*KaeFrameFn)(void *user);
typedef void (*KaeInputFn)(KaeInput *seen_by_game, const KaeInput *real, void *user);
typedef void (*KaeViewFn)(KaeView *view, void *user);

/* priority: lower runs first; 0 is normal. Returns 0, or a negative error. */
int kae_on_frame(KaeFrameFn fn, void *user, int priority);
int kae_on_input(KaeInputFn fn, void *user, int priority);
int kae_on_view (KaeViewFn  fn, void *user, int priority);

/* ---- hook points (named places inside the game's code, from the symbol pack) -------------- */

typedef struct {
    uint32_t size;
    uint64_t x[31];
    uint64_t sp;
    double   d[32];
} KaeRegs;

typedef void (*KaeHookFn)(KaeRegs *regs, void *user);
int kae_hook(const char *hookpoint, KaeHookFn fn, void *user, int priority);

/* ---- input bindings --------------------------------------------------------------------- */

typedef uint32_t KaeAction;
KaeAction kae_action(const char *name, const char *default_binding);  /* "toggle", "L3" */
int       kae_pressed(KaeAction action);     /* went down this frame */
int       kae_held(KaeAction action);
void      kae_capture(KaeAction action, int on);   /* hide the action's buttons from the game */

/* ---- config and log --------------------------------------------------------------------- */

double      kae_config_number(const char *key, double default_value);
const char *kae_config_text(const char *key, const char *default_value);
void        kae_log(const char *format, ...);

/* ---- memory ----------------------------------------------------------------------------- */

void *kae_alloc(size_t size);
void  kae_free(void *p);

/* A mod's module init:
 *
 *     static KaeMod mod = { sizeof mod, KAE_API_MAJOR, KAE_API_MINOR,
 *                           "kabosune.first-person", "2.0.0", start, 0, 0 };
 *     void module_init(void) { kae_register(&mod); }
 */

#ifdef __cplusplus
}
#endif
#endif
