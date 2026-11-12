// The Mods menu's settings, kept between runs: one text file on the SD card, kaegae/settings.txt
// (in Fritchii: %APPDATA%\fritchii\sdmc\kaegae\settings.txt).
//
//   [kaegae.hello]
//   (on) = 1
//   Show the square = 1
//   Flash the diamond = 0x10
//   Flash the diamond (key) = F5
//
// One section per mod (its id), one line per setting (its label). Values: 0 / 1, a choice's index,
// a number, a binding's button mask in hex. A binding with a keyboard key (0.7) has a second line,
// its label and " (key)", with the key's name (kae_key_name). Core's own settings are [kaegae.core]. Read on the first frame, written when the menu closes
// with something changed. Sections of mods that aren't installed now are written back unchanged.
//
// The file functions are the system's (nn::fs in the sdk module), found by name like the
// controller's. Any that are missing, or a failed mount, turn saving off with a line in the log,
// and the menu works as before. nn::fs stops the game on some errors unless told otherwise, so
// that is switched off around Core's calls and back on after.
#include "core.h"
#include "../menu/kae_menu.h"

typedef struct { void *handle; } fs_file_t;
typedef struct { int32_t flags; } fs_write_option_t;

#define WEAK __attribute__((weak))
WEAK uint32_t _ZN2nn2fs19MountSdCardForDebugEPKc(const char *name);
WEAK uint32_t _ZN2nn2fs15CreateDirectoryEPKc(const char *path);
WEAK uint32_t _ZN2nn2fs10CreateFileEPKcl(const char *path, int64_t size);
WEAK uint32_t _ZN2nn2fs8OpenFileEPNS0_10FileHandleEPKci(fs_file_t *out, const char *path, int mode);
WEAK uint32_t _ZN2nn2fs8ReadFileEPmNS0_10FileHandleElPvm(size_t *read, fs_file_t f, int64_t at, void *to, size_t size);
WEAK uint32_t _ZN2nn2fs9WriteFileENS0_10FileHandleElPKvmRKNS0_11WriteOptionE(fs_file_t f, int64_t at, const void *from,
                                                                          size_t size, const fs_write_option_t *option);
WEAK uint32_t _ZN2nn2fs11SetFileSizeENS0_10FileHandleEl(fs_file_t f, int64_t size);
WEAK void _ZN2nn2fs9CloseFileENS0_10FileHandleE(fs_file_t f);
WEAK void _ZN2nn2fs19SetEnabledAutoAbortEb(bool on);
// All of these are in the game's sdk module (names read from its symbol table, 11 Nov 2026). The
// sdk has no IsEnabledAutoAbort, so Core puts auto-abort back on after its calls: the system's
// default, assumed to be what the game runs with.

#define MOUNT "kaesd"
#define DIR   MOUNT ":/kaegae"
#define PATH  MOUNT ":/kaegae/settings.txt"
#define SHOWN "kaegae/settings.txt on the SD card"
enum { READ = 1, WRITE = 2 };
#define SIZE 16384

static int state;                    // 0 not tried yet, 1 saving on, -1 off
static char file[SIZE];              // the file as last read or written
static size_t file_len;
static char out[SIZE];

bool kp_settings_on(void) { return state > 0; }

// ---- the system's file functions, with auto-abort off around them ----

static void begin(void) { _ZN2nn2fs19SetEnabledAutoAbortEb(false); }
static void end(void) { _ZN2nn2fs19SetEnabledAutoAbortEb(true); }

static bool mount(void) {
#ifdef KAE_NO_SAVE
    kp_log("settings off: this build doesn't save them");
    return false;
#endif
    if (!_ZN2nn2fs19MountSdCardForDebugEPKc || !_ZN2nn2fs15CreateDirectoryEPKc || !_ZN2nn2fs10CreateFileEPKcl ||
        !_ZN2nn2fs8OpenFileEPNS0_10FileHandleEPKci || !_ZN2nn2fs8ReadFileEPmNS0_10FileHandleElPvm ||
        !_ZN2nn2fs9WriteFileENS0_10FileHandleElPKvmRKNS0_11WriteOptionE || !_ZN2nn2fs11SetFileSizeENS0_10FileHandleEl ||
        !_ZN2nn2fs9CloseFileENS0_10FileHandleE || !_ZN2nn2fs19SetEnabledAutoAbortEb) {
        kp_log("settings off: the system's file functions weren't found, so they aren't saved between runs");
        return false;
    }
    begin();
    uint32_t r = _ZN2nn2fs19MountSdCardForDebugEPKc(MOUNT);
    if (r == 0)
        _ZN2nn2fs15CreateDirectoryEPKc(DIR);   // fails when it's already there, which is fine
    end();
    if (r != 0) {
        kp_logf("settings off: the SD card couldn't be opened (result 0x%x), so they aren't saved between runs", r);
        return false;
    }
    return true;
}

static bool read_file(void) {
    begin();
    fs_file_t f;
    size_t got = 0;
    bool ok = _ZN2nn2fs8OpenFileEPNS0_10FileHandleEPKci(&f, PATH, READ) == 0;
    if (ok) {
        ok = _ZN2nn2fs8ReadFileEPmNS0_10FileHandleElPvm(&got, f, 0, file, SIZE - 1) == 0;
        _ZN2nn2fs9CloseFileENS0_10FileHandleE(f);
    }
    end();
    file_len = ok && got < SIZE ? got : 0;
    file[file_len] = 0;
    return ok;
}

static bool write_file(const char *text, size_t len) {
    begin();
    _ZN2nn2fs10CreateFileEPKcl(PATH, 0);   // fails when it's already there
    fs_file_t f;
    bool ok = _ZN2nn2fs8OpenFileEPNS0_10FileHandleEPKci(&f, PATH, WRITE) == 0;
    if (ok) {
        static const fs_write_option_t flush = { 1 };
        ok = _ZN2nn2fs11SetFileSizeENS0_10FileHandleEl(f, (int64_t)len) == 0 &&
             _ZN2nn2fs9WriteFileENS0_10FileHandleElPKvmRKNS0_11WriteOptionE(f, 0, text, len, &flush) == 0;
        _ZN2nn2fs9CloseFileENS0_10FileHandleE(f);
    }
    end();
    return ok;
}

// ---- text ----

static bool same_n(const char *a, size_t n, const char *b) {
    for (size_t i = 0; i < n; i++)
        if (!b[i] || a[i] != b[i])
            return false;
    return !b[n];
}

static bool number(const char *s, size_t n, int64_t *value) {
    bool negative = n && s[0] == '-';
    size_t i = negative;
    uint64_t v = 0;
    int base = 10;
    if (n >= i + 2 && s[i] == '0' && (s[i + 1] == 'x' || s[i + 1] == 'X'))
        base = 16, i += 2;
    if (i == n)
        return false;
    for (; i < n; i++) {
        char c = s[i];
        int d = c >= '0' && c <= '9' ? c - '0' : base == 16 && c >= 'a' && c <= 'f' ? c - 'a' + 10
              : base == 16 && c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
        if (d < 0)
            return false;
        v = v * (uint64_t)base + (uint64_t)d;
    }
    *value = negative ? -(int64_t)v : (int64_t)v;
    return true;
}

static int clamp(int64_t v, int low, int high) { return v < low ? low : v > high ? high : (int)v; }

typedef struct { char *at; size_t left; bool full; } writer_t;

static void put(writer_t *w, const char *s) {
    for (; *s; s++) {
        if (w->left <= 1) {
            w->full = true;
            return;
        }
        *w->at++ = *s;
        w->left--;
    }
    *w->at = 0;
}

static void put_n(writer_t *w, const char *s, size_t n) {
    for (size_t i = 0; i < n; i++) {
        char one[2] = { s[i], 0 };
        put(w, one);
    }
}

static void put_number(writer_t *w, int64_t v, bool hex) {
    char digits[24];
    int n = 0;
    uint64_t u = !hex && v < 0 ? 0 - (uint64_t)v : (uint64_t)v;
    do {
        unsigned d = (unsigned)(u % (hex ? 16 : 10));
        digits[n++] = (char)(d < 10 ? '0' + d : 'a' + d - 10);
        u /= hex ? 16 : 10;
    } while (u);
    if (hex)
        put(w, "0x");
    else if (v < 0)
        put(w, "-");
    while (n)
        put_n(w, &digits[--n], 1);
}

// Calls `line` for each line of the file: the section it's in and its label and value.
typedef void (*line_fn)(const char *id, size_t id_n, const char *label, size_t label_n, const char *value,
                        size_t value_n, void *user);

static void each_line(const char *text, line_fn fn, void *user) {
    const char *id = 0;
    size_t id_n = 0;
    while (*text) {
        const char *start = text;
        while (*text && *text != '\n')
            text++;
        const char *stop = text;
        if (*text)
            text++;
        if (stop > start && stop[-1] == '\r')
            stop--;
        if (stop == start || *start == '#')
            continue;
        if (*start == '[' && stop[-1] == ']') {
            id = start + 1;
            id_n = (size_t)(stop - start - 2);
            continue;
        }
        const char *eq = 0;   // the last " = " on the line: labels may hold anything but a newline
        for (const char *p = start; p + 3 <= stop; p++)
            if (p[0] == ' ' && p[1] == '=' && p[2] == ' ')
                eq = p;
        if (id && eq)
            fn(id, id_n, start, (size_t)(eq - start), eq + 3, (size_t)(stop - eq - 3), user);
    }
}

// ---- reading into the pages ----

typedef struct { KaePage **pages; int count; int applied; } apply_t;

static bool ends_with(const char *s, size_t n, const char *end, size_t end_n) {
    return n > end_n && same_n(s + n - end_n, end_n, end);
}

// "Label (key) = F5": the key of the binding called Label.
static bool apply_key(KaePage *page, const char *label, size_t label_n, const char *value, size_t value_n) {
    static const char suffix[] = " (key)";
    size_t n = sizeof suffix - 1;
    if (!ends_with(label, label_n, suffix, n) || !page->keys)
        return false;
    for (int j = 0; j < page->count && j < KAE_MAX_KEYED; j++) {
        const KaeItem *item = &page->items[j];
        if (item->type == KAE_BINDING && item->label && same_n(label, label_n - n, item->label)) {
            int key = kae_key_from_name(value, (int)value_n);
            if (key < 0)
                return false;
            page->keys[j] = (unsigned char)key;
            return true;
        }
    }
    return false;
}

static void apply_line(const char *id, size_t id_n, const char *label, size_t label_n, const char *value,
                       size_t value_n, void *user) {
    apply_t *a = user;
    for (int i = 0; i < a->count; i++)
        if (same_n(id, id_n, a->pages[i]->id) && apply_key(a->pages[i], label, label_n, value, value_n)) {
            a->applied++;
            return;
        }
    int64_t v;
    if (!number(value, value_n, &v))
        return;
    for (int i = 0; i < a->count; i++) {
        KaePage *page = a->pages[i];
        if (!same_n(id, id_n, page->id))
            continue;
        if (same_n(label, label_n, "(on)")) {
            if (!page->status)   // a mod Core switched off stays off
                page->enabled = v != 0;
            a->applied++;
            return;
        }
        for (int j = 0; j < page->count; j++) {
            KaeItem *item = &page->items[j];
            if (!item->label || !same_n(label, label_n, item->label))
                continue;
            int before = item->value;
            uint64_t bound = item->binding;
            switch (item->type) {
            case KAE_TOGGLE: item->value = v != 0; break;
            case KAE_CHOICE: item->value = clamp(v, 0, item->max); break;
            case KAE_NUMBER: item->value = clamp(v, item->min, item->max); break;
            case KAE_BINDING: item->binding = (uint64_t)v & KAE_BINDING_MASK; break;   // what the menu binds
            default: return;
            }
            a->applied++;
            if ((item->value != before || item->binding != bound) && item->changed)
                item->changed(item, item->user);
            return;
        }
        return;
    }
}

// ---- writing the pages out ----

typedef struct { writer_t *w; KaePage **pages; int count; const char *last_id; size_t last_n; } keep_t;

static bool installed(KaePage **pages, int count, const char *id, size_t n) {
    for (int i = 0; i < count; i++)
        if (same_n(id, n, pages[i]->id))
            return true;
    return false;
}

static void keep_line(const char *id, size_t id_n, const char *label, size_t label_n, const char *value,
                      size_t value_n, void *user) {
    keep_t *k = user;
    if (installed(k->pages, k->count, id, id_n))
        return;
    if (id != k->last_id) {
        put(k->w, "\n[");
        put_n(k->w, id, id_n);
        put(k->w, "]\n");
        k->last_id = id;
        k->last_n = id_n;
    }
    put_n(k->w, label, label_n);
    put(k->w, " = ");
    put_n(k->w, value, value_n);
    put(k->w, "\n");
}

static size_t render(KaePage **pages, int count) {
    writer_t w = { out, SIZE, false };
    out[0] = 0;
    put(&w, "# KaeGae Core: the Mods menu's settings. Written by Core when the menu closes.\n");
    for (int i = 0; i < count; i++) {
        const KaePage *page = pages[i];
        put(&w, "\n[");
        put(&w, page->id);
        put(&w, "]\n(on) = ");
        put_number(&w, page->enabled != 0, false);
        put(&w, "\n");
        for (int j = 0; j < page->count; j++) {
            const KaeItem *item = &page->items[j];
            if (!item->label || item->type == KAE_ACTION)
                continue;
            put(&w, item->label);
            put(&w, " = ");
            if (item->type == KAE_BINDING)
                put_number(&w, (int64_t)item->binding, true);
            else
                put_number(&w, item->value, false);
            put(&w, "\n");
            if (item->type == KAE_BINDING && page->keys && j < KAE_MAX_KEYED && page->keys[j]) {
                char name[24];
                put(&w, item->label);
                put(&w, " (key) = ");
                put(&w, kae_key_name(page->keys[j], name, sizeof name));
                put(&w, "\n");
            }
        }
    }
    keep_t keep = { &w, pages, count, 0, 0 };
    each_line(file, keep_line, &keep);
    return w.full ? 0 : (size_t)(w.at - out);
}

// ---- what the menu calls ----

// On the first frame: every mod has started and given its page by then.
void kp_settings_load(KaePage **pages, int count) {
    if (state)
        return;
    state = mount() ? 1 : -1;
    if (state < 0)
        return;
    if (!read_file()) {
        kp_log("settings: no file yet (" SHOWN "); it is written when the Mods menu closes after a change");
        return;
    }
    apply_t a = { pages, count, 0 };
    each_line(file, apply_line, &a);
    kp_logf("settings: %d loaded from " SHOWN, a.applied);
}

// When the menu closes.
void kp_settings_save(KaePage **pages, int count) {
    if (state <= 0)
        return;
    size_t len = render(pages, count);
    if (!len) {
        kp_log("settings: too many to save, the file was left as it was");
        return;
    }
    if (len == file_len && same_n(out, len, file))
        return;   // nothing changed
    if (!write_file(out, len)) {
        kp_log("settings: writing " SHOWN " failed");
        return;
    }
    for (size_t i = 0; i <= len; i++)
        file[i] = out[i];
    file_len = len;
    kp_log("settings: saved to " SHOWN);
}
