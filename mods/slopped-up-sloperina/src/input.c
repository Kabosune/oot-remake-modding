#include "input.h"

#include <kaegae.h>
#include "menu.h"
#include "sys.h"

/* nn::hid state structs (Switch 1 layout: sampling number, buttons, two sticks, attributes;
 * 0x28 bytes). We only touch the leading fields and read one state into a larger buffer, so
 * a longer Switch 2 struct is harmless. VERIFY the field order on hardware (BUILDING.md). */
typedef struct {
  int64_t  sampling_number;
  uint64_t buttons;
  int32_t  lx, ly, rx, ry;
  uint32_t attributes;
} npad_state_t;

#define NPAD_STATE_SIZE      0x28  /* the Switch 1 state's size: the stride between states */
#define NPAD_STATE_BUF       0x100 /* room for one state, however long the Switch 2 one is */
#define NPAD_ATTR_CONNECTED  1u    /* NpadAttribute::IsConnected */

/* nn::hid::detail::GetNpadStates(int *out_count, NpadXState *out, int count, const NpadIdType &id),
 * exported by sdk. The detail versions are what the public ones call, so they keep working
 * when the public ones are interposed below. */
#define DETAIL(style) "_ZN2nn3hid6detail13GetNpadStatesEPiPNS0_" style "EiRKj"
void hid_detail_fullkey(int *n, void *out, int count, const uint32_t *id)
  __asm__(DETAIL("16NpadFullKeyState"));
void hid_detail_handheld(int *n, void *out, int count, const uint32_t *id)
  __asm__(DETAIL("17NpadHandheldState"));
void hid_detail_joydual(int *n, void *out, int count, const uint32_t *id)
  __asm__(DETAIL("16NpadJoyDualState"));

/* NpadIdType values */
enum { NPAD_NO1 = 0, NPAD_HANDHELD = 0x20 };

/* gz-style repeat for held buttons (menu navigation), in frames */
#define REPEAT_FIRST_DELAY 12 /* before the first repeat */
#define REPEAT_INTERVAL    3  /* then every this many */

static uint32_t buttons_held;
static uint32_t buttons_pressed;  /* went down this frame */
static uint32_t repeat_buttons;   /* held since they went down, so they repeat */
static uint32_t buttons_fired;    /* pressed, or repeating this frame */
static int32_t stick_axes[4];     /* lx, ly, rx, ry */
static int repeat_countdown;
bool input_block_game;
uint32_t input_hide_from_game;

static int controller = INPUT_PRO;

/* Add one controller's state (one style of one NpadIdType) to this frame's input: true when it's connected
 * and something on it is pressed or tilted (*connected: whether it's connected) */
static bool read_npad(void (*get_states)(int *, void *, int, const uint32_t *), uint32_t npad_id, bool *connected)
{
  uint64_t buf[NPAD_STATE_BUF / 8] = { 0 };
  int state_count = 0;
  *connected = false;
  get_states(&state_count, buf, 1, &npad_id);
  if (state_count < 1)
    return false;
  npad_state_t *state = (npad_state_t *)buf;
  if (!(state->attributes & NPAD_ATTR_CONNECTED))
    return false;
  *connected = true;
  /* buttons beyond those this module knows (A..D-pad, the sticks' directions, SL, SR): logged once each, to
   * learn what the Switch 2's controllers send (GL / GR are the system's to assign: nn::hid's
   * GetGlGrButtonConfigState; whether a game ever sees them as buttons of their own is unknown) */
  static uint64_t unknown_seen;
  uint64_t unknown = state->buttons & ~(uint64_t)0x3FFFFFF;
  if (unknown & ~unknown_seen) {
    unknown_seen |= unknown;
    log_printf("input: buttons this module doesn't know, from NpadIdType %u: 0x%llx", (unsigned)npad_id,
               (unsigned long long)unknown);
  }
  buttons_held |= (uint32_t)state->buttons;
  if (state->lx || state->ly) {
    stick_axes[0] = state->lx;
    stick_axes[1] = state->ly;
  }
  if (state->rx || state->ry) {
    stick_axes[2] = state->rx;
    stick_axes[3] = state->ry;
  }
  /* in use: a button (not the sticks' direction bits) or a stick well off centre, so a resting stick's
   * drift doesn't count */
  const int32_t off = 0x3000; /* about 40% of a stick's travel */
  return (state->buttons & 0xFFFF) || state->lx > off || state->lx < -off || state->ly > off || state->ly < -off ||
         state->rx > off || state->rx < -off || state->ry > off || state->ry < -off;
}

int input_controller(void)
{
  return controller;
}

static void actions_update(void);
static void keyboard_menu_keys(void);

void input_update(void)
{
  uint32_t previously_held = buttons_held;
  buttons_held = 0;
  stick_axes[0] = stick_axes[1] = stick_axes[2] = stick_axes[3] = 0;
  /* the controller is the one used last; one that's gone gives way to one that's there */
  bool connected[3], used[3];
  used[INPUT_PRO] = read_npad(hid_detail_fullkey, NPAD_NO1, &connected[INPUT_PRO]);
  used[INPUT_JOYCONS] = read_npad(hid_detail_joydual, NPAD_NO1, &connected[INPUT_JOYCONS]);
  used[INPUT_HANDHELD] = read_npad(hid_detail_handheld, NPAD_HANDHELD, &connected[INPUT_HANDHELD]);
  for (int i = 0; i < 3; i++)
    if (used[i] || (!connected[controller] && connected[i]))
      controller = i;
  keyboard_menu_keys();
  buttons_pressed = buttons_held & ~previously_held;
  actions_update();

  buttons_fired = buttons_pressed;
  if (buttons_pressed) {
    repeat_buttons = buttons_pressed;
    repeat_countdown = REPEAT_FIRST_DELAY;
  } else if (buttons_held & repeat_buttons) {
    repeat_buttons &= buttons_held;
    if (--repeat_countdown <= 0) {
      repeat_countdown = REPEAT_INTERVAL;
      buttons_fired = repeat_buttons;
    }
  } else {
    repeat_buttons = 0;
  }
}

uint32_t input_held(void) { return buttons_held; }
uint32_t input_pressed(void) { return buttons_pressed; }

bool input_combo(uint32_t mask)
{
  return (buttons_held & mask) == mask && (buttons_pressed & mask);
}

bool input_repeat(uint32_t button)
{
  return (buttons_fired & button) != 0;
}

void input_sticks(int32_t *lx, int32_t *ly, int32_t *rx, int32_t *ry)
{
  *lx = stick_axes[0];
  *ly = stick_axes[1];
  *rx = stick_axes[2];
  *ry = stick_axes[3];
}

/* --- hiding input from the game -------------------------------------------------------------
 * Slopped Up Sloperina: KaeGae Core hands every controller read the game makes to input_filter (its
 * input event), where the game's copy is edited: blanked while the menu is open, otherwise frame
 * advance's buffered input added and the buttons the game mustn't see taken out. */
bool input_force_active;
uint32_t input_force_buttons;
bool input_force_sticks[2];
int32_t input_force_stick[4];

void input_filter(void *kae_input)
{
  KaeInput *state = kae_input;
  if (!input_block_game && !input_hide_from_game && !input_force_active)
    return;
  if (input_block_game) {
    state->buttons = 0;
    state->lx = state->ly = state->rx = state->ry = 0;
    return;
  }
  if (input_force_active) {
    state->buttons |= input_force_buttons;
    if (input_force_sticks[0]) {
      state->lx = input_force_stick[0];
      state->ly = input_force_stick[1];
    }
    if (input_force_sticks[1]) {
      state->rx = input_force_stick[2];
      state->ry = input_force_stick[3];
    }
  }
  state->buttons &= ~(uint64_t)input_hide_from_game;
}

/* --- actions --------------------------------------------------------------------------------
 * Each of gz's shortcuts is a KAE_BINDING item on Core's Mods page, so it can be rebound there and
 * given a keyboard key. The controller part is read here from this module's own controller read (so
 * it works while frame advance holds the game's thread); the key through kae_binding_held, which
 * reads the keyboard right away. A combination inside a bigger one that is held doesn't count (R +
 * D-right is the watches, R + A + D-right resets the jump height): gz's three-button commands came
 * first. Frame advance's button is left out of that: it handles its own shortcuts. */
#define BINDING(label, help, buttons) \
  { KAE_BINDING, label, help, 0, 0, 0, 0, 0, 0, buttons, buttons, action_changed, 0 }

int frame_advance_button; /* 0 L, 1 R: gz's own setting, kept in step with the binding */

static void action_changed(KaeItem *item, void *user);

static KaeItem actions[ACT_COUNT] = {
  [ACT_MENU]          = BINDING("Open / close the menu", "gz's menu (R + C-down on the N64).", BTN_R | BTN_RS_DOWN),
  [ACT_BACK]          = BINDING("Menu: back", "Up one level in the menu; closes it at the top.", BTN_R | BTN_DLEFT),
  [ACT_SAVE_POS]      = BINDING("Save position", "Remembers where Link stands.", BTN_R | BTN_DUP),
  [ACT_LOAD_POS]      = BINDING("Load position", "Puts Link back where he was saved.", BTN_R | BTN_DDOWN),
  [ACT_LEVITATE]      = BINDING("Levitate: start / stop", "While levitate is on in the menu.", BTN_LSTICK),
  [ACT_FRAME_ADVANCE] = BINDING("Frame advance", "Tap: pause, then a frame a tap. Hold: frames in a row.", BTN_L),
  [ACT_RUN]           = BINDING("Frame advance: run", "Runs the game again after frame advance.", BTN_L | BTN_LSTICK),
  [ACT_TIMER]         = BINDING("Timer: start / stop", 0, BTN_R | BTN_A | BTN_DLEFT),
  [ACT_TIMER_RESET]   = BINDING("Timer: reset", 0, BTN_R | BTN_B | BTN_DLEFT),
  [ACT_LAG_RESET]     = BINDING("Lag counter: reset", 0, BTN_R | BTN_B | BTN_DRIGHT),
  [ACT_JUMP_RESET]    = BINDING("Jump height: reset", 0, BTN_R | BTN_A | BTN_DRIGHT),
  [ACT_WATCHES]       = BINDING("Watches: show / hide", 0, BTN_R | BTN_DRIGHT),
};
static uint32_t actions_held, actions_pressed;

static void action_changed(KaeItem *item, void *user)
{
  if (item == &actions[ACT_FRAME_ADVANCE])
    frame_advance_button = (item->binding & BTN_R) != 0;
}

void actions_register(void)
{
  if (kae_settings("Slopped Up Sloperina", actions, ACT_COUNT) != KAE_OK)
    KAE_LOG("slopped up sloperina: Core refused the settings page; gz's own buttons only");
}

/* gz's frame advance button setting (L or R): moves the binding and frame advance's run with it */
void action_set_buttons(int action, uint32_t buttons)
{
  actions[action].binding = buttons;
  action_changed(&actions[action], 0);
}

static bool all_held(uint32_t mask) { return mask && (buttons_held & mask) == mask; }

static void actions_update(void)
{
  uint32_t before = actions_held, pad = 0;
  actions_held = 0;
  for (int i = 0; i < ACT_COUNT; i++)
    if (all_held((uint32_t)actions[i].binding))
      pad |= 1u << i;
  for (int i = 0; i < ACT_COUNT; i++) {
    uint32_t mine = (uint32_t)actions[i].binding;
    bool held = pad >> i & 1;
    if (held && i != ACT_FRAME_ADVANCE)
      for (int j = 0; j < ACT_COUNT && held; j++)
        if (j != i && (pad >> j & 1) && ((uint32_t)actions[j].binding & mine) == mine && actions[j].binding != mine)
          held = false;   /* part of a bigger combination that is held */
    /* not held on the controller: its key (kae_binding_held also looks at the controller, which this
     * module read itself just now) */
    if (!(pad >> i & 1) && kae_binding_held(&actions[i]))
      held = true;
    if (held)
      actions_held |= 1u << i;
  }
  actions_pressed = actions_held & ~before;
}

bool action_held(int action) { return actions_held >> action & 1; }
bool action_pressed(int action) { return actions_pressed >> action & 1; }
uint32_t action_buttons(int action) { return (uint32_t)actions[action].binding; }
uint32_t action_buttons_held(int action)
{
  uint32_t mine = (uint32_t)actions[action].binding;
  return all_held(mine) ? mine : 0;
}

/* --- the keyboard in the menu ------------------------------------------------------------------
 * While gz's menu is open: the arrow keys are the D-pad, Enter is L (choose) and Backspace is B
 * (back). Read from the system directly, only when Core says the keyboard is on (kae_has), and only
 * after nn::hid::InitializeKeyboard: GetKeyboardState stops the game without it. */
typedef struct {
  int64_t sample;
  uint32_t modifiers, attributes;
  uint64_t keys[4];   /* bit n = USB HID usage n */
} keyboard_state_t;
void hid_initialize_keyboard(void) __asm__("_ZN2nn3hid18InitializeKeyboardEv");
void hid_get_keyboard_state(keyboard_state_t *out) __asm__("_ZN2nn3hid16GetKeyboardStateEPNS0_13KeyboardStateE");

enum { KEY_ENTER = 40, KEY_BACKSPACE = 42, KEY_RIGHT = 79, KEY_LEFT = 80, KEY_DOWN = 81, KEY_UP = 82 };

static void keyboard_menu_keys(void)
{
  static bool ready;
  if (!menu_current || !kae_has("keyboard"))
    return;
  if (!ready) {
    ready = true;
    hid_initialize_keyboard();
  }
  keyboard_state_t state = { 0 };
  hid_get_keyboard_state(&state);
  static const struct { int key; uint32_t button; } map[] = {
    { KEY_UP, BTN_DUP }, { KEY_DOWN, BTN_DDOWN }, { KEY_LEFT, BTN_DLEFT }, { KEY_RIGHT, BTN_DRIGHT },
    { KEY_ENTER, BTN_L }, { KEY_BACKSPACE, BTN_B },
  };
  for (unsigned i = 0; i < sizeof map / sizeof *map; i++)
    if (state.keys[map[i].key >> 6] >> (map[i].key & 63) & 1)
      buttons_held |= map[i].button;
}
