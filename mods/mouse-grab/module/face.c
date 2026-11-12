// Link's face and voice while he's a ragdoll, played as animation sequencer (AS) commands.
//
// The game's OneShotASPlay node (f_80221f80) fills a request and calls f_802222a0(&request):
//   +0x00 actor
//   +0x08 command name (from Link's AS file, AS/Player_Child.root.asb: "FaceDamageL",
//         "VoiceDamageL", ...)
//   +0x10 partial: index in the actor's partial list (Link's: Lower, Upper, RightArm, LeftArm,
//         Face, Finger, Mouth, MaskChange, MaskEquip), looked up by name; 0 when none is given
//   +0x14 play rate (1.0)
//   +0x18 two floats, -1.0 in every caller seen
//   +0x20 IsIgnoreSameCommand (byte)
//   +0x28 the calling node (only passed on); a zeroed stand-in here
// (An earlier try wrote an index into the personality component, the way
// OneShotPersonalitySetOverwritePartialSlotFace does; that picks which partial is the face, not
// an expression, so nothing changed.)
#include "core.h"

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))
#define F_AS_PLAY 0x2022A0   // f_802222a0(request)
#define PARTIAL_FACE  4
#define PARTIAL_MOUTH 6

typedef struct {
    void *actor;
    const char *command;
    int32_t partial;
    float rate;
    float minus_one[2];
    uint8_t ignore_same;
    uint8_t zero[7];
    void *node;
} as_request_t;
_Static_assert(sizeof(as_request_t) == 0x30, "AS request");

static _Alignas(16) uint8_t stand_in_node[0x200];

void as_play(void *actor, const char *command, int partial) {
    as_request_t r = { actor, command, partial, 1.0f, { -1.0f, -1.0f }, 1, { 0 }, stand_in_node };
    KP_FN(void (*)(as_request_t *), F_AS_PLAY)(&r);
}

static bool was_down, hurt;
static uint32_t frames;

// Called every frame for Link with whether he's down.
void face_update(void *actor, bool down) {
    if (!MG(MG_FACE)) {   // switched off: only undo a hurt face already shown
        if (hurt && !down) {
            as_play(actor, "FaceDefault", PARTIAL_FACE);
            hurt = false;
        }
        was_down = down;
        return;
    }
    if (down && !was_down) {
        hurt = true;
        as_play(actor, "FaceDamageL", PARTIAL_FACE);
        kp_log("face: FaceDamageL");
        frames = 0;
    } else if (down && ++frames % 20 == 0) {
        as_play(actor, "FaceDamageL", PARTIAL_FACE);   // ignored if it's still playing
    } else if (!down && was_down) {
        as_play(actor, "FaceDefault", PARTIAL_FACE);
        hurt = false;
        kp_log("face: FaceDefault");
    }
    was_down = down;
}

// A scream: called when he's dropped, grabbed or thrown.
void link_voice(void *actor, const char *command) {
    if (!MG(MG_VOICE))
        return;
    as_play(actor, command, PARTIAL_MOUTH);
    kp_log(command);
}
