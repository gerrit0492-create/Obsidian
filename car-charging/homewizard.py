"""Read live data from a HomeWizard P1 meter over the local network.

Supports both API generations:
  v1: GET http://<host>/api/v1/data       (enable "Local API" in the HomeWizard app)
  v2: GET https://<host>/api/measurement   (HTTPS + bearer token)

``normalize`` is pure (and unit-tested); ``fetch`` does the HTTP call. Only works
on the same network as the device.
"""

from __future__ import annotations

from dataclasses import dataclass

V1_PATH = "/api/v1/data"
V2_PATH = "/api/measurement"
TIMEOUT = 10


@dataclass
class Reading:
    active_power_w: float | None = None
    import_kwh: float | None = None
    export_kwh: float | None = None
    details: dict | None = None
    raw: dict | None = None


def _energy(d: dict, combined: str, t1: str, t2: str) -> float | None:
    if d.get(combined) is not None:
        return float(d[combined])
    parts = [float(d[k]) for k in (t1, t2) if d.get(k) is not None]
    return sum(parts) if parts else None


def _first(d: dict, *keys: str) -> float | None:
    for key in keys:
        if d.get(key) is not None:
            return float(d[key])
    return None


# Every P1 field we recognise: (candidate raw keys, friendly label). The first
# key that is present wins, so one spec covers both the v1 and v2 payloads.
_FIELDS: list[tuple[tuple[str, ...], str]] = [
    (("active_power_w", "power_w"), "Active power (W)"),
    (("active_power_l1_w",), "Power L1 (W)"),
    (("active_power_l2_w",), "Power L2 (W)"),
    (("active_power_l3_w",), "Power L3 (W)"),
    (("active_voltage_l1_v", "active_voltage_v"), "Voltage L1 (V)"),
    (("active_voltage_l2_v",), "Voltage L2 (V)"),
    (("active_voltage_l3_v",), "Voltage L3 (V)"),
    (("active_current_a", "active_current_l1_a"), "Current L1 (A)"),
    (("active_current_l2_a",), "Current L2 (A)"),
    (("active_current_l3_a",), "Current L3 (A)"),
    (("active_frequency_hz",), "Frequency (Hz)"),
    (("active_tariff",), "Active tariff"),
    (("total_power_import_kwh",), "Import total (kWh)"),
    (("total_power_import_t1_kwh", "energy_import_t1_kwh"), "Import T1 (kWh)"),
    (("total_power_import_t2_kwh", "energy_import_t2_kwh"), "Import T2 (kWh)"),
    (("total_power_export_kwh",), "Export total (kWh)"),
    (("total_power_export_t1_kwh", "energy_export_t1_kwh"), "Export T1 (kWh)"),
    (("total_power_export_t2_kwh", "energy_export_t2_kwh"), "Export T2 (kWh)"),
    (("montly_power_peak_w", "monthly_power_peak_w"), "Monthly power peak (W)"),
    (("any_power_fail_count",), "Power failures (any)"),
    (("long_power_fail_count",), "Power failures (long)"),
    (("voltage_sag_l1_count",), "Voltage sags L1"),
    (("voltage_sag_l2_count",), "Voltage sags L2"),
    (("voltage_sag_l3_count",), "Voltage sags L3"),
    (("voltage_swell_l1_count",), "Voltage swells L1"),
    (("voltage_swell_l2_count",), "Voltage swells L2"),
    (("voltage_swell_l3_count",), "Voltage swells L3"),
    (("total_gas_m3",), "Gas total (m³)"),
    (("total_liter_m3",), "Water total (m³)"),
    (("active_liter_lpm",), "Water flow (L/min)"),
    (("wifi_ssid",), "Wi-Fi SSID"),
    (("wifi_strength",), "Wi-Fi strength (%)"),
    (("meter_model",), "Meter model"),
    (("smr_version",), "SMR version"),
    (("unique_id",), "Meter ID"),
]


def all_fields(data: dict) -> dict:
    """Pull every recognised P1 field into a friendly-labelled dict (present only)."""
    out: dict = {}
    for keys, label in _FIELDS:
        for key in keys:
            if data.get(key) is not None:
                out[label] = data[key]
                break
    return out


def normalize(data: dict) -> Reading:
    """Map a v1 or v2 P1 JSON payload to a Reading (summing tariff buckets)."""
    imp = _energy(
        data, "total_power_import_kwh",
        "total_power_import_t1_kwh", "total_power_import_t2_kwh",
    )
    if imp is None:
        imp = _energy(
            data, "energy_import_kwh", "energy_import_t1_kwh", "energy_import_t2_kwh"
        )
    exp = _energy(
        data, "total_power_export_kwh",
        "total_power_export_t1_kwh", "total_power_export_t2_kwh",
    )
    if exp is None:
        exp = _energy(
            data, "energy_export_kwh", "energy_export_t1_kwh", "energy_export_t2_kwh"
        )
    power = _first(data, "active_power_w", "power_w")
    return Reading(
        active_power_w=power,
        import_kwh=imp,
        export_kwh=exp,
        details=all_fields(data),
        raw=data,
    )


def fetch_url(url: str, token: str | None = None) -> Reading:
    """Fetch a reading from any URL serving v1/v2-shaped P1 JSON.

    Use this when a relay at home (e.g. Home Assistant) republishes the meter's
    JSON to an address the app can reach from anywhere.
    """
    import requests

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False)
    resp.raise_for_status()
    return normalize(resp.json())


def fetch(host: str, token: str | None = None) -> Reading:
    """Fetch a live reading from the P1 meter at ``host`` (IP or hostname)."""
    import requests

    if token:
        resp = requests.get(
            f"https://{host}{V2_PATH}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
            verify=False,  # the device uses a self-signed certificate
        )
    else:
        resp = requests.get(f"http://{host}{V1_PATH}", timeout=TIMEOUT)
    resp.raise_for_status()
    return normalize(resp.json())
