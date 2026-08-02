/*
 * RP2350 host firmware for the Tiny Tapeout demo board v3.
 *
 * Serves a line-based command protocol over USB CDC (commands.c):
 * select a shuttle design, control or single-step the project clock
 * (clock.c), and peek/poke the ui/uo/uio pins (board.c).
 */
#include <stdio.h>

#include "pico/stdio_usb.h"
#include "pico/stdlib.h"

#include "board.h"
#include "clock.h"
#include "commands.h"

#define BOOT_CLK_HZ 1000000u
#define WAIT_FOR_USB 1

int main(void) {
    stdio_init_all();
    board_pins_init();

#if WAIT_FOR_USB
    while (!stdio_usb_connected())
        sleep_ms(100);
#endif

    asic_clk_set_hz(BOOT_CLK_HZ, NULL);

    printf("# tt-explorer host, type 'help'\n");
    command_loop();
}
