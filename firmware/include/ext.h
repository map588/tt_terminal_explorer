#pragma once

#include <stddef.h>
#include <stdint.h>

#include "commands.h"

/*
 * Extension hooks.
 *
 * The core defines an empty weak default for each hook, next to its
 * call site. A project overrides only the hooks it needs: define
 * the function with the same signature in one of the project's own
 * sources and the linker picks it over the weak default.
 *
 * See docs/extending.md for the pattern and a worked example.
 */

/* Extra rows for the command table. Return the array and put its
 * length in *count. The dispatcher and `help` walk it after the
 * core table. */
const struct cmd *ext_commands(size_t *count);

/* Runs once at boot, after the pins and the carrier probe, before
 * the command loop. Start second-core work here. USB serial is not
 * connected yet, so printed output is lost. */
void ext_init(void);

/* Write extra "key=value" fields for the hello / status reply into
 * out (snprintf, cap bytes). The core puts the separating space in
 * front, so do not start with one. Separate multiple fields with
 * single spaces. */
void ext_hello(char *out, size_t cap);
void ext_status(char *out, size_t cap);

/* The project clock changed (the freq or resume command). Recompute
 * timings that follow the clock here. */
void ext_clock_changed(uint32_t hz);

/* A design was selected and reset. The safe pin profile is already
 * applied; reapply a design-specific profile here. */
void ext_design_changed(unsigned addr);

/* The safe pin profile was applied (boot and every design change).
 * Release or park extension-owned hardware here, for example a
 * second-core peripheral that drives shared pins. */
void ext_pins_safe(void);
