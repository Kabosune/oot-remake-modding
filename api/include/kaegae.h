/* KaeGae Core API 0.2. See ../DESIGN.md for the rules behind it and ../CHANGELOG.md for changes.
 *
 * A mod is plain C (or anything that can call C). The whole of a small mod:
 *
 *     #include <kaegae.h>
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
#ifndef KAEGAE_H
#define KAEGAE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define KAE_API_MAJOR 0
#define KAE_API_MINOR 4

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
                                                      "draw.rect" "draw.text" "draw.image" "motion" "symbols"
                                                      "alloc" "menu" */
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
/* Text in Core's built-in font: 8 x 16 pixels a character, times `scale` (1, 2, 3...). (x, y) is the
   top left of the first character; "\n" starts a new line under it. UTF-8; the font has ASCII and
   Latin-1 (U+00A0 to U+00FF), anything else shows as "?". Returns the x where the next character
   would go. Only inside a draw function. */
KAE_API int  kae_draw_text(int x, int y, int scale, uint32_t rgb, const char *text);
/* The size in pixels kae_draw_text would cover (the widest line; every line). Usable anywhere. */
KAE_API int  kae_text_width(int scale, const char *text);
KAE_API int  kae_text_height(int scale, const char *text);
/* A picture of w x h pixels, each 0xAARRGGBB, rows from the top, drawn with every pixel `scale`
   pixels wide and high. For now a pixel is either drawn solid (alpha 0x80 and up) or left out:
   made for small pixel art such as cursors and icons. Only inside a draw function. */
KAE_API void kae_draw_image(int x, int y, int w, int h, const uint32_t *argb, int scale);

/* ---- settings and the Mods menu ------------------------------------------------------------ */

/* Core draws one shared menu, "Mods", opened with - and + pressed together. Every mod is listed
   there and can be switched off (it then gets no events). A mod that calls kae_settings gets a
   page of settings in it. While the menu is open the game sees no buttons or sticks. */

/* Controller buttons, the same bits as KaeInput.buttons. */
enum {
    KAE_A = 1 << 0, KAE_B = 1 << 1, KAE_X = 1 << 2, KAE_Y = 1 << 3, KAE_L3 = 1 << 4, KAE_R3 = 1 << 5,
    KAE_L = 1 << 6, KAE_R = 1 << 7, KAE_ZL = 1 << 8, KAE_ZR = 1 << 9, KAE_PLUS = 1 << 10,
    KAE_MINUS = 1 << 11, KAE_LEFT = 1 << 12, KAE_UP = 1 << 13, KAE_RIGHT = 1 << 14, KAE_DOWN = 1 << 15,
};

typedef enum { KAE_TOGGLE, KAE_CHOICE, KAE_NUMBER, KAE_BINDING, KAE_ACTION } KaeItemType;

/* One line of a mod's page. The mod owns the array and reads `value` / `binding` whenever it
   likes; Core changes them when the player does, then calls `changed` (on the game's thread). */
typedef struct KaeItem KaeItem;
struct KaeItem {
    KaeItemType type;
    const char *label;
    const char *help;                 /* one line shown under the list; may be null */
    int value, def;                   /* toggle 0/1, choice index, number */
    int min, max, step;               /* number; for a choice, max = the last index */
    const char *const *choices;       /* choice: `max + 1` names */
    uint64_t binding, def_binding;    /* binding: button mask, 0 = unbound */
    void (*changed)(KaeItem *item, void *user);   /* after any change; for an action, on A */
    void *user;
};

/* Gives the calling mod its page: a display name and its settings. Only inside the mod's start;
   `name` and `items` must stay valid. Settings are not saved between runs yet. */
KAE_API int kae_settings(const char *name, KaeItem *items, int count);
/* 1 while the Mods menu is open. A mod that reacts to buttons itself should hold still then. */
KAE_API int kae_menu_open(void);

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
