"""Tests for peblar.normalize — run with `python test_peblar.py`."""

from __future__ import annotations

from peblar import normalize


def test_meter_only() -> None:
    r = normalize(
        {
            "PowerTotal": 7360,
            "EnergySession": 4200,
            "EnergyTotal": 1543000,
        }
    )
    assert r.power_w == 7360.0
    assert r.session_kwh == 4.2          # 4200 Wh -> kWh
    assert r.total_kwh == 1543.0         # 1_543_000 Wh -> kWh
    assert r.cp_state is None


def test_with_evinterface() -> None:
    r = normalize(
        {"PowerTotal": 0, "EnergySession": 0, "EnergyTotal": 1000},
        {"CpState": "State C"},
    )
    assert r.power_w == 0.0
    assert r.session_kwh == 0.0
    assert r.cp_state == "Charging"      # last letter "C" maps to Charging


def test_missing_fields() -> None:
    r = normalize({})
    assert r.power_w is None
    assert r.session_kwh is None
    assert r.total_kwh is None


if __name__ == "__main__":
    test_meter_only()
    test_with_evinterface()
    test_missing_fields()
    print("All tests passed.")
