"""Parse EV charger 'meterdata' CSV exports (Dutch locale).

The export has a ``#``-prefixed metadata header, then a semicolon-delimited
table with Dutch number formatting (``,`` decimal, ``.`` thousands) and
``D-M-YYYY`` dates. This module turns it into a tidy pandas DataFrame plus a
small Metadata object, and is shared by the Streamlit app and its tests.
"""

from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass

import pandas as pd

DATE_FMT = "%d-%m-%Y %H:%M:%S"

COLUMN_MAP = {
    "Sessienummer": "session",
    "Starttijd": "start",
    "Stoptijd": "stop",
    "Startenergie (kWh)": "start_kwh",
    "Stopenergie (kWh)": "stop_kwh",
    "Totale sessie-energie (kWh)": "energy_kwh",
    "Kosten": "cost",
    "Autorisatietoken": "token",
    "Sessievalidatie": "validation",
}


def _load_car_map() -> dict:
    """Map RFID card UID -> car name, from the CAR_MAP env var (JSON).

    Kept out of the code for privacy. Example:
      CAR_MAP={"AAAA000000A1": "Car A", "BBBB000000B2": "Car B"}
    """
    raw = os.environ.get("CAR_MAP")
    if not raw:
        return {}
    try:
        return {str(k): str(v) for k, v in json.loads(raw).items()}
    except (ValueError, TypeError, AttributeError):
        return {}


DEFAULT_CAR_MAP = _load_car_map()


def _read_text(source) -> str:
    if hasattr(source, "read"):
        data = source.read()
        return data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    with open(source, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def nl_number(value) -> float:
    """Parse a Dutch-formatted number string ('1.516,843' -> 1516.843)."""
    if value is None:
        return float("nan")
    s = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return float("nan")


@dataclass
class Metadata:
    serial: str = ""
    price_per_kwh: float = float("nan")
    currency: str = "EUR"
    total_energy_kwh: float = float("nan")
    total_cost: float = float("nan")
    period_from: str = ""
    period_to: str = ""


def parse_metadata(text: str) -> Metadata:
    md = Metadata()
    for line in text.splitlines():
        if not line.startswith("#"):
            continue
        body = line.lstrip("#").strip()
        if ";" not in body:
            continue
        key, _, val = body.partition(";")
        key = key.strip().lower()
        val = val.strip()
        if key.startswith("serienummer"):
            md.serial = val
        elif key.startswith("valuta"):
            md.currency = val
        elif key.startswith("prijs per kwh"):
            md.price_per_kwh = nl_number(val.split(";")[0])
        elif "totale verbruikte energie" in key:
            md.total_energy_kwh = nl_number(val)
        elif key.startswith("totale kosten"):
            md.total_cost = nl_number(val)
        elif "beginnend vanaf" in key:
            md.period_from = val
        elif key.startswith("inbegrepen sessies tot"):
            md.period_to = val
    return md


def load_sessions(source, car_map: dict | None = None) -> pd.DataFrame:
    """Load charging sessions from a path or file-like object into a DataFrame."""
    car_map = DEFAULT_CAR_MAP if car_map is None else car_map
    text = _read_text(source)
    df = pd.read_csv(
        io.StringIO(text),
        sep=";",
        comment="#",
        skip_blank_lines=True,
        dtype=str,
    )
    df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})

    for col in ("start_kwh", "stop_kwh", "energy_kwh", "cost"):
        df[col] = df[col].map(nl_number)
    df["session"] = pd.to_numeric(df["session"], errors="coerce").astype("Int64")
    df["start"] = pd.to_datetime(df["start"], format=DATE_FMT, errors="coerce")
    df["stop"] = pd.to_datetime(df["stop"], format=DATE_FMT, errors="coerce")

    # Some exports carry a bogus 1970 epoch start time; use the stop time there.
    bad = df["start"].dt.year < 2000
    df.loc[bad, "start"] = df.loc[bad, "stop"]

    df["duration_h"] = (df["stop"] - df["start"]).dt.total_seconds() / 3600.0
    df.loc[df["duration_h"] < 0, "duration_h"] = pd.NA
    df["power_kw"] = df["energy_kwh"] / df["duration_h"]
    df.loc[~(df["duration_h"] > 0), "power_kw"] = pd.NA
    df["date"] = df["start"].dt.date
    df["month"] = df["start"].dt.to_period("M").astype(str)

    # Friendly card label + RFID id from a token like "Driver A (AAAA000000A1)".
    df["card"] = df["token"].str.replace(r"\s*\(.*\)\s*", "", regex=True).str.strip()
    df["card_id"] = df["token"].str.extract(r"\(([^)]*)\)")
    # car_map may be keyed by RFID id or by the friendly card label; fall back to
    # the card label when neither matches.
    df["car"] = df["card_id"].map(car_map).fillna(df["card"].map(car_map)).fillna(df["card"])

    return df


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate energy, cost and session count per calendar month."""
    return (
        df.groupby("month")
        .agg(
            sessions=("session", "count"),
            energy_kwh=("energy_kwh", "sum"),
            cost=("cost", "sum"),
        )
        .reset_index()
        .sort_values("month")
    )


def monthly_by_car(df: pd.DataFrame) -> pd.DataFrame:
    """Energy, cost and session count per month, split by car."""
    return (
        df.groupby(["month", "car"])
        .agg(
            sessions=("session", "count"),
            energy_kwh=("energy_kwh", "sum"),
            cost=("cost", "sum"),
        )
        .reset_index()
        .sort_values(["month", "car"])
    )


def daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate energy, cost and session count per calendar day."""
    return (
        df.groupby("date")
        .agg(
            sessions=("session", "count"),
            energy_kwh=("energy_kwh", "sum"),
            cost=("cost", "sum"),
        )
        .reset_index()
        .sort_values("date")
    )


def monthly_effective_price(df: pd.DataFrame) -> pd.DataFrame:
    """Effective price paid per kWh (cost / energy) for each calendar month."""
    m = (
        df.groupby("month")
        .agg(energy_kwh=("energy_kwh", "sum"), cost=("cost", "sum"))
        .reset_index()
        .sort_values("month")
    )
    m["eur_per_kwh"] = m["cost"] / m["energy_kwh"]
    return m


def _is_offpeak(ts, dal_start: int, dal_end: int, weekend_offpeak: bool) -> bool:
    """Whether a timestamp falls in the off-peak (dal) window."""
    if weekend_offpeak and ts.weekday() >= 5:  # Saturday/Sunday
        return True
    hour = ts.hour
    if dal_start <= dal_end:
        return dal_start <= hour < dal_end
    return hour >= dal_start or hour < dal_end  # window wraps past midnight


def split_peak_offpeak(
    df: pd.DataFrame,
    dal_start: int = 23,
    dal_end: int = 7,
    weekend_offpeak: bool = True,
) -> pd.DataFrame:
    """Allocate each session's energy to off-peak (dal) vs peak (normaal).

    Energy is split in proportion to the share of the session's duration that
    falls inside the off-peak window, assuming roughly constant power.
    """
    out = df.copy()
    fracs = []
    for start, stop in zip(out["start"], out["stop"]):
        if pd.isna(start) or pd.isna(stop) or stop <= start:
            fracs.append(float("nan"))
            continue
        total = (stop - start).total_seconds()
        off = 0.0
        cur = start
        while cur < stop:
            nxt = min(cur + pd.Timedelta(hours=1), stop)
            mid = cur + (nxt - cur) / 2
            if _is_offpeak(mid, dal_start, dal_end, weekend_offpeak):
                off += (nxt - cur).total_seconds()
            cur = nxt
        fracs.append(off / total if total else float("nan"))
    out["offpeak_frac"] = fracs
    out["energy_offpeak"] = out["energy_kwh"] * out["offpeak_frac"].fillna(0)
    out["energy_peak"] = out["energy_kwh"] - out["energy_offpeak"]
    return out
