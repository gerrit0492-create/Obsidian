"""Tests for homewizard.normalize — run with `python test_homewizard.py`."""

from __future__ import annotations

from homewizard import normalize


def test_v1() -> None:
    r = normalize(
        {
            "active_power_w": 350.0,
            "total_power_import_t1_kwh": 1000.0,
            "total_power_import_t2_kwh": 500.0,
            "total_power_export_t1_kwh": 20.0,
            "total_power_export_t2_kwh": 5.0,
        }
    )
    assert r.active_power_w == 350.0
    assert r.import_kwh == 1500.0
    assert r.export_kwh == 25.0


def test_v2_combined() -> None:
    r = normalize(
        {
            "power_w": 120.0,
            "energy_import_t1_kwh": 800.0,
            "energy_import_t2_kwh": 400.0,
            "energy_export_kwh": 10.0,
        }
    )
    assert r.active_power_w == 120.0
    assert r.import_kwh == 1200.0
    assert r.export_kwh == 10.0


def test_details() -> None:
    r = normalize(
        {
            "active_power_w": 415.0,
            "active_power_l1_w": 200.0,
            "active_voltage_l1_v": 230.1,
            "active_tariff": 2,
            "total_power_import_kwh": 11324.0,
            "montly_power_peak_w": 9000.0,
            "meter_model": "ISKRA",
        }
    )
    d = r.details
    assert d["Active power (W)"] == 415.0
    assert d["Power L1 (W)"] == 200.0
    assert d["Voltage L1 (V)"] == 230.1
    assert d["Active tariff"] == 2
    assert d["Monthly power peak (W)"] == 9000.0
    assert d["Meter model"] == "ISKRA"
    assert "Gas total (m³)" not in d  # only present fields are included


if __name__ == "__main__":
    test_v1()
    test_v2_combined()
    test_details()
    print("All tests passed.")
