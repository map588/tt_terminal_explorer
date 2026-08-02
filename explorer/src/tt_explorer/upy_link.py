"""Drive the stock Tiny Tapeout MicroPython firmware over its raw
REPL.

The stock firmware ships pre-loaded on the demo board and exposes the
ttboard SDK (`tt`) on a Python REPL instead of the tt_host line
protocol. This link translates each tt_host command into one raw-REPL
exec and synthesizes the same "ok/err" replies, so the UI cannot tell
the two firmwares apart.

Marker convention inside the REPL: helper code prints exactly one
line starting with "R " (ok + payload) or "E " (err + token). A
board-side timer pushes "U <hex>" lines whenever uo_out changes
(started with the `monitor <hz>` command). Every other stdout line
is an SDK log line and is forwarded to the console.

A background thread reads the port. Between execs it dispatches
pushed lines at once; during an exec it collects the framed response
(raw REPL brackets every exec with "OK" ... 0x04 0x04 ">").
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
# The globals survive reconnects, so a monitor timer from an earlier
# session is stopped before _mon is rebuilt.
BOOTSTRAP = """
try:
    tt
except NameError:
    from ttboard.demoboard import DemoBoard
    tt = DemoBoard.get()
from ttboard.mode import RPMode
import machine as _m
import time as _t
try:
    if _mon['t']:
        _mon['t'].deinit()
except NameError:
    pass
_mon = {'t': None, 'last': -1}
def _R(s):
    print('R ' + s)
def _tt_sdk():
    try:
        f = open('/VERSION')
        v = f.read()
        f.close()
        for ln in v.split('\\n'):  # "version=3.0.7", "commit=..."
            if ln.startswith('version='):
                return ln[8:].strip()
        return 'unknown'
    except OSError:
        return 'unknown'
def _tt_hello():
    _R('tt-explorer 2 shuttle=%s upy=1 sdk=%s' % (tt.shuttle.run, _tt_sdk()))
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
            _tt_reset(2)
            return
    print('E no-design')
def _tt_reset(arg):
    if arg == 1:
        tt.reset_project(True)
    elif arg == 0:
        tt.reset_project(False)
    else:
        tt.reset_project(True)
        if tt.is_auto_clocking:
            _t.sleep_ms(2)
        else:
            for _ in range(10):
                tt.clock_project_once()
        tt.reset_project(False)
    _R('')
def _tt_ui(v):
    if tt.mode != RPMode.ASIC_RP_CONTROL:
        tt.mode = RPMode.ASIC_RP_CONTROL
    tt.ui_in.value = v
    _R('')
def _tt_step(n):
    for _ in range(n):
        tt.clock_project_once()
    _R(str(n))
def _tt_mon_cb(t):
    v = int(tt.uo_out.value)
    if v != _mon['last']:
        _mon['last'] = v
        print('U %02x' % v)
def _tt_monitor(freq):
    if _mon['t']:
        _mon['t'].deinit()
        _mon['t'] = None
    _mon['last'] = -1
    if freq > 0:
        _mon['t'] = _m.Timer(mode=_m.Timer.PERIODIC, freq=freq,
                             callback=_tt_mon_cb)
    _R('')
_R('ready')
"""


class _Pending:
    def __init__(self, future: asyncio.Future):
        self.future = future
        self.acked = False


class UpyLink:
    """Same public surface as SerialLink, backed by the raw REPL."""

    # The stock firmware clocks with the RP2 PWM block. At the SDK's
    # 133 MHz system clock the divider bottoms out near 8 Hz and the
    # top is sys/2.
    clk_min_hz = 8
    clk_max_hz = 66_000_000
    clock_note = "PWM"

    # The board pushes uo_out changes; the UI need not poll them.
    pushes_uo = True

    def __init__(self, port: str, on_line: Callable[[str], None]):
        self._ser = serial.Serial(port, 115200, timeout=0.2)
        self._on_line = on_line
        self._loop = asyncio.get_running_loop()
        self._lock = asyncio.Lock()
        self._closed = False
        self._last_freq = 0
        self._pending: _Pending | None = None
        self._uo_sink: Callable[[int], None] | None = None
        self._enter_raw_repl()
        out, err = self._exec_blocking(BOOTSTRAP)
        if err or "R ready" not in out:
            raise OSError(f"ttboard SDK bootstrap failed: {err or out!r}")
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

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

    def set_uo_sink(self, sink: Callable[[int], None] | None) -> None:
        """sink gets each pushed uo_out value (called on the loop)."""
        self._uo_sink = sink

    def close(self) -> None:
        self._closed = True
        try:
            self._ser.cancel_read()
        except (OSError, AttributeError):
            pass
        self._thread.join(timeout=1.0)
        try:
            # stop the push timer and hand the friendly REPL back
            self._ser.timeout = 0.5
            self._ser.write(b"_tt_monitor(0)\x04")
            time.sleep(0.2)
            self._ser.write(b"\x02")
            self._ser.close()
        except OSError:
            pass

    async def request(self, line: str, timeout: float = 5.0) -> Reply:
        async with self._lock:
            code = self._translate(line.strip())
            if code is None:
                return Reply(False, "unknown")
            fut: asyncio.Future = self._loop.create_future()
            self._pending = _Pending(fut)
            try:
                self._ser.write(code.encode() + b"\x04")
                out, err = await asyncio.wait_for(fut, timeout)
            finally:
                self._pending = None
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
                return "_tt_reset(2)"
            if args == ["1"]:
                return "_tt_reset(1)"
            if args == ["0"]:
                return "_tt_reset(0)"
            return None
        if cmd == "monitor" and len(args) == 1 and args[0].isdigit():
            return f"_tt_monitor({int(args[0])})"
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
            elif self._dispatch_push(line):
                continue
            else:
                info.append(f"# upy: {line}")
                self._on_line(f"# upy: {line}")
        if err:
            last = err.strip().splitlines()[-1] if err.strip() else "error"
            self._on_line(f"# upy: {last}")
            return Reply(False, "upy-exception", info)
        return result or Reply(False, "no-reply", info)

    def _dispatch_push(self, line: str) -> bool:
        """Handle a pushed 'U <hex>' line. Returns True when it was one."""
        if not line.startswith("U "):
            return False
        try:
            value = int(line[2:], 16)
        except ValueError:
            return False
        if self._uo_sink is not None:
            self._uo_sink(value)
        return True

    # -- reader thread --

    def _reader(self) -> None:
        """Routes bytes: exec responses to the pending future, pushed
        lines and log lines straight to their sinks."""
        buf = b""
        while not self._closed:
            try:
                data = self._ser.read(256)
            except (OSError, serial.SerialException):
                break
            if not data:
                continue
            buf += data
            while True:
                pend = self._pending
                if pend is None:
                    # idle: only complete pushed/log lines can arrive
                    if b"\n" not in buf:
                        break
                    raw, buf = buf.split(b"\n", 1)
                    self._route_idle_line(raw)
                    continue
                if not pend.acked:
                    # drop pushed lines that raced the exec, then the
                    # raw REPL's OK acknowledgement
                    if b"\n" in buf and not buf.startswith(b"OK"):
                        raw, buf = buf.split(b"\n", 1)
                        self._route_idle_line(raw)
                        continue
                    if buf.startswith(b"OK"):
                        buf = buf[2:]
                        pend.acked = True
                        continue
                    break  # partial OK or partial line
                end = buf.find(b"\x04>")
                if end < 0:
                    break
                body, buf = buf[:end], buf[end + 2:]
                stdout, _, err = body.partition(b"\x04")
                self._loop.call_soon_threadsafe(
                    self._resolve, pend,
                    stdout.decode(errors="replace"),
                    err.rstrip(b"\x04").decode(errors="replace"))
                self._pending = None

    def _route_idle_line(self, raw: bytes) -> None:
        line = ANSI.sub("", raw.decode(errors="replace")).strip()
        if not line:
            return
        self._loop.call_soon_threadsafe(self._route_idle_dispatch, line)

    def _route_idle_dispatch(self, line: str) -> None:
        if not self._dispatch_push(line):
            self._on_line(f"# upy: {line}")

    @staticmethod
    def _resolve(pend: _Pending, out: str, err: str) -> None:
        if not pend.future.done():
            pend.future.set_result((out, err))

    # -- raw REPL I/O (blocking, used before the reader starts) --

    def _enter_raw_repl(self) -> None:
        self._ser.timeout = 5
        self._ser.write(b"\r\x03\x03")  # interrupt anything running
        time.sleep(0.3)
        self._ser.reset_input_buffer()
        self._ser.write(b"\r\x01")  # ctrl-A
        got = self._ser.read_until(RAW_REPL_PROMPT)
        if RAW_REPL_PROMPT not in got:
            raise OSError("no raw REPL prompt (not MicroPython?)")

    def _exec_blocking(self, code: str) -> tuple[str, str]:
        """Run one snippet before the reader thread exists."""
        self._ser.write(code.encode() + b"\x04")
        ack = self._ser.read(2)
        if ack != b"OK":
            raise OSError(f"raw REPL lost sync: {ack!r}")
        body = self._ser.read_until(b"\x04>")[:-1]
        self._ser.timeout = 0.2  # reader-thread polling interval
        stdout, _, err = body.partition(b"\x04")
        return (stdout.decode(errors="replace"),
                err.rstrip(b"\x04").decode(errors="replace"))


def _hex8(s: str) -> int | None:
    try:
        v = int(s, 16)
    except ValueError:
        return None
    return v if 0 <= v <= 255 else None
