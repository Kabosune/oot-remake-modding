// Kaepora hook points: small patches to main that call into the module.
//
// Each hook point jumps from a site in main to a stub here. The stub loads a function pointer from
// KP_HOOK_SLOTS (written by the module at start) and, when it isn't zero, calls it; then it runs
// the instruction the jump replaced and goes back. Without the module the stubs do nothing.
//
//   slot 0  movement update   f_82c415e0's second instruction (its first belongs to FPV Drone,
//                              whose stub comes back here). Runs for every physics actor every
//                              frame, on the game's thread; x0 = the actor. Only the arguments
//                              (x0-x8, q0-q7) and the signed return address in x30 are live.

    .section .text.hook, "ax"
    .p2align 2

    .ascii  "KPHOOK01"               // the module checks this tag before it writes the slots

    .global kp_hook_move
kp_hook_move:
    adrp    x16, KP_HOOK_SLOTS
    ldr     x16, [x16, :lo12:KP_HOOK_SLOTS]
    cbz     x16, 9f
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
    blr     x16                      // (actor)
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
9:  str     d10, [sp, #-0x80]!       // the replaced instruction
    b       MOVE_SECOND_RET
