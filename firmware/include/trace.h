/*
 * Signal capture: one sample of all 24 project pins (ui, uio, uo)
 * per rising edge of the project clock. The clock must be running.
 */
#pragma once

#include <stdint.h>

#define TRACE_MIN 16u
#define TRACE_MAX 4096u

/* Sample bit layout: bit 0 = ui[0] .. bit 7 = ui[7],
 * bit 8 = uio[0] .. bit 15 = uio[7], bit 16 = uo[0] .. bit 23 = uo[7]. */
extern uint32_t trace_buf[TRACE_MAX];

/* The fastest project clock the capture loop can follow. */
uint32_t trace_max_hz(void);

/* Capture n samples into trace_buf. Returns the number captured:
 * less than n when the clock stops mid-capture. */
uint32_t trace_capture(uint32_t n);
