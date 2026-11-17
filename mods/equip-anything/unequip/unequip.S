// Equip Anything's unequip patch (game 1.1.1): picking an item that is already equipped takes
// it off. Addresses are module offsets + 0x80020000 (the repo's convention).
//
// f_80a9acd0 (offset 0xA7ACD0) is the pause menu's equip function: (menu, name, mode, flag).
// Its second instruction jumps here. f_80a91080 (0xA71080) answers "is this item equipped?",
// f_833c6a40 (0x33A6A40) is the menu's own unequip: it sets the item's PlayerStatus.Equip...
// slot in GameData to an empty name.

// EQUIP_CONT (equip's third instruction), IS_EQUIPPED and UNEQUIP come from build_ips.py's linker script.

    .section .text.cave, "ax"
    .global entry
entry:                                  // lr is already signed (pacibsp ran), sp unchanged
    stp     x29, x30, [sp, #-0x30]!
    stp     x0, x1, [sp, #0x10]
    stp     x2, x3, [sp, #0x20]
    bl      IS_EQUIPPED                 // (menu, name)
    mov     w16, w0
    ldp     x2, x3, [sp, #0x20]
    ldp     x0, x1, [sp, #0x10]
    ldp     x29, x30, [sp], #0x30
    cbnz    w16, 1f
    sub     sp, sp, #0x180              // the instruction the jump replaced
    b       EQUIP_CONT
1:  b       take_off

    .section .text.piece, "ax"
take_off:
    stp     x29, x30, [sp, #-0x10]!
    mov     w2, wzr
    bl      UNEQUIP                     // (menu, name, 0)
    ldp     x29, x30, [sp], #0x10
    autibsp                             // equip's own pacibsp signed lr
    ret
