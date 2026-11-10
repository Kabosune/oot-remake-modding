/* A module for a subsdk slot: position independent, three page-aligned segments
   (code, read-only data, data + bss), which is what an NSO holds. */
OUTPUT_FORMAT(elf64-littleaarch64)
ENTRY(__kp_module_start)

PHDRS
{
  code    PT_LOAD FLAGS(5);
  ro      PT_LOAD FLAGS(4);
  rw      PT_LOAD FLAGS(6);
  dyn     PT_DYNAMIC;
}

SECTIONS
{
  . = 0;
  .text : { KEEP(*(.text.header)) *(.text .text.*) } :code
  .plt  : { *(.plt .plt.*) } :code

  . = ALIGN(0x1000);
  .rodata   : { KEEP(*(.rodata.mod0)) *(.rodata .rodata.*) } :ro
  .note.gnu.build-id : { *(.note.gnu.build-id) } :ro
  .hash     : { *(.hash) } :ro
  .gnu.hash : { *(.gnu.hash) } :ro
  .dynsym   : { *(.dynsym) } :ro
  .dynstr   : { *(.dynstr) } :ro
  .rela.dyn : { *(.rela.dyn) } :ro
  .rela.plt : { *(.rela.plt) } :ro
  .eh_frame_hdr : { HIDDEN(__kp_eh_hdr_start = .); *(.eh_frame_hdr) HIDDEN(__kp_eh_hdr_end = .); } :ro
  .eh_frame : { KEEP(*(.eh_frame)) } :ro

  . = ALIGN(0x1000);
  .data     : { *(.data .data.*) } :rw
  .dynamic  : { HIDDEN(__kp_dynamic = .); *(.dynamic) } :rw :dyn
  .got      : { *(.got) } :rw
  .got.plt  : { *(.got.plt) } :rw
  .bss (NOLOAD) : {
    . = ALIGN(16);
    HIDDEN(__kp_bss_start = .);
    *(.bss.rtld_object) *(.bss .bss.*) *(COMMON)
    . = ALIGN(16);
    HIDDEN(__kp_bss_end = .);
  } :rw

  /DISCARD/ : { *(.interp) *(.comment) *(.note.GNU-stack) *(.ARM.attributes) }
}
