// World Tools: the time of day, the weather and the wind, on KaeGae Core.
//
// It calls the same WorldMgr functions the game's own event actions call (ExecuteWmSetTime,
// OneShotWmSetWeatherForFlowchart, ExecuteWmSetWindForFlowchart and their resets), asked for by
// name from Core's symbol pack, so it runs on every game version Core has a pack for. Those
// functions queue a request that WorldMgr applies on its next update. Everything is called from
// the frame event (the game's thread); the menu's actions only set a flag for it.
#include <kaegae.h>

// ---- the game's world state, by name ----

typedef int  (*StateFn)(void *state);
typedef void (*SetTimeFn)(void *wm, uint32_t seconds);
typedef void (*SetWeatherFn)(void *wm, const char **name, int change_speed);
typedef void (*ResetWeatherFn)(void *wm, int change_speed);
typedef void (*SetWindFn)(void *wm, int at_once, float azimuth, float elevation, float speed);
typedef void (*ResetWindFn)(void *wm, int at_once);

static void **wm_ptr;            // the WorldMgr pointer variable
static int64_t off_state, off_time, off_weather;
static SetTimeFn set_time;
static SetWeatherFn set_weather;
static ResetWeatherFn reset_weather;
static SetWindFn set_wind;
static ResetWindFn reset_wind;

// ---- settings ----

static const char *const corner_names[] = { "Top right", "Top left", "Bottom right", "Bottom left" };

// The weathers in Pack/EnvPalette.pack (WorldMgr/ResWeatherInfluenceParam): shown name, file name.
static const char *const weather_names[] = {
    "Clear", "Cloudy", "Rain", "Thunderstorm", "Snow",
    "Kokiri (damp)", "Ash clouds", "Graveyard rain", "Graveyard storm",
    "Ganon clouds", "Ganon rain", "Zora's Domain",
};
static const char *const weather_files[] = {
    "Default", "Cloudy", "Rainy", "Thunderstorm", "Snowy",
    "Kokiri", "Cloudy_Ash", "Rainy_Graveyard", "Thunderstorm_Graveyard",
    "GanonCloudy", "GanonRainy", "ZoraDomain",
};
// The game's own number for each (the state's weather call; seen in the game, 18 Nov 2026):
// 0 clear, 1 rain, 2 snow, 3 thunderstorm, 4 cloudy.
static const int weather_numbers[] = { 0, 4, 1, 3, 2, 0, 4, 1, 3, 4, 3, 0 };
#define WEATHERS ((int)(sizeof weather_files / sizeof *weather_files))

static void on_action(KaeItem *item, void *user);

enum {
    CLOCK, CORNER, SIZE, SHOW_WEATHER,
    HOUR, MINUTE, SET_TIME, TO_DAY, TO_NIGHT, PLUS_HOUR,
    WEATHER, CHANGE_SPEED, SET_WEATHER, OWN_WEATHER,
    WIND_DIR, WIND_UP, WIND_SPEED, WIND_AT_ONCE, SET_WIND, OWN_WIND,
    KEEP,
    ITEMS
};
#define ACT(label_, help_, id_) { KAE_ACTION, label_, help_, 0, 0, 0, 0, 0, 0, 0, 0, on_action, (void *)(id_) }
#define KEY(label_, help_)      { KAE_BINDING, label_, help_, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
static KaeItem settings[ITEMS] = {
    [CLOCK]        = { KAE_TOGGLE, "Show clock", "The time of day on screen (hours:minutes).", 1, 1, 0, 1, 1, 0, 0, 0, 0, 0 },
    [CORNER]       = { KAE_CHOICE, "Clock corner", 0, 0, 0, 0, 3, 0, corner_names, 0, 0, 0, 0 },
    [SIZE]         = { KAE_NUMBER, "Clock size", 0, 2, 2, 1, 4, 1, 0, 0, 0, 0, 0 },
    [SHOW_WEATHER] = { KAE_TOGGLE, "Show weather number", "The game's own number for the weather now (0-4), next to the clock.", 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
    [HOUR]         = { KAE_NUMBER, "Hour", "For Set time.", 12, 12, 0, 23, 1, 0, 0, 0, 0, 0 },
    [MINUTE]       = { KAE_NUMBER, "Minute", "For Set time.", 0, 0, 0, 55, 5, 0, 0, 0, 0, 0 },
    [SET_TIME]     = ACT("Set time", "Sets the time of day to the hour and minute above.", SET_TIME),
    [TO_DAY]       = KEY("Jump to day", "Sets the time to 12:00."),
    [TO_NIGHT]     = KEY("Jump to night", "Sets the time to 0:00."),
    [PLUS_HOUR]    = KEY("One hour later", "Moves the time of day on by an hour."),
    [WEATHER]      = { KAE_CHOICE, "Weather", "For Set weather.", 2, 2, 0, WEATHERS - 1, 0, weather_names, 0, 0, 0, 0 },
    [CHANGE_SPEED] = { KAE_NUMBER, "Change speed", "How fast the weather changes: 0 = slow fade, 3 = fast, 5 = at once.", 5, 5, 0, 5, 1, 0, 0, 0, 0, 0 },
    [SET_WEATHER]  = ACT("Set weather", "Changes the weather to the one above.", SET_WEATHER),
    [OWN_WEATHER]  = ACT("Area's own weather", "Back to the weather this area has by itself.", OWN_WEATHER),
    [WIND_DIR]     = { KAE_NUMBER, "Wind direction", "Degrees, as the game's areas give it.", 0, 0, 0, 345, 15, 0, 0, 0, 0, 0 },
    [WIND_UP]      = { KAE_NUMBER, "Wind elevation", "Degrees up (-) or down: how the game reads it is not known yet.", 0, 0, -90, 90, 15, 0, 0, 0, 0, 0 },
    [WIND_SPEED]   = { KAE_NUMBER, "Wind strength", "The areas use 0.5 to 10.", 8, 8, 0, 30, 1, 0, 0, 0, 0, 0 },
    [WIND_AT_ONCE] = { KAE_TOGGLE, "Wind changes at once", "Off: it blends over.", 1, 1, 0, 1, 1, 0, 0, 0, 0, 0 },
    [SET_WIND]     = ACT("Set wind", "Sets the wind to the three numbers above.", SET_WIND),
    [OWN_WIND]     = ACT("Area's own wind", "Back to the wind this area has by itself.", OWN_WIND),
    [KEEP]         = { KAE_TOGGLE, "Keep after loading", "Sets the weather and wind you chose again after each area loads.", 0, 0, 0, 1, 1, 0, 0, 0, 0, 0 },
};

// ---- state (the game's thread writes, the render thread reads the two numbers) ----

static volatile int pending;          // bit per action id, set by the menu, done in frame()
static volatile int shown_seconds = -1, shown_weather = -1;
static int chosen_weather = -1;       // what Set weather last asked for (index), -1 = the area's own
static int chosen_wind;               // 1 while Set wind is in force
static void *last_state;              // WorldMgr's state object: a new one is made when an area loads
static int settle;                    // frames until Keep after loading sets things again
static int checks_left, check_in;     // then: how many more weather checks, frames to the next one
static int logged_state;

static void on_action(KaeItem *item, void *user) {
    (void)item;
    pending |= 1 << (int)(intptr_t)user;
}

static void *world_mgr(void) {
    if (!wm_ptr || !kae_readable(wm_ptr, sizeof *wm_ptr))
        return 0;
    return *wm_ptr;
}

// One of the state object's virtual calls; -1 if the world isn't there.
static int ask_state(int64_t slot) {
    char *wm = world_mgr();
    if (!wm || !kae_readable(wm + off_state, sizeof(void *)))
        return -1;
    void *state = *(void **)(wm + off_state);
    if (!state || !kae_readable(state, sizeof(void *)))
        return -1;
    char *vtable = *(char **)state;
    if (!kae_readable(vtable + slot, sizeof(void *)))
        return -1;
    return (*(StateFn *)(vtable + slot))(state);
}

static int time_of_day(void) {
    int s = ask_state(off_time);
    if (s < 0)
        return -1;
    return s % 86400;
}

static void do_set_time(int seconds) {
    void *wm = world_mgr();
    if (!wm)
        return;
    seconds %= 86400;
    if (seconds < 0)
        seconds += 86400;
    set_time(wm, (uint32_t)seconds);
    KAE_LOG("world tools: time set to %d:%02d", seconds / 3600, seconds / 60 % 60);
}

static void do_set_weather(int index) {
    void *wm = world_mgr();
    if (!wm || index < 0 || index >= WEATHERS)
        return;
    const char *name = weather_files[index];
    set_weather(wm, &name, settings[CHANGE_SPEED].value);
    KAE_LOG("world tools: weather set to %s (change speed %d)", name, settings[CHANGE_SPEED].value);
}

static void do_set_wind(void) {
    void *wm = world_mgr();
    if (!wm)
        return;
    set_wind(wm, settings[WIND_AT_ONCE].value, (float)settings[WIND_DIR].value, (float)settings[WIND_UP].value,
             (float)settings[WIND_SPEED].value);
    KAE_LOG("world tools: wind set to %d deg, %d deg up, strength %d", settings[WIND_DIR].value,
            settings[WIND_UP].value, settings[WIND_SPEED].value);
}

static void frame(void *user) {
    (void)user;
    void *wm = world_mgr();
    if (!wm) {
        shown_seconds = shown_weather = -1;
        return;
    }
    if (!logged_state) {
        logged_state = 1;
        KAE_LOG("world tools: WorldMgr at %p", wm);
    }

    int now = time_of_day();
    shown_seconds = now;
    shown_weather = settings[SHOW_WEATHER].value ? ask_state(off_weather) : -1;

    int todo = pending;
    pending = 0;
    if (todo & (1 << SET_TIME))
        do_set_time(settings[HOUR].value * 3600 + settings[MINUTE].value * 60);
    if (kae_binding_pressed(&settings[TO_DAY]))
        do_set_time(12 * 3600);
    if (kae_binding_pressed(&settings[TO_NIGHT]))
        do_set_time(0);
    if (kae_binding_pressed(&settings[PLUS_HOUR]) && now >= 0)
        do_set_time(now + 3600);

    if (todo & (1 << SET_WEATHER)) {
        chosen_weather = settings[WEATHER].value;
        do_set_weather(chosen_weather);
    }
    if (todo & (1 << OWN_WEATHER)) {
        chosen_weather = -1;
        reset_weather(wm, settings[CHANGE_SPEED].value);
        KAE_LOG("world tools: weather back to the area's own");
    }
    if (todo & (1 << SET_WIND)) {
        chosen_wind = 1;
        do_set_wind();
    }
    if (todo & (1 << OWN_WIND)) {
        chosen_wind = 0;
        reset_wind(wm, settings[WIND_AT_ONCE].value);
        KAE_LOG("world tools: wind back to the area's own");
    }

    // Keep after loading: loading an area gives WorldMgr a new state object (and the area's own
    // weather and wind). Once it has stayed the same for a second, set our choices again, then check
    // the weather number every second for ten seconds in case the area sets its own after that.
    char *slot = (char *)wm + off_state;
    void *state = kae_readable(slot, sizeof(void *)) ? *(void **)slot : 0;
    if (state != last_state) {
        if (last_state && settings[KEEP].value && (chosen_weather >= 0 || chosen_wind)) {
            settle = 60;
            checks_left = 0;
        }
        last_state = state;
    }
    if (settle > 0 && --settle == 0 && settings[KEEP].value) {
        KAE_LOG("world tools: new area: setting the chosen weather and wind again");
        if (chosen_weather >= 0)
            do_set_weather(chosen_weather);
        if (chosen_wind)
            do_set_wind();
        checks_left = 10;
        check_in = 60;
    }
    if (checks_left > 0 && --check_in == 0) {
        checks_left--;
        check_in = 60;
        int n = ask_state(off_weather);
        if (settings[KEEP].value && chosen_weather >= 0 && n >= 0 && n != weather_numbers[chosen_weather]) {
            KAE_LOG("world tools: the area changed the weather (%d): setting it again", n);
            do_set_weather(chosen_weather);
        }
    }
}

// ---- drawing, on the render thread ----

static void draw(const KaeFrame *f, void *user) {
    (void)user;
    if (!settings[CLOCK].value)
        return;
    int s = shown_seconds, w = shown_weather;
    char text[24];
    int n = 0;
    if (s < 0) {
        text[n++] = '-'; text[n++] = '-'; text[n++] = ':'; text[n++] = '-'; text[n++] = '-';
    } else {
        int h = s / 3600, m = s / 60 % 60;
        if (h >= 10)
            text[n++] = (char)('0' + h / 10);
        text[n++] = (char)('0' + h % 10);
        text[n++] = ':';
        text[n++] = (char)('0' + m / 10);
        text[n++] = (char)('0' + m % 10);
    }
    if (settings[SHOW_WEATHER].value) {
        const char *label = "  weather ";
        while (*label)
            text[n++] = *label++;
        if (w < 0) {
            text[n++] = '-';
        } else {
            if (w >= 10)
                text[n++] = (char)('0' + w / 10 % 10);
            text[n++] = (char)('0' + w % 10);
        }
    }
    text[n] = 0;

    int scale = settings[SIZE].value, pad = 4 * scale;
    int width = kae_text_width(scale, text) + 2 * pad, height = kae_text_height(scale, text) + 2 * pad;
    int margin = f->height / 45, corner = settings[CORNER].value;
    int x = (corner == 1 || corner == 3) ? margin : f->width - margin - width;
    int y = (corner == 0 || corner == 1) ? margin : f->height - margin - height;
    kae_draw_rect(x, y, width, height, 0x101820);
    kae_draw_text(x + pad, y + pad, scale, s < 0 ? 0x808890 : 0xF0E6C8, text);
}

// ---- start ----

static int start(void) {
    wm_ptr = kae_sym("WorldMgrPtr");
    set_time = (SetTimeFn)kae_sym("WmSetTime");
    set_weather = (SetWeatherFn)kae_sym("WmSetWeather");
    reset_weather = (ResetWeatherFn)kae_sym("WmResetWeather");
    set_wind = (SetWindFn)kae_sym("WmSetWind");
    reset_wind = (ResetWindFn)kae_sym("WmResetWind");
    off_state = kae_field("WorldMgr.state");
    off_time = kae_field("WorldState.time_slot");
    off_weather = kae_field("WorldState.weather_slot");
    if (!wm_ptr || !set_time || !set_weather || !reset_weather || !set_wind || !reset_wind || off_state < 0 ||
        off_time < 0 || off_weather < 0) {
        KAE_LOG("world tools: this Core doesn't know the world's names for game %s (needs Core 0.8.6): doing nothing",
                kae_game_version());
        return 2;
    }
    if (kae_on_frame(frame, 0, 0) != KAE_OK || kae_on_draw(draw, 0, 0) != KAE_OK)
        return 2;
    kae_settings("World Tools", settings, ITEMS);
    KAE_LOG("world tools 0.1.1: clock, time of day, weather, wind (game %s)", kae_game_version());
    return 0;
}

KAE_MOD("kabosune.world-tools", "0.1.1", start, 0);
