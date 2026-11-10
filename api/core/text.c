// Text and small pictures, turned into rectangles for draw.c.
//
// Core has one way to put pixels on the picture so far: filled rectangles. A glyph or a picture
// becomes runs of equal pixels, and rows that repeat are drawn as one taller run. The functions
// here only call kae_draw_rect, so they work wherever that does and are tested on the PC.
#include "core.h"
#include "font_gen.h"

// The next code point of a UTF-8 string. A byte that doesn't decode comes back as U+FFFD.
static uint32_t next_code(const char **text) {
    const uint8_t *s = (const uint8_t *)*text;
    uint32_t c = *s++;
    int more = c < 0x80 ? 0 : (c & 0xE0) == 0xC0 ? 1 : (c & 0xF0) == 0xE0 ? 2 : (c & 0xF8) == 0xF0 ? 3 : -1;
    if (more < 0) {
        *text = (const char *)s;
        return 0xFFFD;
    }
    if (more)
        c &= 0x3F >> more;
    for (; more; more--) {
        if ((*s & 0xC0) != 0x80) {
            *text = (const char *)s;
            return 0xFFFD;
        }
        c = (c << 6) | (*s++ & 0x3F);
    }
    *text = (const char *)s;
    return c;
}

static void glyph(int x, int y, int scale, uint32_t rgb, const uint8_t *rows) {
    for (int row = 0; row < KP_FONT_HEIGHT;) {
        int same = 1;
        while (row + same < KP_FONT_HEIGHT && rows[row + same] == rows[row])
            same++;
        uint8_t bits = rows[row];
        for (int col = 0; col < KP_FONT_WIDTH;) {
            if (!(bits & (0x80 >> col))) {
                col++;
                continue;
            }
            int run = 1;
            while (col + run < KP_FONT_WIDTH && (bits & (0x80 >> (col + run))))
                run++;
            kae_draw_rect(x + col * scale, y + row * scale, run * scale, same * scale, rgb);
            col += run;
        }
        row += same;
    }
}

int kae_text_width(int scale, const char *text) {
    if (!text || scale < 1)
        return 0;
    int widest = 0, line = 0;
    while (*text) {
        if (next_code(&text) == '\n') {
            line = 0;
            continue;
        }
        line += KP_FONT_WIDTH * scale;
        if (line > widest)
            widest = line;
    }
    return widest;
}

int kae_text_height(int scale, const char *text) {
    if (!text || scale < 1)
        return 0;
    int lines = 1;
    for (; *text; text++)
        lines += *text == '\n';
    return lines * KP_FONT_HEIGHT * scale;
}

int kae_draw_text(int x, int y, int scale, uint32_t rgb, const char *text) {
    if (!text || scale < 1)
        return x;
    int pen = x;
    while (*text) {
        uint32_t code = next_code(&text);
        if (code == '\n') {
            pen = x;
            y += KP_FONT_HEIGHT * scale;
            continue;
        }
        if (code != ' ')
            glyph(pen, y, scale, rgb, kp_font_glyph(code));
        pen += KP_FONT_WIDTH * scale;
    }
    return pen;
}

static bool same_row(const uint32_t *a, const uint32_t *b, int w) {
    for (int i = 0; i < w; i++)
        if (a[i] != b[i] && ((a[i] | b[i]) >> 24) >= 0x80)   // two see-through pixels count as equal
            return false;
    return true;
}

void kae_draw_image(int x, int y, int w, int h, const uint32_t *argb, int scale) {
    if (!argb || w <= 0 || h <= 0 || scale < 1)
        return;
    for (int row = 0; row < h;) {
        const uint32_t *line = argb + (size_t)row * (size_t)w;
        int same = 1;
        while (row + same < h && same_row(line, line + (size_t)same * (size_t)w, w))
            same++;
        for (int col = 0; col < w;) {
            if ((line[col] >> 24) < 0x80) {
                col++;
                continue;
            }
            int run = 1;
            while (col + run < w && line[col + run] == line[col])
                run++;
            kae_draw_rect(x + col * scale, y + row * scale, run * scale, same * scale, line[col] & 0xFFFFFF);
            col += run;
        }
        row += same;
    }
}
