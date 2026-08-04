"""Shuttle index: fetch, cache, and parse a shuttle's project list."""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

FIELDS = ("address,title,author,description,clock_hz,pinout"
          ",repo,tiles,analog_pins")
CACHE_DIR = Path("~/.cache/tt-explorer").expanduser()
CACHE_MAX_AGE_S = 7 * 24 * 3600


@dataclass
class Project:
    macro: str
    address: int
    title: str = ""
    author: str = ""
    description: str = ""
    clock_hz: int | None = None
    pinout: dict[str, str] = field(default_factory=dict)
    repo: str = ""
    tiles: str = ""
    analog_pins: list[int] = field(default_factory=list)


def _parse(raw: bytes) -> list[Project]:
    data = json.loads(raw)
    projects = []
    for p in data["projects"]:
        projects.append(
            Project(
                macro=p.get("macro", ""),
                address=p["address"],
                title=p.get("title", ""),
                author=p.get("author", ""),
                description=p.get("description", ""),
                clock_hz=p.get("clock_hz"),
                pinout=p.get("pinout", {}) or {},
                repo=p.get("repo", "") or "",
                tiles=p.get("tiles", "") or "",
                analog_pins=list(p.get("analog_pins", []) or []),
            )
        )
    projects.sort(key=lambda p: p.address)
    return projects


def load_index(shuttle: str, refresh: bool = False) -> list[Project]:
    """Return the project list for a shuttle. Network fetch when the
    cache is stale or refresh is requested; otherwise (and on fetch
    failure) use the cache."""
    url = f"https://index.tinytapeout.com/{shuttle}.json?fields={FIELDS}"
    # The cache name carries a version: a cache written before a
    # FIELDS change lacks the new fields and must not satisfy reads.
    cache = CACHE_DIR / f"{shuttle}-v2.json"
    cache_ok = cache.exists()
    cache_fresh = cache_ok and (time.time() - cache.stat().st_mtime) < CACHE_MAX_AGE_S

    if cache_fresh and not refresh:
        return _parse(cache.read_bytes())

    try:
        # The index server rejects the default Python-urllib user agent.
        req = urllib.request.Request(url, headers={"User-Agent": "tt-explorer"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
        return _parse(raw)
    except OSError:
        if cache_ok:
            return _parse(cache.read_bytes())
        raise
