// A small printf: %s %c %d %i %u %x %X %p %f %%, with l / ll / z, a width, 0 padding and a
// precision for %f. Enough for log lines; nothing here allocates.
#include "core.h"

typedef struct { char *at, *end; } out_t;

static void put(out_t *o, char c) {
    if (o->at < o->end)
        *o->at++ = c;
}

static void put_padded(out_t *o, const char *text, int length, int width, char pad, bool negative) {
    int total = length + (negative ? 1 : 0);
    if (negative && pad == '0')
        put(o, '-');
    for (; total < width; total++)
        put(o, pad);
    if (negative && pad != '0')
        put(o, '-');
    for (int i = 0; i < length; i++)
        put(o, text[i]);
}

static int digits(char *tmp, uint64_t v, unsigned base, bool upper) {
    const char *set = upper ? "0123456789ABCDEF" : "0123456789abcdef";
    int n = 0;
    do {
        tmp[n++] = set[v % base];
        v /= base;
    } while (v);
    for (int i = 0; i < n / 2; i++) {
        char c = tmp[i];
        tmp[i] = tmp[n - 1 - i];
        tmp[n - 1 - i] = c;
    }
    return n;
}

static void put_float(out_t *o, double v, int precision, int width, char pad) {
    if (v != v) {
        put_padded(o, "nan", 3, width, ' ', false);
        return;
    }
    bool negative = v < 0;
    if (negative)
        v = -v;
    if (v > 1e15) {
        put_padded(o, "inf", 3, width, ' ', negative);
        return;
    }
    if (precision < 0)
        precision = 3;
    if (precision > 9)
        precision = 9;
    uint64_t scale = 1;
    for (int i = 0; i < precision; i++)
        scale *= 10;
    uint64_t whole = (uint64_t)v;
    uint64_t part = (uint64_t)((v - (double)whole) * (double)scale + 0.5);
    if (part >= scale) {
        whole++;
        part -= scale;
    }
    char text[48];
    int n = digits(text, whole, 10, false);
    if (precision) {
        text[n++] = '.';
        char tmp[24];
        int m = digits(tmp, part, 10, false);
        for (int i = m; i < precision; i++)
            text[n++] = '0';
        for (int i = 0; i < m; i++)
            text[n++] = tmp[i];
    }
    put_padded(o, text, n, width, pad, negative);
}

size_t kp_vformat(char *out, size_t cap, const char *f, va_list args) {
    if (!cap)
        return 0;
    out_t o = { out, out + cap - 1 };
    for (; *f; f++) {
        if (*f != '%') {
            put(&o, *f);
            continue;
        }
        f++;
        char pad = ' ';
        int width = 0, precision = -1, longs = 0;
        if (*f == '0') {
            pad = '0';
            f++;
        }
        while (*f >= '0' && *f <= '9')
            width = width * 10 + (*f++ - '0');
        if (*f == '.') {
            precision = 0;
            for (f++; *f >= '0' && *f <= '9'; f++)
                precision = precision * 10 + (*f - '0');
        }
        while (*f == 'l' || *f == 'z') {
            longs += *f == 'z' ? 2 : 1;
            f++;
        }
        char tmp[24];
        switch (*f) {
        case 'd':
        case 'i': {
            int64_t v = longs ? va_arg(args, int64_t) : va_arg(args, int);
            uint64_t u = v < 0 ? (uint64_t)0 - (uint64_t)v : (uint64_t)v;
            put_padded(&o, tmp, digits(tmp, u, 10, false), width, pad, v < 0);
            break;
        }
        case 'u':
        case 'x':
        case 'X': {
            uint64_t v = longs ? va_arg(args, uint64_t) : va_arg(args, unsigned);
            put_padded(&o, tmp, digits(tmp, v, *f == 'u' ? 10 : 16, *f == 'X'), width, pad, false);
            break;
        }
        case 'p': {
            uint64_t v = (uint64_t)(uintptr_t)va_arg(args, void *);
            put(&o, '0');
            put(&o, 'x');
            put_padded(&o, tmp, digits(tmp, v, 16, false), width, pad, false);
            break;
        }
        case 'f':
            put_float(&o, va_arg(args, double), precision, width, pad);
            break;
        case 's': {
            const char *s = va_arg(args, const char *);
            if (!s)
                s = "(null)";
            int n = 0;
            while (s[n])
                n++;
            put_padded(&o, s, n, width, ' ', false);
            break;
        }
        case 'c':
            put(&o, (char)va_arg(args, int));
            break;
        case '%':
            put(&o, '%');
            break;
        case 0:
            f--;   // a lone % at the end
            break;
        default:   // not a format this knows: show it as written
            put(&o, '%');
            put(&o, *f);
            break;
        }
    }
    *o.at = 0;
    return (size_t)(o.at - out);
}
