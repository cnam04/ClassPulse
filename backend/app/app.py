from flask import Flask, render_template, url_for, redirect, request, jsonify
from string import ascii_uppercase
from random import choice
from threading import Lock
from time import time 
import os
import redis

app = Flask(__name__)


ALLOWED_STATUSES = {"not_confused", "confused", "soso"}

lock = Lock()

# ------- Session Storage -------- #
r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

def K_votes(code): return f"session:{code}:votes"    # HASH: {not_confused, soso, confused}
def K_meta(code):  return f"session:{code}:meta"     # HASH: {locked, participants, window_active, window_expires_at}
def K_voted(code): return f"session:{code}:voted"    # SET:  voter_id who already voted this window


def session_exists(code: str) -> bool:
    # exists if meta hash is present
    return r.exists(K_meta(code)) == 1



def gen_code():
    return ''.join(choice(ascii_uppercase) for _ in range(8))


def empty_counts():
    return {"not_confused": 0, "confused": 0, "soso": 0}



def create_session() -> str:
    # generate unique code and initialize all structures
    code = gen_code()
    while session_exists(code):
        code = gen_code()
    pipe = r.pipeline()
    pipe.hset(K_votes(code), mapping={"not_confused": 0, "soso": 0, "confused": 0})
    pipe.hset(K_meta(code),  mapping={"locked": 0, "participants": 0, "window_active": 0, "window_expires_at": 0})
    pipe.execute()
    return code

def is_locked(code) -> bool:
    return r.hget(K_meta(code), "locked") == "1"

def lock_session(code):
    r.hset(K_meta(code), "locked", 1)

def inc_participants(code):
    r.hincrby(K_meta(code), "participants", 1)

def start_window(code, seconds=60):
    expires = int(time()) + int(seconds)
    pipe = r.pipeline()
    pipe.hset(K_votes(code), mapping={"not_confused": 0, "soso": 0, "confused": 0})
    pipe.hset(K_meta(code),  mapping={"window_active": 1, "window_expires_at": expires})
    pipe.delete(K_voted(code))   # clear who already voted
    pipe.execute()

def _window_state(code):
    meta = r.hgetall(K_meta(code)) or {}
    active = meta.get("window_active") == "1"
    expires_at = int(meta.get("window_expires_at") or 0)
    remaining = max(0, expires_at - int(time()))
    if active and remaining == 0:
        # lazily close the window
        r.hset(K_meta(code), "window_active", 0)
        active = False
    return active, remaining

def record_vote(code, status, voter_id):
    # one vote per window; accept outside of a window if you want—here we enforce only within/while open
    if not voter_id:
        return False, "missing voter_id"

    # already voted this window?
    if r.sismember(K_voted(code), voter_id):
        return False, "already voted"

    active, remaining = _window_state(code)
    if active and remaining == 0:
        return False, "window closed"

    pipe = r.pipeline()
    pipe.hincrby(K_votes(code), status, 1)
    pipe.sadd(K_voted(code), voter_id)
    pipe.execute()
    return True, None

def read_stats(code):
    votes = r.hgetall(K_votes(code)) or {}
    meta  = r.hgetall(K_meta(code)) or {}
    active, remaining = _window_state(code)
    return {
        "not_confused": int(votes.get("not_confused", 0)),
        "soso":         int(votes.get("soso", 0)),
        "confused":     int(votes.get("confused", 0)),
        "participants": int(meta.get("participants", 0)),
        "locked":       meta.get("locked") == "1",
        "window_active": active,
        "window_seconds_remaining": remaining,
    }
# ----------- PAGES -------------------- #
@app.route("/")
def index():
    return render_template("index1.html")


# ---- teacher ----
@app.post("/teacher/start")
def teacher_start():
    code = create_session()
    return redirect(url_for("teacher_lobby", code=code))


@app.get("/teacher/<code>")
def teacher_lobby(code):
    if not session_exists(code):
        return ("Session not found", 404)
    stats = read_stats(code)
    return render_template(
        "teacher_lobby.html",
        code=code,
        participants=stats["participants"],
        locked=stats["locked"],
    )


@app.post("/teacher/<code>/lock")
def teacher_lock(code):
    if not session_exists(code):
        return ("Session not found", 404)
    lock_session(code)
    return redirect(url_for("teacher_vote", code=code))


@app.get("/teacher/<code>/vote")
def teacher_vote(code):
    if not session_exists(code):
        return ("Session not found", 404)
    return render_template("teacher_vote.html", code=code)


# ---- student ----
@app.get("/student")
def student_join_page():
    return render_template("student_join.html", error=None)


@app.post("/student/join")
def student_join():
    code = (request.form.get("code") or "").strip()
    if not session_exists(code):
        return render_template("student_join.html", error="Invalid Code")
    if is_locked(code):
        return render_template("student_join.html", error="Session has already started")
    inc_participants(code)
    return redirect(url_for("student_vote", code=code))

@app.get("/student/<code>/vote")
def student_vote(code):
    if not session_exists(code):
        return ("Session not found", 404)
    return render_template("student_vote.html", code=code)

#------voting--------
@app.post("/api/session/<code>/start_window")
def api_start_window(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    start_window(code, seconds=60)
    return jsonify({"ok": True, "seconds": 60})


@app.get("/api/session/<code>/stats")
def api_stats(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    resp=jsonify(read_stats(code))
    resp.headers["Cache-Control"]="no-store"
    return resp



@app.post("/api/session/<code>/vote")
def api_vote(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").lower().replace("-", "_")
    voter_id = payload.get("voter_id")
    if status not in ALLOWED_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(ALLOWED_STATUSES)}"}), 400

    ok, reason = record_vote(code, status, voter_id)
    if not ok:
        http = 409 if reason == "already voted" else 403 if reason == "window closed" else 400
        return jsonify({"ok": False, "reason": reason}), http
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT",5051))
    app.run(host="0.0.0.0", port=port)
