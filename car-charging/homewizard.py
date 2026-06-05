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
    return Reading(active_power_w=power, import_kwh=imp, export_kwh=exp, raw=data)


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
