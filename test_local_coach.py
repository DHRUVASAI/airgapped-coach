"""Unit tests for local_coach.py — standard library only.

Run:  python test_local_coach.py
"""
import local_coach

SHOTS = [
    {"shot_type": "Speedup", "outcome": "Fault (Net)", "count": 6},
    {"shot_type": "Speedup", "outcome": "Winner", "count": 2},
    {"shot_type": "Speedup", "outcome": "In Play", "count": 2},
    {"shot_type": "Dink", "outcome": "Winner", "count": 5},
    {"shot_type": "Dink", "outcome": "In Play", "count": 5},
    {"shot_type": "Lob", "outcome": "Fault (Out)", "count": 1},
]

SESSIONS = [
    {"session_id": "g1", "player_score": 11, "bot_score": 8,
     "bot_difficulty": "4.5", "winner": "player", "rally_length": 9,
     "fault_type": "Out of Bounds", "coaching_summary": ""},
    {"session_id": "g2", "player_score": 6, "bot_score": 11,
     "bot_difficulty": "4.5", "winner": "bot", "rally_length": 5,
     "fault_type": "Net", "coaching_summary": ""},
    {"session_id": "g3", "player_score": 9, "bot_score": 11,
     "bot_difficulty": "5.0", "winner": "bot", "rally_length": 7,
     "fault_type": "Net", "coaching_summary": ""},
]


def test_shot_stats():
    s = local_coach.summarize_shots(SHOTS)
    assert s["total"] == 21, s
    assert s["by_type"]["Speedup"]["fault_rate"] == 60.0, s
    assert s["worst_shot"] == "Speedup", s
    assert s["best_shot"] == "Dink", s
    # Lob has only 1 sample: never qualifies as worst/best.
    assert s["by_type"]["Lob"]["total"] == 1
    empty = local_coach.summarize_shots([])
    assert empty["total"] == 0 and empty["worst_shot"] is None


def test_session_stats():
    s = local_coach.summarize_sessions(SESSIONS)
    assert (s["wins"], s["losses"], s["matches"]) == (1, 2, 3), s
    assert s["win_rate"] == 33.3, s
    assert s["avg_rally_length"] == 7.0, s
    assert s["common_fault"] == "Net" and s["common_fault_count"] == 2, s
    empty = local_coach.summarize_sessions([])
    assert empty["matches"] == 0 and empty["common_fault"] is None


def test_chat_record():
    ctx = {"courts": [], "bookings": [], "sessions": SESSIONS, "shots": SHOTS}
    ans = local_coach.local_chat_answer("how did I do?", ctx)
    assert "1W" in ans and "2L" in ans, ans
    assert "Net" in ans, ans  # most common fault is cited, not invented


def test_chat_courts_uses_real_data():
    ctx = {"courts": ["Court 1: Riverside ($30/hr)"],
           "bookings": ["Reserved: Court 1 on 2026-10-26 18:00"],
           "sessions": [], "shots": []}
    ans = local_coach.local_chat_answer("which courts are free?", ctx)
    assert "Riverside" in ans and "2026-10-26" in ans, ans
    # The old canned fallback hardcoded other court names; they must be gone.
    assert "Center Championship Court" not in ans


def test_chat_rules_and_empty():
    ctx = {"courts": [], "bookings": [], "sessions": [], "shots": []}
    assert "Non-Volley Zone" in local_coach.local_chat_answer(
        "explain the kitchen rule", ctx)
    ans = local_coach.local_chat_answer("how did I do?", ctx)
    assert "No completed matches" in ans, ans


def test_shot_tip():
    stats = local_coach.summarize_shots(SHOTS)
    tip = local_coach.local_shot_tip("Speedup", 45.0, "Topspin",
                                     "z_kitchen", "z_kitchen_opp", stats)
    assert "60.0% faulted" in tip and "40 mph" in tip, tip
    tip2 = local_coach.local_shot_tip("Dink", 19.0, "Flat",
                                      "z_kitchen", "z_kitchen_opp",
                                      local_coach.summarize_shots([]))
    assert "No history" in tip2, tip2


def test_rally_analysis():
    stats = local_coach.summarize_sessions(SESSIONS)
    a = local_coach.local_rally_analysis("bot", "Net", 12, 3, 4, stats)
    assert "Local Coach" in a and "longer than your average" in a, a
    assert "most common fault" in a, a
    b = local_coach.local_rally_analysis("player", "Out of Bounds", 3, 4, 4,
                                         stats)
    assert "shorter than your average" in b, b


if __name__ == "__main__":
    for name, fn in sorted(dict(globals()).items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("ALL LOCAL COACH TESTS PASSED")
