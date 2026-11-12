// Mouse Grab's settings: its page in the Mods menu (- and + together). The defaults are the
// values the mod had built in before it had a page, except the debug log, now off by default.
#include "settings.h"

static const char *const sizes[] = { "By screen size", "Small", "Medium", "Large" };

#define TOGGLE(label, help, on)               { KAE_TOGGLE, label, help, on, on, 0, 0, 0, 0, 0, 0, 0, 0 }
#define NUMBER(label, help, v, low, high, by) { KAE_NUMBER, label, help, v, v, low, high, by, 0, 0, 0, 0, 0 }

KaeItem mg_settings[MG_COUNT] = {
    [MG_GYRO_SPEED]     = NUMBER("Gyro depth speed", "How far tilting the controller pushes or pulls what you hold, in %. 0 turns it off.", 100, 0, 300, 10),
    [MG_GYRO_INVERT]    = TOGGLE("Invert gyro depth", "Tilt the other way to bring what you hold closer.", 0),
    [MG_GYRO_DEADZONE]  = NUMBER("Gyro deadzone", "Turns slower than this are ignored, in tenths of a radian per second.", 5, 0, 30, 1),
    [MG_GYRO_SMOOTHING] = NUMBER("Gyro smoothing", "How much of a tilt counts at once, in %. Lower is smoother but slower.", 35, 5, 100, 5),
    [MG_GRAB_RADIUS]    = NUMBER("Grab radius", "How close to the cursor a character must be to be picked up, in cm.", 120, 30, 300, 10),
    [MG_PULL]           = NUMBER("Pull strength", "How fast what you hold catches up with the cursor.", 8, 1, 20, 1),
    [MG_MAX_SPEED]      = NUMBER("Top speed", "The fastest Link is pulled, in metres per second.", 25, 5, 60, 5),
    [MG_THROW]          = NUMBER("Throw strength", "How much of the cursor's speed a throw keeps, in %.", 100, 0, 300, 10),
    [MG_GRAB_OTHERS]    = TOGGLE("Grab other characters", "Pick up people and animals too, not only Link.", 1),
    [MG_VOICE]          = TOGGLE("Link's voice", "Link cries out when grabbed, dropped and thrown.", 1),
    [MG_FACE]           = TOGGLE("Link's face", "Link makes a hurt face while he's a ragdoll.", 1),
    [MG_CURSOR]         = TOGGLE("Show the cursor", "The arrow under the mouse.", 1),
    [MG_CURSOR_SIZE]    = { KAE_CHOICE, "Cursor size", "The size of the arrow.", 0, 0, 0, 3, 0, sizes, 0, 0, 0, 0 },
    [MG_DEBUG_LOG]      = TOGGLE("Debug log", "Writes what the mod finds to the emulator's log. For finding bugs; off for play.", 0),
};

void mg_settings_start(void) {
    kae_settings("Mouse Grab", mg_settings, MG_COUNT);
}
