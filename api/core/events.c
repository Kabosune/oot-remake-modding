// Events: lists of subscribers, called in priority order.
#include "core.h"

#define MAX_SUBSCRIBERS 32

typedef struct {
    void *fn, *user;
    int priority;
    const KaeMod *owner;   // the mod whose start subscribed, for switching it off
} sub_t;

typedef struct {
    sub_t subs[MAX_SUBSCRIBERS];
    int count;
} list_t;

static list_t lists[KP_EV_COUNT];
static kp_lock_t lock;
bool kp_event_on[KP_EV_COUNT];

static int subscribe(int event, void *fn, void *user, int priority) {
    if (!fn)
        return KAE_ERR_ARGUMENT;
    if (!kp_event_on[event])
        return KAE_ERR_UNAVAILABLE;
    int result = KAE_OK;
    kp_lock(&lock);
    list_t *l = &lists[event];
    if (l->count == MAX_SUBSCRIBERS) {
        result = KAE_ERR_FULL;
    } else {
        int at = l->count;
        while (at > 0 && l->subs[at - 1].priority > priority) {   // after equals: first come, first run
            l->subs[at] = l->subs[at - 1];
            at--;
        }
        l->subs[at] = (sub_t){ fn, user, priority, kp_mod_starting() };
        l->count++;
    }
    kp_unlock(&lock);
    return result;
}

// Copies the list so the functions run without the lock (they may subscribe themselves).
static int snapshot(int event, sub_t *out) {
    kp_mods_ready();
    list_t *l = &lists[event];
    if (!__atomic_load_n(&l->count, __ATOMIC_RELAXED))
        return 0;
    kp_lock(&lock);
    int n = l->count;
    for (int i = 0; i < n; i++)
        out[i] = l->subs[i];
    kp_unlock(&lock);
    return n;
}

void kp_unsubscribe_mod(const KaeMod *mod) {
    kp_lock(&lock);
    for (int e = 0; e < KP_EV_COUNT; e++) {
        list_t *l = &lists[e];
        int kept = 0;
        for (int i = 0; i < l->count; i++)
            if (l->subs[i].owner != mod)
                l->subs[kept++] = l->subs[i];
        l->count = kept;
    }
    kp_unlock(&lock);
}

int kae_on_frame(KaeFrameFn fn, void *user, int priority) { return subscribe(KP_EV_FRAME, (void *)fn, user, priority); }
int kae_on_input(KaeInputFn fn, void *user, int priority) { return subscribe(KP_EV_INPUT, (void *)fn, user, priority); }
int kae_on_draw(KaeDrawFn fn, void *user, int priority) { return subscribe(KP_EV_DRAW, (void *)fn, user, priority); }
int kae_on_actor_move(KaeActorFn fn, void *user, int priority) {
    return subscribe(KP_EV_ACTOR_MOVE, (void *)fn, user, priority);
}

int kae_on_player_move(KaePlayerFn fn, void *user, int priority) {
    return subscribe(KP_EV_PLAYER_MOVE, (void *)fn, user, priority);
}

void kp_fire_frame(void) {
    sub_t s[MAX_SUBSCRIBERS];
    int n = snapshot(KP_EV_FRAME, s);
    kp_menu_frame();
    for (int i = 0; i < n; i++)
        if (!kp_mod_off(s[i].owner))
            ((KaeFrameFn)s[i].fn)(s[i].user);
}

void kp_fire_input(KaeInput *seen, const KaeInput *real) {
    sub_t s[MAX_SUBSCRIBERS];
    int n = snapshot(KP_EV_INPUT, s);
    KaeInput for_mods = *real;   // keys held for older mods' bindings are added to it
    kp_menu_input(seen, &for_mods);
    for (int i = 0; i < n; i++)
        if (!kp_mod_off(s[i].owner))
            ((KaeInputFn)s[i].fn)(seen, &for_mods, s[i].user);
    kp_menu_input_done(seen);
}

void kp_fire_draw(const KaeFrame *frame) {
    sub_t s[MAX_SUBSCRIBERS];
    int n = snapshot(KP_EV_DRAW, s);
    for (int i = 0; i < n; i++)
        if (!kp_mod_off(s[i].owner))
            ((KaeDrawFn)s[i].fn)(frame, s[i].user);
    kp_menu_draw(frame->width, frame->height);
}

void kp_fire_actor_move(void *actor) {
    sub_t s[MAX_SUBSCRIBERS];
    int n = snapshot(KP_EV_ACTOR_MOVE, s);
    for (int i = 0; i < n; i++)
        if (!kp_mod_off(s[i].owner))
            ((KaeActorFn)s[i].fn)(actor, s[i].user);
}

bool kp_wants_player_move(void) { return __atomic_load_n(&lists[KP_EV_PLAYER_MOVE].count, __ATOMIC_RELAXED) != 0; }

void kp_fire_player_move(const KaePlayer *link) {
    sub_t s[MAX_SUBSCRIBERS];
    int n = snapshot(KP_EV_PLAYER_MOVE, s);
    for (int i = 0; i < n; i++)
        if (!kp_mod_off(s[i].owner))
            ((KaePlayerFn)s[i].fn)(link, s[i].user);
}
