// The one helper of Core's first skeleton that has no direct equivalent in the public API.
#include "core.h"

// "text a b c ..." with each float printed in thousandths (1.5 -> 1500); up to 12 per line.
void kp_log_floats(const char *text, const float *values, int count) {
    long long m[12] = { 0 };
    char format[2 + 12 * 5 + 1] = "%s";
    int n = 2;
    for (int i = 0; i < count && i < 12; i++) {
        float v = values[i];
        m[i] = v != v ? -999999999 : v > 9e6f ? 999999999 : v < -9e6f ? -999999999 : (long long)(v * 1000.0f);
        format[n++] = ' ';
        format[n++] = '%';
        format[n++] = 'l';
        format[n++] = 'l';
        format[n++] = 'd';
    }
    format[n] = 0;
    kae_logf(&kae_this_mod, format, text, m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11]);
}
