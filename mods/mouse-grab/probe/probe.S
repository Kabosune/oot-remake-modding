// Input probe: three wrappers on the import stubs of nn::hid functions the game already calls.
// Each replaces the stub's last instruction (br x17), a function call boundary, so only the
// return value and the link register need keeping.
//
//   style_wrap - GetNpadStyleSet: the game calls it for every controller slot on every poll, so
//                it serves as the probe's clock. Calls the real function, then probe_tick.
//   six_wrap   - GetSixAxisSensorStates: calls the real function, then probe_six with the states
//                it returned.
//   mouse_wrap - GetMouseStates: counts the game's own calls (those returning to
//                GAME_MOUSE_READ_RET), then goes on to the real function.

#include "params.inc"

    .section .text.hook, "ax"
    .p2align 2

    .global style_wrap
style_wrap:
    stp     x29, x30, [sp, #-0x20]!
    mov     x29, sp
    blr     x17
    str     x0, [sp, #0x10]
    bl      probe_tick
    ldr     x0, [sp, #0x10]
    ldp     x29, x30, [sp], #0x20
    ret

    .global six_wrap
six_wrap:
    stp     x29, x30, [sp, #-0x20]!
    mov     x29, sp
    str     x0, [sp, #0x10]                 // states
    blr     x17
    ldr     x9, [sp, #0x10]
    str     x0, [sp, #0x10]                 // keep the return value (states written)
    mov     w1, w0
    mov     x0, x9
    bl      probe_six                       // (states, count)
    ldr     x0, [sp, #0x10]
    ldp     x29, x30, [sp], #0x20
    ret

    .global mouse_wrap
mouse_wrap:
    adrp    x16, GAME_MOUSE_READ_RET
    add     x16, x16, :lo12:GAME_MOUSE_READ_RET
    cmp     x30, x16
    b.ne    1f
    adrp    x16, PROBE_STATE
    ldr     w9, [x16, :lo12:PROBE_STATE + 0x0c]
    add     w9, w9, #1
    str     w9, [x16, :lo12:PROBE_STATE + 0x0c]
1:  br      x17
