"""SHARED time helpers. All times in code are Minute (minutes since local midnight)."""
import re

from .schemas import Minute

_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def from_csv(hhmm: int) -> Minute:
    """flights.csv stores 1724 for 17:24 and 2400 for midnight."""
    return (hhmm // 100) * 60 + hhmm % 100


def to_hhmm(m: Minute) -> str:
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def parse_hhmm(s: str) -> Minute:
    """Parse "17:24" from LLM output. Raises ValueError on anything else."""
    match = _HHMM.match(s.strip())
    if not match:
        raise ValueError(f"bad HH:MM time: {s!r}")
    return int(match.group(1)) * 60 + int(match.group(2))
