// A one-off survey, run a second after Link goes down: where are the ragdoll's bodies?
//
// 1. Link's controller body ([property+0x20], vtable BODY_VT): which offsets hold his position.
// 2. From the ragdoll component, follow pointers three levels deep and log every object with the
//    body vtable, and every place that holds three floats within 3 m of Link (bone or body
//    positions), with the path of offsets that leads there.
#include "core.h"

#define BODY_VT   0x4C34658   // controller body (sloperina's notes)
#define OBJ_BYTES 0x400
#define MAX_SEEN  400
#define MAX_LINES 90

#define AT(p, off, type) (*(type *)((char *)(p) + (off)))

static uintptr_t seen[MAX_SEEN];
static int seen_count, lines;
static float link_pos[3];

static bool near_link(const float *f) {
    float d = 0;
    for (int i = 0; i < 3; i++) {
        float x = f[i] - link_pos[i];
        if (!(x == x) || x > 3.0f || x < -3.0f)   // NaN or far
            return false;
        d += x * x;
    }
    return d > 0.0001f && d < 9.0f;
}

static void line(const char *text, uintptr_t value, const int *path, int depth) {
    if (lines++ >= MAX_LINES)
        return;
    int64_t p = 0;
    for (int i = 0; i < depth; i++)
        p = p * 0x10000 + path[i];
    kp_log_hex(text, value);
    kp_log_2("    path (offsets, 16 bits each), depth:", p, depth);
}

static void visit(uintptr_t obj, int *path, int depth) {
    if (seen_count >= MAX_SEEN || !kp_readable(obj, OBJ_BYTES))
        return;
    for (int i = 0; i < seen_count; i++)
        if (seen[i] == obj)
            return;
    seen[seen_count++] = obj;
    if (AT(obj, 0, uintptr_t) == kp_main + BODY_VT)
        line("survey: body object", obj, path, depth);
    for (int off = 0; off + 12 <= OBJ_BYTES; off += 4) {
        if (near_link((const float *)(obj + off))) {
            path[depth] = off;
            line("survey: position near Link at object", obj, path, depth + 1);
            off += 8;
        }
    }
    if (depth == 3)
        return;
    for (int off = 0; off < OBJ_BYTES; off += 8) {
        uintptr_t p = AT(obj, off, uintptr_t);
        if ((p & 7) || p < 0x1000000000ULL || p > 0x8000000000ULL)   // heap pointers only (seen: 0x21........)
            continue;
        path[depth] = off;
        visit(p, path, depth + 1);
    }
}

void survey(void *actor, void *holder, void *ragdoll) {
    for (int i = 0; i < 3; i++)
        link_pos[i] = AT(actor, 0x31c + 4 * i, float);
    kp_log_2("survey: Link at (cm)", (int64_t)(link_pos[0] * 100), (int64_t)(link_pos[2] * 100));
    kp_log_2("survey: Link height (cm), ragdoll state", (int64_t)(link_pos[1] * 100), AT(ragdoll, 0x17c, int32_t));
    void *property = AT(holder, 8, void *);
    void *body = property ? AT(property, 0x20, void *) : 0;
    if (body && AT(body, 0, uintptr_t) == kp_main + BODY_VT) {
        kp_log_hex("survey: controller body", (uintptr_t)body);
        for (int off = 0; off + 12 <= 0x400; off += 4) {
            const float *f = (const float *)((char *)body + off);
            float dx = f[0] - link_pos[0], dy = f[1] - link_pos[1], dz = f[2] - link_pos[2];
            if (dx * dx + dy * dy + dz * dz < 1.0f)
                kp_log_2("    controller body: Link's position (within 1 m) at offset, y cm", off, (int64_t)(f[1] * 100));
        }
    } else {
        kp_log_hex("survey: no controller body; property", (uintptr_t)property);
    }
    seen_count = 0;
    lines = 0;
    int path[4];
    visit((uintptr_t)ragdoll, path, 0);
    kp_log_2("survey: done. objects seen, lines:", seen_count, lines);
}
