// The part of the fake view update around Core's "Camera.View" hook point: x19 = camera, x20 = view,
// the site is the real one's instruction (ldr x8, [x19, #0x20]) at the real one's address. Before
// the site it fills the registers a C function may change with known values, after it stores them
// to `out` (x2), so the test can see the hook kept them all.
    .section .text_view, "ax", %progbits
    .global view_update
    .hidden view_update
view_update:                            // (camera, view, out)
    stp     x19, x20, [sp, #-0x30]!
    stp     x29, x30, [sp, #0x10]
    str     x21, [sp, #0x20]
    mov     x19, x0
    mov     x20, x1
    mov     x21, x2
    mov     x0, #0x1000
    mov     x1, #0x1001
    mov     x3, #0x1003
    mov     x4, #0x1004
    mov     x5, #0x1005
    mov     x6, #0x1006
    mov     x7, #0x1007
    mov     x9, #0x1009
    mov     x10, #0x100a
    mov     x11, #0x100b
    mov     x12, #0x100c
    mov     x13, #0x100d
    mov     x14, #0x100e
    mov     x15, #0x100f
    mov     x16, #0x1010
    mov     x17, #0x1011
    fmov    d0, #1.0
    fmov    d7, #7.0
    fmov    d16, #16.0
    fmov    d31, #31.0
    cmp     x0, x0                      // Z set
    b       1f
    .org    0x4C5068 - 0x4C4F00
1:  ldr     x8, [x19, #0x20]            // Core's hook point "Camera.View"
    cbz     x8, 2f
    stp     x0, x1, [x21, #0x00]
    stp     x3, x4, [x21, #0x10]
    stp     x5, x6, [x21, #0x20]
    stp     x7, x9, [x21, #0x30]
    stp     x10, x11, [x21, #0x40]
    stp     x12, x13, [x21, #0x50]
    stp     x14, x15, [x21, #0x60]
    stp     x16, x17, [x21, #0x70]
    stp     d0, d7, [x21, #0x80]
    stp     d16, d31, [x21, #0x90]
    cset    x9, eq
    stp     x9, x8, [x21, #0xa0]
2:  ldr     x21, [sp, #0x20]
    ldp     x29, x30, [sp, #0x10]
    ldp     x19, x20, [sp], #0x30
    ret
