// The four functions a C compiler may call on its own (struct copies, zeroed arrays).
#include <stddef.h>

void *memcpy(void *to, const void *from, size_t n) {
    unsigned char *t = to;
    const unsigned char *f = from;
    while (n--)
        *t++ = *f++;
    return to;
}

void *memmove(void *to, const void *from, size_t n) {
    unsigned char *t = to;
    const unsigned char *f = from;
    if (t < f) {
        while (n--)
            *t++ = *f++;
    } else {
        while (n--)
            t[n] = f[n];
    }
    return to;
}

void *memset(void *to, int value, size_t n) {
    unsigned char *t = to;
    while (n--)
        *t++ = (unsigned char)value;
    return to;
}

int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *x = a, *y = b;
    for (; n--; x++, y++)
        if (*x != *y)
            return *x - *y;
    return 0;
}
