#include "pico/stdlib.h"

#include "board.h"
#include "ext.h"
#include "tt_pins.h"

__attribute__((weak)) void ext_pins_safe(void) {}

carrier_t carrier = CARRIER_NONE;

const char *carrier_str(void) {
    switch (carrier) {
    case CARRIER_ASIC:
        return "asic";
    case CARRIER_FPGA:
        return "fpga";
    default:
        return "none";
    }
}

/* Probe sequence per tt-micropython-firmware
 * (ttboard/boot/demoboard_detect.py, probe_rp2350):
 * the FPGA breakout pulls MNG07 high, a chip carrier pulls the mux
 * ctrl lines low. Read both as plain inputs before anything drives
 * them. */
void board_detect_carrier(void) {
    static const uint probe[] = {TT_PIN_CTRL_ENA, TT_PIN_CTRL_NRST};
    for (uint i = 0; i < count_of(probe); i++) {
        gpio_init(probe[i]); /* SIO function, input */
        gpio_disable_pulls(probe[i]);
    }
#ifdef TT_PIN_MNG_FPGA_DETECT
    gpio_init(TT_PIN_MNG_FPGA_DETECT);
    gpio_disable_pulls(TT_PIN_MNG_FPGA_DETECT);
    sleep_ms(2);
    if (gpio_get(TT_PIN_MNG_FPGA_DETECT)) {
        carrier = CARRIER_FPGA;
        return;
    }
#else
    sleep_ms(2);
#endif
    if (!gpio_get(TT_PIN_CTRL_ENA) && !gpio_get(TT_PIN_CTRL_NRST))
        carrier = CARRIER_ASIC;
    else
        carrier = CARRIER_NONE;
}

void board_pins_init(void) {
    static const uint pins[] = {TT_PIN_CTRL_ENA, TT_PIN_CTRL_NRST,
                                TT_PIN_CTRL_INC, TT_PIN_PROJ_NRST,
                                TT_PIN_LED};
    board_detect_carrier();
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
    ext_pins_safe();
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
