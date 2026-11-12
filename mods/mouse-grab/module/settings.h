// Mouse Grab's page in the Mods menu. The values are read where they're used; Core saves them
// between runs (Core 0.5.2 and later).
#pragma once
#include <kaegae.h>

enum {
    MG_GYRO_SPEED,      // % of 1.5 m of depth per radian of controller pitch; 0 = off
    MG_GYRO_INVERT,
    MG_GYRO_DEADZONE,   // tenths of a radian per second
    MG_GYRO_SMOOTHING,  // % of a frame's turn that counts at once
    MG_GRAB_RADIUS,     // cm from the cursor's ray
    MG_PULL,            // per second: how fast the held character catches up with the cursor
    MG_MAX_SPEED,       // m/s
    MG_THROW,           // % of the cursor's speed given on letting go
    MG_GRAB_OTHERS,
    MG_VOICE,
    MG_FACE,
    MG_CURSOR,
    MG_CURSOR_SIZE,     // 0 = by screen size, else 1..3
    MG_DEBUG_LOG,
    MG_COUNT
};

extern KaeItem mg_settings[MG_COUNT];
#define MG(i) (mg_settings[i].value)
void mg_settings_start(void);
