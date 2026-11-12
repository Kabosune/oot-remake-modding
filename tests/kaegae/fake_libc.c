// More of the system's sdk module for the tests: the C library and nn:: functions that Slopped Up
// Sloperina (sloperinaGZ's code) imports itself. Made-up but faithful enough behaviour: a printf
// with the conversions sloperinaGZ uses, rough maths, controllers from sdk_buttons (fake_sdk.c),
// and an SD card that can't be mounted. Nothing here comes from the system.
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>

#define EXPORT __attribute__((visibility("default")))

EXPORT size_t strlen(const char *s) {
    size_t n = 0;
    while (s[n])
        n++;
    return n;
}

// ---- printf ----
typedef struct { char *buf; size_t size, len; } out_t;

static void put(out_t *o, char c) {
    if (o->len + 1 < o->size)
        o->buf[o->len] = c;
    o->len++;
}

static void pad(out_t *o, int n, char c) {
    for (; n > 0; n--)
        put(o, c);
}

static void put_text(out_t *o, const char *s, int len, int width, int left) {
    if (!left)
        pad(o, width - len, ' ');
    for (int i = 0; i < len; i++)
        put(o, s[i]);
    if (left)
        pad(o, width - len, ' ');
}

static int digits(char *at, unsigned long long v, int base, int upper) {
    char tmp[32];
    int n = 0;
    do {
        int d = (int)(v % (unsigned)base);
        tmp[n++] = (char)(d < 10 ? '0' + d : (upper ? 'A' : 'a') + d - 10);
        v /= (unsigned)base;
    } while (v);
    for (int i = 0; i < n; i++)
        at[i] = tmp[n - 1 - i];
    return n;
}

EXPORT int vsnprintf(char *buf, size_t size, const char *f, va_list ap) {
    out_t o = { buf, size, 0 };
    for (; *f; f++) {
        if (*f != '%') {
            put(&o, *f);
            continue;
        }
        f++;
        int left = 0, zero = 0, plus = 0, space = 0, alt = 0, width = 0, prec = -1, longs = 0;
        for (;; f++) {
            if (*f == '-') left = 1;
            else if (*f == '0') zero = 1;
            else if (*f == '+') plus = 1;
            else if (*f == ' ') space = 1;
            else if (*f == '#') alt = 1;
            else break;
        }
        if (*f == '*') { width = va_arg(ap, int); f++; if (width < 0) { left = 1; width = -width; } }
        else while (*f >= '0' && *f <= '9') width = width * 10 + *f++ - '0';
        if (*f == '.') {
            f++;
            prec = 0;
            if (*f == '*') { prec = va_arg(ap, int); f++; }
            else while (*f >= '0' && *f <= '9') prec = prec * 10 + *f++ - '0';
        }
        while (*f == 'l' || *f == 'h' || *f == 'z' || *f == 'j' || *f == 't') {
            if (*f == 'l' || *f == 'z' || *f == 'j' || *f == 't') longs++;
            f++;
        }
        char num[80];
        int n = 0;
        switch (*f) {
        case '%': put(&o, '%'); break;
        case 'c': num[0] = (char)va_arg(ap, int); put_text(&o, num, 1, width, left); break;
        case 's': {
            const char *s = va_arg(ap, const char *);
            if (!s) s = "(null)";
            int len = (int)strlen(s);
            if (prec >= 0 && len > prec) len = prec;
            put_text(&o, s, len, width, left);
            break;
        }
        case 'd': case 'i': case 'u': case 'x': case 'X': case 'o': case 'p': {
            unsigned long long v;
            int negative = 0;
            if (*f == 'p') { v = (uintptr_t)va_arg(ap, void *); alt = 1; }
            else if (*f == 'd' || *f == 'i') {
                long long s = longs ? va_arg(ap, long long) : va_arg(ap, int);
                negative = s < 0;
                v = negative ? (unsigned long long)-s : (unsigned long long)s;
            } else
                v = longs ? va_arg(ap, unsigned long long) : va_arg(ap, unsigned);
            int base = *f == 'o' ? 8 : (*f == 'x' || *f == 'X' || *f == 'p') ? 16 : 10;
            if (negative) num[n++] = '-';
            else if (plus) num[n++] = '+';
            else if (space) num[n++] = ' ';
            if (alt && base == 16 && v) { num[n++] = '0'; num[n++] = *f == 'X' ? 'X' : 'x'; }
            char d[32];
            int nd = digits(d, v, base, *f == 'X');
            if (zero && !left)
                while (n + nd < width && n < 60) num[n++] = '0';
            for (int i = 0; i < nd; i++) num[n++] = d[i];
            put_text(&o, num, n, width, left);
            break;
        }
        case 'f': case 'g': case 'e': {
            double v = va_arg(ap, double);
            if (prec < 0) prec = *f == 'f' ? 6 : 3;
            if (prec > 9) prec = 9;
            if (v != v) { put_text(&o, "nan", 3, width, left); break; }
            if (v < 0) { num[n++] = '-'; v = -v; } else if (plus) num[n++] = '+';
            if (v > 1e18) v = 1e18;
            double scale = 1;
            for (int i = 0; i < prec; i++) scale *= 10;
            unsigned long long all = (unsigned long long)(v * scale + 0.5);
            unsigned long long whole = all / (unsigned long long)scale, frac = all % (unsigned long long)scale;
            char d[32];
            int nd = digits(d, whole, 10, 0);
            if (zero && !left)
                while (n + nd + (prec ? prec + 1 : 0) < width && n < 40) num[n++] = '0';
            for (int i = 0; i < nd; i++) num[n++] = d[i];
            if (prec) {
                num[n++] = '.';
                for (int i = prec - 1; i >= 0; i--) {
                    unsigned long long p = 1;
                    for (int k = 0; k < i; k++) p *= 10;
                    num[n++] = (char)('0' + (frac / p) % 10);
                }
            }
            put_text(&o, num, n, width, left);
            break;
        }
        case 'n': break;
        default: put(&o, '%'); if (*f) put(&o, *f); else f--; break;
        }
    }
    if (size)
        buf[o.len < size ? o.len : size - 1] = 0;
    return (int)o.len;
}

EXPORT int snprintf(char *buf, size_t size, const char *f, ...) {
    va_list ap;
    va_start(ap, f);
    int n = vsnprintf(buf, size, f, ap);
    va_end(ap);
    return n;
}

// ---- maths: rough, enough not to crash ----
static float wrap(float x) {
    const float pi = 3.14159265f;
    while (x > pi) x -= 2 * pi;
    while (x < -pi) x += 2 * pi;
    return x;
}
EXPORT float sinf(float x) {
    x = wrap(x);
    float x2 = x * x;
    return x * (1 - x2 / 6 * (1 - x2 / 20 * (1 - x2 / 42)));
}
EXPORT float cosf(float x) { return sinf(x + 1.5707963f); }
EXPORT float tanf(float x) { float c = cosf(x); return c == 0 ? 1e9f : sinf(x) / c; }
EXPORT float atan2f(float y, float x) {
    if (x == 0 && y == 0) return 0;
    float ax = x < 0 ? -x : x, ay = y < 0 ? -y : y;
    float a = ax > ay ? ay / ax : ax / ay;
    float r = a * (0.7853981f + 0.273f * (1 - a));
    if (ay > ax) r = 1.5707963f - r;
    if (x < 0) r = 3.14159265f - r;
    return y < 0 ? -r : r;
}
EXPORT float hypotf(float x, float y) {
    float v = x * x + y * y, r = v > 1 ? v : 1;
    for (int i = 0; i < 30; i++) r = (r + v / r) / 2;
    return v == 0 ? 0 : r;
}

// ---- controllers, the way sloperinaGZ reads them (nn::hid::detail) ----
typedef struct {
    int64_t sample;
    uint64_t buttons;
    int32_t lx, ly, rx, ry;
    uint32_t attributes, pad;
} npad_state_t;
extern uint64_t sdk_buttons;
extern int32_t sdk_lx, sdk_ly, sdk_rx, sdk_ry;

static void detail(int *n, npad_state_t *out, int count, const uint32_t *id, int handheld) {
    *n = 0;
    if (count < 1 || (*id == 0x20) != handheld)
        return;
    *out = (npad_state_t){ 1, sdk_buttons, sdk_lx, sdk_ly, sdk_rx, sdk_ry, 1, 0 };
    *n = 1;
}
EXPORT void _ZN2nn3hid6detail13GetNpadStatesEPiPNS0_16NpadFullKeyStateEiRKj(int *n, npad_state_t *o, int c, const uint32_t *id) { detail(n, o, c, id, 0); }
EXPORT void _ZN2nn3hid6detail13GetNpadStatesEPiPNS0_16NpadJoyDualStateEiRKj(int *n, npad_state_t *o, int c, const uint32_t *id) { *n = 0; (void)o; (void)c; (void)id; }
EXPORT void _ZN2nn3hid6detail13GetNpadStatesEPiPNS0_17NpadHandheldStateEiRKj(int *n, npad_state_t *o, int c, const uint32_t *id) { *n = 0; (void)o; (void)c; (void)id; }

// ---- files: sloperinaGZ's SD card can't be mounted here ----
EXPORT uint32_t _ZN2nn2fs11MountSdCardEPKc(const char *name) { (void)name; return 0x7D402; }
EXPORT uint32_t _ZN2nn2fs10DeleteFileEPKc(const char *path) { (void)path; return 0x202; }
EXPORT uint32_t _ZN2nn2fs11GetFileSizeEPlNS0_10FileHandleE(long *out, void *f) { (void)f; *out = 0; return 0x202; }
