// The module's side of the camera view hook point (slot 1, hookpoints.S).
//
// The stub in main jumps here from the middle of f_804e48c0, where every register may be live.
// It has kept x16, x17, x29 and x30; this keeps every other register a C function may change
// (x0-x15, x18, the flags, q0-q7, q16-q31), then calls kp_view(view = x20, camera = x19).
// x19-x28 and d8-d15 are kept by the C code itself (the ABI).

    .text
    .p2align 2
    .global kp_view_entry
    .hidden kp_view_entry
    .type   kp_view_entry, %function
kp_view_entry:
    sub     sp, sp, #0x2c0
    stp     x0, x1, [sp, #0x00]
    stp     x2, x3, [sp, #0x10]
    stp     x4, x5, [sp, #0x20]
    stp     x6, x7, [sp, #0x30]
    stp     x8, x9, [sp, #0x40]
    stp     x10, x11, [sp, #0x50]
    stp     x12, x13, [sp, #0x60]
    stp     x14, x15, [sp, #0x70]
    stp     x18, x30, [sp, #0x80]
    mrs     x9, nzcv
    str     x9, [sp, #0x90]
    stp     q0, q1, [sp, #0xa0]
    stp     q2, q3, [sp, #0xc0]
    stp     q4, q5, [sp, #0xe0]
    stp     q6, q7, [sp, #0x100]
    stp     q16, q17, [sp, #0x120]
    stp     q18, q19, [sp, #0x140]
    stp     q20, q21, [sp, #0x160]
    stp     q22, q23, [sp, #0x180]
    stp     q24, q25, [sp, #0x1a0]
    stp     q26, q27, [sp, #0x1c0]
    stp     q28, q29, [sp, #0x1e0]
    stp     q30, q31, [sp, #0x200]
    mrs     x9, fpcr
    mrs     x10, fpsr
    add     x11, sp, #0x220
    stp     x9, x10, [x11]
    mov     x0, x20
    mov     x1, x19
    bl      kp_view
    add     x11, sp, #0x220
    ldp     x9, x10, [x11]
    msr     fpcr, x9
    msr     fpsr, x10
    ldp     q0, q1, [sp, #0xa0]
    ldp     q2, q3, [sp, #0xc0]
    ldp     q4, q5, [sp, #0xe0]
    ldp     q6, q7, [sp, #0x100]
    ldp     q16, q17, [sp, #0x120]
    ldp     q18, q19, [sp, #0x140]
    ldp     q20, q21, [sp, #0x160]
    ldp     q22, q23, [sp, #0x180]
    ldp     q24, q25, [sp, #0x1a0]
    ldp     q26, q27, [sp, #0x1c0]
    ldp     q28, q29, [sp, #0x1e0]
    ldp     q30, q31, [sp, #0x200]
    ldr     x9, [sp, #0x90]
    msr     nzcv, x9
    ldp     x0, x1, [sp, #0x00]
    ldp     x2, x3, [sp, #0x10]
    ldp     x4, x5, [sp, #0x20]
    ldp     x6, x7, [sp, #0x30]
    ldp     x8, x9, [sp, #0x40]
    ldp     x10, x11, [sp, #0x50]
    ldp     x12, x13, [sp, #0x60]
    ldp     x14, x15, [sp, #0x70]
    ldp     x18, x30, [sp, #0x80]
    add     sp, sp, #0x2c0
    ret
    .size   kp_view_entry, . - kp_view_entry
