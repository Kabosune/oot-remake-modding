// The names Mouse Grab asks Core for (Core's symbol pack, symbols/<build>.toml). Before 0.4.0 these
// were 1.1.1 offsets in the mod itself, so it only ran on 1.1.1 (and crashed on 1.0.0).
#include "core.h"

static const char *const names[MG_SYM_COUNT] = {
    [F_HOLDER] = "ActorHolder",
    [F_FIND_RAGDOLL] = "RagdollFind",
    [F_RAGDOLL_DOWN] = "RagdollStart",
    [F_RAGDOLL_END] = "RagdollEnd",
    [F_PREP_SPEED] = "RagdollDownPrepSpeed",
    [F_PREP_A] = "RagdollDownPrepA",
    [F_PREP_B] = "RagdollDownPrepB",
    [F_PREP_STATE] = "RagdollDownPrepState",
    [F_REACTION] = "RagdollReaction",
    [F_REACTION_ACTIVE] = "RagdollReactionIsActive",
    [F_REACTION_END] = "RagdollReactionEnd",
    [F_AS_PLAY] = "AsPlay",
    [F_SET_VELOCITY] = "BodySetLinearVelocity",
    [F_CHANGE_POS] = "CctChangePosition",
    [G_ZERO] = "IdentityQuatPtr",
    [G_NAMES] = "RagdollDownNamesPtr",
    [CAMERA_SLOT] = "GameCameraPtr",
    [VT_ACTOR] = "vtable.Actor",
    [VT_PLAYER] = "vtable.Player",
    [VT_CCT] = "vtable.Cct",
    [BODY_VT] = "vtable.CctBody",
};

uintptr_t mg_sym[MG_SYM_COUNT];

const char *mg_symbols_start(void) {
    for (int i = 0; i < MG_SYM_COUNT; i++) {
        mg_sym[i] = (uintptr_t)kae_sym(names[i]);
        if (!mg_sym[i])
            return names[i];
    }
    return 0;
}
