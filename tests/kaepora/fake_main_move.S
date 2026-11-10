// The start of the fake movement update, at the address of the real one. Its second instruction is
// the real one's, the one Core's patch replaces.
    .section .text_move, "ax", %progbits
    .global move_update
    .hidden move_update
move_update:
    nop                              // the game: pacibsp (FPV Drone's hook site)
    str     d10, [sp, #-0x80]!       // Core's hook point "Actor.MoveUpdate"
    stp     x29, x30, [sp, #0x10]
    bl      record_move
    ldp     x29, x30, [sp, #0x10]
    ldr     d10, [sp], #0x80
    ret
