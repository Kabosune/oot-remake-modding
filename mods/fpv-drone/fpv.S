// FPV drone: the hooks. The flying itself is fpv_input in fpv.c.
//
//   npad_wrap      - the last instruction (br x17) of each nn::hid::GetNpadStates import stub
//                    branches here instead. It calls the real function, then fpv_input with the
//                    states it returned. This is a function call boundary, so only the return
//                    value and the link register need keeping.
//   fpv_view_hook  - right after the game has built the camera's view matrix (after First
//                    Person's hook, so the drone wins when both are on). On the gameplay view it
//                    keeps the game camera's eye and back axis for the next drone reset, and while
//                    the drone flies it copies the drone's matrix over the game's. Integer
//                    registers only. Replaces: cbz x8, 0x804e5b78
//
//   fpv_actor_hook - the first instruction (pacibsp) of f_82c415e0, the movement update of
//                    physics actors. Only while carrying Link, it calls fpv_actor(actor). At a
//                    function's first instruction only the arguments (x0-x7, q0-q7, x8) are live,
//                    so those are all that need keeping; x16 / x17 are free there by the ABI.

#include "params.inc"

    .section .text.hook, "ax"
    .p2align 2

    .global npad_wrap
npad_wrap:
    stp     x29, x30, [sp, #-0x20]!
    mov     x29, sp
    stp     x0, x2, [sp, #0x10]             // states, &npad id
    blr     x17                             // the real GetNpadStates (the stub loaded x17)
    ldp     x9, x2, [sp, #0x10]
    str     x0, [sp, #0x10]                 // keep its return value (states written)
    mov     w1, w0
    mov     x0, x9
    bl      fpv_input                       // (states, count, &id)
    ldr     x0, [sp, #0x10]
    ldp     x29, x30, [sp], #0x20
    ret

    .global fpv_view_hook
fpv_view_hook:
    stp     x9, x10, [sp, #-0x20]!
    stp     x11, x12, [sp, #0x10]
    mrs     x12, nzcv

    // Gameplay view only: camera 0 of the camera manager (same check as First Person).
    ldr     x9, [x20]
    adrp    x10, VT_VIEW
    add     x10, x10, :lo12:VT_VIEW
    cmp     x9, x10
    b.ne    9f
    adrp    x9, CAMMGR_SLOT
    ldr     x9, [x9, :lo12:CAMMGR_SLOT]
    cbz     x9, 9f
    ldr     x9, [x9]
    cbz     x9, 9f
    ldr     w10, [x9, #0x20]
    cbz     w10, 9f
    ldr     x9, [x9, #0x28]
    cbz     x9, 9f
    ldr     x9, [x9]
    cbz     x9, 9f
    ldr     x9, [x9, #0x78]
    cmp     x9, x20
    b.ne    9f

    adrp    x11, DRONE_STATE
    add     x11, x11, :lo12:DRONE_STATE
    str     wzr, [x11, #0x18]               // seen: the gameplay view is alive
    ldr     w9, [x11]                       // on
    cbnz    w9, 5f
    ldr     x9, [x20, #0x38]                // off: keep the game camera for the next reset
    ldr     w10, [x20, #0x40]
    str     x9, [x11, #0x20]                // eye x, y
    str     w10, [x11, #0x28]               // eye z
    ldr     x9, [x20, #0x28]
    ldr     w10, [x20, #0x30]
    str     x9, [x11, #0x2c]                // back x, y
    str     w10, [x11, #0x34]               // back z
    b       9f
5:  .irp    off, 0x00, 0x10, 0x20           // on: the drone's matrix replaces the game's
    ldp     x9, x10, [x11, #0x38 + \off]
    stp     x9, x10, [x20, #0x08 + \off]
    .endr
9:
    msr     nzcv, x12
    ldp     x11, x12, [sp, #0x10]
    ldp     x9, x10, [sp], #0x20
    cbz     x8, 8f                          // the replaced instruction
    b       HOOK_VIEW2_RET
8:  b       HOOK_VIEW2_TAKEN

    .global fpv_actor_hook
fpv_actor_hook:
    adrp    x16, DRONE_STATE
    ldr     w16, [x16, :lo12:DRONE_STATE + 0x0c]   // carrying?
    cbz     w16, 9f
    stp     x29, x30, [sp, #-0xe0]!
    mov     x29, sp
    stp     x0, x1, [sp, #0x10]
    stp     x2, x3, [sp, #0x20]
    stp     x4, x5, [sp, #0x30]
    stp     x6, x7, [sp, #0x40]
    str     x8, [sp, #0x50]
    stp     q0, q1, [sp, #0x60]
    stp     q2, q3, [sp, #0x80]
    stp     q4, q5, [sp, #0xa0]
    stp     q6, q7, [sp, #0xc0]
    bl      fpv_actor                       // (actor)
    ldp     q6, q7, [sp, #0xc0]
    ldp     q4, q5, [sp, #0xa0]
    ldp     q2, q3, [sp, #0x80]
    ldp     q0, q1, [sp, #0x60]
    ldr     x8, [sp, #0x50]
    ldp     x6, x7, [sp, #0x40]
    ldp     x4, x5, [sp, #0x30]
    ldp     x2, x3, [sp, #0x20]
    ldp     x0, x1, [sp, #0x10]
    ldp     x29, x30, [sp], #0xe0
9:  hint    #27                             // pacibsp, the replaced instruction (same sp and x30 as the game's)
    b       HOOK_MOVE_RET
