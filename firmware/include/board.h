#pragma once

/* Board-level pin control. */

/* One-time init of mux control, project reset, and LED pins; ends in
 * the safe profile. */
void board_pins_init(void);

/* Release everything a design could drive: uio pads become inputs,
 * ui pads (always design inputs) are driven 0. */
void pins_safe(void);

/* Walk the project mux to design n and enable it. */
void tt_select_design(unsigned n);
