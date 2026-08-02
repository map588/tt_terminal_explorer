#include "pico/stdlib.h"

#include "board.h"
#include "tt_pins.h"

void board_pins_init(void) {
    static const uint pins[] = {TT_PIN_CTRL_ENA, TT_PIN_CTRL_NRST,
                                TT_PIN_CTRL_INC, TT_PIN_PROJ_NRST,
                                TT_PIN_LED};
    for (uint i = 0; i < count_of(pins); i++) {
        gpio_init(pins[i]);
        gpio_put(pins[i], 0);
        gpio_set_dir(pins[i], GPIO_OUT);
    }
    pins_safe();
}

void pins_safe(void) {
    for (uint i = 0; i < 8; i++) {
        uint p = TT_GPIO_UIO_BASE + i;
        gpio_init(p); /* SIO function, input */
        gpio_disable_pulls(p);
    }
    for (uint i = 0; i < 8; i++) {
        uint p = TT_GPIO_UI_BASE + i;
        gpio_init(p);
        gpio_put(p, 0);
        gpio_set_dir(p, GPIO_OUT);
    }
    for (uint i = 0; i < 8; i++)
        gpio_init(TT_GPIO_UO_BASE + i);
}

/* Mux sequence per tt-micropython-firmware project_mux.py. */
void tt_select_design(unsigned n) {
    gpio_put(TT_PIN_CTRL_INC, 0);
    gpio_put(TT_PIN_CTRL_NRST, 0);
    gpio_put(TT_PIN_CTRL_ENA, 0);
    sleep_ms(10);
    gpio_put(TT_PIN_CTRL_NRST, 1);
    sleep_ms(10);
    for (uint i = 0; i < n; i++) {
        gpio_put(TT_PIN_CTRL_INC, 1);
        sleep_ms(1);
        gpio_put(TT_PIN_CTRL_INC, 0);
        sleep_ms(1);
    }
    gpio_put(TT_PIN_CTRL_ENA, 1);
    sleep_ms(1);
}
