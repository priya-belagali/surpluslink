# SurplusLink

Hotels, caterers and event kitchens list surplus cooked food. The best-matched NGO is offered it first;
if it does not respond in time, the offer moves to the next NGO. A volunteer or the NGO collects it, and every
delivery produces a record laid out in the format of FSSAI Schedule II.

## What it does

- **Matching with a visible cascade.** NGOs are ranked by distance, capacity and vehicle. Each listing has a live
  timeline showing every offer, who did not respond, and who claimed it.
- **Address search.** Donors and NGOs find their address on a map (OpenStreetMap Nominatim) instead of picking a city.
- **Surplus food record.** Donor licence and NGO registration numbers, batch reference, food temperature, quantity
  distributed and area distributed are captured, and a PDF can be downloaded for each delivery.
- **NGO approval checks.** NGOs give an FSSAI registration number and NGO Darpan ID; an administrator reviews them before
  approving. Darpan IDs are self-declared, so they are something to check, not proof.
- **Alerts.** In-app notifications always; SMS or WhatsApp through Twilio if configured. Donors can send a heads-up to
  the nearest NGOs based on tomorrow's forecast.
- **Coverage.** A map of kitchens and venues from OpenStreetMap next to the NGOs registered on the platform.
- **Impact.** Meals delivered, estimated food and emissions avoided, and a next-day forecast with a range.

## Where the intelligence is, and what it is not

- **Matching that learns.** From every past offer (accepted, declined, or never answered, and how long it took) the app
  estimates how likely each NGO is to accept and how long it typically wastes. That becomes a waiting penalty added to the
  distance rule. Estimates are smoothed so a few offers do not decide anything. Each donor can see the working under
  "Why NGOs are asked in this order", and Administration shows what has been learned. This is simple statistics (Bayesian
  smoothing), not a neural network.
- **A simulation of whether it helps.** On the Impact page, 400 synthetic listings are replayed under two policies,
  distance only and distance plus learning, against identical hidden NGO behaviour. In five runs with different seeds the
  learning policy waited less on average each time (by roughly 3 to 19 percent). The behaviour is invented, so this
  shows the idea works under stated assumptions, not that real NGOs behave this way.
- **A forecast that tests itself.** Tomorrow's surplus is the same-weekday average with days of no surplus counted as zero,
  with a range. The Impact page back-tests it over the last two weeks against assuming every day is average. A regression on
  weekday and trend was tried on demo-like data and did not beat the simple weekday average, so it is not used.
- **An optional language-model assistant.** If `ANTHROPIC_API_KEY` is set, a donor can describe the food in a sentence and the
  form is pre-filled. Every value is validated, the donor checks it before posting, and nothing is posted automatically.
  The text typed is sent to the Anthropic API.
- **Not AI:** the address search (OpenStreetMap), the distance formula, the safe-time table and the impact estimates are
  ordinary rules and lookups. The demo history is synthetic.

## Run it

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env   (then set ADMIN_PASSWORD)
python seed_demo.py           # optional demo data (password demo123, every name ends in "(demo)")
streamlit run Home.py         # http://localhost:8501
python worker.py              # optional second terminal: keeps the cascade moving when nobody is browsing
pytest                        # run the tests
```

An existing database is upgraded automatically on start: new columns are added in place.

## Show the cascade

1. In `.env` set `OFFER_TIMEOUT_SEC=90` and keep `DEMO_MODE=false`. Restart the app.
2. Sign in as a donor in one window and as two NGOs in others (after seeding: `donor1@demo.com`, `ngo1@demo.com`,
   `ngo2@demo.com`, password `demo123`).
3. Post food as the donor. The Overview page shows the timeline updating every few seconds as the offer passes from one
   NGO to the next.

## WhatsApp alerts with the Twilio sandbox

Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and `TWILIO_FROM=whatsapp:+14155238886` (the sandbox number shown in your
Twilio console), and `pip install twilio`. Each phone must first join the sandbox by sending the join code from the
console. Then use Administration, Test an alert. Phone numbers need the country code, for example `+91...`.

## Coverage map

Run `py scripts/fetch_places.py` once with internet access, or use Administration, Coverage data. It saves
`data/places.json`. The public Overpass servers are sometimes busy; try again later. Set `COVERAGE_CITY` and
`COVERAGE_RADIUS_KM` to change the area.

## Putting it online

Streamlit Community Cloud wipes local files on restart, so use a hosted PostgreSQL database and set `DATABASE_URL`
(starting `postgresql+psycopg2://`) in the app's Secrets together with `ADMIN_EMAIL` and `ADMIN_PASSWORD`. Set
`SEED_DEMO_ON_EMPTY=true` if you want the first screen to show history. Photos are stored on local disk, so they do not
survive a restart.

## Layout

```
Home.py                  entry point: setup, then a role-based menu
views/                   welcome, overview, post_food, find_food, activity, impact, coverage, admin
core/                    db, auth, matching, listings, records, geocode, places, forecast, impact, notify, safety, ui
core/style.css           the look; .streamlit/config.toml holds the base theme
scripts/fetch_places.py  downloads the coverage data
worker.py                background cascade and expiry (optional)
seed_demo.py             demo data
tests/                   pytest suite
```

## Limits to be honest about

- The planning limits in `core/safety.py` are defaults used to schedule pickups. They are not regulatory limits. Food
  safety remains the responsibility of the donor and the distribution organisation.
- The record is laid out like Schedule II but is not a legal certificate. Check the current regulation text and keep a
  signed copy.
- Login is demo-grade: no email verification, password reset or attempt limits.
- The forecast is a same-weekday average. It needs real history to mean anything.
- The coverage counts come from OpenStreetMap, which is volunteer-edited and incomplete.
