/*
 * GPIO map: Tiny Tapeout demo board v3 (RP2350B).
 *
 * Board-side numbers come from TinyTapeout/tt-micropython-firmware
 * (src/ttboard/pins/gpio_map_dbv3.py, class GPIOMapTTDBv3).
 * Define TT_DBV3_ALPHA when building for the v3 "Alpha" prototype
 * board, which uses a different set of GPIOs.
 */
#pragma once

#ifdef TT_DBV3_ALPHA
#define TT_GPIO_UI_BASE 12 /* ui_in[0..7]  = GPIO 12..19 */
#define TT_GPIO_UO_BASE 30 /* uo_out[0..7] = GPIO 30..37 */
#define TT_GPIO_UIO_BASE 22 /* uio[0..7]   = GPIO 22..29 */
#define TT_PIN_PROJ_CLK 21
#define TT_PIN_PROJ_NRST 20
#else
#define TT_GPIO_UI_BASE 17 /* ui_in[0..7]  = GPIO 17..24 */
#define TT_GPIO_UO_BASE 33 /* uo_out[0..7] = GPIO 33..40 */
#define TT_GPIO_UIO_BASE 25 /* uio[0..7]   = GPIO 25..32 */
#define TT_PIN_PROJ_CLK 16
#define TT_PIN_PROJ_NRST 14
/* MNG07: the FPGA breakout pulls this management pin high. The
 * Alpha board has no MNG pins. */
#define TT_PIN_MNG_FPGA_DETECT 10
#endif

/* Project mux control (same on both board revisions). */
#define TT_PIN_CTRL_ENA 0
#define TT_PIN_CTRL_NRST 1
#define TT_PIN_CTRL_INC 2

#define TT_PIN_LED 11
