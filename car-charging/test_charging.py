"""Tests for charging.py — run with `python test_charging.py`."""

from __future__ import annotations

import io

from charging import (
    daily_summary,
    load_sessions,
    monthly_effective_price,
    nl_number,
    parse_metadata,
)

SAMPLE = """# Laderinformatie
# Serienummer;00-00-DEMO-000
# Prijs per kWh;0,20;(Ingesteld door gebruiker)
# Totale verbruikte energie (kWh);25,678
# Totale kosten;5,14
# Valuta;EUR

Sessienummer;Starttijd;Stoptijd;Startenergie (kWh);Stopenergie (kWh);Totale sessie-energie (kWh);Kosten;Autorisatietoken;Sessievalidatie
1;28-1-2026 16:19:12;28-1-2026 18:21:19;1.675,601;1.688,434;12,833;2,57;Driver A (AAAA000000A1);Geslaagd
2;1-1-1970 01:01:18;30-1-2026 00:10:54;1.688,434;1.701,279;12,845;2,57;Driver B (BBBB000000B2);Geslaagd
"""

CAR_MAP = {"AAAA000000A1": "Car A", "BBBB000000B2": "Car B"}


def test_nl_number() -> None:
    assert nl_number("1.516,843") == 1516.843
    assert nl_number("0,20") == 0.20
    assert nl_number("303,37") == 303.37


def test_metadata() -> None:
    md = parse_metadata(SAMPLE)
    assert md.serial == "00-00-DEMO-000"
    assert md.price_per_kwh == 0.20
    assert md.currency == "EUR"


def test_load_sessions() -> None:
    df = load_sessions(io.StringIO(SAMPLE), car_map=CAR_MAP)
    assert len(df) == 2
    assert round(df["cost"].sum(), 2) == 5.14
    assert round(df["energy_kwh"].sum(), 3) == 25.678
    assert df["start"].dt.year.min() >= 2026  # 1970 start replaced by stop date
    assert set(df["car"]) == {"Car A", "Car B"}


def test_car_fallback_without_map() -> None:
    # No mapping -> car falls back to the card label.
    df = load_sessions(io.StringIO(SAMPLE), car_map={})
    assert set(df["car"]) == {"Driver A", "Driver B"}


def test_power_kw() -> None:
    df = load_sessions(io.StringIO(SAMPLE), car_map=CAR_MAP)
    by_session = df.set_index("session")["power_kw"]
    # Session 1: 12.833 kWh over ~2.035 h -> ~6.3 kW.
    assert round(by_session[1], 1) == 6.3
    # Session 2 had a bogus 1970 start replaced by its stop -> zero duration -> NA.
    assert by_session[2] != by_session[2]  # NaN


def test_daily_summary() -> None:
    df = load_sessions(io.StringIO(SAMPLE), car_map=CAR_MAP)
    days = daily_summary(df)
    assert len(days) == 2  # 28-1 and 30-1
    assert round(days["cost"].sum(), 2) == 5.14


def test_monthly_effective_price() -> None:
    df = load_sessions(io.StringIO(SAMPLE), car_map=CAR_MAP)
    price = monthly_effective_price(df)
    assert list(price["month"]) == ["2026-01"]
    assert round(price["eur_per_kwh"].iloc[0], 3) == round(5.14 / 25.678, 3)


if __name__ == "__main__":
    test_nl_number()
    test_metadata()
    test_load_sessions()
    test_car_fallback_without_map()
    test_power_kw()
    test_daily_summary()
    test_monthly_effective_price()
    print("All tests passed.")
