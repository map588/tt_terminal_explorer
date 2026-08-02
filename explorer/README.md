# tt-explorer

Textual TUI to explore Tiny Tapeout shuttle designs through the
`../firmware` command protocol: browse the shuttle index, select a
design (or load a mux address directly), control or single-step the
project clock, and peek/poke the ui/uo/uio pins.

## Run

```sh
uv sync
uv run tt-explorer            # autodetects /dev/tty.usbmodem*
uv run tt-explorer --port /dev/tty.usbmodemXXXX
```

## Layout

Two tabs. "Projects" is the shuttle browser: filter, read the
description, press enter to load a design. You can also type a mux
address and press Load. "Bench" is the instrument panel for the loaded
design: the clock (running or single-step, plus a design reset
button), one labeled row per pin on all three buses with the
design's own pin names and direction hints, a mirror of the board's
7-segment display, and the serial console.

## Keys

- `s` stops or resumes the project clock.
- `space` sends one clock pulse while the clock is stopped.
- `i` refreshes the shuttle index (cached in `~/.cache/tt-explorer/`).
- `q` quits.

## Test

```sh
uv run pytest
```
