// First-person camera for The Legend of Zelda: Ocarina of Time (Switch 2), main build E0F3CCFA.
//
// Two hooks:
//   fp_actor_hook  - in the movement update, copies Link's position into FP_STATE every frame.
//   fp_view_hook   - right after the gameplay camera's view matrix is built. Reads the controller,
//                    toggles on R3 (right stick click), and when on, moves the view to Link's eyes.
//                    The rotation stays the game's own, so the right stick still looks around and
//                    the left stick still moves relative to where you look.
//                    R3 is also the game's camera recenter; with KEEP_PITCH, fp_pitch.c keeps the
//                    up / down angle through it and only the left / right swing happens.
//
// FP_STATE layout (zeroed at boot, so the mode starts off):
//   +0x00 u32 enabled        +0x04 u32 R3 last frame    +0x08 u32 Link update counter
//   +0x0c u32 counter seen   +0x10 u32 views since Link last updated
//   +0x14 f32 x, y, z of Link (+0x14 +0x18 +0x1c)      +0x20 f32 measured eye height above Link
//   +0x24 f32 height offset from the keyboard (kept across toggles until the game restarts)
//   +0x28 u32 keys last frame        +0x2c u32 show Link toggle (0 = hidden, the default)
//   +0x30 u32 Link currently hidden by us                 +0x34 u32 his visible byte before that
//   +0x38..+0x54 pitch kept across the R3 recenter (fp_pitch.c)
//
// Keyboard (needs the emulator's keyboard emulation on): ',' eye down, '.' eye up, '/' offset back
// to 0, ';' show / hide Link while in first person (he starts hidden).
//
// Tunables come from params.inc, written by build.py.

#include "params.inc"

// The Link hook lives in its own section (a second gap of the code cave, see build.py).
    .section .text.actor,"ax",@progbits
    .p2align 2

// ---------------------------------------------------------------------------------------------
// Movement update hook. x19 = the actor being moved. Replaces: add x23, x19, #0x328
// ---------------------------------------------------------------------------------------------
    .global fp_actor_hook
fp_actor_hook:
    stp     x9, x10, [sp, #-0x40]!
    stp     x11, x12, [sp, #0x10]
    stp     x13, x14, [sp, #0x20]
    mrs     x9, nzcv
    str     x9, [sp, #0x30]

    ldr     x9, [x19]                       // actor vtable
    adrp    x10, VT_ACTOR
    add     x10, x10, :lo12:VT_ACTOR
    cmp     x9, x10
    b.ne    9f
    ldr     x9, [x19, #0x270]               // components
    cbz     x9, 9f
    ldr     x9, [x9, #0x320]                // movement component
    cbz     x9, 9f
    ldr     x10, [x9, #0x18]                // ...whose owner must be this actor
    cmp     x10, x19
    b.ne    9f
    sub     x9, x9, #0x1, lsl #12           // player object = movement - 0x1d50
    sub     x9, x9, #0xd50
    ldr     x10, [x9]
    adrp    x11, VT_PLAYER
    add     x11, x11, :lo12:VT_PLAYER
    cmp     x10, x11
    b.ne    9f
    ldr     x10, [x9, #0x10]                // resource record
    cbz     x10, 9f
    ldr     w11, [x10, #0x58]               // name == "Player\0"
    movz    w12, #0x6c50
    movk    w12, #0x7961, lsl #16
    cmp     w11, w12
    b.ne    9f
    ldrh    w11, [x10, #0x5c]
    mov     w12, #0x7265
    cmp     w11, w12
    b.ne    9f
    ldrb    w11, [x10, #0x5e]
    cbnz    w11, 9f

    adrp    x10, FP_STATE
    add     x10, x10, :lo12:FP_STATE
    ldr     w11, [x19, #0x31c]
    str     w11, [x10, #0x14]
    ldr     w11, [x19, #0x320]
    str     w11, [x10, #0x18]
    ldr     w11, [x19, #0x324]
    str     w11, [x10, #0x1c]
    ldr     w11, [x10, #0x08]
    add     w11, w11, #1
    str     w11, [x10, #0x08]

    // Hide Link's model while first person is on and the show toggle is off, the same way the
    // game's OneShotSetModelVisible does: model = [[actor+0x270]+0x260], visible byte +0xe5,
    // then flag +0x120 bit 11 so the model picks up the change. What the game had before is
    // put back when hiding stops.
.if HIDE_LINK
    ldr     x12, [x19, #0x270]
    ldr     x12, [x12, #0x260]              // model component
    cbz     x12, 9f
    ldr     w11, [x10]                      // first person on
    ldr     w13, [x10, #0x2c]               // show toggle
    bic     w11, w11, w13
    ldr     w13, [x10, #0x30]               // we hid him
    cbz     w11, 50f
    cbnz    w13, 45f
    ldrb    w14, [x12, #0xe5]               // start hiding: remember the game's value
    str     w14, [x10, #0x34]
    mov     w13, #1
    str     w13, [x10, #0x30]
45: ldrb    w14, [x12, #0xe5]
    cbz     w14, 9f
    strb    wzr, [x12, #0xe5]
    b       55f
50: cbz     w13, 9f                         // stop hiding: put the game's value back
    str     wzr, [x10, #0x30]
    ldr     w14, [x10, #0x34]
    strb    w14, [x12, #0xe5]
55: ldr     w14, [x12, #0x120]
    orr     w14, w14, #0x800
    str     w14, [x12, #0x120]
.endif
9:
    ldr     x9, [sp, #0x30]
    msr     nzcv, x9
    ldp     x13, x14, [sp, #0x20]
    ldp     x11, x12, [sp, #0x10]
    ldp     x9, x10, [sp], #0x40
    add     x23, x19, #0x328                // the replaced instruction
    b       HOOK_ACTOR_RET

    .text
    .p2align 2

// ---------------------------------------------------------------------------------------------
// View hook. x19 = camera, x20 = view (matrix just written). Replaces: ldr x8, [x19, #0x20]
// Calls into nn::hid, so every caller-saved register is kept.
// ---------------------------------------------------------------------------------------------
    .equ    FRAME, 0x2d0
    .equ    PADBUF, 0x230                   // one Npad state (0x28 bytes, room for 0x80)
    .equ    PADID,  0x2b0
    .equ    BUTTONS, 0x2b8
    .equ    STICKS, 0x2c0                   // right stick y of each controller type (3 x s32)

    .macro  READPAD plt, id, n
    mov     w9, #\id
    str     w9, [sp, #PADID]
    str     xzr, [sp, #PADBUF + 8]
.if KEEP_PITCH
    str     xzr, [sp, #PADBUF + 0x18]       // right stick
.endif
    add     x0, sp, #PADBUF
    mov     w1, #1
    add     x2, sp, #PADID
    bl      \plt
    ldr     x9, [sp, #PADBUF + 8]           // buttons
    ldr     x10, [sp, #BUTTONS]
    orr     x10, x10, x9
    str     x10, [sp, #BUTTONS]
.if KEEP_PITCH
    ldr     w9, [sp, #PADBUF + 0x1c]
    str     w9, [sp, #STICKS + 4 * \n]
.endif
    .endm

    .macro  TRANSLATE row
    ldp     s4, s5, [x20, #\row]
    ldr     s6, [x20, #\row + 8]
    fmul    s7, s4, s0
    fmadd   s7, s5, s1, s7
    fmadd   s7, s6, s2, s7
    fneg    s7, s7
    str     s7, [x20, #\row + 12]
    .endm

    .global fp_view_hook
fp_view_hook:
    sub     sp, sp, #FRAME
    stp     x0, x1, [sp, #0x00]
    stp     x2, x3, [sp, #0x10]
    stp     x4, x5, [sp, #0x20]
    stp     x6, x7, [sp, #0x30]
    stp     x8, x9, [sp, #0x40]
    stp     x10, x11, [sp, #0x50]
    stp     x12, x13, [sp, #0x60]
    stp     x14, x15, [sp, #0x70]
    stp     x16, x17, [sp, #0x80]
    stp     x18, x30, [sp, #0x90]
    mrs     x9, nzcv
    str     x9, [sp, #0xa0]
    stp     q0, q1, [sp, #0xb0]
    stp     q2, q3, [sp, #0xd0]
    stp     q4, q5, [sp, #0xf0]
    stp     q6, q7, [sp, #0x110]
    stp     q16, q17, [sp, #0x130]
    stp     q18, q19, [sp, #0x150]
    stp     q20, q21, [sp, #0x170]
    stp     q22, q23, [sp, #0x190]
    stp     q24, q25, [sp, #0x1b0]
    stp     q26, q27, [sp, #0x1d0]
    stp     q28, q29, [sp, #0x1f0]
    stp     q30, q31, [sp, #0x210]

    // 1. Only the gameplay view (camera 0 of the camera manager).
    ldr     x9, [x20]
    adrp    x10, VT_VIEW
    add     x10, x10, :lo12:VT_VIEW
    cmp     x9, x10
    b.ne    90f
    adrp    x9, CAMMGR_SLOT
    ldr     x9, [x9, :lo12:CAMMGR_SLOT]
    cbz     x9, 90f
    ldr     x9, [x9]
    cbz     x9, 90f
    ldr     w10, [x9, #0x20]
    cbz     w10, 90f
    ldr     x9, [x9, #0x28]
    cbz     x9, 90f
    ldr     x9, [x9]
    cbz     x9, 90f
    ldr     x9, [x9, #0x78]
    cmp     x9, x20
    b.ne    90f

    // 2. Buttons of player 1 (Pro Controller / Joy-Con pair) and handheld, merged.
    str     xzr, [sp, #BUTTONS]
    READPAD PLT_GETNPAD_FULLKEY, 0, 0
    READPAD PLT_GETNPAD_JOYDUAL, 0, 1
    READPAD PLT_GETNPAD_HANDHELD, 0x20, 2

    // 3. R3 pressed this frame -> toggle.
    adrp    x11, FP_STATE
    add     x11, x11, :lo12:FP_STATE
    ldr     x10, [sp, #BUTTONS]
    ubfx    w10, w10, #TOGGLE_BIT, #1
    ldr     w9, [x11, #0x04]
    str     w10, [x11, #0x04]
    bic     w9, w10, w9
    cbz     w9, 20f
    ldr     w9, [x11]
    eor     w9, w9, #1
    str     w9, [x11]
    cbz     w9, 20f
    str     wzr, [x11, #0x10]               // fresh start for the staleness count
.if KEEP_PITCH
    mov     w10, #1
    str     w10, [x11, #0x50]               // fp_pitch: keep the pitch from before this press
.endif
.if FIXED_HEIGHT
    ldr     s0, height_fixed
.else
    // Turned on: eye height = camera target height - Link's height, clamped, plus an offset.
    // Measured once here, so it fits child and adult Link without knowing which one is active.
    ldr     d0, [x20, #0x80]                // target y (f64)
    fcvt    s0, d0
    ldr     s1, [x11, #0x18]
    fsub    s0, s0, s1
    ldr     s1, height_min
    fmax    s0, s0, s1
    ldr     s1, height_max
    fmin    s0, s0, s1
    ldr     s1, height_add
    fadd    s0, s0, s1
.endif
    str     s0, [x11, #0x20]
20:
.if KEEP_PITCH
    add     x0, x20, #8
    add     x1, sp, #STICKS
    bl      fp_pitch_track
    adrp    x11, FP_STATE
    add     x11, x11, :lo12:FP_STATE
.endif
    ldr     w9, [x11]
    cbz     w9, 90f

    // 3b. Height keys: one step per press (rising edge), so presses can be counted.
.if HEIGHT_KEYS
    add     x0, sp, #PADBUF
    stp     xzr, xzr, [x0]
    stp     xzr, xzr, [x0, #0x10]
    stp     xzr, xzr, [x0, #0x20]
    bl      PLT_GETKEYBOARD
    adrp    x11, FP_STATE
    add     x11, x11, :lo12:FP_STATE
    ldr     x10, [sp, #PADBUF + 0x10]       // keys 0..63
    ubfx    x10, x10, #0x33, #6             // bit 0 ';', 3 ',', 4 '.', 5 '/'
    ldr     w9, [x11, #0x28]
    str     w10, [x11, #0x28]
    bic     w9, w10, w9
    ldr     s0, [x11, #0x24]
    ldr     s1, height_step
    tbz     w9, #3, 21f
    fsub    s0, s0, s1
21: tbz     w9, #4, 22f
    fadd    s0, s0, s1
22: tbz     w9, #5, 23f
    movi    d0, #0
23: str     s0, [x11, #0x24]
    tbz     w9, #0, 24f                     // ';' toggles showing Link
    ldr     w10, [x11, #0x2c]
    eor     w10, w10, #1
    str     w10, [x11, #0x2c]
24:
.endif

    // 4. Link must still be updating (not paused, loading, or gone).
    ldr     w9, [x11, #0x08]
    ldr     w10, [x11, #0x0c]
    str     w9, [x11, #0x0c]
    ldr     w12, [x11, #0x10]
    add     w12, w12, #1
    cmp     w9, w10
    csel    w12, wzr, w12, ne
    str     w12, [x11, #0x10]
    cmp     w12, #STALE_LIMIT
.if FALLBACK_TARGET
    // Diagnostic build: with no Link update, put the eye on the camera's look-at point instead,
    // so a test can tell the view hook working apart from the Link hook working.
    b.ls    25f
    ldp     d0, d1, [x20, #0x78]
    ldr     d2, [x20, #0x88]
    fcvt    s0, d0
    fcvt    s1, d1
    fcvt    s2, d2
    b       30f
25:
.else
    b.hi    90f
.endif
.if KEEP_PITCH
    add     x0, x20, #8
    bl      fp_pitch_apply
    adrp    x11, FP_STATE
    add     x11, x11, :lo12:FP_STATE
.endif

    // 5. Eye = Link + (0, height, 0), pushed forward along the flat view direction so his
    //    head stays behind the camera. Row 2 of the matrix points backwards.
    ldp     s0, s1, [x11, #0x14]
    ldr     s2, [x11, #0x1c]
    ldr     s3, [x11, #0x20]
    fadd    s1, s1, s3
    ldr     s3, [x11, #0x24]
    fadd    s1, s1, s3
    ldr     s4, [x20, #0x28]
    ldr     s6, [x20, #0x30]
    fmul    s7, s4, s4
    fmadd   s7, s6, s6, s7
    fsqrt   s7, s7
    ldr     s16, epsilon
    fcmp    s7, s16
    b.le    30f
    ldr     s16, forward
    fdiv    s16, s16, s7
    fmsub   s0, s4, s16, s0                 // x -= back.x * k
    fmsub   s2, s6, s16, s2                 // z -= back.z * k
30:
    // 6. New translation for each row: t = -(axis . eye).
    TRANSLATE 0x08
    TRANSLATE 0x18
    TRANSLATE 0x28

90:
    ldp     q0, q1, [sp, #0xb0]
    ldp     q2, q3, [sp, #0xd0]
    ldp     q4, q5, [sp, #0xf0]
    ldp     q6, q7, [sp, #0x110]
    ldp     q16, q17, [sp, #0x130]
    ldp     q18, q19, [sp, #0x150]
    ldp     q20, q21, [sp, #0x170]
    ldp     q22, q23, [sp, #0x190]
    ldp     q24, q25, [sp, #0x1b0]
    ldp     q26, q27, [sp, #0x1d0]
    ldp     q28, q29, [sp, #0x1f0]
    ldp     q30, q31, [sp, #0x210]
    ldr     x9, [sp, #0xa0]
    msr     nzcv, x9
    ldp     x0, x1, [sp, #0x00]
    ldp     x2, x3, [sp, #0x10]
    ldp     x4, x5, [sp, #0x20]
    ldp     x6, x7, [sp, #0x30]
    ldp     x8, x9, [sp, #0x40]
    ldp     x10, x11, [sp, #0x50]
    ldp     x12, x13, [sp, #0x60]
    ldp     x14, x15, [sp, #0x70]
    ldp     x16, x17, [sp, #0x80]
    ldp     x18, x30, [sp, #0x90]
    add     sp, sp, #FRAME
    ldr     x8, [x19, #0x20]                // the replaced instruction
    b       HOOK_VIEW_RET

    .p2align 2
epsilon:      .float 0.0001
forward:      .float FORWARD
height_min:   .float HEIGHT_MIN
height_max:   .float HEIGHT_MAX
height_add:   .float HEIGHT_ADD
height_fixed: .float HEIGHT_FIXED
height_step:  .float HEIGHT_STEP
