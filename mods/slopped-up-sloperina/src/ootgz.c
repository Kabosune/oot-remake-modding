/* Slopped Up Sloperina: sloperinaGZ (PracticeROM, GPL-3.0) running as a KaeGae Core mod.
 *
 * Ported from sloperinaGZ's ootgz.c. What changed from the original (see ../README.md):
 *   - KaeGae Core starts the mod (KAE_MOD below) instead of rtld's DT_INIT, and calls frame() from its
 *     frame event (once per game frame, on the game's thread, when the game reads the controllers)
 *     instead of sloperinaGZ's IPS patch on the GameData unlock. No patch to main of its own.
 *   - The game's copy of the controller is edited in Core's input event (input_filter), not by
 *     rewriting main's GOT.
 *   - Drawing goes through Core's draw event (kaedraw.c) in Core's font: gz's style only. The game's
 *     own type, pictures and GPU drawing (nvn.c, gpuui.c, nativeui.c, gameimage.c...) are left out.
 *   - The X / Y / Z locks need sloperinaGZ's store patches and are unavailable.
 */
#include "age.h"
#include "cheats.h"
#include "gamedata.h"
#include "gameimage.h"
#include "gfx.h"
#include "input.h"
#include "job.h"
#include "link.h"
#include "menu.h"
#include "menus.h"
#include "airwall.h"
#include "enemyhp.h"
#include "divetest.h"
#include "levitate.h"
#include "settings.h"
#include "warp.h"
#include "watches.h"
#include "ootgz_version.h"
#include "pouch.h"
#include "position.h"
#include "lock.h"
#include "sys.h"
#include "z64hd.h"
#include "z64hd_builds.h"
#include "kaedraw.h"
#include "build_info.h"

#include <kaegae.h>

uintptr_t z64hd_main;
const struct z64hd_build *z64hd_game;

/* exported by main */
extern void nnMain(void);

typedef uint64_t (*gd_unlock_t)(void *lock);

static bool started;
static uint32_t frames_run;

/* the menu's combinations are actions (input.h): ACT_MENU (gz: R + C-down) and ACT_BACK */
#define BACK_BUTTON BTN_B

/* --- frame advance ---------------------------------------------------------------------------
 * With it on (settings > frame advance), a tap of its button (L or R, menu closed) pauses the game:
 * this hook, on the game's thread, holds it here, as a debugger's breakpoint would. While held, a
 * tap lets one frame through, and the button + L3 lets it run again; the menu still opens (R + right
 * stick down) and works as usual. gz's pause icon shows at the top left. The game never sees the
 * button while it's on.
 * As in gz, everything else can be held or pressed meanwhile (the stick, A, Z...): the frame let
 * through reads the controller as it is, plus what was buffered while paused. Only R's shortcuts
 * (R + right stick down, R + d-pad...) don't count as a tap, so they don't pause the game; L has none.
 * While the game's own pause is on (its pause screen or an item menu), the button is left to the game
 * and can't start frame advance, unless "in pause screen" is ticked (frame_advance_in_pause; off by
 * default). Once paused by frame advance, stepping into the pause screen still works as before.
 * Off until it's ticked (settings_load turns it off once in files from before settings_version 1). */
bool frame_advance = false;
bool frame_advance_in_pause = false;
bool pause_display = true;
bool hide_in_game_menus = true;

/* settings > hide in game menus: the game's own menus (Plus, Minus) are open, or opening (from the frame
 * they start to fade in). gfx_frame keeps the HUD shown while sloperinaGZ's menu is open (it can be moved
 * then). */
static bool hud_hidden(void)
{
  return hide_in_game_menus && (gd_game_pausing() || gd_game_paused(0, 0));
}

/* Held (not as a shortcut) for FA_HOLD_MS, the button advances a frame every FA_REPEAT_MS
 * until it's let go. The wait leaves room for a tap that's a little long. */
#define FA_HOLD_MS 400
#define FA_REPEAT_MS 66

/* The menu uses the button too (L selects; a warp closes the menu on the same press). While the menu
 * is open, on the frame it closes, until the button is let go and for FA_AFTER_MENU_MS after, the
 * button isn't frame advance's. */
#define FA_AFTER_MENU_MS 250

/* While paused, how long to sleep between polls of the controller (about one 60 Hz frame). */
#define FA_POLL_NS (16 * 1000 * 1000)

static bool fa_paused;
static bool fa_button_down;     /* the button went down and hasn't been let go yet */
static bool fa_not_a_tap;       /* something else was pressed while it was down */
static uint64_t fa_button_down_at;
static bool fa_repeating;       /* held long enough that it's stepping frames on its own */
static uint64_t fa_last_repeat_at;
static bool fa_menu_was_open;   /* the menu was open at the start of this frame */
static bool fa_blocked_after_menu;
static uint64_t fa_menu_closed_at;

/* What the frame advance button did this frame. */
typedef enum {
  FA_NOTHING = 0,
  FA_TAP = 1,    /* pressed and let go on its own */
  FA_RUN = 2,    /* the button + L3: run again */
  FA_REPEAT = 3, /* held while paused: another frame */
} fa_event_t;

/* Another action pressed while the button is held makes it a shortcut (R + D-up saves the
 * position), not a tap. */
static bool fa_other_action_pressed(void)
{
  for (int a = 0; a < ACT_COUNT; a++)
    if (a != ACT_FRAME_ADVANCE && action_pressed(a))
      return true;
  return false;
}

static fa_event_t fa_read_button(void)
{
  bool pressed = action_pressed(ACT_FRAME_ADVANCE);
  bool held = action_held(ACT_FRAME_ADVANCE);
  uint64_t ticks_per_ms = sys_tick_freq() / 1000;
  uint64_t now = sys_tick();

  if (menu_current || fa_menu_was_open) {
    fa_button_down = false;
    fa_blocked_after_menu = true;
    fa_menu_closed_at = now;
    return FA_NOTHING;
  }
  if (fa_blocked_after_menu) {
    if (held || now - fa_menu_closed_at < FA_AFTER_MENU_MS * ticks_per_ms)
      return FA_NOTHING;
    fa_blocked_after_menu = false;
  }

  if (pressed) {
    fa_button_down = true;
    fa_not_a_tap = false;
    fa_button_down_at = sys_tick();
    fa_repeating = false;
  }
  if (!fa_button_down)
    return FA_NOTHING;

  if (action_pressed(ACT_RUN)) {
    fa_not_a_tap = true;
    return FA_RUN;
  }
  if (fa_other_action_pressed())
    fa_not_a_tap = true;

  if (!held) {
    bool tap = !fa_not_a_tap && !fa_repeating; /* a hold already advanced: no extra frame */
    fa_button_down = false;
    fa_repeating = false;
    return tap ? FA_TAP : FA_NOTHING;
  }

  /* Held: after FA_HOLD_MS, a frame every FA_REPEAT_MS (only while paused, in fa_hold_game). */
  bool held_long_enough = now - fa_button_down_at >= FA_HOLD_MS * ticks_per_ms;
  bool repeat_due = !fa_repeating || now - fa_last_repeat_at >= FA_REPEAT_MS * ticks_per_ms;
  if (fa_paused && !fa_not_a_tap && held_long_enough && repeat_due) {
    fa_repeating = true;
    fa_last_repeat_at = now;
    return FA_REPEAT;
  }
  return FA_NOTHING;
}

/* Opens, closes and drives the menu. Returns true if the input was the menu's. */
static bool menu_controls(void)
{
  if (!menu_current && action_pressed(ACT_MENU))
    menu_open(&menu_root);
  else if (menu_current && action_pressed(ACT_MENU))
    menu_close(); /* the open combo toggles it */
  else if (menu_current && (action_pressed(ACT_BACK) || (input_pressed() & BACK_BUTTON)))
    menu_back();
  else if (menu_current) {
    watches_sync();
    menu_input();
  } else
    return false;
  return true;
}

/* What's pressed while paused is buffered and given to the game on the frame that's let through:
 * every button pressed (not the frame advance button, nor L3 pressed with it), and each stick's last
 * direction away from the middle. */
#define FA_DEADZONE 6000
#define BUTTON_BITS 0xFFFF /* the buttons, not the stick-direction bits above them */

static uint32_t buffered_buttons;
static bool buffered_stick_moved[2];   /* left, right */
static int32_t buffered_stick_axes[4]; /* lx, ly, rx, ry */

static void fa_buffer_input(void)
{
  if (menu_current) /* what's pressed for the menu isn't for the game */
    return;
  uint32_t held = input_held();
  /* the button, and run's combination, are frame advance's, not the game's */
  uint32_t for_game = held & ~action_buttons_held(ACT_FRAME_ADVANCE) & ~action_buttons_held(ACT_RUN) & BUTTON_BITS;
  buffered_buttons |= for_game;

  int32_t axes[4];
  input_sticks(&axes[0], &axes[1], &axes[2], &axes[3]);
  for (int stick = 0; stick < 2; stick++) {
    int32_t x = axes[2 * stick];
    int32_t y = axes[2 * stick + 1];
    if (x > FA_DEADZONE || x < -FA_DEADZONE || y > FA_DEADZONE || y < -FA_DEADZONE) {
      buffered_stick_moved[stick] = true;
      buffered_stick_axes[2 * stick] = x;
      buffered_stick_axes[2 * stick + 1] = y;
    }
  }
}

/* Hand the buffered input to the game for the one frame that's let through. */
static void fa_release_buffered_input(void)
{
  input_force_buttons = buffered_buttons;
  input_force_sticks[0] = buffered_stick_moved[0];
  input_force_sticks[1] = buffered_stick_moved[1];
  memcpy(input_force_stick, buffered_stick_axes, sizeof(input_force_stick));
  input_force_active = buffered_buttons || buffered_stick_moved[0] || buffered_stick_moved[1];
}

/* Holds the game's thread here while paused, running the menu and overlays, until a frame is let
 * through or the game is set running again. */
static void fa_hold_game(void)
{
  uint32_t presents_at_start = gfx_presents;
  uint64_t paused_at = sys_tick();
  bool logged = false;
  /* the frame let through has been played: its buffered input is done with */
  input_force_active = false;
  buffered_buttons = 0;
  buffered_stick_moved[0] = false;
  buffered_stick_moved[1] = false;
  /* The game presents nothing while it's held here (0 presents, measured), so what shows while
   * paused is the last frame let through: it gets the pause icon (set before it's presented). */
  gfx_pause_icon = pause_display ? 1 : 0;
  for (;;) {
    sys_sleep_ns(FA_POLL_NS);
    sys_frame();
    input_update();
    /* The button + L3 always runs again, even with the menu open: nothing is drawn while paused, so a
     * menu opened here can't be seen, and it would take the button. Checked before the menu gets it. */
    if (action_pressed(ACT_RUN)) {
      if (menu_current)
        menu_close();
      fa_button_down = false;
      fa_repeating = false;
      fa_blocked_after_menu = true; /* letting go of the button isn't a tap */
      fa_menu_closed_at = sys_tick();
      fa_paused = false;
      gfx_pause_icon = 0;
      gfx_notice("frame advance: running");
      break;
    }
    menu_controls();
    fa_event_t event = fa_read_button();
    if (event == FA_RUN) {
      fa_paused = false;
      gfx_pause_icon = 0;
      gfx_notice("frame advance: running");
      break;
    }
    if (event == FA_TAP || event == FA_REPEAT) { /* one frame, with what was pressed meanwhile */
      fa_release_buffered_input();
      break;
    }
    fa_buffer_input();
    if (menu_current) {
      watches_sync();
      menu_draw();
    }
    watches_frame(menu_current != 0);
    gfx_hud_hidden = hud_hidden();
    gfx_frame();
    settings_frame(menu_current != 0);
    settings_log_frame();
    /* does the picture still get presented? */
    if (!logged && sys_tick() - paused_at > sys_tick_freq()) {
      logged = true;
      log_printf("frame advance: %u presents in the first second paused",
                 (unsigned)(gfx_presents - presents_at_start));
    }
  }
}

static void fa_frame(void)
{
  if (!frame_advance) {
    fa_paused = false;
    fa_button_down = false;
    gfx_pause_icon = 0;
    input_force_active = false;
    return;
  }
  if (!fa_paused && !frame_advance_in_pause && gd_game_paused(0, 0)) {
    /* The game's pause screen has the button (as when the menu is open): it isn't frame advance's
     * until the pause screen has closed and the button has been let go. */
    fa_button_down = false;
    fa_blocked_after_menu = true;
    fa_menu_closed_at = sys_tick();
    return;
  }
  input_hide_from_game |= action_buttons_held(ACT_FRAME_ADVANCE) | action_buttons_held(ACT_RUN);
  if (!fa_paused)
    input_force_active = false;
  if (!fa_paused && fa_read_button() == FA_TAP) {
    fa_paused = true;
    gfx_notice("frame advance: paused (tap for a frame; run to go on)");
    /* The game shows nothing new while it's held, so this frame is let through first, with the pause
     * icon on it: the screen shows the game is paused (and hasn't crashed). Held from the next one. */
    gfx_pause_icon = pause_display ? 1 : 0;
    return;
  }
  if (fa_paused)
    fa_hold_game();
}

/* --- frame hook -------------------------------------------------------------------------- */

static void first_frame(void)
{
  menus_build();
  settings_load();
  log_printf("running on game %s (on KaeGae Core, main %#lx)", z64hd_game->version, (unsigned long)z64hd_main);
  menus_splash();
}

static void frame(void)
{
  if (!started) {
    started = true;
    first_frame();
  }
  frames_run++;
  sys_frame();
  input_update();

  fa_menu_was_open = menu_current != 0; /* an L that closes the menu isn't frame advance's */
  /* KaeGae Core's Mods menu is open: its buttons are its own */
  bool core_menu = kae_menu_open();
  if (!core_menu)
    menu_controls();
  if (menu_current) {
    watches_sync();
    menu_draw();
  }
  bool overlays_on_gpu = false; /* Core draws rectangles: no lines or bars for the GPU */
  airwall_frame(overlays_on_gpu);
  enemyhp_frame(overlays_on_gpu);
  menus_research_frame();
  watches_frame(menu_current != 0);
  levitate_frame(menu_current != 0);
  position_frame(menu_current != 0);
  divetest_frame(menu_current != 0);
  lock_frame();
  warp_frame();
  age_frame();
  gfx_hud_hidden = hud_hidden();
  gfx_frame();

  cheats_frame();
  pouch_frame();
  job_frame();
  settings_frame(menu_current != 0);
  settings_log_frame();
  if (!core_menu)
    fa_frame(); /* last: the frame's work is done before the game is held */
}

/* --- KaeGae Core --------------------------------------------------------------------------- */

static void on_frame(void *user)
{
  frame();
}

static void on_input(KaeInput *seen_by_game, const KaeInput *real, void *user)
{
  input_filter(seen_by_game);
}

/* nnMain is exported by main: which build is running, from main's own header */
static const struct z64hd_build *detect_build(uintptr_t nnmain)
{
  for (size_t i = 0; i < sizeof(z64hd_builds) / sizeof(*z64hd_builds); i++) {
    const struct z64hd_build *build = &z64hd_builds[i];
    uintptr_t base = nnmain - build->nnmain;
    uint32_t mod0, magic;
    if (sys_read32(base + 4, &mod0) && mod0 == build->mod0 &&
        sys_read32(base + mod0, &magic) && magic == 0x30444F4D) /* MOD0 */
      return build;
  }
  return 0;
}

static int start(void)
{
  z64hd_game = detect_build((uintptr_t)&nnMain);
  if (!z64hd_game) {
    KAE_LOG("slopped up sloperina: unsupported Ocarina of Time build (1.0.0 and 1.1.1 are known)");
    return -1;
  }
  z64hd_main = (uintptr_t)&nnMain - z64hd_game->nnmain;
  /* frame first, then the others: the game's thread, before any of them is used */
  actions_register();
  if (kae_on_frame(on_frame, 0, 0) || kae_on_input(on_input, 0, 0) || kae_on_draw(kaedraw_frame, 0, 0)) {
    KAE_LOG("slopped up sloperina: Core refused an event");
    return -1;
  }
  KAE_LOG("slopped up sloperina %s: sloperinaGZ %s on game %s", SLOPPED_VERSION, SLOPERINA_GZ_VERSION,
          z64hd_game->version);
  return 0;
}

KAE_MOD("kabosune.slopped-up-sloperina", SLOPPED_VERSION, start, 0);
