// The shared log. Core's own lines start "kaepora: ", a mod's "kaepora [its.id]: ".
#include "core.h"

#define LINE 200

static void line(const char *who, const char *format, va_list args) {
    char text[LINE];
    size_t n = 0;
    const char *head = "kaepora";
    while (*head)
        text[n++] = *head++;
    if (who) {
        text[n++] = ' ';
        text[n++] = '[';
        for (int i = 0; who[i] && i < 48; i++)
            text[n++] = who[i];
        text[n++] = ']';
    }
    text[n++] = ':';
    text[n++] = ' ';
    n += kp_vformat(text + n, LINE - n, format, args);
    kp_debug_out(text, n);
}

void kp_logf(const char *format, ...) {
    va_list args;
    va_start(args, format);
    line(0, format, args);
    va_end(args);
}

void kp_log(const char *text) { kp_logf("%s", text); }
void kp_log_hex(const char *text, uint64_t value) { kp_logf("%s 0x%llx", text, (unsigned long long)value); }
void kp_log_2(const char *text, int64_t a, int64_t b) { kp_logf("%s %lld %lld", text, (long long)a, (long long)b); }

void kae_logf(const KaeMod *mod, const char *format, ...) {
    if (!format)
        return;
    va_list args;
    va_start(args, format);
    line(mod && mod->id ? mod->id : "?", format, args);
    va_end(args);
}
