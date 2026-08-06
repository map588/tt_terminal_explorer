"""tt-explorer: Textual TUI for the tt-explorer firmware."""

from __future__ import annotations

import argparse
import asyncio
import os

from textual import work
from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    TabbedContent,
    TabPane,
)

from . import index, protocol
from .index import Project
from .serial_link import SerialLink, find_ports, is_micropython
from .upy_link import UpyLink
from .widgets import (
    ClockPanel,
    ConsolePane,
    CycleButton,
    DetailPane,
    ProjectList,
    TracePanel,
    UiPanel,
    UioPanel,
    UoPanel,
)



def parse_hz(text: str) -> int | None:
    """'440' -> 440, '32k' -> 32000, '1.5M' -> 1500000."""
    text = text.strip().replace(" ", "").removesuffix("Hz").removesuffix("hz")
    scale = 1
    if text and text[-1] in "kK":
        scale, text = 1_000, text[:-1]
    elif text and text[-1] in "mM":
        scale, text = 1_000_000, text[:-1]
    try:
        value = float(text)
    except ValueError:
        return None
    hz = int(round(value * scale))
    return hz if hz > 0 else None


class TTExplorerApp(App):
    TITLE = "tt-explorer"

    CSS = """
    /* projects tab */
    ProjectList { width: 45%; }
    #project-table { height: 1fr; }
    DetailPane { width: 55%; border: round $primary; padding: 0 1; }

    /* bench tab */
    ClockPanel { height: auto; border: round $secondary; padding: 0 1; }
    #clk-run, #clk-step { height: auto; }
    .clk-line { height: 1; margin-bottom: 1; }
    #clk-run-state { width: 12; color: $success; text-style: bold; }
    #clk-step-state { width: 32; color: $warning; text-style: bold; }
    #clk-run-freq { width: 16; text-style: bold; }
    #step-total { width: 20; color: $text-muted; }
    #clk-error { color: $error; height: 1; }
    ClockPanel Button { border: none; height: 1; margin-right: 2; }
    #clk-stop { background: $warning-darken-2; }
    #clk-resume { background: $success-darken-2; }
    .preset { background: $panel-lighten-1; }
    #freq-input {
        width: 16; height: 1; border: none;
        padding: 0 1; background: $boost;
    }
    #freq-input:focus { background: $primary-darken-2; }
    .byte-input {
        width: 18; height: 1; border: none;
        padding: 0 1; margin-left: 2; background: $boost;
    }
    .byte-input:focus { background: $primary-darken-2; }
    #freq-preview { width: 22; margin: 0 1; color: $success; }
    #freq-preview.preview-bad { color: $warning; }
    .hint { color: $text-muted; }

    #buses { height: auto; }
    UiPanel, UoPanel, UioPanel {
        width: 1fr; height: auto;
        border: round $primary; padding: 0 1; margin-right: 1;
    }
    .bus-head { height: 1; margin-bottom: 1; }
    .pin-row { height: 1; }
    .pin-bit { width: 2; color: $text-muted; }
    .pin-lvl { width: 2; }
    .pin-name { width: 1fr; color: $text; }
    .pin-btn { margin-right: 1; }
    CycleButton { border: none; height: 1; min-width: 5; }
    .cyc-low { background: $panel-lighten-2; }
    .cyc-high { background: $success-darken-1; }
    .cyc-listen { background: $panel; color: $text-muted; }
    .cyc-mcu { background: $primary-darken-1; }
    .cyc-ext { background: $warning-darken-2; }
    #sevenseg-row { height: 3; margin-top: 1; }
    #sevenseg { width: 6; text-style: bold; color: $error; }
    #uo-hex { color: $text-muted; }

    ConsolePane { height: 1fr; border: round $accent; }
    #console-log { height: 1fr; }

    /* projects tab extras */
    #addr-row { height: 1; margin-bottom: 1; }
    #addr-input { width: 10; height: 1; border: none;
                  padding: 0 1; background: $boost; }
    #addr-input:focus { background: $primary-darken-2; }
    #addr-load { border: none; height: 1; }

    #proj-reset { background: $panel-lighten-1; }
    .pin-designout { color: $warning; }

    /* signals tab */
    TracePanel { padding: 0 1; }
    #trace-controls { height: 1; margin-bottom: 1; }
    #trace-depth { width: 8; height: 1; border: none;
                   padding: 0 1; background: $boost; }
    #trace-depth:focus { background: $primary-darken-2; }
    #trace-run { border: none; height: 1; margin: 0 2; }
    #trace-status { color: $text-muted; }
    #trace-body { height: 1fr; margin-top: 1; }
    #trace-labels { width: 27; color: $text-muted; }
    #trace-scroll { width: 1fr; }
    #trace-waves { width: auto; color: $success; }
    """

    BINDINGS = [
        ("q", "quit", "quit"),
        ("i", "refresh_index", "refresh index"),
        ("s", "toggle_clock", "stop/resume"),
        ("space", "step_one", "step ×1"),
    ]

    def __init__(self, shuttle: str, port: str | None = None) -> None:
        super().__init__()
        self._port_arg = port
        self.link: SerialLink | None = None
        self._shuttle = shuttle
        self._design: int | None = None
        self._freq = 0
        self._ui_driving = True
        self._clk_running = True
        self._steps = 0
        self._carrier: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="tab-projects"):
            with TabPane("Projects", id="tab-projects"):
                with Horizontal():
                    yield ProjectList()
                    yield DetailPane()
            with TabPane("Bench", id="tab-bench"):
                with Vertical():
                    yield ClockPanel()
                    with Horizontal(id="buses"):
                        yield UiPanel()
                        yield UoPanel()
                        yield UioPanel()
                    yield ConsolePane()
            with TabPane("Signals", id="tab-signals"):
                yield TracePanel()
            yield from self.extension_tabs()
        yield Footer()

    # -- extension hooks --
    #
    # The UI twin of the firmware's ext.h slots: a project-specific
    # explorer subclasses TTExplorerApp and fills the hooks it needs.
    # Everything else, including future kit features, is inherited.
    #
    # Textual dispatches message handlers (on_mount, on_button_pressed,
    # on_input_submitted, ...) once for EVERY class in the MRO that
    # defines one. A subclass handler must therefore NOT call super():
    # the kit's handler runs on its own, and a super() call runs it a
    # second time.

    def extension_tabs(self):
        """Extra TabPane widgets after the built-in tabs."""
        return ()

    def on_hello(self, hello: dict) -> None:
        """The parsed hello reply, right after connecting."""

    def on_design_loaded(self, p: Project) -> None:
        """A design was selected and its panels are reset. Runs
        before the clock is set."""

    def design_clock_cap(self, p: Project) -> int | None:
        """Upper clock bound for this design, or None for the link
        maximum."""
        return None

    # -- startup --

    async def on_mount(self) -> None:
        await self._connect()
        self.load_projects(refresh=False)
        self.set_interval(0.25, self._poll)

    @work(thread=True)
    def load_projects(self, refresh: bool) -> None:
        try:
            projects = index.load_index(self._shuttle, refresh=refresh)
        except OSError as exc:
            self.call_from_thread(self._log, f"! index fetch failed: {exc}")
            return
        self.call_from_thread(
            self.query_one(ProjectList).set_projects, projects)
        self.call_from_thread(
            self._log, f"# index: {len(projects)} projects")

    async def _connect(self) -> None:
        # A second Mount dispatch (a subclass on_mount that calls
        # super()) must never open the port twice: two reader threads
        # on one device steal each other's replies and every command
        # times out.
        if self.link is not None:
            return
        ports = [self._port_arg] if self._port_arg else find_ports()
        if not ports:
            self._log("! no serial port found. Is the board plugged in?")
            return
        try:
            if is_micropython(ports[0]):
                self._log("# stock MicroPython firmware detected, "
                          "driving the ttboard SDK over the raw REPL")
                self.link = UpyLink(ports[0], on_line=self._log)
            else:
                self.link = SerialLink(ports[0], on_line=self._log)
        except OSError as exc:
            self._log(f"! cannot open {ports[0]}: {exc}")
            return
        self._log(f"# connected to {ports[0]}")
        self.query_one(ClockPanel).set_range(
            self.link.clk_min_hz, self.link.clk_max_hz,
            self.link.clock_note)
        if not getattr(self.link, "traces", False):
            self.query_one(TabbedContent).get_tab(
                "tab-signals").disabled = True
        self._carrier = None
        reply = await self.send("hello")
        if reply and reply.ok:
            hello = protocol.parse_hello(reply.payload)
            board = hello.get("shuttle")
            if board and board != self._shuttle:
                self._log(f"! the firmware was built for {board}, "
                          f"using {self._shuttle} from --shuttle")
            self.sub_title = (f"{self.link.port} · fw v{hello['version']}"
                              f" · {self._shuttle}")
            sdk = hello.get("sdk")
            if sdk and sdk != "unknown":
                self.sub_title = f"{self.sub_title} · SDK {sdk}"
            self.on_hello(hello)
        await self._refresh_status()
        if getattr(self.link, "pushes_uo", False):
            self.link.set_uo_sink(self._on_uo_push)
            await self.send("monitor 20")

    def _on_uo_push(self, value: int) -> None:
        self.query_one(UoPanel).show(value)

    # -- command plumbing --

    async def send(self, cmd: str,
                   timeout: float = 3.0) -> protocol.Reply | None:
        if self.link is None:
            self._log("! not connected")
            return None
        self._log(f"> {cmd}")
        try:
            reply = await self.link.request(cmd, timeout=timeout)
        except asyncio.TimeoutError:
            self._log(f"! timeout waiting for reply to {cmd!r}")
            return None
        except OSError as exc:
            self._log(f"! serial error: {exc}. Is the board still plugged in?")
            return None
        prefix = "ok" if reply.ok else "err"
        self._log(f"{prefix} {reply.payload}".rstrip())
        return reply

    async def _clock_send(self, cmd: str) -> protocol.Reply | None:
        """A clock command with its error shown inline on the panel."""
        reply = await self.send(cmd)
        clock = self.query_one(ClockPanel)
        if reply is None:
            clock.set_error(f"no reply to '{cmd}'")
        elif not reply.ok:
            clock.set_error(f"'{cmd}' failed: {reply.payload}")
        else:
            clock.set_error("")
        return reply

    def _log(self, line: str) -> None:
        if line.startswith("# t"):
            return  # trace sample lines: hundreds, shown as waveforms
        self.query_one(ConsolePane).log_line(line)

    async def _refresh_status(self) -> None:
        reply = await self.send("status")
        if not (reply and reply.ok):
            return
        st = protocol.parse_status(reply.payload)
        self._show_carrier(st.get("carrier"))
        self._clk_running = st["mode"] == "run"
        self._freq = st["freq"]
        if st["design"] >= 0:
            self._design = st["design"]
        self.query_one(ClockPanel).show_mode(st["mode"], st["freq"])
        if "uidrv" in st:
            self._ui_driving = bool(st["uidrv"])
            self.query_one(UiPanel).set_bus(self._ui_driving)

    def _show_carrier(self, carrier: str | None) -> None:
        """Subtitle tag from the firmware's boot probe. Old firmware
        sends no carrier field, then nothing is shown."""
        if carrier is None or carrier == self._carrier:
            return
        self._carrier = carrier
        self.sub_title = f"{self.sub_title} · carrier: {carrier.upper()}"
        if carrier == "none":
            self._log("! no carrier detected. Is a chip mounted?")

    async def _poll(self) -> None:
        link = self.link
        if link is None or link.busy or link.raw:
            return
        try:
            if not getattr(link, "pushes_uo", False):
                reply = await link.request("uo", timeout=1.0)
                if reply.ok:
                    self.query_one(UoPanel).show(
                        protocol.parse_hex_byte(reply.payload))
            reply = await link.request("uio", timeout=1.0)
            if reply.ok:
                self.query_one(UioPanel).show(
                    protocol.parse_hex_byte(reply.payload))
            if not self._ui_driving:
                reply = await link.request("ui", timeout=1.0)
                if reply.ok:
                    self.query_one(UiPanel).show_levels(
                        protocol.parse_hex_byte(reply.payload))
        except (asyncio.TimeoutError, ValueError, OSError):
            pass
        except NoMatches:
            pass  # the poll timer can fire while the app shuts down

    # -- actions --

    def action_refresh_index(self) -> None:
        self.load_projects(refresh=True)

    async def action_toggle_clock(self) -> None:
        if self._clk_running:
            await self._stop_clock()
        else:
            await self._clock_send("resume")
            await self._refresh_status()

    async def action_step_one(self) -> None:
        if not self._clk_running:
            await self._do_step(1)

    async def _stop_clock(self) -> None:
        reply = await self._clock_send("stop")
        if reply and reply.ok:
            self._steps = 0
            self.query_one(ClockPanel).set_steps(0)
        await self._refresh_status()

    async def _set_freq_from_input(self) -> None:
        text = self.query_one("#freq-input", Input).value
        hz = parse_hz(text)
        if hz is None:
            self.query_one(ClockPanel).set_error(
                f"cannot read {text!r}, try 440, 32k, or 1.5M")
            return
        await self._clock_send(f"freq {hz}")
        await self._refresh_status()

    async def _do_step(self, n: int) -> None:
        reply = await self._clock_send(f"step {n}")
        if reply and reply.ok:
            self._steps += n
            self.query_one(ClockPanel).set_steps(self._steps)

    async def _do_trace(self) -> None:
        panel = self.query_one(TracePanel)
        text = self.query_one("#trace-depth", Input).value.strip() or "256"
        if not text.isdigit() or not 16 <= int(text) <= 4096:
            panel.set_status("samples must be 16..4096")
            return
        n = int(text)
        # The capture takes n clock periods; give slow clocks time.
        timeout = 3.0 + (1.5 * n / self._freq if self._freq else 0.0)
        panel.set_status("capturing…")
        reply = await self.send(f"trace {n}", timeout=timeout)
        if reply is None:
            panel.set_status("no reply")
            return
        if not reply.ok:
            hints = {"mode": "the clock is stopped — resume it first",
                     "too-fast": "clock too fast for the capture loop"}
            panel.set_status(hints.get(reply.payload,
                                       f"trace failed: {reply.payload}"))
            return
        samples = protocol.parse_trace(reply)
        panel.show(samples)
        fields = dict(part.partition("=")[::2] for part in
                      reply.payload.split())
        freq = int(fields.get("freq", 0) or 0)
        panel.set_status(f"{len(samples)} samples at {freq:,} Hz")



    # -- UI events --

    def on_project_list_highlighted(
            self, event: ProjectList.Highlighted) -> None:
        """Browsing preview: details only, nothing sent to the board."""
        self.query_one(DetailPane).show(event.project)

    async def on_project_list_selected(self, event: ProjectList.Selected) -> None:
        await self._load_design(event.project)

    async def _load_by_address(self) -> None:
        text = self.query_one("#addr-input", Input).value.strip()
        if not text.isdigit() or not 0 <= int(text) <= 1023:
            self._log("! address must be 0-1023")
            return
        address = int(text)
        pl = self.query_one(ProjectList)
        project = pl._by_address.get(address) or Project(
            macro=f"design {address}", address=address,
            title=f"design {address}")
        await self._load_design(project)

    async def _load_design(self, p: Project) -> None:
        self.query_one(DetailPane).show(p)
        # The firmware walks the mux one address per millisecond plus
        # settle time, so high addresses take over two seconds. The
        # default timeout sat right on that edge and high designs
        # intermittently "did not load".
        reply = await self.send(f"design {p.address}", timeout=10.0)
        if not (reply and reply.ok):
            return
        self.query_one(UiPanel).set_names(p.pinout)
        self.query_one(UoPanel).set_names(p.pinout)
        self.query_one(UioPanel).set_names(p.pinout)
        self.query_one(TracePanel).set_names(p.pinout)
        self.query_one(UiPanel).reset()
        self.query_one(UioPanel).reset()
        self._ui_driving = True
        self.on_design_loaded(p)
        if p.clock_hz:
            hz = p.clock_hz
            if self.link:
                top = self.link.clk_max_hz
                cap = self.design_clock_cap(p)
                if cap is not None:
                    top = min(top, cap)
                hz = min(max(hz, self.link.clk_min_hz), top)
            await self._clock_send(f"freq {hz}")
        await self._refresh_status()
        tabs = self.query_one(TabbedContent)
        tabs.get_tab("tab-bench").label = f"Bench · {p.title or p.macro}"
        tabs.active = "tab-bench"
        self.set_focus(None)  # so keys like space and s work at once

    async def on_cycle_button_cycled(self, event: CycleButton.Cycled) -> None:
        bid = event.button.id or ""
        if bid == "ui-bus":
            ui = self.query_one(UiPanel)
            if event.state == "ext":
                reply = await self.send("ui off")
                if reply and reply.ok:
                    self._ui_driving = False
                    ui.set_bus(False)
                else:
                    ui.set_bus(True)
            else:
                reply = await self.send(f"ui {protocol.hex_byte(ui.byte())}")
                if reply and reply.ok:
                    self._ui_driving = True
                    ui.set_bus(True)
                else:
                    ui.set_bus(False)
        elif bid.startswith("uiov"):
            # The firmware latches the value and applies it only on
            # driven pins, so a value edit never forces a drive.
            panel = self.query_one(UioPanel)
            await self.send(f"uiow {protocol.hex_byte(panel.value())}")
        elif bid.startswith("uiod"):
            panel = self.query_one(UioPanel)
            # value latch first, so a newly-driven pin never glitches
            await self.send(f"uiow {protocol.hex_byte(panel.value())}")
            await self.send(f"uiod {protocol.hex_byte(panel.mask())}")
        elif bid.startswith("ui") and self._ui_driving:
            byte = self.query_one(UiPanel).byte()
            await self.send(f"ui {protocol.hex_byte(byte)}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "clk-stop":
            await self._stop_clock()
        elif bid == "clk-resume":
            await self._clock_send("resume")
            await self._refresh_status()
        elif bid == "freq-set":
            await self._set_freq_from_input()
        elif bid.startswith("preset-"):
            await self._clock_send(f"freq {bid.removeprefix('preset-')}")
            await self._refresh_status()
        elif bid.startswith("step-"):
            await self._do_step(int(bid.removeprefix("step-")))
        elif bid == "proj-reset":
            await self.send("reset")
        elif bid == "addr-load":
            await self._load_by_address()
        elif bid == "trace-run":
            await self._do_trace()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "freq-input":
            text = event.value
            self.query_one(ClockPanel).show_freq_preview(
                parse_hz(text), empty=not text.strip())

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if event.input.id == "addr-input":
            await self._load_by_address()
            return
        if event.input.id == "console-input":
            if value:
                await self.send(value)
                event.input.value = ""
        elif event.input.id == "freq-input":
            await self._set_freq_from_input()
        elif event.input.id == "ui-value":
            byte = protocol.parse_pin_byte(value)
            if byte is None:
                self._log(f"! cannot read {value!r}, try a5 or 0b10100101")
                return
            reply = await self.send(f"ui {protocol.hex_byte(byte)}")
            if reply and reply.ok:
                ui = self.query_one(UiPanel)
                ui.set_value(byte)
                self._ui_driving = True
                ui.set_bus(True)
                event.input.value = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiny Tapeout board explorer")
    parser.add_argument("--shuttle", default=os.environ.get("TT_SHUTTLE"),
                        help="shuttle run the chip is from, e.g. ttsky25a. "
                             "Sets which project index to download. "
                             "TT_SHUTTLE in the environment works too.")
    parser.add_argument("--port", help="serial device (default: autodetect)")
    args = parser.parse_args()
    if not args.shuttle:
        parser.error("--shuttle is required (or set TT_SHUTTLE)")
    TTExplorerApp(shuttle=args.shuttle, port=args.port).run()


if __name__ == "__main__":
    main()
