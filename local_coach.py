"""Airgapped Coach: a local, Spanner-grounded pickleball coach.

This module is the original contribution of the "Airgapped Coach" Project
Pioneer entry (Code Vipassana Season 16). It answers coaching questions
using ONLY data already stored in Spanner Omni (match sessions, shot
telemetry, courts, bookings) plus deterministic pickleball rules. It makes
no network call, needs no API key, and imports nothing beyond the standard
library, so the app keeps coaching even when the Gemini API is unreachable,
unconfigured, or deliberately switched off (COACH_MODE=local).

Design rules:
- Never invent numbers. Every statistic comes from the rows passed in.
- Empty data degrades to honest "no matches recorded yet" guidance, never
  to fabricated records or hardcoded court names.
- Outcome strings come from the app itself: 'Winner', 'In Play', and
  'Fault (<type>)' for faulted shots.
"""

from collections import Counter

# The app marks high-pressure transitions at speeds above this threshold
# (see ShotTransitions pressure_level in app.py). Reused, not reinvented.
HIGH_SPEED_MPH = 40.0


def _is_fault(outcome):
    return isinstance(outcome, str) and outcome.strip().lower().startswith("fault")


def _is_winner(outcome):
    return isinstance(outcome, str) and outcome.strip().lower() == "winner"


def _pct(part, whole):
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)


# --------------------------------------------------------------------------
# Statistics builders (pure functions over rows the app already fetches)
# --------------------------------------------------------------------------

def summarize_shots(shot_rows):
    """shot_rows: iterable of dicts with shot_type, outcome, count.

    Returns per-shot-type totals plus the most/least reliable shot types.
    A shot type only qualifies as 'most fault-prone' / 'most reliable' with
    at least 3 recorded shots, so one lucky shot never becomes advice.
    """
    by_type = {}
    total = 0
    for row in shot_rows or []:
        stype = row.get("shot_type") or "Unknown"
        count = int(row.get("count") or 0)
        outcome = row.get("outcome") or ""
        entry = by_type.setdefault(stype, {"total": 0, "faults": 0, "winners": 0})
        entry["total"] += count
        if _is_fault(outcome):
            entry["faults"] += count
        elif _is_winner(outcome):
            entry["winners"] += count
        total += count
    for stype, entry in by_type.items():
        entry["fault_rate"] = _pct(entry["faults"], entry["total"])
        entry["winner_rate"] = _pct(entry["winners"], entry["total"])
    qualified = {k: v for k, v in by_type.items() if v["total"] >= 3}
    worst = None
    best = None
    if qualified:
        worst = max(qualified.items(), key=lambda kv: kv[1]["fault_rate"])[0]
        best = max(qualified.items(), key=lambda kv: kv[1]["winner_rate"])[0]
    return {"total": total, "by_type": by_type, "worst_shot": worst, "best_shot": best}


def summarize_sessions(session_rows):
    """session_rows: iterable of dicts with winner, rally_length, fault_type,
    player_score, bot_score, bot_difficulty. Works for Spanner tuples mapped
    to dicts and for the app's in-memory mock sessions (same keys)."""
    rows = list(session_rows or [])
    wins = sum(1 for r in rows if r.get("winner") == "player")
    losses = sum(1 for r in rows if r.get("winner") not in (None, "player"))
    rally_lengths = [int(r["rally_length"]) for r in rows
                     if r.get("rally_length") is not None]
    faults = Counter(r.get("fault_type") for r in rows if r.get("fault_type"))
    return {
        "matches": len(rows),
        "wins": wins,
        "losses": losses,
        "win_rate": _pct(wins, len(rows)),
        "avg_rally_length": round(sum(rally_lengths) / len(rally_lengths), 1) if rally_lengths else 0,
        "common_fault": faults.most_common(1)[0][0] if faults else None,
        "common_fault_count": faults.most_common(1)[0][1] if faults else 0,
        "last": rows[0] if rows else None,
    }


# --------------------------------------------------------------------------
# Answers
# --------------------------------------------------------------------------

KITCHEN_RULES = (
    "📖 **Pickleball Rule Pro-Tip: The Non-Volley Zone (The Kitchen)**\n\n"
    "1. **No volleys inside the kitchen**: you cannot hit the ball out of the air "
    "while standing in the 7-foot zone or on its line.\n"
    "2. **Momentum counts**: if momentum carries your foot into the kitchen after "
    "a volley, it is a fault.\n"
    "3. **Bounces allowed**: if the ball bounces in the kitchen first, you can "
    "legally step in and return it.\n"
    "4. **Two-bounce rule**: each side must let the ball bounce once before volleys "
    "are allowed — the serve and the return both bounce."
)


def _record_section(sess):
    if sess["matches"] == 0:
        return ("No completed matches recorded yet in Spanner. Play a match "
                "against OmniBot first — every rally you finish becomes the "
                "ground truth this coach learns from.")
    last = sess["last"]
    lines = [
        f"🏓 **Your record (from Spanner match history): {sess['wins']}W – {sess['losses']}L "
        f"across {sess['matches']} match(es) ({sess['win_rate']}% wins).**",
        f"- Average rally length: {sess['avg_rally_length']} shots.",
    ]
    if sess["common_fault"]:
        lines.append(
            f"- Most common way points end: **{sess['common_fault']}** "
            f"({sess['common_fault_count']} time(s))."
        )
    if last:
        lines.append(
            f"- Last match: You {last.get('player_score')} – OmniBot {last.get('bot_score')} "
            f"(Bot DUPR {last.get('bot_difficulty')}, winner: {last.get('winner')})."
        )
    if sess["common_fault"]:
        lines.append(
            f"\n💡 **Coach's take:** your recurring fault is {sess['common_fault']}. "
            "In your next match, play one gear safer on the shots that produce it "
            "and extend rallies instead of forcing winners."
        )
    return "\n".join(lines)


def _shot_section(shot_stats):
    if shot_stats["total"] == 0:
        return ("No individual shot stats recorded yet. Shot advice appears here "
                "once rallies are logged to Spanner.")
    lines = [f"🎯 **Shot telemetry ({shot_stats['total']} shots logged):**"]
    for stype, entry in sorted(shot_stats["by_type"].items(),
                               key=lambda kv: -kv[1]["total"]):
        lines.append(
            f"- {stype}: {entry['total']} shots, {entry['fault_rate']}% faulted, "
            f"{entry['winner_rate']}% winners."
        )
    if shot_stats["worst_shot"]:
        w = shot_stats["by_type"][shot_stats["worst_shot"]]
        lines.append(
            f"\n⚠️ **Watch out:** {shot_stats['worst_shot']} faults {w['fault_rate']}% "
            "of the time — the weakest link in your game. Drill it slower before "
            "using it under pressure."
        )
    if shot_stats["best_shot"]:
        b = shot_stats["by_type"][shot_stats["best_shot"]]
        lines.append(
            f"✅ **Lean on:** {shot_stats['best_shot']} wins {b['winner_rate']}% "
            "of its points — build rallies that set this shot up."
        )
    return "\n".join(lines)


def local_chat_answer(prompt, ctx):
    """Answer a concierge/coach question from Spanner-grounded context only.

    ctx keys: courts (list of preformatted strings), bookings (list of
    preformatted strings), sessions (list of dicts), shots (list of dicts).
    """
    p = (prompt or "").lower()
    sess = summarize_sessions(ctx.get("sessions"))
    shot_stats = summarize_shots(ctx.get("shots"))
    courts = ctx.get("courts") or []
    bookings = ctx.get("bookings") or []

    if any(k in p for k in ("how did i do", "my record", "performance",
                            "win", "lost", "won", "match histor")):
        return _record_section(sess) + "\n\n" + _shot_section(shot_stats)
    if any(k in p for k in ("court", "book", "availab", "rate", "indoor", "recommend")):
        lines = ["🏓 **Courts & live availability (from Spanner):**"]
        lines += [f"- {c}" for c in courts] if courts else ["- No courts listed yet."]
        if bookings:
            lines.append("\n**Confirmed reservations:**")
            lines += [f"- {b}" for b in bookings]
        else:
            lines.append("\nNo confirmed reservations right now — courts are open.")
        return "\n".join(lines)
    if any(k in p for k in ("kitchen", "rule", "nvz", "serve", "bounce", "fault")):
        return KITCHEN_RULES
    if any(k in p for k in ("shot", "dink", "speedup", "lob", "drop", "technique", "improve")):
        return _shot_section(shot_stats)
    lines = [
        "🏓 **Spanner Omni Local Coach (offline mode)**",
        f"- Courts on record: {len(courts)}.",
        f"- Confirmed bookings: {len(bookings)}.",
        f"- Matches logged: {sess['matches']} ({sess['wins']}W – {sess['losses']}L).",
        f"- Shots logged: {shot_stats['total']}.",
        "",
        "Ask me about your record, your shots, court availability, or the "
        "kitchen rules — every answer comes from your own Spanner data, "
        "no internet required.",
    ]
    return "\n".join(lines)


def local_shot_tip(shot_type, speed_mph, spin, from_zone, to_zone, shot_stats):
    """Data-driven tip for one executed shot. shot_stats is the output of
    summarize_shots() (or an empty summary when Spanner has no shots yet)."""
    stype = shot_type or "Unknown shot"
    entry = (shot_stats or {}).get("by_type", {}).get(stype)
    has_history = bool(entry and entry["total"] >= 3)
    tips = [f"📴 **Local Coach · offline** — {stype} at {speed_mph} mph ({spin})."]
    if has_history:
        tips.append(
            f"Your history with this shot: {entry['total']} logged, "
            f"{entry['fault_rate']}% faulted, {entry['winner_rate']}% winners."
        )
        if entry["fault_rate"] >= 40:
            tips.append(
                "This is a high-fault shot for you — play it slower and aim "
                "for placement over pace until the fault rate drops."
            )
        elif entry["winner_rate"] >= 30:
            tips.append("This shot wins points for you — keep setting it up.")
    if (speed_mph or 0) > HIGH_SPEED_MPH:
        tips.append(
            f"At {speed_mph} mph this is a high-pressure ball (the app's own "
            "threshold is 40 mph) — a fast ball that sits up gets punished, "
            "so aim low at the opponent's feet."
        )
    if "kitchen" in (to_zone or "").lower():
        tips.append(
            "Kitchen placement: keep your paddle out in front and stay patient "
            "— the soft game rewards control, not power."
        )
    if not has_history:
        tips.append(
            "No history on this shot yet — play a few rallies and this coach "
            "will start advising from your real numbers."
        )
    return " ".join(tips)


def local_rally_analysis(winner, fault_type, rally_length, user_score, bot_score, session_stats):
    """Data-driven rally breakdown. session_stats is summarize_sessions()
    output for matches BEFORE this rally's session is stored (or including
    it — either way the comparisons stay honest)."""
    stats = session_stats or {}
    avg = stats.get("avg_rally_length") or 0
    who = "You" if winner == "player" else "OmniBot"
    lines = [
        f"📴 **Local Coach · offline** — Point to **{who}** after a "
        f"**{rally_length}-shot rally** (fault: {fault_type}). "
        f"Score: You {user_score} – OmniBot {bot_score}.",
    ]
    if avg:
        if rally_length > avg:
            lines.append(
                f"This rally ran longer than your average ({avg} shots) — "
                "patience won the point here; long rallies suit your game."
            )
        elif rally_length < avg:
            lines.append(
                f"This was shorter than your average rally ({avg} shots) — "
                "quick points usually mean someone forced the issue early."
            )
    common = stats.get("common_fault")
    if common and fault_type and common.lower() in str(fault_type).lower():
        lines.append(
            f"Note: {fault_type} is also your most common fault overall "
            f"({stats.get('common_fault_count', 0)} time(s)) — this is the "
            "pattern to drill, not a one-off."
        )
    return " ".join(lines)
