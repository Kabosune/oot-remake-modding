// Link: telling his physics actor from the others, moving him, his velocity.
//
// Every offset and address comes from the symbol pack of the running build. The walk is the one
// FPV Drone, Mouse Grab and Sloped Up Sloperina each did themselves, tested in the game on 1.1.1:
// the actor's movement component sits inside Link's player object, whose resource is named
// "Player", and the actor's character controller is four pointers away from its components.
#include "core.h"

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))

bool kp_player_on;

static struct {
    void *vt_actor, *vt_player, *vt_cct, *vt_body;
    void (*change_position)(void *controller, const float position[4]);
    void (*set_velocity)(void *body, const float velocity[3], int);
    int64_t position, components, movement, movement_actor, player_movement, resource, resource_name;
    int64_t chain[4], cct_body, body_velocity;
} k;

static KaePlayer answer;

bool kp_player_start(void) {
    static const struct { const char *name; int64_t *to; } fields[] = {
        { "Actor.position", &k.position }, { "Actor.components", &k.components },
        { "Components.movement", &k.movement }, { "Movement.actor", &k.movement_actor },
        { "Player.movement", &k.player_movement }, { "Player.resource", &k.resource },
        { "Resource.name", &k.resource_name }, { "Components.physics", &k.chain[0] },
        { "Physics.owner", &k.chain[1] }, { "PhysicsOwner.holder", &k.chain[2] },
        { "Holder.controller", &k.chain[3] },
    };
    for (size_t i = 0; i < sizeof fields / sizeof *fields; i++)
        if ((*fields[i].to = kae_field(fields[i].name)) < 0)
            return false;
    k.vt_actor = kae_sym("vtable.Actor");
    k.vt_player = kae_sym("vtable.Player");
    k.vt_cct = kae_sym("vtable.Cct");
    k.change_position = (void (*)(void *, const float *))kae_sym("CctChangePosition");
    if (!k.vt_actor || !k.vt_player || !k.vt_cct || !k.change_position || !kp_event_on[KP_EV_ACTOR_MOVE])
        return false;
    // The body is extra: without it Link is still found and moved, only his velocity is out of reach.
    k.vt_body = kae_sym("vtable.CctBody");
    k.set_velocity = (void (*)(void *, const float *, int))kae_sym("BodySetLinearVelocity");
    k.cct_body = kae_field("Cct.body");
    k.body_velocity = kae_field("CctBody.velocity");
    kp_event_on[KP_EV_PLAYER_MOVE] = true;
    kp_player_on = true;
    return true;
}

static bool is_player_name(const char *name) {
    static const char want[] = "Player";
    return kp_readable((uintptr_t)name, sizeof want) && __builtin_memcmp(name, want, sizeof want) == 0;
}

const KaePlayer *kae_player_of(void *actor) {
    if (!kp_player_on || !actor || !kp_readable((uintptr_t)actor, 0x340) || AT(actor, 0, void *) != k.vt_actor)
        return 0;
    char *components = AT(actor, k.components, char *);
    if (!components || !kp_readable((uintptr_t)components, (size_t)k.movement + 8))
        return 0;
    char *movement = AT(components, k.movement, char *);
    if (!movement || !kp_readable((uintptr_t)(movement - k.player_movement), (size_t)k.player_movement + 0x20) ||
        AT(movement, k.movement_actor, void *) != actor)
        return 0;
    char *object = movement - k.player_movement;
    if (AT(object, 0, void *) != k.vt_player)
        return 0;
    char *resource = AT(object, k.resource, char *);
    if (!resource || !is_player_name(resource + k.resource_name))
        return 0;
    char *controller = components;
    for (int i = 0; i < 4; i++) {
        if (!kp_readable((uintptr_t)controller + (uintptr_t)k.chain[i], 8))
            return 0;
        controller = AT(controller, k.chain[i], char *);
        if (!controller)
            return 0;
    }
    if (!kp_readable((uintptr_t)controller, 0x28) || AT(controller, 0, void *) != k.vt_cct)
        return 0;
    void *body = 0;
    if (k.vt_body && k.cct_body >= 0) {
        body = AT(controller, k.cct_body, void *);
        if (!body || !kp_readable((uintptr_t)body, 0x100) || AT(body, 0, void *) != k.vt_body)
            body = 0;
    }
    const float *position = &AT(actor, k.position, float);
    static bool said;
    if (!said) {
        said = true;
        kp_log(body ? "player: found Link, his controller and its body" : "player: found Link and his controller; no body, so no velocity");
    }
    answer = (KaePlayer){ sizeof(KaePlayer), actor, object, controller, body, { position[0], position[1], position[2] } };
    return &answer;
}

int kae_player_move(const KaePlayer *link, const float position[3]) {
    if (!link || !position)
        return KAE_ERR_ARGUMENT;
    if (!kp_player_on || !link->controller)
        return KAE_ERR_UNAVAILABLE;
    float to[4] = { position[0], position[1], position[2], 0 };
    k.change_position(link->controller, to);
    return KAE_OK;
}

int kae_player_velocity(const KaePlayer *link, float out[3]) {
    if (!link || !out)
        return KAE_ERR_ARGUMENT;
    out[0] = out[1] = out[2] = 0;
    if (!kp_player_on || !link->body || k.body_velocity < 0)
        return KAE_ERR_UNAVAILABLE;
    const float *v = &AT(link->body, k.body_velocity, float);
    for (int i = 0; i < 3; i++)
        if (!(v[i] > -10000.0f && v[i] < 10000.0f))   // not a number, or not a speed: don't hand it on
            return KAE_ERR_UNAVAILABLE;
    for (int i = 0; i < 3; i++)
        out[i] = v[i];
    return KAE_OK;
}

int kae_player_set_velocity(const KaePlayer *link, const float velocity[3]) {
    if (!link || !velocity)
        return KAE_ERR_ARGUMENT;
    if (!kp_player_on || !link->body || !k.set_velocity)
        return KAE_ERR_UNAVAILABLE;
    k.set_velocity(link->body, velocity, 0);
    return KAE_OK;
}
