"""Drive the stock Tiny Tapeout MicroPython firmware over its raw
REPL.

The stock firmware ships pre-loaded on the demo board and exposes the
ttboard SDK (`tt`) on a Python REPL instead of the tt_host line
protocol. This link translates each tt_host command into one raw-REPL
exec and synthesizes the same "ok/err" replies, so the UI cannot tell
the two firmwares apart.

Marker convention inside the REPL: helper code prints exactly one
line starting with "R " (ok + payload) or "E " (err + token). Every
other stdout line is an SDK log line and is forwarded to the console.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from typing import Callable

import serial

from .protocol import Reply

ANSI = re.compile(r"\x1b\[[0-9;]*m")

RAW_REPL_PROMPT = b"raw REPL; CTRL-B to exit\r\n>"

# Runs once at connect: get the SDK handle the boot script made and
# define one helper per command that needs more than a single call.
BOOTSTRAP = """
try:
    tt
except NameError:
    from ttboard.demoboard import DemoBoard
    tt = DemoBoard.get()
from ttboard.mode import RPMode
import time as _t
def _R(s):
    print('R ' + s)
def _tt_hello():
    _R('tt-explorer 2 shuttle=%s upy=1' % tt.shuttle.run)
def _tt_status():
    d = tt.shuttle.enabled
    run = tt.is_auto_clocking
    _R('design=%d mode=%s freq=%d ui=%02x uidrv=%d uiod=%02x' % (
        d.count if d else -1, 'run' if run else 'step',
        int(tt.auto_clocking_freq) if run else 0,
        int(tt.ui_in.value),
        1 if tt.mode == RPMode.ASIC_RP_CONTROL else 0,
        int(tt.uio_oe_pico.value)))
def _tt_design(n):
    for d in tt.shuttle.all:
        if d.count == n:
            d.enable(force=True)
            tt.reset_project(True)
            _t.sleep_ms(2)
            tt.reset_project(False)
            _R(str(n))
            return
    print('E no-design')
def _tt_ui(v):
    if tt.mode != RPMode.ASIC_RP_CONTROL:
        tt.mode = RPMode.ASIC_RP_CONTROL
    tt.ui_in.value = v
    _R('')
def _tt_step(n):
    for _ in range(n):
        tt.clock_project_once()
    _R(str(n))
_R('ready')
"""


class UpyLink:
    """Same public surface as SerialLink, backed by the raw REPL."""

    def __init__(self, port: str, on_line: Callable[[str], None]):
        self._ser = serial.Serial(port, 115200, timeout=5)
        self._on_line = on_line
        self._loop = asyncio.get_running_loop()
        self._lock = asyncio.Lock()
        self._io = threading.Lock()
        self._closed = False
        self._last_freq = 0
        self._enter_raw_repl()
        out, err = self._exec(BOOTSTRAP)
        if err or "R ready" not in out:
            raise OSError(f"ttboard SDK bootstrap failed: {err or out!r}")

    # -- SerialLink surface --

    @property
    def port(self) -> str:
        return self._ser.port

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    @property
    def raw(self) -> bool:
        return False  # raw sessions are a tt_host feature

    def set_raw_sink(self, sink) -> None:
        raise OSError("raw sessions need the tt_host firmware")

    def write_raw(self, text: str) -> None:
        raise OSError("raw sessions need the tt_host firmware")

    def close(self) -> None:
        self._closed = True
        try:
            with self._io:
                self._ser.write(b"\x02")  # back to the friendly REPL
                self._ser.close()
        except OSError:
            pass

    async def request(self, line: str, timeout: float = 5.0) -> Reply:
        async with self._lock:
            code = self._translate(line.strip())
            if code is None:
                return Reply(False, "unknown")
            out, err = await asyncio.wait_for(
                self._loop.run_in_executor(None, self._exec, code), timeout)
            return self._to_reply(out, err)

    # -- command translation --

    def _translate(self, line: str) -> str | None:
        """One tt_host command line -> one REPL exec, or None."""
        parts = line.split()
        if not parts:
            return None
        cmd, args = parts[0], parts[1:]
        if cmd == "hello":
            return "_tt_hello()"
        if cmd == "status":
            return "_tt_status()"
        if cmd == "design" and len(args) == 1 and args[0].isdigit():
            return f"_tt_design({int(args[0])})"
        if cmd == "freq" and len(args) == 1 and args[0].isdigit():
            self._last_freq = int(args[0])
            return (f"tt.clock_project_PWM({int(args[0])})\n"
                    "_R(str(int(tt.auto_clocking_freq)))")
        if cmd == "stop":
            return "tt.clock_project_stop()\n_R('')"
        if cmd == "step":
            n = 1
            if args:
                if not args[0].isdigit():
                    return None
                n = int(args[0])
            return f"_tt_step({n})"
        if cmd == "resume":
            hz = self._last_freq or 1000
            return (f"tt.clock_project_PWM({hz})\n"
                    "_R(str(int(tt.auto_clocking_freq)))")
        if cmd == "reset":
            if not args:
                return ("tt.reset_project(True)\n_t.sleep_ms(2)\n"
                        "tt.reset_project(False)\n_R('')")
            if args == ["1"]:
                return "tt.reset_project(True)\n_R('')"
            if args == ["0"]:
                return "tt.reset_project(False)\n_R('')"
            return None
        if cmd == "ui":
            if not args:
                return "_R('%02x' % int(tt.ui_in.value))"
            if args == ["off"]:
                return "tt.mode = RPMode.ASIC_MANUAL_INPUTS\n_R('')"
            v = _hex8(args[0])
            return None if v is None else f"_tt_ui({v})"
        if cmd == "uo":
            return "_R('%02x' % int(tt.uo_out.value))"
        if cmd == "uio":
            return "_R('%02x' % int(tt.uio_out.value))"
        if cmd == "uiod":
            if not args:
                return "_R('%02x' % int(tt.uio_oe_pico.value))"
            m = _hex8(args[0])
            if m is None:
                return None
            return (f"tt.uio_oe_pico.value = {m}\n"
                    "_R('%02x' % int(tt.uio_oe_pico.value))")
        if cmd == "uiow" and len(args) == 1:
            v = _hex8(args[0])
            return None if v is None else f"tt.uio_in.value = {v}\n_R('')"
        return None

    def _to_reply(self, out: str, err: str) -> Reply:
        info: list[str] = []
        result: Reply | None = None
        for raw_line in out.splitlines():
            line = ANSI.sub("", raw_line).strip()
            if not line:
                continue
            if line.startswith("R "):
                result = Reply(True, line[2:], info)
            elif line == "R":
                result = Reply(True, "", info)
            elif line.startswith("E "):
                result = Reply(False, line[2:], info)
            else:
                info.append(f"# upy: {line}")
                self._on_line(f"# upy: {line}")
        if err:
            last = err.strip().splitlines()[-1] if err.strip() else "error"
            self._on_line(f"# upy: {last}")
            return Reply(False, "upy-exception", info)
        return result or Reply(False, "no-reply", info)

    # -- raw REPL I/O (blocking, called in the executor) --

    def _enter_raw_repl(self) -> None:
        with self._io:
            self._ser.write(b"\r\x03\x03")  # interrupt anything running
            time.sleep(0.3)
            self._ser.reset_input_buffer()
            self._ser.write(b"\r\x01")  # ctrl-A
            got = self._ser.read_until(RAW_REPL_PROMPT)
            if RAW_REPL_PROMPT not in got:
                raise OSError("no raw REPL prompt (not MicroPython?)")

    def _exec(self, code: str) -> tuple[str, str]:
        """Run one snippet, return (stdout, stderr)."""
        with self._io:
            if self._closed:
                raise OSError("closed")
            self._ser.write(code.encode() + b"\x04")
            ack = self._ser.read(2)
            if ack != b"OK":
                raise OSError(f"raw REPL lost sync: {ack!r}")
            body = self._ser.read_until(b"\x04>")[:-1]
            stdout, _, err = body.partition(b"\x04")
            return (stdout.decode(errors="replace"),
                    err.rstrip(b"\x04").decode(errors="replace"))


def _hex8(s: str) -> int | None:
    try:
        v = int(s, 16)
    except ValueError:
        return None
    return v if 0 <= v <= 255 else None
