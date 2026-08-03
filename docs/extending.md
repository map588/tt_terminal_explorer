# Extending the kit for your own design

The firmware is built to be extended without edits to its core
files. You write one C file with your commands, and a short
CMakeLists builds it together with the core.

## What the firmware does on its own

Read this first. Each hook below is a moment in this sequence.

At boot the firmware puts the design pins in a neutral state: it
drives the design's 8 inputs low, releases the 8 bidirectional
pins, and listens on the 8 outputs. Nothing fights the design.
Then it waits for USB serial, starts the project clock at 1 MHz,
and enters a command loop.

The loop is the whole firmware. It reads one line, runs it, and
prints one `ok ...` or `err ...` reply:

- `design 5` returns the pins to the neutral state, walks the mux
  to design 5, and pulses reset.
- `freq 200000`, `stop`, `step`, `resume` control the project
  clock.
- `ui 0f`, `uo`, `uio`, `uiod`, `uiow` drive and read the pins.
- `hello` and `status` are one-line reports the UI reads.

That is complete. You can select, clock, and probe any shuttle
design with zero extension code. An extension adds commands for
one specific design: a loader, a self-test, a command that drives
the pins in your design's own terms.

## Start from the example

`firmware/example` is a complete extension: one `blink` command,
a six-line CMakeLists, and a README. Build it, flash it, type
`blink 3` on the port. Then copy the directory into your own repo,
add this repo as a git submodule, and point the two includes in its
CMakeLists at the submodule. That is the whole setup.

## Add a command

A handler gets `argc/argv`, writes its reply payload into
`tt_reply[]`, and returns `NULL` for success or a short error
token:

```c
#include "ext.h"
#include "tt_pins.h"
#include "pico/stdlib.h"
#include <stdio.h>

static const char *cmd_blink(int argc, char **argv) {
    uint32_t n;
    if (argc != 2 || !parse_u32(argv[1], &n))
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
```

`help`, the reply framing, and the UI console pick the command up.

Helpers that already exist: `parse_u32` / `parse_hex8` for
arguments, `read_byte(TT_GPIO_UO_BASE)` style bus reads (all in
`commands.h`), `pins_safe()` and `tt_select_design(n)` in
`board.h`, `asic_clk_set_hz` / `asic_clk_stop` / `asic_clk_step`
in `clock.h`.

## The hooks: empty slots, not overrides

`firmware/include/ext.h` declares seven hooks. Every one has an
empty default. Define none of them and nothing is missing. Each
hook is a fixed moment in the sequence above where your code can
run. Define only the ones your project needs. Most projects need
one.

**`ext_commands`** runs when a command line arrives, and on
`help`. Need it if you add commands. Return your command table.
The skeleton above is the complete pattern.

**`ext_init`** runs once at boot, before the command loop. Need it
if your commands depend on hardware that must be set up once, for
example a PWM slice, an I2C peripheral, or a DMA channel. USB
serial is not connected yet, so printed output is lost. Most
projects skip it.

**`ext_clock_changed`** runs after `freq` or `resume`, with the
achieved frequency. Need it if your host code holds delays
measured in ASIC clock cycles: recompute them here. If it does
not, skip it.

**`ext_design_changed`** runs after the `design` command selects
and resets a design. Need it if one specific design wants its own
pin setup: check the address, apply your profile. The neutral
state is already applied, so for every other design you do
nothing.

**`ext_release_pins`** runs at the end of the core's
reset-to-neutral (boot, and before every design switch). The core
can only neutralize pins it knows about. Need it if your extension
leaves anything driving a design pin between commands, for example
a PWM aimed at a design input. Stop it here, so it cannot fight
the next design. If you drive nothing outside your own commands,
skip it.

**`ext_hello`** and **`ext_status`** run while those two commands
build their one-line replies. Need them if a UI must detect your
firmware variant (`hello`) or show extension state (`status`).
Write `key=value` fields. The core adds the separating space.

How the override works:

- Include `ext.h` in the file that defines your hooks. A wrong
  signature is then a compile error.
- A wrong name is not: a misspelled hook compiles clean and never
  runs. After a build, check the `help` and `hello` output on the
  port before you debug anything deeper.

## Your own repo on the kit core

Add this repo as a submodule (for example at `kit`) and write a
CMakeLists like this:

```cmake
cmake_minimum_required(VERSION 3.13)
include(kit/firmware/kit.cmake)   # board, pico-sdk, tt_extension()
project(my_project C CXX ASM)
pico_sdk_init()

tt_extension(tt_host src/my_ext.c)
```

`tt_extension` builds the kit's main plus your sources and links
`tt_core`. Your extension can use any pico-sdk library: name it in
a normal `target_link_libraries(tt_host <library>)` line after the
call. `pico_multicore`, `hardware_pwm`, `hardware_dma`, and the
rest all work this way.

To replace the main instead, call `tt_core_library()`, then use
`add_executable` with your own main file and link `tt_core`.
`TT_CORE_MAIN` holds the path of the kit's main when you want to
reference it.

## Interactive sessions (raw streams)

A command that runs longer than one reply, for example a program
loader or a debugger, can switch the connection to a raw byte
stream:

1. Check preconditions and return an error token if they fail.
2. Print `ok <name>\n` yourself, then read and write bytes freely.
3. End with a final `ok done` or `err <token>` line.

Do not read with a plain blocking `getchar()` inside a session. It
blocks forever after the port closes mid-session, and the stuck
session then eats the next connection's commands as session input.
Poll with `getchar_timeout_us()` and abort the session when
`stdio_usb_connected()` goes false.

The UI's serial layer supports raw sessions: call
`await link.begin_raw(callback)` before the session, feed keys or
pastes with `link.write_raw(...)`, and watch for the final line to
restore normal polling. Raw sessions need the C firmware. The stock
MicroPython backend refuses them.

## Add a UI panel or tab

The UI is [Textual](https://textual.textualize.io). The pieces:

- `explorer/src/tt_explorer/widgets.py` holds the panels. Copy the
  shape of `ClockPanel`: a `Vertical` with a `compose()` and a few
  update methods.
- `explorer/src/tt_explorer/app.py` composes the tabs. Add a
  `TabPane` in `compose()`, then handle your buttons in
  `on_button_pressed` and send protocol commands with
  `await self.send("yourcommand 12")`.
- `protocol.py` parses replies. It is pure functions with unit
  tests in `explorer/tests/`, so start there if you extend the
  protocol.

Two Textual habits save time:

- Any widget inside a 1-row container needs `border: none;
  height: 1;` in CSS, or it clips to an unlabeled rectangle.
- Verify layouts with a real render:
  `app.save_screenshot("x.svg")` from a `run_test()` pilot, then
  look at the file.

## Keep the pin names honest

The Bench reads pin names from the shuttle index pinout of the
loaded design. If your design's `info.yaml` names pins with `_IN`
and `_OUT` conventions, the uio rows tag them automatically and warn
before you drive a design output.

## A full-scale example

[tt_um_brainf-ck_asic](https://github.com/map588/tt_um_brainfck_asic)
is a complete project built this way. It uses every hook: its own
commands, a second-core RAM emulator started at boot, timing that
follows the clock, a design-specific pin profile, and extra reply
fields. Its UI adds a third tab with an editor and a debugger, and
its loader and debugger are raw sessions.
