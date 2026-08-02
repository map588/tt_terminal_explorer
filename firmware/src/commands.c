/*
 * Line-based command protocol over USB CDC.
 *
 * One command per line. Each command gets exactly one reply line:
 * "ok [payload]" or "err <token>". Informational output is prefixed
 * with "# ". Hex arguments are two hex digits, no "0x".
 *
 * Pin safety: `design` always applies the safe profile first (all
 * uio pins released to inputs, ui pins driven 0).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "pico/stdlib.h"

#include "board.h"
#include "clock.h"
#include "commands.h"
#include "ext.h"
#include "tt_pins.h"

#define PROTO_VERSION 2u
/* The shuttle this build is for. The hello reply reports it as a
 * hint; the UI's required --shuttle flag decides which index loads
 * and warns on a mismatch. */
#define SHUTTLE_NAME "ttsky25b"

static int current_design = -1; /* -1 = none selected since boot */
static bool ui_driven = true; /* false: ui pins released for DIP/PMOD */
static uint8_t ui_value;
static uint8_t uio_dir_mask; /* 1 = MCU drives the pad */
static uint8_t uio_out_value;

char tt_reply[TT_REPLY_CAP]; /* handlers put their "ok" payload here */

/* Weak defaults for the extension hooks this file calls. A project
 * overrides them by defining the same functions (see ext.h). */
__attribute__((weak)) const struct cmd *ext_commands(size_t *count) {
    *count = 0;
    return NULL;
}
__attribute__((weak)) void ext_hello(char *out, size_t cap) {
    (void)out;
    (void)cap;
}
__attribute__((weak)) void ext_status(char *out, size_t cap) {
    (void)out;
    (void)cap;
}
__attribute__((weak)) void ext_design_changed(unsigned addr) {
    (void)addr;
}

/* Append the hook's " key=value" fields to tt_reply[]. The core
 * writes the separating space and removes it again when the hook
 * wrote nothing, so hooks only write "key=value" text. */
static void ext_append(void (*hook)(char *, size_t)) {
    size_t used = strlen(tt_reply);
    if (used + 2 >= TT_REPLY_CAP)
        return;
    tt_reply[used] = ' ';
    tt_reply[used + 1] = 0;
    hook(tt_reply + used + 1, TT_REPLY_CAP - used - 1);
    if (tt_reply[used + 1] == 0)
        tt_reply[used] = 0;
}

/* pins_safe() in board.c does not know this file's mirror state;
 * reset it together whenever the safe profile is applied. */
static void apply_safe_profile(void) {
    pins_safe();
    ui_driven = true; /* pins_safe drives the ui pins low */
    ui_value = 0;
    uio_dir_mask = 0;
    uio_out_value = 0;
}

/* ---- argument parsing ---- */

bool parse_u32(const char *s, uint32_t *out) {
    char *end;
    unsigned long v = strtoul(s, &end, 10);
    if (end == s || *end)
        return false;
    *out = (uint32_t)v;
    return true;
}

bool parse_hex8(const char *s, uint8_t *out) {
    char *end;
    unsigned long v = strtoul(s, &end, 16);
    if (end == s || *end || v > 255)
        return false;
    *out = (uint8_t)v;
    return true;
}

uint8_t read_byte(unsigned base) {
    uint8_t v = 0;
    for (uint i = 0; i < 8; i++)
        v |= (uint8_t)(gpio_get(base + i) << i);
    return v;
}

/* ---- command handlers ---- */
/* A handler returns NULL for success (payload, if any, in tt_reply[]) or
 * an error token. */

static const char *cmd_hello(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sprintf(tt_reply, "tt-explorer %u shuttle=%s", PROTO_VERSION, SHUTTLE_NAME);
    ext_append(ext_hello);
    return NULL;
}

static const char *cmd_status(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sprintf(tt_reply,
            "design=%d mode=%s freq=%lu ui=%02x uidrv=%d uiod=%02x"
            " carrier=%s",
            current_design, clk_mode == CLK_RUN ? "run" : "step",
            (unsigned long)clk_hz, ui_value, ui_driven ? 1 : 0,
            uio_dir_mask, carrier_str());
    ext_append(ext_status);
    return NULL;
}

static const char *cmd_freq(int argc, char **argv) {
    uint32_t hz, actual;
    if (argc != 2 || !parse_u32(argv[1], &hz))
        return "bad-arg";
    if (!asic_clk_set_hz(hz, &actual))
        return "range";
    sprintf(tt_reply, "%lu", (unsigned long)actual);
    return NULL;
}

static const char *cmd_stop(int argc, char **argv) {
    (void)argc;
    (void)argv;
    asic_clk_stop();
    return NULL;
}

static const char *cmd_step(int argc, char **argv) {
    uint32_t n = 1;
    if (argc > 2 || (argc == 2 && !parse_u32(argv[1], &n)))
        return "bad-arg";
    if (n < 1 || n > CLK_STEP_MAX)
        return "range";
    if (!asic_clk_step(n))
        return "mode";
    sprintf(tt_reply, "%lu", (unsigned long)n);
    return NULL;
}

static const char *cmd_resume(int argc, char **argv) {
    (void)argc;
    (void)argv;
    asic_clk_resume();
    sprintf(tt_reply, "%lu", (unsigned long)clk_hz);
    return NULL;
}

/* Hold reset low and give the design clock edges while it is low.
 * Some designs need a clocked reset. With a running clock the 2 ms
 * hold covers that; in step mode we make the edges ourselves. */
static void reset_pulse(void) {
    gpio_put(TT_PIN_PROJ_NRST, 0);
    if (clk_mode == CLK_STEP)
        asic_clk_step(10);
    else
        sleep_ms(2);
    gpio_put(TT_PIN_PROJ_NRST, 1);
}

static const char *cmd_design(int argc, char **argv) {
    uint32_t n;
    if (argc != 2 || !parse_u32(argv[1], &n))
        return "bad-arg";
    if (n > 1023)
        return "range";
    apply_safe_profile();
    tt_select_design(n);
    reset_pulse();
    current_design = (int)n;
    ext_design_changed((unsigned)n);
    sprintf(tt_reply, "%lu", (unsigned long)n);
    return NULL;
}

static const char *cmd_reset(int argc, char **argv) {
    if (argc == 1) { /* pulse */
        reset_pulse();
        return NULL;
    }
    if (argc == 2 && !strcmp(argv[1], "1")) { /* assert: NRST low */
        gpio_put(TT_PIN_PROJ_NRST, 0);
        return NULL;
    }
    if (argc == 2 && !strcmp(argv[1], "0")) { /* release */
        gpio_put(TT_PIN_PROJ_NRST, 1);
        return NULL;
    }
    return "bad-arg";
}

/* The board wires the DIP switches and the PMOD to the same nets as
 * the MCU's ui pins. `ui off` releases the pins so those sources can
 * drive (the official firmware calls this ASIC_MANUAL_INPUTS). */
static const char *cmd_ui(int argc, char **argv) {
    if (argc == 1) { /* read the pad levels (useful when released) */
        sprintf(tt_reply, "%02x", read_byte(TT_GPIO_UI_BASE));
        return NULL;
    }
    if (argc == 2 && !strcmp(argv[1], "off")) {
        for (uint i = 0; i < 8; i++)
            gpio_set_dir(TT_GPIO_UI_BASE + i, GPIO_IN);
        ui_driven = false;
        return NULL;
    }
    uint8_t v;
    if (argc != 2 || !parse_hex8(argv[1], &v))
        return "bad-arg";
    for (uint i = 0; i < 8; i++) {
        uint p = TT_GPIO_UI_BASE + i;
        gpio_put(p, (v >> i) & 1);
        gpio_set_dir(p, GPIO_OUT);
    }
    ui_driven = true;
    ui_value = v;
    return NULL;
}

static const char *cmd_uo(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sprintf(tt_reply, "%02x", read_byte(TT_GPIO_UO_BASE));
    return NULL;
}

static const char *cmd_uio(int argc, char **argv) {
    (void)argc;
    (void)argv;
    sprintf(tt_reply, "%02x", read_byte(TT_GPIO_UIO_BASE));
    return NULL;
}

static const char *cmd_uiod(int argc, char **argv) {
    if (argc == 2) {
        uint8_t m;
        if (!parse_hex8(argv[1], &m))
            return "bad-arg";
        for (uint i = 0; i < 8; i++) {
            uint p = TT_GPIO_UIO_BASE + i;
            if ((m >> i) & 1) {
                gpio_put(p, (uio_out_value >> i) & 1);
                gpio_set_dir(p, GPIO_OUT);
            } else {
                gpio_set_dir(p, GPIO_IN);
            }
        }
        uio_dir_mask = m;
    } else if (argc != 1) {
        return "bad-arg";
    }
    sprintf(tt_reply, "%02x", uio_dir_mask);
    return NULL;
}

static const char *cmd_uiow(int argc, char **argv) {
    uint8_t v;
    if (argc != 2 || !parse_hex8(argv[1], &v))
        return "bad-arg";
    uio_out_value = v;
    for (uint i = 0; i < 8; i++) {
        if ((uio_dir_mask >> i) & 1)
            gpio_put(TT_GPIO_UIO_BASE + i, (v >> i) & 1);
    }
    return NULL;
}

static const char *cmd_help(int argc, char **argv);

static const struct cmd cmds[] = {
    {"hello", cmd_hello, "hello              -> ok tt-explorer <ver> shuttle=<name>"},
    {"status", cmd_status, "status             -> ok design= mode= freq= ui= uiod="},
    {"freq", cmd_freq, "freq <hz>          set clock, 10 Hz .. clk_sys/2"},
    {"stop", cmd_stop, "stop               park clock low, step mode"},
    {"step", cmd_step, "step [n]           n clock pulses (step mode only)"},
    {"resume", cmd_resume, "resume             back to run mode at last freq"},
    {"design", cmd_design, "design <n>         select mux design 0..1023 + reset"},
    {"reset", cmd_reset, "reset [1|0]        pulse, or assert(1)/release(0) NRST"},
    {"ui", cmd_ui, "ui <hh>|off|(none) drive ui_in, release for DIP/PMOD, read"},
    {"uo", cmd_uo, "uo                 read uo_out byte"},
    {"uio", cmd_uio, "uio                read uio pad levels"},
    {"uiod", cmd_uiod, "uiod [hh]          set/get uio dir mask, 1=MCU drives"},
    {"uiow", cmd_uiow, "uiow <hh>          write uio output latch"},
    {"help", cmd_help, "help               this list"},
};

static const char *cmd_help(int argc, char **argv) {
    (void)argc;
    (void)argv;
    for (uint i = 0; i < count_of(cmds); i++)
        printf("# %s\n", cmds[i].help);
    size_t n;
    const struct cmd *ext = ext_commands(&n);
    for (size_t i = 0; i < n; i++)
        printf("# %s\n", ext[i].help);
    return NULL;
}

/* The core table first, then the extension table. */
static const struct cmd *find_cmd(const char *name) {
    for (uint i = 0; i < count_of(cmds); i++) {
        if (!strcmp(name, cmds[i].name))
            return &cmds[i];
    }
    size_t n;
    const struct cmd *ext = ext_commands(&n);
    for (size_t i = 0; i < n; i++) {
        if (!strcmp(name, ext[i].name))
            return &ext[i];
    }
    return NULL;
}

/* ---- line reader / dispatch ---- */

/* Echo input so a human in a bare terminal sees what they type. '\r'
 * and '\n' both end a line, so CRLF costs one ignored empty line. */
static void read_line(char *buf, size_t cap) {
    size_t n = 0;
    for (;;) {
        int c = getchar();
        if (c == '\r' || c == '\n') {
            if (n == 0)
                continue;
            putchar('\n');
            buf[n] = 0;
            return;
        }
        if (c == 0x08 || c == 0x7f) { /* backspace / DEL */
            if (n) {
                n--;
                printf("\b \b");
            }
            continue;
        }
        if (c < 0x20 || c > 0x7e)
            continue;
        if (n + 1 < cap) {
            buf[n++] = (char)c;
            putchar(c);
        }
    }
}

void command_loop(void) {
    char line[128];
    for (;;) {
        read_line(line, sizeof line);

        char *argv[4];
        int argc = 0;
        for (char *t = strtok(line, " "); t && argc < 4;
             t = strtok(NULL, " "))
            argv[argc++] = t;
        if (argc == 0)
            continue;

        const struct cmd *c = find_cmd(argv[0]);
        if (!c) {
            printf("err unknown\n");
            continue;
        }
        tt_reply[0] = 0;
        const char *err = c->fn(argc, argv);
        if (err)
            printf("err %s\n", err);
        else if (tt_reply[0])
            printf("ok %s\n", tt_reply);
        else
            printf("ok\n");
        stdio_flush();
    }
}
