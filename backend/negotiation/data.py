"""DOT flight data loading and scenario listing.

The CSV is intentionally not committed to the repository.  In production it
is supplied as ``data/flights.csv`` or through ``FLIGHTS_CSV``.  The helpers in
this module keep the pandas-facing details out of the world builder and turn
the relevant DOT columns into the shared ``FlightRecord`` contract.
"""
from __future__ import annotations

from datetime import date as date_type
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

import pandas as pd

from .schemas import FlightRecord, ScenarioSummary
from .timeutil import from_csv


_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_FLIGHTS = _ROOT / "data" / "flights.csv"
_DERIVED_SERIES: dict[tuple[int, str], pd.Series] = {}


def _path_for(path: str | os.PathLike[str] | None) -> str:
    if path is None:
        path = os.getenv("FLIGHTS_CSV") or _DEFAULT_FLIGHTS
    return str(Path(path).expanduser().resolve())


@lru_cache(maxsize=8)
def _load_flights_cached(path: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"flights.csv not found at {csv_path}; set FLIGHTS_CSV or add data/flights.csv"
        )
    # Do not use an index column: row_id is the pandas default index after the
    # pre-filtered CSV is read, as specified in PLAN.md.
    return pd.read_csv(csv_path)


def load_flights(path: str | os.PathLike[str] | None = None) -> pd.DataFrame:
    """Load the pre-filtered DOT flight table, cached by its resolved path."""

    return _load_flights_cached(_path_for(path))


# Useful for tests and for a caller that replaces FLIGHTS_CSV during a process.
def _clear_load_cache() -> None:
    _load_flights_cached.cache_clear()
    _DERIVED_SERIES.clear()


load_flights.cache_clear = _clear_load_cache  # type: ignore[attr-defined]
load_flights.cache_info = _load_flights_cached.cache_info  # type: ignore[attr-defined]


def _column(row: pd.Series, *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row.index:
            value = row[name]
            if not pd.isna(value):
                return value
    return default


def _int(value: Any, default: int | None = None) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _text(value: Any, default: str = "") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip()


def _minute(value: Any, *, optional: bool = False) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None if optional else 0
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None if optional else 0
        if ":" in value:
            hours, minutes = value.split(":", 1)
            return int(hours) * 60 + int(minutes)
    parsed = _int(value)
    if parsed is None:
        return None if optional else 0
    return from_csv(parsed)


def _date(row: pd.Series) -> str:
    explicit = _column(row, "DATE", "date")
    if explicit is not None:
        parsed = pd.to_datetime(explicit, errors="coerce")
        if not pd.isna(parsed):
            return parsed.strftime("%Y-%m-%d")
        text = _text(explicit)
        if text:
            return text
    year = _int(_column(row, "YEAR", "year"), 2015) or 2015
    month = _int(_column(row, "MONTH", "month"), 1) or 1
    day = _int(_column(row, "DAY", "day"), 1) or 1
    try:
        return date_type(year, month, day).isoformat()
    except ValueError:
        return f"{year:04d}-{month:02d}-{day:02d}"


def _row_id(index: Any, position: int) -> int:
    try:
        return int(index)
    except (TypeError, ValueError):
        return position


def flight_from_row(row: pd.Series, row_id: int) -> FlightRecord:
    """Convert one DOT row to the shared, typed flight record."""

    return FlightRecord(
        row_id=int(row_id),
        date=_date(row),
        airline=_text(_column(row, "AIRLINE", "airline")),
        flight_number=_int(_column(row, "FLIGHT_NUMBER", "flight_number"), 0) or 0,
        tail_number=_text(_column(row, "TAIL_NUMBER", "tail_number")),
        origin=_text(_column(row, "ORIGIN_AIRPORT", "ORIGIN", "origin")),
        destination=_text(_column(row, "DESTINATION_AIRPORT", "DESTINATION", "destination")),
        scheduled_departure=_minute(_column(row, "SCHEDULED_DEPARTURE", "scheduled_departure")) or 0,
        scheduled_arrival=_minute(_column(row, "SCHEDULED_ARRIVAL", "scheduled_arrival")) or 0,
        actual_arrival=_minute(_column(row, "ARRIVAL_TIME", "ACTUAL_ARRIVAL", "actual_arrival"), optional=True),
        arrival_delay=_int(_column(row, "ARRIVAL_DELAY", "arrival_delay"), None),
        departure_delay=_int(_column(row, "DEPARTURE_DELAY", "departure_delay"), None),
        weather_delay=_int(_column(row, "WEATHER_DELAY", "weather_delay"), 0) or 0,
        late_aircraft_delay=_int(_column(row, "LATE_AIRCRAFT_DELAY", "late_aircraft_delay"), 0) or 0,
        distance=_int(_column(row, "DISTANCE", "distance"), 0) or 0,
        taxi_in=_int(_column(row, "TAXI_IN", "taxi_in"), None),
    )


def flight_at(df: pd.DataFrame, row_id: int) -> FlightRecord:
    """Return the flight at pandas' default row position ``row_id``."""

    if row_id < 0 or row_id >= len(df):
        raise ValueError(f"row_id {row_id} is outside flights.csv (0..{max(len(df) - 1, 0)})")
    row = df.iloc[row_id]
    return flight_from_row(row, row_id)


def _date_key(value: Any) -> str:
    if value is None:
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    if not pd.isna(parsed):
        return parsed.strftime("%Y-%m-%d")
    return str(value).strip()


def _date_series(df: pd.DataFrame) -> pd.Series:
    cache_key = (id(df), "dates")
    cached = _DERIVED_SERIES.get(cache_key)
    if cached is not None and cached.index.equals(df.index):
        return cached
    if {"YEAR", "MONTH", "DAY"} <= set(df.columns) and not ({"DATE", "date"} & set(df.columns)):
        parts = df[["YEAR", "MONTH", "DAY"]].rename(columns=str.lower)
        values = pd.to_datetime(parts, errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    else:
        values = pd.Series([_date(row) for _, row in df.iterrows()], index=df.index)
    _DERIVED_SERIES[cache_key] = values
    return values


def _time_series(df: pd.DataFrame, column: str) -> pd.Series:
    cache_key = (id(df), f"minutes:{column}")
    cached = _DERIVED_SERIES.get(cache_key)
    if isinstance(cached, pd.Series) and cached.index.equals(df.index):
        return cached
    numeric = pd.to_numeric(df[column], errors="coerce")
    if numeric.notna().sum() == df[column].notna().sum():  # plain HHMM numbers: vectorised
        result = ((numeric // 100) * 60 + numeric % 100).fillna(-1).astype(int)
    else:
        values: list[int] = []
        for value in df[column]:
            minute = _minute(value, optional=True)
            values.append(minute if minute is not None else -1)
        result = pd.Series(values, index=df.index)
    _DERIVED_SERIES[cache_key] = result
    return result


def _departure_series(df: pd.DataFrame, departure_col: str) -> pd.Series:
    return _time_series(df, departure_col)


def next_leg(df: pd.DataFrame, flight: FlightRecord) -> FlightRecord | None:
    """Find the same tail's next scheduled departure from this destination."""

    if not flight.tail_number:
        return None
    candidates: list[FlightRecord] = []
    tail_col = next((name for name in ("TAIL_NUMBER", "tail_number") if name in df.columns), None)
    origin_col = next((name for name in ("ORIGIN_AIRPORT", "ORIGIN", "origin") if name in df.columns), None)
    departure_col = next((name for name in ("SCHEDULED_DEPARTURE", "scheduled_departure") if name in df.columns), None)
    if not tail_col or not origin_col or not departure_col:
        return None

    # Filter in pandas first.  The real file has hundreds of thousands of
    # rows; iterating through all of them for every scenario listing would be
    # needlessly expensive.
    dates = _date_series(df)
    departures = _departure_series(df, departure_col)
    mask = (
        df[tail_col].fillna("").astype(str).eq(flight.tail_number)
        & dates.eq(flight.date)
        & df[origin_col].fillna("").astype(str).eq(flight.destination)
        & departures.gt(flight.scheduled_departure)
    )
    for position, (index, row) in enumerate(df.loc[mask].iterrows()):
        candidate_id = _row_id(index, position)
        if candidate_id != flight.row_id:
            candidates.append(flight_from_row(row, candidate_id))
    return min(candidates, key=lambda item: (item.scheduled_departure, item.row_id), default=None)


def list_scenarios(
    airport: str | None = None,
    date: str | None = None,
    limit: int = 50,
    origin: str | None = None,
) -> list[ScenarioSummary]:
    """List real arrival rows that can be used as disruption scenarios (airport = destination)."""

    if limit <= 0:
        return []
    df = load_flights()
    airport_key = airport.upper().strip() if airport else None
    date_key = _date_key(date) if date else None
    # Narrow with column-wise masks first; only the matching rows are turned into records below.
    dest_col = next((n for n in ("DESTINATION_AIRPORT", "DESTINATION", "destination") if n in df.columns), None)
    mask = pd.Series(True, index=df.index)
    if airport_key and dest_col:
        mask &= df[dest_col].fillna("").astype(str).str.upper().str.strip().eq(airport_key)
    if date_key:
        mask &= _date_series(df).eq(date_key)
    origin_col = next((n for n in ("ORIGIN_AIRPORT", "ORIGIN", "origin") if n in df.columns), None)
    if origin and origin_col:
        mask &= df[origin_col].fillna("").astype(str).str.upper().str.strip().eq(origin.upper().strip())
    positions = {index: position for position, index in enumerate(df.index)} if not mask.all() else None
    scenarios: list[ScenarioSummary] = []
    for index, row in df.loc[mask].iterrows():
        position = positions[index] if positions is not None else index
        row_id = _row_id(index, position)
        flight = flight_from_row(row, row_id)
        # The disruption airport is the destination: the world being built is
        # for the arrival that needs a runway, gate and turnaround.
        if airport_key and flight.destination.upper() != airport_key:
            continue
        if date_key and flight.date != date_key:
            continue
        scenarios.append(
            ScenarioSummary(
                row_id=flight.row_id,
                date=flight.date,
                flight=f"{flight.airline}{flight.flight_number}",
                origin=flight.origin,
                destination=flight.destination,
                scheduled_arrival=flight.scheduled_arrival,
                arrival_delay=flight.arrival_delay,
                weather_delay=flight.weather_delay,
                late_aircraft_delay=flight.late_aircraft_delay,
                has_next_leg=next_leg(df, flight) is not None,
            )
        )
        if len(scenarios) >= limit:
            break
    return scenarios

