"""Offline smoke test for the patched Flask app.

No Spanner, no Gemini key, no network: the app must still serve the arena
endpoints and answer every coaching question from local data.

Run:  python smoke_test_offline.py   (needs flask + python-dotenv installed)
"""
import os
import sys

# No key on purpose: this is the airgapped configuration under test.
os.environ.pop("GEMINI_API_KEY", None)
os.environ["COACH_MODE"] = "local"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as arena  # noqa: E402

client = arena.app.test_client()

status = client.get("/api/status").get_json()
assert status["coach_mode"] == "local", status
assert status["coach_source"] == "local", status
assert status["spanner_connected"] is False, status
print("PASS status reports local coach, no Spanner, no key")

mode = client.post("/api/coach/mode", json={"mode": "local"}).get_json()
assert mode["coach_mode"] == "local", mode
bad = client.post("/api/coach/mode", json={"mode": "banana"})
assert bad.status_code == 400, bad.status_code
print("PASS coach mode endpoint accepts local, rejects invalid modes")

rally = client.post("/api/rally-end", json={
    "winner": "player", "fault_type": "Out of Bounds", "rally_length": 9,
    "shot_sequence": [], "user_score": 3, "bot_score": 2,
    "bot_difficulty": "4.5",
}).get_json()
assert rally["coach_source"] == "local", rally
assert "Local Coach" in rally["analysis"], rally
print("PASS rally-end answered by local coach:", rally["analysis"][:80])

chat = client.post("/api/ai/chat", json={
    "prompt": "how did I do?"}).get_json()
assert chat["coach_source"] == "local", chat
assert "Local Coach" in chat["ai_source"], chat
assert "1W" in chat["response"], chat["response"]
print("PASS chat cites the real 1W record from the mock session")

shot = client.post("/api/execute-shot", json={
    "shot_type": "Shoulder Speedup", "from_zone": "z_kitchen",
    "to_zone": "z_kitchen_opp", "speed_mph": 45.0, "spin": "Topspin",
}).get_json()
assert shot["coach_source"] == "local", shot
assert "Local Coach" in shot["coaching_analysis"], shot
print("PASS execute-shot answered by local coach")

print("ALL OFFLINE SMOKE TESTS PASSED")
