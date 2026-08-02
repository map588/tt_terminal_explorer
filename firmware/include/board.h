#pragma once

/* Board-level pin control. */

/* What sits on top of the demo board, probed once at boot. */
typedef enum {
    CARRIER_NONE, /* nothing detected */
    CARRIER_ASIC, /* a Tiny Tapeout chip carrier */
    CARRIER_FPGA, /* the FPGA breakout */
} carrier_t;

extern carrier_t carrier;

/* "asic", "fpga", or "none". */
const char *carrier_str(void);

/* Probe the carrier. Call before the ctrl pins become outputs:
 * the probe reads them as inputs. */
void board_detect_carrier(void);

/* One-time init of mux control, project reset, and LED pins; ends in
 * the safe profile. Runs board_detect_carrier() first. */
void board_pins_init(void);

/* Release everything a design could drive: uio pads become inputs,
 * ui pads (always design inputs) are driven 0. */
void pins_safe(void);

/* Walk the project mux to design n and enable it. */
void tt_select_design(unsigned n);
