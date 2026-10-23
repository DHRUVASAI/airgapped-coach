"""Apply the Airgapped Coach patch to app.py.

Every replacement asserts its anchor exists exactly once, so a mismatch
fails loudly instead of silently producing a half-patched file.
Run from the project directory:  python patch_app.py
"""
import pathlib

path = pathlib.Path(__file__).with_name("app.py")
src = path.read_text()
orig = src


def rep(old, new, count=1):
    global src
    found = src.count(old)
    assert found == count, f"anchor found {found}x (expected {count}x): {old[:90]!r}"
    src = src.replace(old, new)


# --- 1. Coach machinery, inserted after the Gemini client init block -------
rep(
    '''        except Exception as e2:
            print(f"Warning initializing Gemini client: {e2}")

# Spanner Client & Database State''',
    '''        except Exception as e2:
            print(f"Warning initializing Gemini client: {e2}")

# ==========================================
# Airgapped Coach (Project Pioneer addition)
# ------------------------------------------
# COACH_MODE=auto   (default): use Gemini when available, fall back to the
#                   local Spanner-grounded coach on any failure or when no
#                   key is configured.
# COACH_MODE=local: never call Gemini; coach purely from Spanner data.
#                   This is the airgapped demo switch: the app keeps coaching
#                   with no network and no API key.
# The mode can also be flipped at runtime via /api/coach/mode.
# ==========================================
import local_coach

COACH_MODE = os.getenv("COACH_MODE", "auto").strip().lower()
if COACH_MODE not in ("auto", "local"):
    COACH_MODE = "auto"
COACH_MODE_RUNTIME = {"mode": COACH_MODE}


def get_coach_mode():
    return COACH_MODE_RUNTIME.get("mode", "auto")


def set_coach_mode(mode):
    mode = (mode or "").strip().lower()
    if mode not in ("auto", "local"):
        return False
    COACH_MODE_RUNTIME["mode"] = mode
    return True


def coach_client():
    """Gemini client, or None when the local coach is forced (or unset)."""
    if get_coach_mode() == "local":
        return None
    return ai_client


def coach_source():
    if get_coach_mode() == "local" or ai_client is None:
        return "local"
    return "gemini"


def _local_shot_stats():
    """Shot-type/outcome counts from Spanner; [] when unavailable."""
    db = get_spanner_db()
    if not db:
        return []
    try:
        with db.snapshot() as snapshot:
            rows = snapshot.execute_sql(
                "SELECT shot_type, outcome, count(*) as cnt "
                "FROM Shots GROUP BY shot_type, outcome LIMIT 50"
            )
            return [{"shot_type": r[0], "outcome": r[1], "count": int(r[2])}
                    for r in rows]
    except Exception as e:
        print(f"Local shot stats note: {e}")
        return []


def _local_session_rows():
    """Recent match sessions as dicts; mock sessions when Spanner is down."""
    db = get_spanner_db()
    if db:
        try:
            with db.snapshot() as snapshot:
                rows = snapshot.execute_sql(
                    "SELECT session_id, player_score, bot_score, bot_difficulty, "
                    "winner, rally_length, fault_type, coaching_summary, created_at "
                    "FROM GameSessions ORDER BY created_at DESC LIMIT 20"
                )
                keys = ("session_id", "player_score", "bot_score",
                        "bot_difficulty", "winner", "rally_length",
                        "fault_type", "coaching_summary", "created_at")
                return [dict(zip(keys, r)) for r in rows]
        except Exception as e:
            print(f"Local session stats note: {e}")
    return [dict(s) for s in mock_game_sessions]


# Spanner Client & Database State''')

# --- 2. /api/status reports the coach mode --------------------------------
rep(
    '''        "gemini_configured": bool(GEMINI_API_KEY)
    })''',
    '''        "gemini_configured": bool(GEMINI_API_KEY),
        "coach_mode": get_coach_mode(),
        "coach_source": coach_source()
    })''')

# --- 3. Runtime mode endpoint, before /api/spanner/init --------------------
rep(
    '''@app.route("/api/spanner/init", methods=["POST"])''',
    '''@app.route("/api/coach/mode", methods=["GET", "POST"])
def api_coach_mode():
    """Read or switch the coach at runtime.

    POST {"mode": "local"} forces the offline coach (the airgapped demo);
    POST {"mode": "auto"} restores Gemini-first with local fallback.
    """
    if request.method == "POST":
        data = request.json or {}
        if not set_coach_mode(data.get("mode", "")):
            return jsonify({"error": "mode must be 'auto' or 'local'"}), 400
    return jsonify({
        "coach_mode": get_coach_mode(),
        "coach_source": coach_source(),
        "gemini_configured": bool(ai_client),
        "note": ("local mode coaches purely from Spanner data with no network "
                 "call; auto uses Gemini when available and falls back to "
                 "local otherwise.")
    })


@app.route("/api/spanner/init", methods=["POST"])''')

# --- 4a. Chat: capture structured rows alongside the display strings -------
rep(
    '''    courts_context = []
    bookings_context = []
    sessions_context = []
    shots_context = []''',
    '''    courts_context = []
    bookings_context = []
    sessions_context = []
    shots_context = []
    session_rows = []
    shot_rows = []''')

rep(
    '''                        sessions_context.append(
                            f"Match {s[0]}: Player {s[1]} - OmniBot {s[2]} (Bot DUPR: {s[3]}, Winner: {s[4]}, Rally Length: {s[5]} shots, Concluding Fault: {s[6]}). Tactical Note: {s[7][:120]}..."
                        )''',
    '''                        sessions_context.append(
                            f"Match {s[0]}: Player {s[1]} - OmniBot {s[2]} (Bot DUPR: {s[3]}, Winner: {s[4]}, Rally Length: {s[5]} shots, Concluding Fault: {s[6]}). Tactical Note: {s[7][:120]}..."
                        )
                        session_rows.append({
                            "session_id": s[0], "player_score": s[1],
                            "bot_score": s[2], "bot_difficulty": s[3],
                            "winner": s[4], "rally_length": s[5],
                            "fault_type": s[6], "coaching_summary": s[7],
                        })''')

rep(
    '''                        shots_context.append(f"{st[0]} ({st[1]}): {st[2]} times")''',
    '''                        shots_context.append(f"{st[0]} ({st[1]}): {st[2]} times")
                        shot_rows.append({"shot_type": st[0], "outcome": st[1],
                                          "count": int(st[2])})''')

rep(
    '''    if not sessions_context and mock_game_sessions:
        for s in mock_game_sessions[:8]:
            sessions_context.append(
                f"Match {s['session_id']}: Player {s['player_score']} - OmniBot {s['bot_score']} (Bot DUPR: {s['bot_difficulty']}, Winner: {s['winner']}, Rally Length: {s['rally_length']} shots, Concluding Fault: {s['fault_type']}). Tactical Note: {s['coaching_summary'][:120]}..."
            )''',
    '''    if not sessions_context and mock_game_sessions:
        for s in mock_game_sessions[:8]:
            sessions_context.append(
                f"Match {s['session_id']}: Player {s['player_score']} - OmniBot {s['bot_score']} (Bot DUPR: {s['bot_difficulty']}, Winner: {s['winner']}, Rally Length: {s['rally_length']} shots, Concluding Fault: {s['fault_type']}). Tactical Note: {s['coaching_summary'][:120]}..."
            )
            session_rows.append(dict(s))''')

# --- 4b. Chat: route Gemini through coach_client() ---------------------------
rep(
    '''    if ai_client:
        try:
            if hasattr(ai_client, "models"):
                res = ai_client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=f"{system_instruction}\\n\\nUser Question: {user_prompt}"
                )
                return jsonify({
                    "response": res.text,
                    "ai_source": "Gemini 3.8 Flash",
                    "spanner_synced": True
                })
            elif hasattr(ai_client, "generate_content"):
                res = ai_client.generate_content(f"{system_instruction}\\n\\nUser Question: {user_prompt}")
                return jsonify({
                    "response": res.text,
                    "ai_source": "Gemini 1.5 Flash (Live API)",
                    "spanner_synced": True
                })
        except Exception as e:
            print(f"Gemini API invocation note: {e}")''',
    '''    _client = coach_client()
    if _client:
        try:
            if hasattr(_client, "models"):
                res = _client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=f"{system_instruction}\\n\\nUser Question: {user_prompt}"
                )
                return jsonify({
                    "response": res.text,
                    "ai_source": "Gemini 3.8 Flash",
                    "coach_source": "gemini",
                    "spanner_synced": True
                })
            elif hasattr(_client, "generate_content"):
                res = _client.generate_content(f"{system_instruction}\\n\\nUser Question: {user_prompt}")
                return jsonify({
                    "response": res.text,
                    "ai_source": "Gemini 1.5 Flash (Live API)",
                    "coach_source": "gemini",
                    "spanner_synced": True
                })
        except Exception as e:
            print(f"Gemini API invocation note: {e}")''')

# --- 4c. Chat: replace the canned fallback with the local coach -------------
start_marker = "    # Fallback simulated response"
end_marker = '''    return jsonify({
        "response": resp,
        "ai_source": "Spanner Omni AI Engine",
        "spanner_synced": True
    })'''
start = src.index(start_marker)
end = src.index(end_marker) + len(end_marker)
replacement = '''    # Airgapped fallback: answers computed from the Spanner grounding
    # context above — no canned court names, no network call.
    ctx = {
        "courts": courts_context,
        "bookings": bookings_context,
        "sessions": session_rows,
        "shots": shot_rows,
    }
    resp = local_coach.local_chat_answer(user_prompt, ctx)
    return jsonify({
        "response": resp,
        "ai_source": "Local Coach (Offline, Spanner-grounded)",
        "coach_source": "local",
        "spanner_synced": True
    })'''
src = src[:start] + replacement + src[end:]

# --- 5. Execute-shot: Gemini through coach_client() + local tip ------------
rep(
    '''    agent_text = tactical_feedback
    if ai_client:
        try:
            prompt = f"""
            You are the OmniBot AI Pickleball Coach running on Spanner Omni.''',
    '''    agent_text = tactical_feedback
    _client = coach_client()
    if _client:
        try:
            prompt = f"""
            You are the OmniBot AI Pickleball Coach running on Spanner Omni.''')

rep(
    '''            if hasattr(ai_client, "models"):
                res = ai_client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
                if res.text:
                    agent_text = res.text
            elif hasattr(ai_client, "generate_content"):
                res = ai_client.generate_content(prompt)
                if res.text:
                    agent_text = res.text
        except Exception as e:
            print(f"Gemini live coaching note: {e}")''',
    '''            if hasattr(_client, "models"):
                res = _client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
                if res.text:
                    agent_text = res.text
            elif hasattr(_client, "generate_content"):
                res = _client.generate_content(prompt)
                if res.text:
                    agent_text = res.text
        except Exception as e:
            print(f"Gemini live coaching note: {e}")

    # Airgapped enhancement: if Gemini did not enhance the feedback (local
    # mode, no key, or a failed call), ground it in the player's own Spanner
    # shot history instead of leaving canned text.
    if agent_text == tactical_feedback:
        try:
            _stats = local_coach.summarize_shots(_local_shot_stats())
            agent_text = local_coach.local_shot_tip(
                user_shot, speed, spin, from_zone, to_zone, _stats
            ) + "\\n\\n" + agent_text
            coach_used = "local"
        except Exception as e_local:
            print(f"Local shot coach note: {e_local}")
            coach_used = "canned"
    else:
        coach_used = "gemini"''')

rep(
    '''        "coaching_analysis": agent_text,''',
    '''        "coaching_analysis": agent_text,
        "coach_source": coach_used,''')

# --- 6a. Rally-end: capture the pre-Gemini analysis for change detection -----
rep(
    '''    analysis = (
        f"🏆 Point won by **{'You' if winner == 'player' else bot_label}** after a **{rally_length}-shot rally**!\\n"
        f"Fault: *{fault_type}*.\\n"
        f"Score is now **You: {user_score} | {bot_label}: {bot_score}**."
    )''',
    '''    analysis = (
        f"🏆 Point won by **{'You' if winner == 'player' else bot_label}** after a **{rally_length}-shot rally**!\\n"
        f"Fault: *{fault_type}*.\\n"
        f"Score is now **You: {user_score} | {bot_label}: {bot_score}**."
    )
    _base_analysis = analysis
    _coach_used = "local"''')

# --- 6b. Rally-end: Gemini through coach_client(), track enhancement --------
rep(
    '''        try:
            if hasattr(ai_client, "models"):
                res = ai_client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
                if res.text:
                    analysis = res.text
            elif hasattr(ai_client, "generate_content"):
                res = ai_client.generate_content(prompt)
                if res.text:
                    analysis = res.text
        except Exception as e:
            print(f"Gemini rally analysis note: {e}")''',
    '''        try:
            if hasattr(_client, "models"):
                res = _client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
                if res.text:
                    analysis = res.text
            elif hasattr(_client, "generate_content"):
                res = _client.generate_content(prompt)
                if res.text:
                    analysis = res.text
        except Exception as e:
            print(f"Gemini rally analysis note: {e}")
        _coach_used = "gemini" if analysis != _base_analysis else "local"''')

# The rally-end Gemini block sits under `if ai_client:`; switch it over.
# Its `if ai_client:` line is the one directly preceding the referee prompt.
rep(
    '''    if ai_client:
        prompt = f"""
        You are the official Gemini AI Pickleball Coach & Tournament Referee running on Spanner Omni.''',
    '''    _client = coach_client()
    if _client:
        prompt = f"""
        You are the official Gemini AI Pickleball Coach & Tournament Referee running on Spanner Omni.''')

# --- 6c. Rally-end: local analysis when Gemini did not enhance ---------------
rep(
    '''    session_id = f"game_{int(time.time() * 1000)}"''',
    '''    if _coach_used == "local":
        try:
            _sess_stats = local_coach.summarize_sessions(_local_session_rows())
            analysis = local_coach.local_rally_analysis(
                winner, fault_type, rally_length, user_score, bot_score, _sess_stats
            )
        except Exception as e_local:
            print(f"Local rally coach note: {e_local}")

    session_id = f"game_{int(time.time() * 1000)}"''')

rep(
    '''    return jsonify({
        "status": "success",
        "analysis": analysis,
        "spanner_committed": spanner_committed
    })''',
    '''    return jsonify({
        "status": "success",
        "analysis": analysis,
        "coach_source": _coach_used,
        "spanner_committed": spanner_committed
    })''')

assert src != orig, "patch produced no changes"
path.write_text(src)
print("patched OK")
