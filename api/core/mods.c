// The list of mods: registering, the version check, starting each one once.
#include "core.h"

#define MAX_MODS 64

static kp_lock_t lock;
static KaeMod *waiting;            // registered and not looked at yet, newest first (through ->next)
static KaeMod *mods[MAX_MODS];     // looked at, in the order they registered
static int mod_count;
static char started;               // set by the first entry from the game
static KaeMod *starting;

KaeMod *kp_mod_starting(void) { return starting; }

static bool same_text(const char *a, const char *b) {
    for (; *a == *b; a++, b++)
        if (!*a)
            return true;
    return false;
}

// Why Core won't run this mod, or null.
static const char *refusal(const KaeMod *mod) {
    if (mod->size < sizeof(KaeMod))
        return "its descriptor is smaller than this Core's (built with a broken header?)";
    if (!mod->id || !mod->id[0])
        return "it has no id";
    if (mod->api_major != KAE_API_MAJOR)
        return "it was built for a different major version of the API";
    if (mod->api_minor > KAE_API_MINOR)
        return "it was built for a newer Core than this one";
    if (KAE_API_MAJOR == 0 && mod->api_minor != KAE_API_MINOR)
        return "it was built for an older 0.x API, and 0.x versions don't mix: rebuild it";
    for (int i = 0; i < mod_count; i++)
        if (mods[i] != mod && same_text(mods[i]->id, mod->id))
            return "a mod with the same id is already loaded";
    return 0;
}

static void start(KaeMod *mod) {
    const char *version = mod->version ? mod->version : "?";
    const char *why = refusal(mod);
    if (why) {
        kp_logf("mod %s %s is off: %s", mod->id && mod->id[0] ? mod->id : "(no id)", version, why);
        return;
    }
    if (mod_count == MAX_MODS) {
        kp_logf("mod %s is off: too many mods", mod->id);
        return;
    }
    mods[mod_count++] = mod;
    if (!kp_main) {
        kp_logf("mod %s %s is off: this build of the game isn't known to Core", mod->id, version);
        return;
    }
    kp_menu_add_mod(mod, 0);
    starting = mod;
    int result = mod->start ? mod->start() : 0;
    starting = 0;
    if (result != 0) {
        kp_unsubscribe_mod(mod);
        kp_menu_add_mod(mod, "This mod could not start in this game (see the log).");
        kp_logf("mod %s %s is off: its start returned %d", mod->id, version, result);
        return;
    }
    kp_logf("mod %s %s started", mod->id, version);
}

// Takes everything off the waiting list and starts it, oldest first.
static void start_waiting(void) {
    for (;;) {
        kp_lock(&lock);
        KaeMod *list = waiting;
        waiting = 0;
        kp_unlock(&lock);
        if (!list)
            return;
        KaeMod *in_order = 0;
        while (list) {            // the list is newest first: turn it round
            KaeMod *next = list->next;
            list->next = in_order;
            in_order = list;
            list = next;
        }
        while (in_order) {
            KaeMod *next = in_order->next;
            in_order->next = 0;
            start(in_order);
            in_order = next;
        }
    }
}

void kae_register(KaeMod *mod) {
    if (!mod)
        return;
    kp_lock(&lock);
    mod->next = waiting;
    waiting = mod;
    kp_unlock(&lock);
    // A mod that registers after the game is running is started straight away.
    if (__atomic_load_n(&started, __ATOMIC_ACQUIRE) == 2)
        start_waiting();
}

void kp_mods_ready(void) {
    if (__atomic_load_n(&started, __ATOMIC_ACQUIRE))
        return;
    char expected = 0;
    if (!__atomic_compare_exchange_n(&started, &expected, 1, false, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE))
        return;   // another thread is starting the mods right now
    start_waiting();
    __atomic_store_n(&started, 2, __ATOMIC_RELEASE);
    start_waiting();   // anything that registered meanwhile
}
