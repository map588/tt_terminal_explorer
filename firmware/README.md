# RP2350 host firmware (tt_host)

Runs on the Tiny Tapeout demo board v3 (RP2350B) and serves a
line-based command protocol over USB serial for exploring shuttle
designs.

## Command protocol

One command per line. Each command gets exactly one reply line,
`ok [payload]` or `err <token>`. Informational lines start with `# `.
Type `help` on the port for the list. The `../explorer` TUI speaks
this protocol, and a bare terminal (`tio`, `screen`) works too.

| Command | Effect |
|---|---|
| `hello` | `ok tt-explorer 2 shuttle=ttsky25b`: protocol version and shuttle name (the TUI loads the matching index) |
| `status` | design, clock mode/freq, pin state (`uidrv=0` when ui is released) |
| `freq <hz>` | free-running clock, 1 Hz – clk_sys/2 (75 MHz), made by PIO with one-sys-cycle resolution. The true output frequency never exceeds the request; the reply reports it. |
| `stop` / `step [n]` / `resume` | park the clock low, pulse it n times, restart the clock |
| `design <n>` | safe pin profile, mux-select design n, reset pulse |
| `reset [1\|0]` | pulse (no arg), assert, or release the project reset |
| `ui <hh>` / `ui off` / `ui` | drive ui_in, release it for the DIP switches / PMOD, or read the pad levels |
| `uo` / `uio` | read uo_out / uio pad levels (hex byte) |
| `uiod [hh]` / `uiow <hh>` | uio direction mask (1 = MCU drives) / output latch |

## Build

A prebuilt `tt_host.uf2` is on the repo's Releases page. To build
from source you need the pico-sdk (`PICO_SDK_PATH`), the Arm GNU
toolchain (`arm-none-eabi-gcc`), cmake, and ninja. The top-level
README has the full setup.

```sh
cmake -S . -B build -G Ninja
cmake --build build
```

Flash `build/tt_host.uf2` over BOOTSEL or with `picotool load -f -x`.
The firmware waits for the USB serial port to open.

For the v3 *Alpha* prototype board add `-DTT_DBV3_ALPHA` (different
GPIO map, see `include/tt_pins.h`).

## Pin safety

`design` always applies the safe profile first: all uio pins released
to inputs, ui pins driven 0. The uio direction mask (`uiod`) is the
MCU side only. The design controls its own side per pin (`uio_oe`),
so drive only the pins the design documents as its inputs.
