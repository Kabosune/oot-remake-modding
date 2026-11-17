// Mouse Grab was written against Core's first skeleton, whose functions were named kp_. This
// header gives those names to the public API (kaegae.h), so the mod's files didn't need to change
// when Core became its own module. New code should use kaegae.h directly.
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <kaegae.h>

typedef KaeFrame kp_frame_t;

// The game's functions, data and vtables Mouse Grab uses, by name from Core's symbol pack (0.4.0):
// the same names on every game version Core knows (1.0.0 and 1.1.1). symbols.c looks them all up
// in the mod's start; if one is missing there, the mod doesn't start (and says which).
enum {
    F_HOLDER, F_FIND_RAGDOLL, F_RAGDOLL_DOWN, F_RAGDOLL_END, F_PREP_SPEED, F_PREP_A, F_PREP_B, F_PREP_STATE,
    F_REACTION, F_REACTION_ACTIVE, F_REACTION_END, F_AS_PLAY, F_SET_VELOCITY, F_CHANGE_POS,
    G_ZERO, G_NAMES, CAMERA_SLOT, VT_ACTOR, VT_PLAYER, VT_CCT, BODY_VT, MG_SYM_COUNT
};
extern uintptr_t mg_sym[MG_SYM_COUNT];
const char *mg_symbols_start(void);   // 0 if every name was found, else the first missing one
#define KP_FN(type, which) ((type)mg_sym[which])
#define KP_ADDR(which)     (mg_sym[which])

// Research output, written only with the "Debug log" setting on. Lines a player needs (the build,
// something missing) use KAE_LOG directly.
#include "settings.h"
#define kp_debug                 (MG(MG_DEBUG_LOG) != 0)
#define kp_log(text)             do { if (kp_debug) KAE_LOG("%s", (text)); } while (0)
#define kp_log_hex(text, value)  do { if (kp_debug) KAE_LOG("%s 0x%llx", (text), (unsigned long long)(value)); } while (0)
#define kp_log_2(text, a, b)     do { if (kp_debug) KAE_LOG("%s %lld %lld", (text), (long long)(a), (long long)(b)); } while (0)
void kp_log_floats(const char *text, const float *values, int count);   // in thousandths, up to 12

#define kp_readable(address, size)                 (kae_readable((const void *)(address), (size)) != 0)
#define kp_draw_rect(x, y, w, h, rgb)              kae_draw_rect((x), (y), (w), (h), (rgb))
#define kp_motion_direction(out)                   kae_motion_direction(out)
