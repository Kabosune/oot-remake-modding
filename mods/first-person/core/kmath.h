// Small float maths for a mod with no libc: sin / cos / tan / atan good to about 1e-6 over the
// ranges a camera needs, so the mod imports nothing from the system.
#pragma once

#define KPI 3.14159265f

static inline float kclamp(float x, float lo, float hi) { return x < lo ? lo : x > hi ? hi : x; }
static inline float ksqrt(float x) {   // fsqrt itself: __builtin_sqrtf may call sqrtf, which a mod doesn't have
#if defined(__aarch64__)
    float r;
    __asm__("fsqrt %s0, %s1" : "=w"(r) : "w"(x));
    return r;
#else
    return __builtin_sqrtf(x);
#endif
}

// x in [-pi, pi]
static inline float ksin(float x) {
    float x2 = x * x;
    return x * (1 - x2 / 6 * (1 - x2 / 20 * (1 - x2 / 42 * (1 - x2 / 72 * (1 - x2 / 110 * (1 - x2 / 156))))));
}
static inline float kcos(float x) {
    float x2 = x * x;
    return 1 - x2 / 2 * (1 - x2 / 12 * (1 - x2 / 30 * (1 - x2 / 56 * (1 - x2 / 90 * (1 - x2 / 132 * (1 - x2 / 182))))));
}
static inline float krad(float degrees) { return degrees * (KPI / 180.0f); }

static inline float katan(float x) {
    float a = __builtin_fabsf(x), t = a > 1 ? 1 / a : a, t2 = t * t;
    float r = t * (0.99997726f + t2 * (-0.33262347f + t2 * (0.19354346f + t2 * (-0.11643287f + t2 * (0.05265332f + t2 * -0.01172120f)))));
    if (a > 1)
        r = KPI / 2 - r;
    return x < 0 ? -r : r;
}

// The vertical field of view (radians) that gives `degrees` across the picture at this aspect.
static inline float kfovy_from_horizontal(float degrees, float aspect) {
    float h = krad(degrees) / 2;
    return 2 * katan(ksin(h) / kcos(h) / aspect);
}
