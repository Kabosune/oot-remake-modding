// Header of a module that the game's rtld loads from a subsdk slot.
//
// rtld reads the word at offset 4 to find MOD0, relocates the module, resolves its imports
// against the other modules (main, sdk, other subsdk) and calls DT_INIT (kp_module_init, set by
// the link command). MOD0's last word points at space rtld uses for its own record of the module.

    .section .text.header, "ax", %progbits
    .global __kp_module_start
    .hidden __kp_module_start
__kp_module_start:
    .word   0
    .word   __kp_mod0 - __kp_module_start
    .ascii  "KAEGAE\0\0"

    .section .rodata.mod0, "a", %progbits
    .p2align 2
    .global __kp_mod0
    .hidden __kp_mod0
__kp_mod0:
    .ascii  "MOD0"
    .word   __kp_dynamic        - __kp_mod0
    .word   __kp_bss_start      - __kp_mod0
    .word   __kp_bss_end        - __kp_mod0
    .word   __kp_eh_hdr_start   - __kp_mod0
    .word   __kp_eh_hdr_end     - __kp_mod0
    .word   __kp_rtld_object    - __kp_mod0

    .section .bss.rtld_object, "aw", %nobits
    .p2align 4
    .global __kp_rtld_object
    .hidden __kp_rtld_object
__kp_rtld_object:
    .space  0x400
