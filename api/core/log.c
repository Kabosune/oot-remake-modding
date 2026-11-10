#include "core.h"

static void out(const char *s, size_t n) {
    register const char *x0 __asm__("x0") = s;
    register uint64_t x1 __asm__("x1") = n;
    __asm__ volatile("svc #0x27" : "+r"(x0), "+r"(x1) : : "x2", "x3", "x4", "x5", "x6", "x7", "memory");
}

static char *put(char *o, char *end, const char *s) {
    while (*s && o < end)
        *o++ = *s++;
    return o;
}

static char *put_hex(char *o, char *end, uint64_t v) {
    o = put(o, end, "0x");
    int shift = 60;
    while (shift > 0 && !((v >> shift) & 15))
        shift -= 4;
    for (; shift >= 0 && o < end; shift -= 4)
        *o++ = "0123456789abcdef"[(v >> shift) & 15];
    return o;
}

static char *put_dec(char *o, char *end, int64_t v) {
    char tmp[24];
    int n = 0;
    uint64_t u = v < 0 ? (uint64_t)0 - (uint64_t)v : (uint64_t)v;
    do {
        tmp[n++] = (char)('0' + u % 10);
        u /= 10;
    } while (u);
    if (v < 0 && o < end)
        *o++ = '-';
    while (n && o < end)
        *o++ = tmp[--n];
    return o;
}

#define LINE 160
#define TAG "kaepora: "

void kp_log(const char *text) {
    char line[LINE], *end = line + LINE;
    char *o = put(put(line, end, TAG), end, text);
    out(line, (size_t)(o - line));
}

void kp_log_hex(const char *text, uint64_t value) {
    char line[LINE], *end = line + LINE;
    char *o = put(put(line, end, TAG), end, text);
    o = put_hex(put(o, end, " "), end, value);
    out(line, (size_t)(o - line));
}

void kp_log_2(const char *text, int64_t a, int64_t b) {
    char line[LINE], *end = line + LINE;
    char *o = put(put(line, end, TAG), end, text);
    o = put_dec(put(o, end, " "), end, a);
    o = put_dec(put(o, end, " "), end, b);
    out(line, (size_t)(o - line));
}

// "text a b c ..." with each float printed in thousandths (1.5 -> 1500); up to 12 per line.
void kp_log_floats(const char *text, const float *values, int count) {
    char line[LINE], *end = line + LINE;
    char *o = put(put(line, end, TAG), end, text);
    for (int i = 0; i < count && i < 12; i++) {
        float v = values[i];
        int64_t m = v != v ? -999999999 : v > 9e6f ? 999999999 : v < -9e6f ? -999999999 : (int64_t)(v * 1000.0f);
        o = put_dec(put(o, end, " "), end, m);
    }
    out(line, (size_t)(o - line));
}
