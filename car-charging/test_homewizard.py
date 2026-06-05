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


if __name__ == "__main__":
    test_v1()
    test_v2_combined()
    print("All tests passed.")
