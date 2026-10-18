# SurplusLink

Hotels, caterers and canteens post surplus food; verified NGOs claim it; volunteers transport it.

**Features:** role-based accounts · NGO verification by admin · food-safety "safe until" countdowns ·
smart matching with 15-minute escalation · one-tap repeat donation · in-app (and optional
SMS/WhatsApp) notifications · impact reports · simple next-day surplus forecast.

## Quick start

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env   (then edit ADMIN_PASSWORD)
python seed_demo.py           # optional demo data (password for all demo users: demo123)
streamlit run Home.py         # opens http://localhost:8501
python worker.py              # optional 2nd terminal: escalation while nobody is browsing
pytest                        # run the tests
```

Set `DEMO_MODE=true` in `.env` while testing so every NGO sees every open listing immediately.

Demo logins (after seeding): `donor1@demo.com`, `ngo1@demo.com`, `vol1@demo.com`, plus the admin from `.env`
(default `admin@example.com` / `admin123`, change it).

## Layout

```
Home.py                  entry point: setup, then a role-based navigation menu
views/                   welcome, overview, post_food, find_food, activity, impact, admin
core/                    db models, auth, matching, listings, safety, impact, forecast, notify, ui
core/style.css           the visual theme (colours, type, cards); edit this to restyle the app
.streamlit/config.toml   base theme and toolbar settings
worker.py                background escalation and expiry (optional)
seed_demo.py             demo data
tests/                   pytest suite
```

## Important limitations (read before real use)

- Safe-hours in `core/safety.py` are illustrative defaults, not legal or medical advice. Check FSSAI
  guidance on surplus food recovery and agree handling rules with your NGO partners.
- Authentication is demo-grade (no email verification, no password reset, no rate limiting).
- SQLite + one Streamlit process is fine for a demo; use Postgres and proper auth for production.
- Real WhatsApp alerts need the WhatsApp Business API (via Twilio). Leave Twilio unset to use in-app alerts only.
- Impact numbers use rough constants from `core/config.py`.
