#pragma once

#include <stddef.h>
#include <stdint.h>

#include "commands.h"

/*
 * Extension hooks.
 *
 * Every hook has an empty weak default. The firmware is complete
 * without them: it can select, clock, and probe any design on its
 * own. Define only the hooks your project needs, in your own
 * source file, with the same signature; the linker picks your
 * definition over the empty one.
 *
 * docs/extending.md starts with what the firmware does on its own,
 * so each hook below reads as a moment in that story.
 */

/* When: a command line arrives, and on `help`.
 * Need it if: you add commands. This is the hook most projects
 * define, and often the only one. Return your command table and
 * put its length in *count. */
const struct cmd *ext_commands(size_t *count);

/* When: once at boot, before the command loop.
 * Need it if: your commands depend on hardware that must be set
 * up once (a PWM slice, an I2C peripheral, a DMA channel). USB
 * serial is not connected yet, so printed output is lost. */
void ext_init(void);

/* ---- bench events ---- */

/* When: after `freq` or `resume`, with the achieved frequency.
 * Need it if: your host code holds delays measured in ASIC clock
 * cycles; recompute them here. Otherwise skip. */
void ext_clock_changed(uint32_t hz);

/* When: after `design` selected and reset a design.
 * Need it if: one specific design needs its own pin profile or
 * state; check the address and apply it here. The neutral profile
 * is already applied. */
void ext_design_changed(unsigned addr);

/* When: at the end of pins_safe(), the core's reset-to-neutral for
 * the design pins. That runs at boot and before every design
 * switch.
 * Need it if: your extension leaves anything driving a design pin
 * between commands, for example a PWM aimed at a design input.
 * The core resets the pins it knows; you stop what you added. */
void ext_release_pins(void);

/* ---- reply fields ---- */

/* When: while `hello` / `status` build their one-line replies.
 * Need it if: a UI must detect your firmware variant (hello) or
 * show extension state (status). Write "key=value" fields into out
 * (snprintf, cap bytes). The core puts the separating space in
 * front, so do not start with one. */
void ext_hello(char *out, size_t cap);
void ext_status(char *out, size_t cap);
