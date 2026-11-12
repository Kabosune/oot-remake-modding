/* Slopped Up Sloperina: sloperinaGZ's panels drawn with KaeGae Core, on the game's render thread.
 *
 * This file replaces sloperinaGZ's nvn.c, gpuui.c and nativeui.c (its own NVN hooks and the game's
 * type). gfx.c still lays the panels out as grids of character cells on the game's thread and
 * publishes them; here each published panel is drawn in gz's style: a solid background and its text in
 * Core's 8 x 16 font (kae_draw_text), the icons as small rectangles. The air walls' outlines and the
 * enemies' health bars arrive as rectangles already (airwall.c and enemyhp.c's gz-style output).
 *
 * Differences from sloperinaGZ's gz style: Core's font instead of gz's pixel font (so cells are 8 x 18
 * font pixels, not 8 x 10), backgrounds are opaque or off (Core has no blending), the controller
 * drawing of the input display is two stick boxes, and the game's item pictures are left out.
 *
 * Licence: GPL-3.0 (see ../LICENSE), as the rest of this mod's sources. */
#include "kaedraw.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "airwall.h"
#include "enemyhp.h"
#include "gfx.h"

#define FONT_W 8      /* Core's font */
#define FONT_H 16
#define CELL_H 18     /* a row: the font and a gap */
#define PAD_Y 4       /* above the first row and below the last, font pixels */
#define MARGIN 8      /* panels keep this far from the picture's edges, font pixels */
#define MIN_MENU_ROWS 6
#define MIN_PANEL_COLS 16
#define MENU_X_PERMILLE 35  /* sloperinaGZ's: the menu under the game's D-pad display */
#define MENU_Y_PERMILLE 345
#define DOT_COORD_MAX 65535 /* aw_dot_t's coordinates: 0..65535 across the picture */

static const int panel_max_cols[GFX_PANELS] = { GFX_COLS, 32, 48, 58 };
static const int panel_max_rows[GFX_PANELS] = { GFX_ROWS, 20, GFX_LOG_ROWS, 10 };

/* sloperinaGZ's colours */
static const uint32_t style_rgb[GFX_NSTYLES] = {
  [GFX_NORMAL] = 0xFFFFFF, [GFX_SELECTED] = 0x80FF80, [GFX_TITLE] = 0xA0C8FF, [GFX_DIM] = 0x909090,
  [GFX_NOTICE] = 0xFFE060, [GFX_LOG] = 0xC0C0C0, [GFX_FAINT] = 0x505058, [GFX_BUTTON] = 0x181820,
};
#define CAP_RGB 0xE0E0E0     /* a button's key cap in the prompts */
#define PAD_DIM_RGB 0x6A6A74 /* the d-pad's and the sticks' outlines in the prompts */
#define BG_RGB 0x181820
#define BAR_RGB 0x606070
static const uint32_t airwall_rgb[AW_NCOLORS] = {
  [AW_BLOCKS] = 0x3BD6FF, [AW_INSIDE] = 0xFF4747, [AW_OTHER] = 0x998CFF, [AW_PUSHES] = 0xFFC22E,
};
static const uint32_t enemyhp_rgb[EH_NCOLORS] = {
  [EH_BACK] = 0x0D0D0D, [EH_FILL] = 0x4CD94C, [EH_LOW] = 0xFF4747, [EH_TEXT] = 0xFFFFFF,
};

/* a colour times a fraction (0..255): the log's fading lines, darkened since nothing can be blended */
static uint32_t dim(uint32_t rgb, int alpha)
{
  uint32_t r = ((rgb >> 16) & 255) * (uint32_t)alpha / 255, g = ((rgb >> 8) & 255) * (uint32_t)alpha / 255,
           b = (rgb & 255) * (uint32_t)alpha / 255;
  return (r << 16) | (g << 8) | b;
}

/* the text scale for a picture this tall: 1 up to 1439 lines, 2 up to 2159, then 3; or the setting's */
static int scale_for(int height)
{
  int menu_scale = gfx_menu_scale;
  if (menu_scale >= 1 && menu_scale <= 3)
    return menu_scale;
  int s = height / 720;
  return s < 1 ? 1 : s > 3 ? 3 : s;
}

static void outline(int x, int y, int w, int h, int t, uint32_t rgb)
{
  kae_draw_rect(x, y, w, t, rgb);
  kae_draw_rect(x, y + h - t, w, t, rgb);
  kae_draw_rect(x, y, t, h, rgb);
  kae_draw_rect(x + w - t, y, t, h, rgb);
}

/* The prompts' d-pad (two cells at x, y) with direction `dir` (0 up, 1 right, 2 down, 3 left) lit. */
static void draw_dpad(int x, int y, int s, int dir, uint32_t lit)
{
  int u = 4 * s, cx = x + 2 * s + u, cy = y + s + u; /* the middle square's corner; arms of u x u */
  static const int dx[4] = { 0, 1, 0, -1 }, dy[4] = { -1, 0, 1, 0 };
  kae_draw_rect(cx, cy, u, u, PAD_DIM_RGB);
  for (int d = 0; d < 4; d++)
    kae_draw_rect(cx + dx[d] * u, cy + dy[d] * u, u, u, d == dir ? lit : PAD_DIM_RGB);
}

/* A stick (two cells at x, y), its ring and its dot pushed towards `dir`; L or R inside isn't drawn (too
 * small), so the left stick's ring is square and the right one's has cut corners. */
static void draw_stick(int x, int y, int s, int dir, bool right, uint32_t lit)
{
  int size = 12 * s, ox = x + 2 * s, oy = y + 2 * s, t = s;
  if (right) { /* cut corners */
    kae_draw_rect(ox + 2 * s, oy, size - 4 * s, t, PAD_DIM_RGB);
    kae_draw_rect(ox + 2 * s, oy + size - t, size - 4 * s, t, PAD_DIM_RGB);
    kae_draw_rect(ox, oy + 2 * s, t, size - 4 * s, PAD_DIM_RGB);
    kae_draw_rect(ox + size - t, oy + 2 * s, t, size - 4 * s, PAD_DIM_RGB);
  } else {
    outline(ox, oy, size, size, t, PAD_DIM_RGB);
  }
  static const int dx[4] = { 0, 1, 0, -1 }, dy[4] = { -1, 0, 1, 0 };
  int dot = 4 * s, mid = (size - dot) / 2, push = 3 * s;
  kae_draw_rect(ox + mid + dx[dir] * push, oy + mid + dy[dir] * push, dot, dot, lit);
}

/* One of sloperinaGZ's icon characters in a cell at (x, y); returns the cells it takes (0: not an icon). */
static int draw_icon(char c, int x, int y, int s, uint32_t rgb)
{
  int cw = FONT_W * s, top = y + 3 * s, size = 10 * s;
  unsigned char u = (unsigned char)c;
  if (u >= (unsigned char)GFX_ICON_DPAD && u < (unsigned char)GFX_ICON_DPAD + 4) {
    draw_dpad(x, y, s, u - (unsigned char)GFX_ICON_DPAD, 0xFFFFFF);
    return 2;
  }
  if (u >= (unsigned char)GFX_ICON_LSTICK && u < (unsigned char)GFX_ICON_RSTICK + 4) {
    bool right = u >= (unsigned char)GFX_ICON_RSTICK;
    draw_stick(x, y, s, (u - (unsigned char)GFX_ICON_LSTICK) % 4, right, 0xFFFFFF);
    return 2;
  }
  switch (c) {
    case GFX_CHECK_OFF:
    case GFX_CHECK_ON: /* a box two cells wide, ticked green */
      outline(x + 2 * s, top, size + 2 * s, size, s, rgb);
      if (c == GFX_CHECK_ON)
        kae_draw_rect(x + 5 * s, top + 3 * s, size - 4 * s, size - 6 * s, 0x40E040);
      return 2;
    case GFX_ICON_REMOVE:
      kae_draw_text(x, y, s, 0xFF5050, "x");
      return 1;
    case GFX_ICON_FOLDER:
      kae_draw_rect(x + s, top + 2 * s, 2 * cw - 2 * s, size - 2 * s, 0xE0C040);
      kae_draw_rect(x + s, top, 6 * s, 2 * s, 0xE0C040);
      return 2;
    case GFX_ICON_WRENCH:
      kae_draw_text(x, y, s, 0xC0C0C0, "*");
      return 1;
    case GFX_ICON_UP:
      kae_draw_text(x, y, s, rgb, "^");
      return 1;
    case GFX_ICON_DOWN:
      kae_draw_text(x, y, s, rgb, "v");
      return 1;
    case GFX_ICON_ADD:
      kae_draw_text(x, y, s, 0x50E050, "+");
      return 1;
    case GFX_ICON_RIGHT:
      kae_draw_text(x, y, s, rgb, ">");
      return 1;
    case GFX_ICON_LEFT:
      kae_draw_text(x, y, s, rgb, "<");
      return 1;
    case GFX_WIDE_REST:
    case 0x7F: /* invisible: sizes a panel */
      return 1;
    default:
      break;
  }
  if ((unsigned char)c == (unsigned char)GFX_ICON_LOCK) { /* a padlock */
    kae_draw_rect(x + 2 * s, top + 4 * s, 5 * s, 5 * s, 0xE0C040);
    outline(x + 3 * s, top + s, 3 * s, 4 * s, s, 0xE0C040);
    return 1;
  }
  return 0;
}

/* a row of a panel: runs of plain text in one style go to Core's text in one call */
static void draw_row(const gfx_panel_t *panel, int row, int cols, int x, int y, int s, int alpha)
{
  char run[GFX_COLS * 4 + 1];
  int n = 0, run_col = 0, run_style = -1;
  int cw = FONT_W * s;
#define FLUSH()                                                                                    \
  do {                                                                                             \
    if (n) {                                                                                       \
      run[n] = 0;                                                                                  \
      uint32_t rgb = style_rgb[run_style < GFX_NSTYLES ? run_style : 0];                         \
      kae_draw_text(x + run_col * cw, y, s, alpha < 255 ? dim(rgb, alpha) : rgb, run);             \
      n = 0;                                                                                       \
    }                                                                                              \
  } while (0)
  /* the prompts' key caps first: a light box behind each run of GFX_BUTTON cells, its corners cut */
  for (int col = 0; col < cols;) {
    if (!panel->ch[row][col] || panel->style[row][col] != GFX_BUTTON) {
      col++;
      continue;
    }
    int end = col;
    while (end < cols && panel->ch[row][end] && panel->style[row][end] == GFX_BUTTON)
      end++;
    int bx = x + col * cw - 2 * s, bw = (end - col) * cw + 4 * s, by = y - s, bh = FONT_H * s + 2 * s;
    uint32_t cap = alpha < 255 ? dim(CAP_RGB, alpha) : CAP_RGB;
    kae_draw_rect(bx + s, by, bw - 2 * s, bh, cap);
    kae_draw_rect(bx, by + s, bw, bh - 2 * s, cap);
    col = end;
  }
  for (int col = 0; col < cols;) {
    char c = panel->ch[row][col];
    int style = panel->style[row][col];
    if (!c || c == ' ') {
      FLUSH();
      col++;
      continue;
    }
    if (c == GFX_PICTURE) { /* the game's picture of an item: not drawn here */
      FLUSH();
      col += 2;
      continue;
    }
    uint32_t rgb = style_rgb[style < GFX_NSTYLES ? style : 0];
    int icon = draw_icon(c, x + col * cw, y, s, alpha < 255 ? dim(rgb, alpha) : rgb);
    if (icon) {
      FLUSH();
      col += icon;
      continue;
    }
    if (n && style != run_style)
      FLUSH();
    if (!n) {
      run_col = col;
      run_style = style;
    }
    run[n++] = c;
    col++;
  }
  FLUSH();
#undef FLUSH
}

/* a list's scroll bar down the panel's right edge */
static void draw_bar(int x, int y, int h, int items, int rows, int top, int s)
{
  if (items <= rows || rows <= 0 || h <= 0)
    return;
  kae_draw_rect(x, y, 2 * s, h, BAR_RGB);
  int thumb = h * rows / items;
  if (thumb < 4 * s)
    thumb = 4 * s;
  int at = (h - thumb) * top / (items - rows);
  kae_draw_rect(x - s, y + at, 4 * s, thumb, 0xD0D0D0);
}

static void panel_size(int p, const gfx_panel_t *panel, int s, int *cols, int *rows, int *w, int *h)
{
  *cols = panel->cols > MIN_PANEL_COLS ? panel->cols : MIN_PANEL_COLS;
  if (*cols > panel_max_cols[p])
    *cols = panel_max_cols[p];
  *rows = panel->rows > panel_max_rows[p] ? panel_max_rows[p] : panel->rows;
  *w = (*cols + 2) * FONT_W * s;
  *h = (*rows * CELL_H + 2 * PAD_Y) * s;
}

static void place(int p, const gfx_panel_t *panel, int fw, int fh, int margin, int w, int h, int *x, int *y)
{
  *x = margin;
  *y = margin;
  if (p == 0) {
    *x = fw * MENU_X_PERMILLE / 1000;
    *y = fh * MENU_Y_PERMILLE / 1000;
    return;
  }
  switch (panel->corner) {
    case GFX_TOP_RIGHT: *x = fw - w - margin; break;
    case GFX_BOTTOM_LEFT: *y = fh - h - margin; break;
    case GFX_BOTTOM_RIGHT: *x = fw - w - margin; *y = fh - h - margin; break;
    case GFX_TOP_CENTRE: *x = (fw - w) / 2; break;
    case GFX_BOTTOM_CENTRE: *x = (fw - w) / 2; *y = fh - h - margin; break;
    case GFX_CUSTOM:
      *x = fw * panel->x / 1000;
      *y = fh * panel->y / 1000;
      if (*x > fw - w - margin) *x = fw - w - margin;
      if (*y > fh - h - margin) *y = fh - h - margin;
      if (*x < margin) *x = margin;
      if (*y < margin) *y = margin;
      gfx_custom_x[p] = *x * 1000 / fw;
      gfx_custom_y[p] = *y * 1000 / fh;
      break;
    default: break;
  }
}

/* the input display's two sticks: a box each with a dot where the stick is */
static void draw_sticks(const gfx_panel_t *panel, int x, int y, int s)
{
  int box = 20 * s;
  for (int i = 0; i < 2; i++) {
    int bx = x + i * (box + 6 * s), by = y;
    outline(bx, by, box, box, s, 0x909090);
    int dx = panel->sticks[2 * i] * (box / 2 - 3 * s) / 100, dy = -panel->sticks[2 * i + 1] * (box / 2 - 3 * s) / 100;
    bool clicked = panel->clicks & (1u << (i == 0 ? GFX_CLICK_L3 : GFX_CLICK_R3));
    kae_draw_rect(bx + box / 2 + dx - 2 * s, by + box / 2 + dy - 2 * s, 4 * s, 4 * s, clicked ? 0x80FF80 : 0xFFFFFF);
  }
}

static void draw_dots(const aw_dot_t *dots, int n, const uint32_t *rgb, int n_rgb, int fw, int fh, int s)
{
  int min = 2 * s;
  for (int i = 0; i < n; i++) {
    int x0 = dots[i].x0 * fw / DOT_COORD_MAX, y0 = dots[i].y0 * fh / DOT_COORD_MAX;
    int x1 = dots[i].x1 * fw / DOT_COORD_MAX, y1 = dots[i].y1 * fh / DOT_COORD_MAX;
    int w = x1 - x0, h = y1 - y0;
    if (w < min) { x0 -= (min - w) / 2; w = min; }
    if (h < min) { y0 -= (min - h) / 2; h = min; }
    kae_draw_rect(x0, y0, w, h, rgb[dots[i].color < n_rgb ? dots[i].color : 0]);
  }
}

void kaedraw_frame(const KaeFrame *frame, void *user)
{
  int fw = frame->width, fh = frame->height;
  if (fw <= 0 || fh <= 0)
    return;
  gfx_presents++;
  int s = scale_for(fh);
  int margin = MARGIN * s;

  /* the overlays first, so the panels go over them */
  airwall_take();
  enemyhp_take();
  int n_dots = 0, n_hp = 0;
  const aw_dot_t *dots = airwall_published(&n_dots);
  const aw_dot_t *hp = enemyhp_published(&n_hp);
  if (dots && n_dots)
    draw_dots(dots, n_dots, airwall_rgb, AW_NCOLORS, fw, fh, s);
  if (hp && n_hp)
    draw_dots(hp, n_hp, enemyhp_rgb, EH_NCOLORS, fw, fh, s);
  airwall_release();
  enemyhp_release();

  /* gz's pause icon: two bars (paused) or a bar and a play arrow (a frame let through) */
  int icon = gfx_pause_icon;
  if (icon) {
    int ix = margin, iy = margin, bh = 16 * s;
    kae_draw_rect(ix, iy, 5 * s, bh, 0xFFFFFF);
    if (icon == 1)
      kae_draw_rect(ix + 9 * s, iy, 5 * s, bh, 0xFFFFFF);
    else
      for (int i = 0; i < 8; i++)
        kae_draw_rect(ix + 9 * s + i * s, iy + i * s, s, bh - 2 * i * s, 0xFFFFFF);
  }

  /* tell the menu how many rows fit under the D-pad */
  int menu_y = fh * MENU_Y_PERMILLE / 1000;
  int fit = ((fh - menu_y - margin) / s - 2 * PAD_Y) / CELL_H;
  gfx_menu_rows = fit < MIN_MENU_ROWS ? MIN_MENU_ROWS : fit > GFX_ROWS ? GFX_ROWS : fit;

  const gfx_screen_t *screen = gfx_published();
  if (!screen)
    return;
  int opacity = gfx_opacity;
  int hud_bottom_right = -1, hud_bottom_left = -1;
  for (int i = 0; i < GFX_PANELS; i++) {
    int p = (i + 1) % GFX_PANELS; /* the menu (0) last, over everything else */
    const gfx_panel_t *panel = &screen->panel[p];
    if (!panel->rows)
      continue;
    int ps = panel->scale_pct ? s * panel->scale_pct / 100 : s;
    if (ps < 1)
      ps = 1;
    int cols, rows, w, h, x, y;
    panel_size(p, panel, ps, &cols, &rows, &w, &h);
    if (p == GFX_PANEL_INPUT && panel->pad)
      h += 24 * ps;
    place(p, panel, fw, fh, margin, w, h, &x, &y);
    if (p == 1 && panel->corner == GFX_BOTTOM_RIGHT)
      hud_bottom_right = y;
    if (p == 1 && panel->corner == GFX_BOTTOM_LEFT)
      hud_bottom_left = y;
    if (p == GFX_PANEL_LOG && hud_bottom_right >= 0 && y + h > hud_bottom_right)
      y = hud_bottom_right - h;
    if (p == GFX_PANEL_INPUT && panel->corner == GFX_BOTTOM_LEFT && hud_bottom_left >= 0 && y + h > hud_bottom_left)
      y = hud_bottom_left - h;
    if (y < margin)
      y = margin;
    bool clear = panel->clear;
    if (!clear && opacity > 0)
      kae_draw_rect(x, y, w, h, BG_RGB);
    int tx = x + FONT_W * ps, ty = y + PAD_Y * ps;
    if (p == GFX_PANEL_INPUT && panel->pad) {
      draw_sticks(panel, tx, ty, ps);
      ty += 24 * ps;
    }
    int yoff = panel->yoff * ps;
    for (int row = 0; row < rows; row++) {
      int alpha = p == GFX_PANEL_LOG ? panel->alpha[row] : 255;
      if (alpha < 48)
        continue;
      draw_row(panel, row, cols, tx, ty + row * CELL_H * ps + ps + yoff, ps, alpha);
    }
    if (p == 0) {
      draw_bar(x + w - 4 * ps, ty + panel->scroll_row * CELL_H * ps, panel->scroll_rows * CELL_H * ps,
               panel->scroll_items, panel->scroll_rows, panel->scroll_top, ps);
      draw_bar(x + w - 9 * ps, ty + panel->inner_row * CELL_H * ps, panel->inner_rows * CELL_H * ps,
               panel->inner_items, panel->inner_rows, panel->inner_top, ps);
    }
  }
  gfx_release();
  if (!gfx_on_screen)
    gfx_on_screen = true;
}
