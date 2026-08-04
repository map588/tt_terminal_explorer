/*
 * Signal capture on pio2, hand-encoded like the clock generator (no
 * pioasm step). GPIO base 16 makes pins 16..47 reachable; the state
 * machine and a DMA channel are claimed only for the capture, so an
 * extension keeps full use of pio1 and the other pio2 machines.
 *
 * Program (3 instructions):
 *
 *   0: wait 0 gpio PROJ_CLK
 *   1: wait 1 gpio PROJ_CLK      ; one rising edge of the project clock
 *   2: in pins, 24               ; ui, uio, uo in one window
 *
 * Autopush at 24 bits pushes one word per clock edge; DMA moves the
 * words into trace_buf. Each pass costs a few machine cycles plus
 * the input synchronizers, so the loop follows project clocks up to
 * roughly clk_sys / 8 (trace_max_hz).
 */
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/pio.h"
#include "pico/stdlib.h"

#include "clock.h"
#include "trace.h"
#include "tt_pins.h"

#define TRACE_PIO pio2
#define TRACE_SM 0u
#define TRACE_OFF 0u

uint32_t trace_buf[TRACE_MAX];

uint32_t trace_max_hz(void) {
    return clock_get_hz(clk_sys) / 8u;
}

uint32_t trace_capture(uint32_t n) {
    pio_set_gpio_base(TRACE_PIO, 16);
    pio_sm_claim(TRACE_PIO, TRACE_SM);

    TRACE_PIO->instr_mem[TRACE_OFF + 0] =
        pio_encode_wait_gpio(false, TT_PIN_PROJ_CLK - 16);
    TRACE_PIO->instr_mem[TRACE_OFF + 1] =
        pio_encode_wait_gpio(true, TT_PIN_PROJ_CLK - 16);
    TRACE_PIO->instr_mem[TRACE_OFF + 2] = pio_encode_in(pio_pins, 24);

    pio_sm_config c = pio_get_default_sm_config();
    sm_config_set_in_pins(&c, TT_GPIO_UI_BASE); /* 24 pins from ui[0] */
    sm_config_set_in_shift(&c, false, true, 24); /* sample in low bits */
    sm_config_set_wrap(&c, TRACE_OFF, TRACE_OFF + 2);
    pio_sm_init(TRACE_PIO, TRACE_SM, TRACE_OFF, &c);

    int chan = dma_claim_unused_channel(true);
    dma_channel_config dc = dma_channel_get_default_config(chan);
    channel_config_set_read_increment(&dc, false);
    channel_config_set_write_increment(&dc, true);
    channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
    channel_config_set_dreq(&dc, pio_get_dreq(TRACE_PIO, TRACE_SM, false));
    dma_channel_configure(chan, &dc, trace_buf, &TRACE_PIO->rxf[TRACE_SM],
                          n, true);
    pio_sm_set_enabled(TRACE_PIO, TRACE_SM, true);

    /* n clock periods, half again for margin, and a 30 s cap so a
     * slow clock cannot hold the command loop for minutes. A capped
     * capture returns the samples that landed. */
    uint64_t wait_us = (uint64_t)n * 1500000u / clk_hz + 100000u;
    if (wait_us > 30000000u)
        wait_us = 30000000u;
    absolute_time_t dl = make_timeout_time_us(wait_us);
    while (dma_channel_is_busy(chan)) {
        if (time_reached(dl))
            break;
    }
    pio_sm_set_enabled(TRACE_PIO, TRACE_SM, false);
    uint32_t got = n - dma_channel_hw_addr(chan)->transfer_count;
    dma_channel_abort(chan);
    dma_channel_unclaim(chan);
    pio_sm_unclaim(TRACE_PIO, TRACE_SM);
    return got;
}
