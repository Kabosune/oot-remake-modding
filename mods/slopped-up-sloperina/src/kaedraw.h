/* Slopped Up Sloperina: drawing sloperinaGZ's panels and overlays with KaeGae Core (kaedraw.c). */
#ifndef KAEDRAW_H
#define KAEDRAW_H

#include <kaegae.h>

/* Core's draw event: the panels gfx.c published, the air walls' and enemies' rectangles, the pause icon. */
void kaedraw_frame(const KaeFrame *frame, void *user);

#endif
