"""Read live data from a Peblar EV charger over its local REST API.

The "WLAC" local REST API is available on Peblar chargers from firmware 1.6 and
must be enabled in the charger's Advanced settings (which is where you copy the
access token). Endpoints live under::

    http://<host>/api/wlac/v1/<endpoint>     # meter, evinterface, system, health

and the token is sent verbatim in the ``Authorization`` header. ``normalize`` is
pure (and unit-tested); ``fetch`` does the HTTP calls. Only works on the same
network as the charger.

Note: this API exposes only live/cumulative meter state — it has no per-session
history. The session log the dashboard charts comes from the CSV export instead.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_PATH = "/api/wlac/v1"
TIMEOUT = 10

# Common IEC 61851 control-pilot states, mapped to a friendly label.
_CP_STATES = {
    "A": "No vehicle",
    "B": "Connected",
    "C": "Charging",
    "D": "Charging (vent.)",
    "E": "Error",
    "F": "Error",
}


@dataclass
class ChargerReading:
    power_w: float | None = None
    session_kwh: float | None = None
    total_kwh: float | None = None
    cp_state: str | None = None
    raw: dict | None = None


def _num(d: dict, *keys: str) -> float | None:
    for key in keys:
        if d.get(key) is not None:
            return float(d[key])
    return None


def _cp_label(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    # Accept "C", "State C", "StateC" — take the last letter and map it.
    letter = text[-1:].upper()
    return _CP_STATES.get(letter, text)


def normalize(meter: dict, ev: dict | None = None) -> ChargerReading:
    """Map the ``meter`` (and optional ``evinterface``) payloads to a reading.

    Energy fields are reported in Wh and converted to kWh; power stays in W.
    """
    session_wh = _num(meter, "EnergySession", "energy_session")
    total_wh = _num(meter, "EnergyTotal", "energy_total")
    power = _num(meter, "PowerTotal", "power_total")
    cp = None
    if ev:
        cp = _cp_label(ev.get("CpState", ev.get("cp_state")))
    return ChargerReading(
        power_w=power,
        session_kwh=session_wh / 1000 if session_wh is not None else None,
        total_kwh=total_wh / 1000 if total_wh is not None else None,
        cp_state=cp,
        raw={"meter": meter, "evinterface": ev},
    )


def fetch(host: str, token: str) -> ChargerReading:
    """Fetch a live reading from the Peblar charger at ``host`` (IP or hostname)."""
    import requests

    headers = {"Authorization": token}
    base = f"http://{host}{BASE_PATH}"

    meter = requests.get(f"{base}/meter", headers=headers, timeout=TIMEOUT)
    meter.raise_for_status()

    ev_data = None
    try:  # evinterface is a nice-to-have (charging state); don't fail without it
        ev = requests.get(f"{base}/evinterface", headers=headers, timeout=TIMEOUT)
        ev.raise_for_status()
        ev_data = ev.json()
    except Exception:  # noqa: BLE001
        ev_data = None

    return normalize(meter.json(), ev_data)
