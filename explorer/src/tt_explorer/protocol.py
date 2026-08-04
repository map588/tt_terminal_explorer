"""Pure helpers for the tt-explorer serial protocol.

The firmware accepts one command per line and answers with exactly one
"ok [payload]" or "err <token>" line. Informational lines start with
"# ". No I/O happens here, so everything is unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PROTO_VERSION = 2


@dataclass
class Reply:
    ok: bool
    payload: str
    info: list[str] = field(default_factory=list)


def is_reply_line(line: str) -> bool:
    """True when the line ends a command (ok/err)."""
    return line.startswith("ok") or line.startswith("err")


def is_info_line(line: str) -> bool:
    return line.startswith("# ") or line == "#"


def parse_reply(line: str, info: list[str] | None = None) -> Reply:
    if line.startswith("ok"):
        return Reply(True, line[2:].strip(), info or [])
    if line.startswith("err"):
        return Reply(False, line[3:].strip(), info or [])
    raise ValueError(f"not a reply line: {line!r}")


def parse_hello(payload: str) -> dict:
    """'tt-explorer 2 shuttle=ttsky25b' -> {'version': 2,
    'shuttle': 'ttsky25b'}. Unknown key=value fields pass through."""
    parts = payload.split()
    if len(parts) < 2 or parts[0] != "tt-explorer":
        raise ValueError(f"bad hello: {payload!r}")
    out: dict = {"version": int(parts[1])}
    for part in parts[2:]:
        key, _, value = part.partition("=")
        out[key] = value
    return out


def parse_status(payload: str) -> dict:
    """'design=448 mode=run freq=1000000 ui=00 uiod=00' -> dict."""
    out: dict = {}
    for part in payload.split():
        key, _, value = part.partition("=")
        if key in ("design", "freq", "uidrv"):
            out[key] = int(value)
        elif key in ("ui", "uiod"):
            out[key] = int(value, 16)
        else:
            out[key] = value
    return out


def hex_byte(value: int) -> str:
    if not 0 <= value <= 255:
        raise ValueError(f"byte out of range: {value}")
    return f"{value:02x}"


def parse_pin_byte(text: str) -> int | None:
    """A byte the user typed for a pin bus. Accepts hex ('a5',
    '0xa5') and binary ('0b101', or exactly 8 bare 0/1 digits so
    '10100101' reads as bits, not hex). None when unreadable."""
    text = text.strip().lower().replace("_", "")
    if not text:
        return None
    try:
        if text.startswith("0b"):
            value = int(text[2:], 2)
        elif text.startswith("0x"):
            value = int(text[2:], 16)
        elif len(text) == 8 and set(text) <= {"0", "1"}:
            value = int(text, 2)
        else:
            value = int(text, 16)
    except ValueError:
        return None
    return value if 0 <= value <= 255 else None


def parse_hex_byte(payload: str) -> int:
    value = int(payload, 16)
    if not 0 <= value <= 255:
        raise ValueError(f"byte out of range: {payload!r}")
    return value
