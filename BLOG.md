# Airgapped Coach: what if the AI coach has no internet?

*A Project Pioneer build on Code Vipassana Season 16's Spanner Omni
pickleball codelab.*

## The problem I noticed

Season 16 is about bringing data and AI to **airgapped, regulated
systems** — places where the network is not guaranteed. But the season's
own pickleball lab has a quiet contradiction: its coach is Gemini, and
when Gemini is unavailable the app falls back to canned text. Worse, the
chat fallback hardcodes court names ("Center Championship Court", ...)
that may not exist in your database at all. A coach that invents courts
is the opposite of grounded.

So the question became: **can the app keep coaching, truthfully, with
zero network and zero API key?**

## What I built

A local coach that answers from the data the app already owns:

- **Chat** — "how did I do?" returns your real Spanner record (wins,
  losses, average rally length, most common fault, last match), and court
  questions return your real courts and reservations.
- **Shot coaching** — every shot tip now carries your own fault/win rates
  for that shot type, plus a speed-risk note (the app's own 40 mph
  high-pressure threshold).
- **Rally analysis** — each point is compared against your average rally
  length, and a recurring fault is flagged as a pattern, not a one-off.
- **A real mode switch** — `COACH_MODE=auto` (Gemini first, local on any
  failure) or `COACH_MODE=local` (never call Gemini), flippable at runtime
  via `POST /api/coach/mode`. Every response carries `coach_source`, and
  the UI already displays the `ai_source` label, so a screenshot proves
  which coach answered.

The local brain is one file, `local_coach.py`, standard library only —
no new dependencies, no model download, nothing to configure. It refuses
to invent numbers: with no data it says "no matches recorded yet" instead
of fabricating a record, and a shot type needs at least 3 logged shots
before it becomes advice.

## Architecture

```
Browser arena (unchanged)
  → Flask app.py (patched: coach routing + /api/coach/mode)
    → Gemini 3.8 Flash        (auto mode, when available)
    → local_coach.py          (auto fallback, or forced local mode)
      → Spanner Omni rows     (GameSessions, Shots, Courts, Bookings)
```

The patch is fully reproducible: `patch_app.py` applies every change to
the codelab's `app.py` with assertions, so anyone can diff exactly what
moved. The frontend is untouched.

## Verified so far

- 7 unit tests for the local coach (stats, answers, empty-data behaviour).
- 5 offline API smoke tests through the real Flask app with **no
  Spanner, no Gemini key, no network** — status, mode switching, and all
  three coaching endpoints answer from local data.

## Verify with Spanner (one live run)

The Spanner-backed query path is implemented but still needs a live
confirmation run, since the build machine had no Docker:

1. Start the Spanner Omni container (see README).
2. Run the app, play two matches, finish several rallies.
3. `POST /api/coach/mode {"mode": "local"}`, then ask "how did I do?"
   and check the answer cites your real matches.
4. Flip back to `auto` and confirm Gemini answers return when the key
   is present.

## Why this matters beyond pickleball

The pattern generalises to exactly the season's theme: in a regulated
plant, a rural clinic, or a ship at sea, the database is local and the
model may not be. An agent whose fallback is canned text is a demo; an
agent whose fallback is computed from its own ground truth is a system
you can deploy. That is the difference this entry demonstrates.

## Credit

Built on Abirami Sukumaran's Season 16 codelab app (Apache 2.0). Arena,
physics, bot, and schema are the codelab's; the local coach, mode
switch, and tests are mine.
