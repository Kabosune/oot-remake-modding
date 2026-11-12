#include "kae_menu.h"
#ifndef KAE_MENU_ON_CORE
#include "font.h"
#endif

enum { TAB_MODS, TAB_CONTROLS, TAB_ABOUT, TAB_COUNT };
static const char *const tab_names[TAB_COUNT] = { "Mods", "Controls", "About" };

/* ---------------------------------------------------------------- small helpers */

static int str_len(const char *s) { int n = 0; while (s && s[n]) n++; return n; }

static void str_add(char *out, int size, const char *s)
{
    int n = str_len(out);
    while (s && *s && n < size - 1) out[n++] = *s++;
    out[n] = 0;
}

static void int_text(int v, char *out, int size)
{
    char tmp[12]; int n = 0; unsigned u = v < 0 ? 0u - (unsigned)v : (unsigned)v;
    out[0] = 0;
    do tmp[n++] = (char)('0' + u % 10); while (u /= 10);
    if (v < 0) str_add(out, size, "-");
    while (n) { char c[2] = { tmp[--n], 0 }; str_add(out, size, c); }
}

char *kae_binding_text(uint64_t mask, char *out, int size)
{
    static const char *const names[24] = { "A", "B", "X", "Y", "L3", "R3", "L", "R", "ZL", "ZR",
                                           "Plus", "Minus", "Left", "Up", "Right", "Down",
                                           "LS Left", "LS Up", "LS Right", "LS Down",
                                           "RS Left", "RS Up", "RS Right", "RS Down" };
    out[0] = 0;
    for (int i = 0; i < 24; i++)
        if (mask >> i & 1) { if (out[0]) str_add(out, size, " + "); str_add(out, size, names[i]); }
    if (!out[0]) str_add(out, size, "none");
    return out;
}

/* ---------------------------------------------------------------- keyboard keys */

/* USB HID usages, as nn::hid's KeyboardState reports them (bit n of its keys = usage n). */
static const char *key_names(int key, char *tmp)
{
    static const char *const low[] = {                         /* 40 .. 57 */
        "Enter", "Escape", "Backspace", "Tab", "Space", "-", "=", "[", "]", "\\", "#", ";", "'", "`", ",", ".", "/",
        "Caps Lock" };
    static const char *const mid[] = {                         /* 70 .. 99 */
        "Print Screen", "Scroll Lock", "Pause", "Insert", "Home", "Page Up", "Delete", "End", "Page Down",
        "Right", "Left", "Down", "Up", "Num Lock", "Num /", "Num *", "Num -", "Num +", "Num Enter",
        "Num 1", "Num 2", "Num 3", "Num 4", "Num 5", "Num 6", "Num 7", "Num 8", "Num 9", "Num 0", "Num ." };
    static const char *const mods[] = {                        /* 224 .. 231 */
        "Left Ctrl", "Left Shift", "Left Alt", "Left Win", "Right Ctrl", "Right Shift", "Right Alt", "Right Win" };
    if (key >= 4 && key <= 29) { tmp[0] = (char)('A' + key - 4); tmp[1] = 0; return tmp; }
    if (key >= 30 && key <= 39) { tmp[0] = (char)(key == 39 ? '0' : '1' + key - 30); tmp[1] = 0; return tmp; }
    if (key >= 40 && key <= 57) return low[key - 40];
    if (key >= 58 && key <= 69) { tmp[0] = 'F'; int_text(key - 57, tmp + 1, 4); return tmp; }
    if (key >= 70 && key <= 99) return mid[key - 70];
    if (key >= 224 && key <= 231) return mods[key - 224];
    return 0;
}

const char *kae_key_name(int key, char *out, int size)
{
    char tmp[16];
    out[0] = 0;
    if (key <= 0 || key > 255) { str_add(out, size, "none"); return out; }
    const char *name = key_names(key, tmp);
    if (name) str_add(out, size, name);
    else { char n[12]; int_text(key, n, sizeof n); str_add(out, size, "Key "); str_add(out, size, n); }
    return out;
}

static int lower(int c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }

int kae_key_from_name(const char *name, int n)
{
    char buf[24];
    for (int key = 0; key < 256; key++) {
        kae_key_name(key, buf, sizeof buf);
        int i = 0;
        while (i < n && buf[i] && lower(buf[i]) == lower(name[i])) i++;
        if (i == n && !buf[i]) return key;
    }
    return -1;
}

static int key_down(const uint64_t *keys, int key) { return key > 0 && key < 256 && (int)(keys[key >> 6] >> (key & 63) & 1); }

unsigned char *kae_menu_key_of(const KaeMenu *m, const KaeItem *item, const KaePage **owner)
{
    for (int p = 0; p < m->npages; p++) {
        const KaePage *pg = m->pages[p];
        if (pg->items && item >= pg->items && item < pg->items + pg->count) {
            int i = (int)(item - pg->items);
            if (owner) *owner = pg;
            return pg->keys && i < KAE_MAX_KEYED && item->type == KAE_BINDING ? &pg->keys[i] : 0;
        }
    }
    return 0;
}

/* The selected cell of a binding is its key. */
static int on_key_cell(const KaeMenu *m, const KaeItem *it)
{
    return it->type == KAE_BINDING && m->keyboard && m->column && kae_menu_key_of(m, it, 0);
}

static int key_of(const KaeMenu *m, const KaeItem *item)
{
    const unsigned char *k = kae_menu_key_of(m, item, 0);
    return k ? *k : 0;
}

const KaeItem *kae_menu_key_clash(const KaeMenu *m, const KaeItem *item, const KaePage **owner)
{
    int key = key_of(m, item);
    if (!key) return 0;
    for (int p = 0; p < m->npages; p++) {
        const KaePage *pg = m->pages[p];
        if (!pg->enabled || !pg->keys) continue;
        for (int i = 0; i < pg->count && i < KAE_MAX_KEYED; i++) {
            const KaeItem *o = &pg->items[i];
            if (o != item && o->type == KAE_BINDING && pg->keys[i] == key) {
                if (owner) *owner = pg;
                return o;
            }
        }
    }
    return 0;
}

void kae_menu_add(KaeMenu *m, KaePage *page)
{
    if (m->npages < KAE_MAX_PAGES) m->pages[m->npages++] = page;
}

const KaeItem *kae_menu_clash(const KaeMenu *m, const KaeItem *item, const KaePage **owner)
{
    if (item->type != KAE_BINDING || !item->binding) return 0;
    for (int p = 0; p < m->npages; p++) {
        const KaePage *pg = m->pages[p];
        if (!pg->enabled) continue;
        for (int i = 0; i < pg->count; i++) {
            const KaeItem *o = &pg->items[i];
            if (o != item && o->type == KAE_BINDING && o->binding == item->binding) {
                if (owner) *owner = pg;
                return o;
            }
        }
    }
    return 0;
}

/* The Controls tab lists every binding of every mod: entry n -> its item. */
static KaeItem *control_at(const KaeMenu *m, int n, const KaePage **owner)
{
    for (int p = 0; p < m->npages; p++)
        for (int i = 0; i < m->pages[p]->count; i++)
            if (m->pages[p]->items[i].type == KAE_BINDING && n-- == 0) {
                if (owner) *owner = m->pages[p];
                return &m->pages[p]->items[i];
            }
    return 0;
}

static int control_count(const KaeMenu *m) { int n = 0; while (control_at(m, n, 0)) n++; return n; }

/* ---------------------------------------------------------------- input */

static void notify(KaeItem *it) { if (it->changed) it->changed(it, it->user); }

static void adjust(KaeItem *it, int dir)
{
    int old = it->value;
    if (it->type == KAE_TOGGLE) it->value = !it->value;
    else if (it->type == KAE_CHOICE) it->value = (it->value + dir + it->max + 1) % (it->max + 1);
    else if (it->type == KAE_NUMBER) {
        it->value += dir * (it->step ? it->step : 1);
        if (it->value < it->min) it->value = it->min;
        if (it->value > it->max) it->value = it->max;
    } else return;
    if (it->value != old) notify(it);
}

static void reset_item(KaeMenu *m, KaeItem *it)
{
    if (on_key_cell(m, it)) { *kae_menu_key_of(m, it, 0) = 0; return; }   /* keys have no default: back to none */
    if (it->type == KAE_BINDING) { if (it->binding != it->def_binding) { it->binding = it->def_binding; notify(it); } }
    else if (it->type != KAE_ACTION && it->value != it->def) { it->value = it->def; notify(it); }
}

static void activate(KaeMenu *m, KaeItem *it)
{
    if (on_key_cell(m, it)) { m->capture = it; m->key_capture = 1; m->capture_stage = 0; m->capture_frames = 0; }
    else if (it->type == KAE_BINDING) { m->key_capture = 0; m->capture = it; m->capture_stage = 0; m->capture_frames = 0; m->capture_mask = 0; }
    else if (it->type == KAE_ACTION) notify(it);
    else adjust(it, 1);
}

static void move(int *cursor, int count, int dir)
{
    if (count > 0) *cursor = (*cursor + dir + count) % count;
}

static void navigate(KaeMenu *m, uint64_t press)
{
    KaeItem *it = 0;
    int count;
    if (m->depth == 1) {
        KaePage *pg = m->pages[m->page];
        count = pg->count;
        it = count ? &pg->items[m->item_cursor] : 0;
        if (press & KAE_UP) move(&m->item_cursor, count, -1);
        if (press & KAE_DOWN) move(&m->item_cursor, count, 1);
        if (press & KAE_B) m->depth = 0;
    } else {
        count = m->tab == TAB_MODS ? m->npages : m->tab == TAB_CONTROLS ? control_count(m) : m->ncore;
        if (press & KAE_UP) move(&m->cursor[m->tab], count, -1);
        if (press & KAE_DOWN) move(&m->cursor[m->tab], count, 1);
        if (press & KAE_L) m->tab = (m->tab + TAB_COUNT - 1) % TAB_COUNT;
        if (press & KAE_R) m->tab = (m->tab + 1) % TAB_COUNT;
        if (press & KAE_B) { m->open = 0; m->swallow = 1; return; }
        if (m->tab == TAB_MODS && count) {
            KaePage *pg = m->pages[m->cursor[TAB_MODS]];
            if (press & KAE_A) { m->page = m->cursor[TAB_MODS]; m->depth = 1; m->item_cursor = 0; }
            if (press & KAE_X && !pg->status) pg->enabled = !pg->enabled;
            return;
        }
        if (m->tab == TAB_CONTROLS && count) it = control_at(m, m->cursor[TAB_CONTROLS], 0);
        if (m->tab == TAB_ABOUT && count) it = &m->core_items[m->cursor[TAB_ABOUT] % count];
    }
    if (!it) return;
    if (it->type == KAE_BINDING && m->keyboard && kae_menu_key_of(m, it, 0)) {   /* Left / Right: the other cell */
        if (press & KAE_LEFT) m->column = 0;
        if (press & KAE_RIGHT) m->column = 1;
    }
    if (press & KAE_A) activate(m, it);
    if (press & KAE_LEFT) adjust(it, -1);
    if (press & KAE_RIGHT) adjust(it, 1);
    if (press & KAE_Y) reset_item(m, it);
}

/* Waits for all buttons up, then records everything pressed until all are up again. */
static void capture_step(KaeMenu *m, uint64_t down)
{
    if (m->capture_stage == 0) { if (!down) m->capture_stage = 1; return; }
    m->capture_mask |= down;
    if (m->capture_mask && !down) { m->capture->binding = m->capture_mask; notify(m->capture); m->capture = 0; }
    else if (!m->capture_mask && ++m->capture_frames > 300) m->capture = 0;   /* nothing pressed: give up */
}

/* Waits for all keys up, then takes the first key pressed. B on the controller gives up. */
static void key_capture_step(KaeMenu *m, uint64_t press)
{
    int any = 0, first = 0;
    for (int key = 1; key < 256; key++)
        if (key_down(m->keys, key)) { any = 1; if (!first && !key_down(m->keys_prev, key)) first = key; }
    if (press & KAE_B || ++m->capture_frames > 300) { m->capture = 0; return; }
    if (m->capture_stage == 0) { if (!any) m->capture_stage = 1; return; }
    if (first) {
        unsigned char *k = kae_menu_key_of(m, m->capture, 0);
        if (k) *k = (unsigned char)first;
        m->capture = 0;
    }
}

void kae_menu_input(KaeMenu *m, const KaePad *real, KaePad *game)
{
    uint64_t down = real->buttons & 0xffff;
    if (real->ly > 16000) down |= KAE_UP;
    if (real->ly < -16000) down |= KAE_DOWN;
    if (real->lx < -16000) down |= KAE_LEFT;
    if (real->lx > 16000) down |= KAE_RIGHT;
    uint64_t press = down & ~m->prev;
    uint64_t chord = real->buttons & KAE_OPEN_CHORD;
    *game = *real;

    if (m->swallow) {                       /* after opening or closing: nothing until all buttons are up */
        game->buttons = 0;
        if (!(real->buttons & 0xffff)) m->swallow = 0;
        m->pending = 0;
    } else if (m->open) {
        game->buttons = 0; game->lx = game->ly = game->rx = game->ry = 0;
        if (m->capture && m->key_capture) key_capture_step(m, press);
        else if (m->capture) capture_step(m, real->buttons & KAE_BINDING_MASK);
        else if (chord == KAE_OPEN_CHORD) { m->open = 0; m->swallow = 1; }
        else {
            uint64_t dirs = down & (KAE_UP | KAE_DOWN | KAE_LEFT | KAE_RIGHT);
            if (dirs && dirs == m->repeat_button) {           /* held direction repeats */
                if (++m->repeat_frames >= 18) { press |= dirs; m->repeat_frames = 14; }
            } else { m->repeat_button = dirs; m->repeat_frames = 0; }
            navigate(m, press);
        }
        if (m->swallow) game->buttons = 0;
    } else {
        if (m->replay_frames) { game->buttons |= m->replay; m->replay_frames--; }
        if (chord == KAE_OPEN_CHORD && m->pending && m->pending_frames <= KAE_CHORD_WINDOW) {
            m->open = 1; m->swallow = 1; m->pending = 0; m->depth = 0; m->capture = 0;
            game->buttons = 0;
        } else if (chord) {
            if (!m->pending) { m->pending = chord; m->pending_frames = 0; }
            if (++m->pending_frames <= KAE_CHORD_WINDOW) game->buttons &= ~(uint64_t)KAE_OPEN_CHORD;
        } else {
            /* a tap shorter than the window never reached the game: play it back now */
            if (m->pending && m->pending_frames <= KAE_CHORD_WINDOW) { m->replay = m->pending; m->replay_frames = 2; game->buttons |= m->replay; m->replay_frames--; }
            m->pending = 0;
        }
    }
    m->prev = down;
    for (int i = 0; i < 4; i++) m->keys_prev[i] = m->keys[i];
}

/* ---------------------------------------------------------------- drawing */

static const uint32_t C_PANEL = 0x16211c, C_HEAD = 0x0f1814, C_ROW = 0x243a30, C_SEL = 0xd9b45a,
                      C_TEXT = 0xeae6d8, C_DIM = 0x9aa79f, C_DARK = 0x16211c, C_WARN = 0xe8734a,
                      C_OFF = 0x6f7b74, C_LINE = 0x35503f;


#ifndef KAE_MENU_ON_CORE
typedef struct { uint8_t *px; int w, h, stride; float s; } Canvas;      /* s: scale from 1080p units */

static void blend(Canvas *c, int x, int y, uint32_t rgb, int a)
{
    if (x < 0 || y < 0 || x >= c->w || y >= c->h) return;
    uint8_t *p = c->px + (long)y * c->stride + x * 4;
    p[0] = (uint8_t)((p[0] * (255 - a) + (rgb >> 16 & 255) * a) / 255);
    p[1] = (uint8_t)((p[1] * (255 - a) + (rgb >> 8 & 255) * a) / 255);
    p[2] = (uint8_t)((p[2] * (255 - a) + (rgb & 255) * a) / 255);
    p[3] = 255;
}

static void rect(Canvas *c, float x, float y, float w, float h, uint32_t rgb)
{
    int x0 = (int)(x * c->s), y0 = (int)(y * c->s), x1 = (int)((x + w) * c->s), y1 = (int)((y + h) * c->s);
    for (int j = y0; j < y1; j++) for (int i = x0; i < x1; i++) blend(c, i, j, rgb, 255);
}

static int glyph_alpha(int g, int x, int y)
{
    if (x < 0 || y < 0 || x >= kae_glyphs[g].w || y >= kae_glyphs[g].h) return 0;
    int n = y * kae_glyphs[g].w + x;
    int v = kae_font_data[kae_glyphs[g].off + n / 2] >> (n & 1 ? 0 : 4) & 15;
    return v * 17;
}

static float text_width(const char *t, float size)
{
    float w = 0;
    for (; t && *t; t++) if (*t >= 32 && *t < 127) w += kae_glyphs[*t - 32].adv;
    return w * size / KAE_FONT_PX;
}

/* size: text height in 1080p units. Bilinear sampling, so any scale works. */
static float text(Canvas *c, float x, float y, const char *t, float size, uint32_t rgb)
{
    float k = size / KAE_FONT_PX * c->s;                 /* font pixels -> screen pixels */
    for (; t && *t; t++) {
        if (*t < 32 || *t >= 127) continue;
        int g = *t - 32;
        float gx = x * c->s + kae_glyphs[g].x * k, gy = y * c->s + kae_glyphs[g].y * k;
        int w = (int)(kae_glyphs[g].w * k) + 1, h = (int)(kae_glyphs[g].h * k) + 1;
        for (int j = 0; j < h; j++) for (int i = 0; i < w; i++) {
            float u = (i + 0.5f) / k - 0.5f, v = (j + 0.5f) / k - 0.5f;
            int u0 = (int)(u < 0 ? u - 1 : u), v0 = (int)(v < 0 ? v - 1 : v);
            float fu = u - u0, fv = v - v0;
            float a = glyph_alpha(g, u0, v0) * (1 - fu) * (1 - fv) + glyph_alpha(g, u0 + 1, v0) * fu * (1 - fv)
                    + glyph_alpha(g, u0, v0 + 1) * (1 - fu) * fv + glyph_alpha(g, u0 + 1, v0 + 1) * fu * fv;
            if (a > 1) blend(c, (int)gx + i, (int)gy + j, rgb, (int)a);
        }
        x += kae_glyphs[g].adv * size / KAE_FONT_PX;
    }
    return x;
}

#else
/* Inside Core: rectangles and Core's own 8 x 16 font at whole-number scales. */
typedef struct { float s; } Canvas;                                     /* s: scale from 1080p units */
static float canvas_scale = 1;

static void rect(Canvas *c, float x, float y, float w, float h, uint32_t rgb)
{
    int x0 = (int)(x * c->s), y0 = (int)(y * c->s), x1 = (int)((x + w) * c->s), y1 = (int)((y + h) * c->s);
    kae_draw_rect(x0, y0, x1 - x0, y1 - y0, rgb);
}

/* The font scale closest to a text height given in 1080p units. */
static int font_scale(float size)
{
    int k = (int)(size * canvas_scale / 16.0f + 0.5f);
    return k < 1 ? 1 : k;
}

static float text_width(const char *t, float size)
{
    return (float)kae_text_width(font_scale(size), t) / canvas_scale;
}

static float text(Canvas *c, float x, float y, const char *t, float size, uint32_t rgb)
{
    int k = font_scale(size);
    /* the line the host font would fill is about 1.2 x size high: centre this font's 16 rows in it */
    int px = (int)(x * c->s), py = (int)(y * c->s + (size * 1.2f * c->s - 16.0f * (float)k) / 2);
    return (float)kae_draw_text(px, py, k, rgb, t ? t : "") / c->s;
}

#endif

static void text_right(Canvas *c, float right, float y, const char *t, float size, uint32_t rgb)
{
    text(c, right - text_width(t, size), y, t, size, rgb);
}

#define PX 330.0f      /* panel, in 1080p units */
#define PY 110.0f
#define PW 1260.0f
#define PH 860.0f
#define ROW 58.0f
#define ROWS 10

static void row(Canvas *c, int n, int selected, const char *left, const char *right, uint32_t left_rgb, uint32_t right_rgb)
{
    float y = PY + 118 + n * ROW;
    rect(c, PX + 30, y, PW - 60, ROW - 6, selected ? C_SEL : C_ROW);
    text(c, PX + 52, y + 12, left, 26, selected ? C_DARK : left_rgb);
    if (right) text_right(c, PX + PW - 52, y + 12, right, 26, selected ? C_DARK : right_rgb);
}

#define KEY_W 220.0f   /* the Keyboard column */

static int keyed(const KaeMenu *m, const KaeItem *it) { return it->type == KAE_BINDING && m->keyboard && kae_menu_key_of(m, it, 0); }

/* A binding's two cells, controller and keyboard, at the right of row n; the selected one boxed. */
static void binding_cells(Canvas *c, const KaeMenu *m, int n, int selected, const KaeItem *it, const char *pad,
                          uint32_t pad_rgb, uint32_t key_rgb)
{
    char key[32];
    float y = PY + 118 + n * ROW, right = PX + PW - 52, pad_right = right - KEY_W - 24;
    if (m->capture == it && m->key_capture) { key[0] = 0; str_add(key, sizeof key, "press a key"); }
    else kae_key_name(key_of(m, it), key, sizeof key);
    for (int cell = 0; cell < 2; cell++) {
        const char *t = cell ? key : pad;
        float r = cell ? right : pad_right, w = text_width(t, 26);
        int boxed = selected && m->column == cell;
        if (boxed) rect(c, r - w - 12, y + 5, w + 24, ROW - 16, C_PANEL);
        text_right(c, r, y + 12, t, 26, boxed ? (cell ? key_rgb : pad_rgb) : selected ? C_DARK : cell ? key_rgb : pad_rgb);
    }
}

static void column_titles(Canvas *c)
{
    float right = PX + PW - 52;
    text_right(c, right - KEY_W - 24, PY + 94, "Controller", 20, C_DIM);
    text_right(c, right, PY + 94, "Keyboard", 20, C_DIM);
}

static void value_text(const KaeItem *it, char *out, int size)
{
    out[0] = 0;
    if (it->type == KAE_TOGGLE) str_add(out, size, it->value ? "On" : "Off");
    else if (it->type == KAE_CHOICE) { str_add(out, size, "< "); str_add(out, size, it->choices[it->value]); str_add(out, size, " >"); }
    else if (it->type == KAE_NUMBER) { char n[12]; int_text(it->value, n, sizeof n); str_add(out, size, "< "); str_add(out, size, n); str_add(out, size, " >"); }
    else if (it->type == KAE_BINDING) kae_binding_text(it->binding, out, size);
}

static void draw_menu(const KaeMenu *m, Canvas *c)
{
    char buf[96], buf2[96];
    const char *help = 0, *hints;
    int titles = 0, bind_hints = 0;
    uint32_t help_rgb = C_DIM;

    rect(c, PX - 4, PY - 4, PW + 8, PH + 8, C_LINE);
    rect(c, PX, PY, PW, PH, C_PANEL);
    rect(c, PX, PY, PW, 92, C_HEAD);
    rect(c, PX, PY + PH - 64, PW, 64, C_HEAD);

    if (m->depth == 1) {
        const KaePage *pg = m->pages[m->page];
        float x = text(c, PX + 40, PY + 26, pg->name, 38, C_TEXT);
        text(c, x + 18, PY + 38, pg->version, 24, C_DIM);
        text_right(c, PX + PW - 40, PY + 36, pg->id, 24, C_DIM);
        int first = m->item_cursor >= ROWS ? m->item_cursor - ROWS + 1 : 0;
        for (int i = first; i < pg->count && i < first + ROWS; i++) {
            const KaeItem *it = &pg->items[i];
            int sel = i == m->item_cursor;
            value_text(it, buf, sizeof buf);
            if (m->capture == it && !m->key_capture) { buf[0] = 0; str_add(buf, sizeof buf, "press buttons, then let go"); }
            int clash = kae_menu_clash(m, it, 0) != 0, key_clash = kae_menu_key_clash(m, it, 0) != 0;
            if (keyed(m, it)) {
                row(c, i - first, sel, it->label, 0, C_TEXT, C_TEXT);
                binding_cells(c, m, i - first, sel, it, buf, clash ? C_WARN : C_TEXT, key_clash ? C_WARN : C_TEXT);
                titles = 1;
            } else
                row(c, i - first, sel, it->label, it->type == KAE_ACTION ? 0 : buf, C_TEXT, clash ? C_WARN : C_TEXT);
            if (sel) help = it->help;
            if (sel && (clash || key_clash)) {
                const KaePage *o = 0;
                int by_key = key_clash && (m->column || !clash);
                const KaeItem *oi = by_key ? kae_menu_key_clash(m, it, &o) : kae_menu_clash(m, it, &o);
                buf2[0] = 0; str_add(buf2, sizeof buf2, by_key ? "Same key as " : "Same buttons as ");
                str_add(buf2, sizeof buf2, o->name);
                str_add(buf2, sizeof buf2, ": "); str_add(buf2, sizeof buf2, oi->label);
                help = buf2; help_rgb = C_WARN;
            }
            if (sel && keyed(m, it)) bind_hints = 1;
        }
        if (titles) column_titles(c);
        if (!pg->count) text(c, PX + 52, PY + 130, "This mod has no settings.", 26, C_DIM);
        hints = bind_hints ? "A  Change      Left / Right  Controller / Keyboard      Y  Default      B  Back"
                           : "A  Change      Left / Right  Adjust      Y  Default      B  Back";
    } else {
        text(c, PX + 40, PY + 26, "Mods", 38, C_TEXT);
        float x = PX + PW - 40;
        for (int t = TAB_COUNT - 1; t >= 0; t--) {
            float w = text_width(tab_names[t], 28);
            x -= w;
            if (t == m->tab) rect(c, x - 14, PY + 76, w + 28, 6, C_SEL);
            text(c, x, PY + 32, tab_names[t], 28, t == m->tab ? C_TEXT : C_DIM);
            x -= 48;
        }
        if (m->tab == TAB_MODS) {
            int cur = m->cursor[TAB_MODS], first = cur >= ROWS ? cur - ROWS + 1 : 0;
            for (int i = first; i < m->npages && i < first + ROWS; i++) {
                const KaePage *pg = m->pages[i];
                buf[0] = 0; str_add(buf, sizeof buf, pg->name); str_add(buf, sizeof buf, "  "); str_add(buf, sizeof buf, pg->version);
                row(c, i - first, i == cur, buf, pg->status ? "Unavailable" : pg->enabled ? "On" : "Off",
                    pg->enabled && !pg->status ? C_TEXT : C_OFF, pg->status ? C_WARN : pg->enabled ? C_TEXT : C_OFF);
                if (i == cur && pg->status) { help = pg->status; help_rgb = C_WARN; }
            }
            if (!m->npages) text(c, PX + 52, PY + 130, "No mods are installed.", 26, C_DIM);
            hints = "A  Settings      X  On / Off      L / R  Tab      B  Close";
        } else if (m->tab == TAB_CONTROLS) {
            int cur = m->cursor[TAB_CONTROLS], first = cur >= ROWS ? cur - ROWS + 1 : 0, n = control_count(m);
            for (int i = first; i < n && i < first + ROWS; i++) {
                const KaePage *pg = 0; const KaeItem *it = control_at(m, i, &pg);
                buf[0] = 0; str_add(buf, sizeof buf, pg->name); str_add(buf, sizeof buf, ": "); str_add(buf, sizeof buf, it->label);
                kae_binding_text(it->binding, buf2, sizeof buf2);
                if (m->capture == it && !m->key_capture) { buf2[0] = 0; str_add(buf2, sizeof buf2, "press buttons, then let go"); }
                int clash = pg->enabled && kae_menu_clash(m, it, 0), key_clash = pg->enabled && kae_menu_key_clash(m, it, 0);
                if (keyed(m, it)) {
                    row(c, i - first, i == cur, buf, 0, pg->enabled ? C_TEXT : C_OFF, C_TEXT);
                    binding_cells(c, m, i - first, i == cur, it, buf2, clash ? C_WARN : C_TEXT, key_clash ? C_WARN : C_TEXT);
                    titles = 1;
                    if (i == cur) bind_hints = 1;
                } else
                    row(c, i - first, i == cur, buf, buf2, pg->enabled ? C_TEXT : C_OFF, clash ? C_WARN : C_TEXT);
                if (i == cur && clash) { help = "Another mod that is switched on uses the same buttons."; help_rgb = C_WARN; }
                else if (i == cur && key_clash) { help = "Another mod that is switched on uses the same key."; help_rgb = C_WARN; }
            }
            if (titles) column_titles(c);
            if (!n) text(c, PX + 52, PY + 130, "No mod has buttons to set.", 26, C_DIM);
            hints = bind_hints ? "A  Rebind      Left / Right  Controller / Keyboard      Y  Default      B  Close"
                               : "A  Rebind      Y  Default      L / R  Tab      B  Close";
        } else {
            for (int i = 0; i < m->nabout; i++) text(c, PX + 52, PY + 124 + i * 40, m->about[i], 26, C_TEXT);
            int first_row = (m->nabout * 40 + 30 + (int)ROW - 1) / (int)ROW;
            for (int i = 0; i < m->ncore && first_row + i < ROWS; i++) {
                const KaeItem *it = &m->core_items[i];
                int sel = i == m->cursor[TAB_ABOUT];
                value_text(it, buf, sizeof buf);
                row(c, first_row + i, sel, it->label, buf, C_TEXT, C_TEXT);
                if (sel) help = it->help;
            }
            hints = m->ncore ? "A  Change      Y  Default      L / R  Tab      B  Close" : "L / R  Tab      B  Close";
        }
    }
    if (help) text(c, PX + 52, PY + PH - 112, help, 24, help_rgb);
    text(c, PX + 40, PY + PH - 46, hints, 22, C_DIM);
    text_right(c, PX + PW - 40, PY + PH - 46, "Minus + Plus  Close", 22, C_DIM);
}

#ifdef KAE_MENU_ON_CORE
void kae_menu_draw_core(const KaeMenu *m, int width, int height)
{
    (void)width;
    if (!m->open) return;
    Canvas cv = { (float)height / 1080.0f };
    canvas_scale = cv.s;
    draw_menu(m, &cv);
}
#else
void kae_menu_draw(const KaeMenu *m, uint8_t *rgba, int width, int height, int stride)
{
    if (!m->open) return;
    Canvas cv = { rgba, width, height, stride, (float)height / 1080.0f };
    draw_menu(m, &cv);
}
#endif
