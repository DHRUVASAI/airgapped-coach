# Airgapped Coach 🏓📴

**A Project Pioneer entry for Code Vipassana Season 16** — a pickleball
tactical coach that keeps coaching when the internet (and the Gemini API)
is gone.

## The idea in one line

The Season 16 Spanner Omni codelab builds a pickleball coach whose brain is
Gemini: no API key or no network, and the "coach" degrades to canned,
hardcoded text (including court names that may not even exist in your
database). **Airgapped Coach replaces that fallback with a real local
coach**: it computes its answers from the match sessions, shot telemetry,
courts, and bookings already stored in Spanner Omni — no network call, no
API key, zero new dependencies.

## What changed vs. the codelab

| Area | Codelab behaviour | Airgapped Coach |
|---|---|---|
| Chat with no Gemini | Canned text, hardcoded court names | Answers computed from live Spanner rows (real record, real courts, real bookings) |
| Shot coaching with no Gemini | Static per-shot-type blurb | Blurb + your own fault/win rates for that shot, speed-risk note |
| Rally analysis with no Gemini | Static point summary | Rally vs. your average rally length, recurring-fault detection |
| Coach selection | Implicit (Gemini if key present) | Explicit: `COACH_MODE=auto` (default) or `local`, plus a runtime endpoint |

New files: `local_coach.py` (the offline brain, standard library only),
`test_local_coach.py`, `smoke_test_offline.py`, `patch_app.py` (the exact
patch that turns the codelab's `app.py` into this one — reproducible and
auditable), `.env.example`, `BLOG.md`.

Patched in `app.py`: coach-mode machinery, `GET/POST /api/coach/mode`,
`coach_mode`/`coach_source` on `/api/status`, local fallback in
`/api/ai/chat`, local grounding in `/api/execute-shot` and
`/api/rally-end`. The frontend is untouched — it already renders the
`ai_source` label, so the UI itself shows "Local Coach (Offline,
Spanner-grounded)" when the local coach answers.

## Base credit

Built on the Season 16 codelab app by Abirami Sukumaran
([pickleball](https://github.com/AbiramiSukumaran/pickleball), Apache 2.0 —
see `LICENSE`). The original `.env` was deliberately **not** copied, so no
credentials from the base project are in this repo. The original arena,
physics, bot, and Spanner schema are unchanged.

## Run it

```bash
# 1. Spanner Omni (same as the codelab)
docker volume create spanner_omni_data
docker run -d --name spanner-omni \
  -p 9010:9010 -p 9020:9020 \
  -v spanner_omni_data:/spanner \
  us-docker.pkg.dev/spanner-omni/images/spanner-omni:2026.r2.1-beta \
  start-single-server

# 2. App
cp .env.example .env   # fill in your own values; Gemini key optional
pip install -r requirements.txt
python app.py
```

Open the arena (in Cloud Shell, use Web Preview on port 5000).

## Demo the airgapped mode (the Pioneer demo)

```bash
# No key at all, or force offline at runtime:
COACH_MODE=local python app.py
# ...or flip a running app without restarting:
curl -X POST localhost:5000/api/coach/mode \
  -H 'Content-Type: application/json' -d '{"mode": "local"}'
```

Then: play a rally, finish a point, and ask the chat "how did I do?".
Every answer cites your real Spanner numbers, and `/api/status` reports
`"coach_source": "local"`. Switch back with `{"mode": "auto"}`.

## Tests (all passing, no Spanner/Gemini needed)

```bash
python test_local_coach.py     # 7 unit tests: stats, answers, edge cases
python smoke_test_offline.py  # 5 API tests through the real Flask app
```

The unit tests and the offline API smoke tests pass. The Spanner-backed
query path (`_local_shot_stats`, `_local_session_rows`) is implemented and
code-reviewed but needs one live run with the container up to confirm
against real rows — see "Verify with Spanner" in `BLOG.md`.

## API additions

- `GET /api/status` → now includes `coach_mode`, `coach_source`.
- `GET/POST /api/coach/mode` → read/switch `auto` ↔ `local`.
- `/api/ai/chat`, `/api/execute-shot`, `/api/rally-end` → now include
  `coach_source` (`gemini` / `local` / `canned`) in responses.
