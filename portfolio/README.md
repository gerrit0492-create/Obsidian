# Gerrit Düthler — portfolio + private application tracker

Two small Streamlit apps in one folder:

| File | What | Who sees it |
| ---- | ---- | ----------- |
| `app.py` | **Public portfolio** — bilingual (NL/EN) one-pager | Deploy this; share the link |
| `tracker.py` | **Private application tracker** — who/what/when/status + follow-ups | You only; run locally |

## Edit your content
All portfolio text is in **`content.py`** — replace anything between `‹ ›`. Add a
square photo as `assets/photo.jpg` for a portrait (optional).

A clean, privacy-safe **CV PDF** (`assets/cv.pdf`, no address/phone/birth date) is
generated from `generate_cv.py`:
```bash
python generate_cv.py
```
Edit the data at the top of that file and re-run to update it.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py        # public portfolio
streamlit run tracker.py    # private tracker (separate window)
```

## The tracker stays private
- It is a **separate app**, not linked from the portfolio and **not deployed**, so
  visitors never see it.
- Its data lives in `data/applications.xlsx`, which is **git-ignored** — never
  committed or uploaded. (It also opens straight in Excel.)
- Optional extra lock: copy `.streamlit/secrets.toml.example` to
  `.streamlit/secrets.toml` and set `TRACKER_PASSWORD`.

In the tracker: add a row at the bottom, edit any cell (Status is a dropdown, dates
have a picker), then **Save**. The **Follow-ups** section lists upcoming actions with
overdue ones flagged 🔴.

## Deploy the portfolio (free)
Push the folder to a GitHub repo and point **Streamlit Community Cloud** at it with
`app.py` as the entry point. Because `tracker.py` isn't the entry point and isn't in a
`pages/` folder, it won't appear on the public site.
