/* Slopped Up Sloperina: small things sloperinaGZ got elsewhere (GCC's builtins, the files left out). */
#include <stdbool.h>

#include "gameimage.h"

/* sloperinaGZ's GCC build turns sqrtf into the instruction; clang with -fno-builtin calls it */
float sqrtf(float x)
{
  float r;
  __asm__("fsqrt %s0, %s1" : "=w"(r) : "w"(x));
  return r;
}

/* the game's pictures aren't loaded here (gameimage.c is left out): every one is "lost" */
bool gameimage_lost(int picture)
{
  return true;
}
