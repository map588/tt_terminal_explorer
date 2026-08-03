/*
 * Minimal extension: one command that blinks the board LED.
 *
 * ext_commands is the only hook this file overrides. The kit core
 * supplies everything else: the command loop, the clock, the pin
 * bench, and the safe profiles.
 */
#include <stdio.h>

#include "pico/stdlib.h"

#include "ext.h"
#include "tt_pins.h"

static const char *cmd_blink(int argc, char **argv) {
    uint32_t n;
    if (argc != 2 || !parse_u32(argv[1], &n) || n == 0 || n > 100)
        return "bad-arg";
    for (uint32_t i = 0; i < n; i++) {
        gpio_put(TT_PIN_LED, 1);
        sleep_ms(100);
        gpio_put(TT_PIN_LED, 0);
        sleep_ms(100);
    }
    snprintf(tt_reply, TT_REPLY_CAP, "%lu", (unsigned long)n);
    return NULL;
}

static const struct cmd my_cmds[] = {
    {"blink", cmd_blink, "blink <n>          blink the board LED n times"},
};

const struct cmd *ext_commands(size_t *count) {
    *count = count_of(my_cmds);
    return my_cmds;
}
