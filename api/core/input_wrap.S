// The wrapper Core puts on main's nn::hid::GetNpadStyleSet import.
//
// It is in assembly so that it changes nothing the real function could depend on: it calls
// kp_before_style_set(id) and then jumps to the real function with x0 and x8 as the game set them.
// (x8 carries the address for the result if the style set is returned through memory. It should
// come back in w0, but a C wrapper would have to assume that.)

    .text
    .p2align 2
    .global kp_style_set_wrap
    .hidden kp_style_set_wrap
    .type   kp_style_set_wrap, %function
kp_style_set_wrap:
    stp     x29, x30, [sp, #-0x20]!
    mov     x29, sp
    stp     x0, x8, [sp, #0x10]
    bl      kp_before_style_set
    ldp     x0, x8, [sp, #0x10]
    adrp    x16, kp_real_style_set
    ldr     x16, [x16, :lo12:kp_real_style_set]
    ldp     x29, x30, [sp], #0x20
    br      x16
    .size   kp_style_set_wrap, . - kp_style_set_wrap
