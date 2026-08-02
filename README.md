# tt_sky25b_explorer

A [Tiny Tapeout](https://tinytapeout.com) shuttle chip carries
hundreds of small hardware designs on one die. Only one design is
active at a time: an on-chip multiplexer selects it, and the demo
board's RP2350 microcontroller controls that multiplexer, the
design's clock, and all of its pins.

This project turns the demo board into an interactive lab bench for
the ttsky25b shuttle. You browse the designs in a terminal UI, load
one onto the chip, clock it at any speed or step it one pulse at a
time, drive its inputs, and watch its outputs live.

The project has two parts:

- **firmware/** builds `tt_host.uf2` for the board's RP2350. It
  serves a small, human-readable command protocol over USB serial:
  select a design through the project mux, control the clock, and
  read or drive the pins. A bare terminal (`tio`, `screen`) can
  speak it directly.
- **explorer/** is the terminal UI (Python,
  [Textual](https://textual.textualize.io)). It speaks the protocol
  and adds the shuttle index: titles, descriptions, and pin names
  for every design.

![The bench with a design loaded](docs/bench.svg)

## Capabilities

- Browse and filter all shuttle projects, or load a mux address
  directly.
- Select a design: the board switches the mux, resets the project, and
  sets the design's intended clock.
- See every pin live, one labeled row per pin, with the design's own
  pin names. A mirror of the board's 7-segment display shows what the
  hardware shows.
- Drive the inputs from the TUI, or release the bus so the DIP
  switches / PMOD drive them.
- Set the uio direction per pin. Rows show a direction hint parsed
  from the design's pin names, and pins that look like design outputs
  get a warning tag before you drive them.
- Set any clock from 1 Hz to 75 MHz (PIO-generated, one-cycle
  resolution, never above your requested frequency), or stop the clock and step it
  one pulse at a time.

## What you need

Hardware: a Tiny Tapeout ttsky25b demo board and a USB cable.

Software, for the terminal UI:

- [uv](https://docs.astral.sh/uv/). It downloads Python and the
  dependencies for you, so no other Python setup is necessary.

  On macOS / Linux:
  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

  On Windows:
  ```powershell
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

The firmware comes prebuilt: `tt_host.uf2` on the
[Releases](../../releases) page. You only need a firmware toolchain
to modify it (see "Build the firmware from source" below).

Optional: [picotool](https://github.com/raspberrypi/picotool) to
flash without touching the BOOTSEL button.

## Quickstart

1. Flash the firmware. Download `tt_host.uf2` from the
   [Releases](../../releases) page. Hold BOOTSEL, plug the board
   in, and copy the file to the `RP2350` drive that appears. Or:

   ```sh
   picotool load -x tt_host.uf2
   ```

2. Run the UI:

   ```sh
   cd explorer
   uv run tt-explorer
   ```

   The serial port is autodetected. Use `--port /dev/tty...` to
   override. Pick a design from the list and press enter.

## Build the firmware from source

Only needed to modify the firmware. You need:

- The [pico-sdk](https://github.com/raspberrypi/pico-sdk), 2.0 or
  newer:

  ```sh
  git clone --branch master https://github.com/raspberrypi/pico-sdk.git ~/pico-sdk
  git -C ~/pico-sdk submodule update --init lib/tinyusb
  export PICO_SDK_PATH=~/pico-sdk
  ```

  tinyusb is the one SDK submodule USB serial needs. Do not clone
  with `--recurse-submodules`: that pulls every nested submodule,
  most of a gigabyte you do not need.
- The [Arm GNU toolchain](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)
  (`arm-none-eabi-gcc`). Use Arm's official release or the one the
  [Pico VS Code extension](https://marketplace.visualstudio.com/items?itemName=raspberry-pi.raspberry-pi-pico)
  installs (`~/.pico-sdk/toolchain/...`). The Homebrew
  `arm-none-eabi-gcc` package does not work: it lacks newlib and
  fails with `cannot read spec file 'nosys.specs'`.
- `cmake` (3.13 or newer) and `ninja`. On macOS:
  `brew install cmake ninja`.

Then:

```sh
cd firmware
cmake -S . -B build -G Ninja
cmake --build build
```

If cmake does not find your cross compiler, point at it:
`cmake -S . -B build -G Ninja -DPICO_TOOLCHAIN_PATH=<toolchain dir>`.
The image is `build/tt_host.uf2`.

## Adapt it to your design

This repo is a starter kit. The firmware command table and the UI
panels are both single obvious places to add things: extra
commands, a custom tab, a design-specific debugger.
[docs/extending.md](docs/extending.md) has code skeletons for each,
and a link to a complete worked example.

![The project browser](docs/projects.svg)

## Keys

- `s` : stop / resume the project clock
- `space` : one clock pulse (when stopped)
- `i` : refresh the shuttle index (cached in `~/.cache/tt-explorer/`)
- `q` : quit

## How pin control works

The UI, UO, and UIO busses are shared on the same nets.

- `uo_out` is always driven by the design. Everything else listens.
- `ui_in` is driven by the firmware, or released so the DIP switches
  or a PMOD can drive it.
- `uio` direction is controlled per pin by the design itself
  (`uio_oe`). The TUI sets only the MCU side. Drive only the pins the
  design's pinout declares as its inputs. The firmware releases all
  uio pins each time you switch designs, so the default is always
  safe.

## Protocol

See `firmware/README.md` for the command table. The protocol is
simple and can be written by hand. The `hello` reply names the shuttle so
the TUI loads the matching index.  It is not specific to the ttsky25b
shuttle, but I've not tested it on anything else.

## License

Apache-2.0. Built around the [Tiny Tapeout](https://tinytapeout.com)
demo board and shuttle index.
