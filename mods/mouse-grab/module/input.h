#pragma once
#include <stdint.h>

typedef struct {
    int64_t sample;
    int32_t x, y;            // 0..1279, 0..719
    int32_t dx, dy;
    int32_t wheel_x, wheel_y;
    uint32_t buttons;        // bit 0 left, bit 1 right, bit 2 middle
    uint32_t attributes;     // bit 1: a mouse is connected
} mouse_state_t;
_Static_assert(sizeof(mouse_state_t) == 0x28, "nn::hid::MouseState");

// nn::hid::GetMouseStates(nn::hid::MouseState*, int), exported by sdk
int _ZN2nn3hid14GetMouseStatesEPNS0_10MouseStateEi(mouse_state_t *states, int count);
