// Mouse Grab was written against Core's first skeleton, whose functions were named kp_. This
// header gives those names to the public API (kaepora.h), so the mod's files didn't need to change
// when Core became its own module. New code should use kaepora.h directly.
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <kaepora.h>

typedef KaeFrame kp_frame_t;

// main's base address, set in the mod's start. Mouse Grab is a research build: it still reaches
// into the game by raw offset (KP_FN) and not by name.
extern uintptr_t mg_main;
#define kp_main mg_main
#define KP_FN(type, offset) ((type)(kp_main + (offset)))

#define kp_log(text)             KAE_LOG("%s", (text))
#define kp_log_hex(text, value)  KAE_LOG("%s 0x%llx", (text), (unsigned long long)(value))
#define kp_log_2(text, a, b)     KAE_LOG("%s %lld %lld", (text), (long long)(a), (long long)(b))
void kp_log_floats(const char *text, const float *values, int count);   // in thousandths, up to 12

#define kp_readable(address, size)                 (kae_readable((const void *)(address), (size)) != 0)
#define kp_draw_rect(x, y, w, h, rgb)              kae_draw_rect((x), (y), (w), (h), (rgb))
#define kp_motion_direction(out)                   kae_motion_direction(out)
