# Extending the kit for your own design

The firmware and the UI are small on purpose. Each has one obvious
place to add design-specific features. This page walks both, with
skeletons you can copy. For a complete worked example, see
[tt_um_brainf-ck_asic](https://github.com/map588/tt_um_brainfck_asic/tree/main/firmware):
the project this kit was extracted from. Its firmware adds a program
loader, an instruction-level debugger with breakpoints, and a
second CPU core that emulates an SPI RAM, and its UI adds a third
tab with an editor and step controls.

## Add a firmware command

Commands live in one table in `firmware/src/commands.c`. A handler
gets `argc/argv`, writes its reply payload into `reply[]`, and
returns `NULL` for success or a short error token.

```c
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
    sprintf(reply, "%lu", (unsigned long)n);
    return NULL;
}
```

Then add one row to the `cmds[]` table:

```c
{"blink", cmd_blink, "blink <n>          blink the board LED n times"},
```

That is the whole change. `help`, the reply framing, and the UI
console all pick it up automatically.

Useful helpers that already exist:

- `parse_u32` / `parse_hex8` for arguments.
- `read_byte(TT_GPIO_UO_BASE)` style bus reads (`commands.c`).
- `pins_safe()` and `tt_select_design(n)` in `board.c`.
- `asic_clk_set_hz` / `asic_clk_stop` / `asic_clk_step` in `clock.c`.
- `apply_safe_profile()` when your command changes pin state, so the
  firmware's pin mirror stays correct.

## Interactive sessions (raw streams)

A command that runs longer than one reply, for example a program
loader or a debugger, can switch the connection to a raw byte
stream:

1. Check preconditions and return an error token if they fail.
2. Print `ok <name>\n` yourself, then read and write bytes freely.
3. End with a final `ok done` or `err <token>` line.

The UI's serial layer supports this: call
`link.set_raw_sink(callback)` before the session, feed keys or
pastes with `link.write_raw(...)`, and watch for the final line to
restore normal polling. The debugger tab in the worked example
(linked above) shows the full pattern, including pacing execution
from the host one step at a time.

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

Two Textual habits that will save you time:

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
