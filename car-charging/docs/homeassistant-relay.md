# Home Assistant → cloud relay for the P1 meter

The hosted dashboard can't reach your meter's LAN address (`192.168.1.31`). This
recipe makes Home Assistant publish the meter reading to a small URL the app can
reach from anywhere, which you then set as `P1_REMOTE_URL`.

It republishes the reading as the **v1 P1 JSON shape** the app already parses
(`homewizard.fetch_url` → `normalize`): the keys `active_power_w`,
`total_power_import_kwh`, `total_power_export_kwh`.

## What you need
- Home Assistant (always-on at home) with the **HomeWizard Energy** integration
  added (Settings → Devices & services → Add integration → HomeWizard).
- A free **secret GitHub Gist** as the publish target.
- A GitHub **token** with only the `gist` scope.

> Privacy: a "secret" gist is unlisted, not private — anyone with the raw URL can
> read it. It exposes only your import/export totals and live power, and the URL
> lives in `P1_REMOTE_URL` (a secret), so it isn't shown in the app. Fine for this,
> but don't put anything more sensitive there.

## 1. Create the gist
1. Go to <https://gist.github.com>, create a **secret** gist with a file named
   `p1.json` containing `{}`, and save.
2. Note the **gist ID** (the hash in the URL) and your GitHub username.
3. The raw URL you'll use later is:
   `https://gist.githubusercontent.com/<username>/<gist_id>/raw/p1.json`

## 2. Create the token
GitHub → Settings → Developer settings → **Tokens (classic)** → generate a token
with the **`gist`** scope only. Copy it.

## 3. Home Assistant config
Find your real entity IDs first: **Developer tools → States**, filter on `p1` /
`import` / `export` / `power`, and swap them into the templates below.

`secrets.yaml`:
```yaml
github_gist_token: "Bearer ghp_your_token_here"
```

`configuration.yaml`:
```yaml
rest_command:
  publish_p1:
    url: https://api.github.com/gists/YOUR_GIST_ID
    method: PATCH
    headers:
      Authorization: !secret github_gist_token
      Accept: application/vnd.github+json
      User-Agent: home-assistant
    content_type: "application/json"
    payload: >-
      {
        "files": {
          "p1.json": {
            "content": "{\"active_power_w\": {{ states('sensor.p1_meter_active_power') | float(0) }}, \"total_power_import_kwh\": {{ states('sensor.p1_meter_energy_import') | float(0) }}, \"total_power_export_kwh\": {{ states('sensor.p1_meter_energy_export') | float(0) }}}"
          }
        }
      }
```

Automation (UI → Automations → new → edit in YAML, or `automations.yaml`):
```yaml
- alias: Publish P1 to gist
  trigger:
    - platform: time_pattern
      minutes: "/5"
  action:
    - service: rest_command.publish_p1
```

Restart HA (or reload YAML), then run the automation once and confirm the gist's
`p1.json` now shows real numbers.

## 4. Point the app at it
Add to your Streamlit secrets:
```toml
P1_REMOTE_URL = "https://gist.githubusercontent.com/<username>/<gist_id>/raw/p1.json"
```
Open **Home energy (HomeWizard P1)** in the app and click **Read P1 now** — the
relay URL is prefilled from the secret, so it works away from home. The gist raw
URL is cached for a minute or two, which is fine for a 5-minute relay.
