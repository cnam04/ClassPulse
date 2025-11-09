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

# ------ Voting Keys--------- #
def K_votes(code): return f"session:{code}:votes"    # HASH: {not_confused, soso, confused}
def K_meta(code): return f"session:{code}:meta"     # HASH: {locked, participants, window_active, window_expires_at}
def K_voted(code): return f"session:{code}:voted"    # SET:  voter_id who already voted this window

# ------ Polling Keys--------- #
def K_poll(code): return f"session:{code}:poll"      # HASH: {active, question, yes, no, poll_id}
def K_poll_voted(code): return f"session:{code}:poll_voted" # SET: voter_ids who voted this poll

# --- Student-questions keys ---
def K_qperm(code): return f"session:{code}:qperm"       # STRING "0|1"
def K_qseq(code): return f"session:{code}:q:seq"       # COUNTER for question ids
def K_qindex(code): return f"session:{code}:q:index"     # LIST of qids (FIFO)
# Voter ID is anonymous to the teacher. it is stored to keep track of votes.
def K_qhash(code,qid): return f"session:{code}:q:{qid}"  # HASH: {id, text, ts, voter_id}

# --- Teacher-question keys ---
def K_broadcast(code): return f"session:{code}:broadcast" # String text
def K_broadcast_qid(code): return f"session:{code}:broadcast_qid"    # STRING qid or ''

def session_exists(code: str) -> bool:
    # exists if meta hash is present
    return r.exists(K_meta(code)) == 1


# ------- Session -------- #
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
    pipe.hset(K_meta(code),  mapping={"locked": 0, 
                                      "participants": 0, 
                                      "window_active": 0, 
                                      "window_expires_at": 0,
                                      "window_id":0
                                      })
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
    pipe.hincrby(K_meta(code), "window_id", 1) 
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

# ------ Voting--------- #
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
        "window_id":    int(meta.get("window_id", 0))
    }

# ------ Polling--------- #
def poll_start(code, question=""):
    # bump poll_id and (re)initialize counts; clear voted set
    pipe = r.pipeline()
    pipe.hincrby(K_poll(code), "poll_id", 1)
    pipe.hset(K_poll(code), mapping={
        "active": 1, "question": question or "", "yes": 0, "no": 0
    })
    pipe.delete(K_poll_voted(code))
    pipe.execute()

def poll_stop(code):
    r.hset(K_poll(code), "active", 0)

def poll_vote(code, choice, voter_id):
    if not voter_id:
        return False, "missing voter_id"
    poll = r.hgetall(K_poll(code)) or {}
    if poll.get("active") != "1":
        return False, "not active"
    if r.sismember(K_poll_voted(code), voter_id):
        return False, "already voted"
    field = "yes" if choice == "yes" else "no"
    pipe = r.pipeline()
    pipe.hincrby(K_poll(code), field, 1)
    pipe.sadd(K_poll_voted(code), voter_id)
    pipe.execute()
    return True, None

def poll_read(code):
    h = r.hgetall(K_poll(code)) or {}
    return {
        "active": h.get("active") == "1",
        "question": h.get("question", ""),
        "yes": int(h.get("yes", 0)),
        "no": int(h.get("no", 0)),
        "poll_id": int(h.get("poll_id", 0)),
    }

# ------ Student Questions--------- #
def set_qperm(code, allow: bool):
    r.set(K_qperm(code), "1" if allow else "0")

def get_qperm(code) -> bool:
    return (r.get(K_qperm(code)) or "0") == "1"

def add_student_question(code, text, voter_id):
    qid = r.incr(K_qseq(code))
    ts  = int(time())
    pipe = r.pipeline()
    pipe.hset(K_qhash(code, qid), mapping={
        "id": qid, "text": text, "ts": ts, "voter_id": voter_id or ""
    })
    pipe.rpush(K_qindex(code), qid)     # lol #CS2
    pipe.execute()
    return {"id": qid, "text": text, "ts": ts}

def list_student_questions(code):
    qids = [int(x) for x in r.lrange(K_qindex(code), 0, -1)]
    if not qids:
        return []
    pipe = r.pipeline()
    for qid in qids:
        pipe.hgetall(K_qhash(code, qid))
    rows = pipe.execute()
    # Normalize + keep only existing
    out = []
    for row in rows:
        if not row: 
            continue
        out.append({
            "id": int(row.get("id", 0)),
            "text": row.get("text", ""),
            "ts": int(row.get("ts", 0))
        })
    return out

def delete_student_question(code, qid: int):
    pipe = r.pipeline()
    pipe.lrem(K_qindex(code), 0, str(qid))
    pipe.delete(K_qhash(code, qid))
    pipe.execute()

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

#------Polling--------
@app.post("/api/session/<code>/poll/start")
def api_poll_start(code):
    q = (request.json or {}).get("question", "")
    poll_start(code, q)
    return jsonify({"ok": True})

@app.post("/api/session/<code>/poll/stop")
def api_poll_stop(code):
    poll_stop(code)
    return jsonify({"ok": True})

@app.get("/api/session/<code>/poll")
def api_poll_get(code):
    data = poll_read(code)
    resp = jsonify(data)
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.post("/api/session/<code>/poll/vote")
def api_poll_vote(code):
    payload = request.get_json(silent=True) or {}
    choice = (payload.get("choice") or "").lower()
    voter  = payload.get("voter_id")
    if choice not in ("yes","no"):
        return jsonify({"ok": False, "reason": "bad choice"}), 400
    ok, reason = poll_vote(code, choice, voter)
    if not ok:
        http = 409 if reason=="already voted" else 403 if reason=="not active" else 400
        return jsonify({"ok": False, "reason": reason}), http
    return jsonify({"ok": True})

#------Questions--------

@app.get("/api/session/<code>/question")
def api_get_broadcast(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    text = r.get(K_broadcast(code)) or ""
    qid  = r.get(K_broadcast_qid(code)) or ""
    return jsonify({"text": text, "qid": int(qid) if qid.isdigit() else None})

@app.post("/api/session/<code>/question")
def api_set_broadcast(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    qid  = payload.get("qid")
    pipe = r.pipeline()
    pipe.set(K_broadcast(code), text)
    if qid is None or text == "":
        pipe.delete(K_broadcast_qid(code))
    else:
        try:
            pipe.set(K_broadcast_qid(code), int(qid))
        except Exception:
            pipe.delete(K_broadcast_qid(code))
    pipe.execute()
    return jsonify({"ok": True})

@app.get("/api/session/<code>/qperm")
def api_qperm_get(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    return jsonify({"allow": get_qperm(code)})

@app.post("/api/session/<code>/qperm")
def api_qperm_set(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    payload = request.get_json(silent=True) or {}
    allow = bool(payload.get("allow"))
    set_qperm(code, allow)
    return jsonify({"ok": True, "allow": allow})


@app.post("/api/session/<code>/student_question")
def api_student_question(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    if not get_qperm(code):
        return jsonify({"error": "questions disabled"}), 403

    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    voter_id = (payload.get("voter_id") or "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400

    q = add_student_question(code, text, voter_id)

    # trims inbox to last n
    r.ltrim(K_qindex(code), -200, -1)
    return jsonify({"ok": True, "id": q["id"], "ts": q["ts"]})


@app.get("/api/session/<code>/student_questions")
def api_student_questions_list(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    return jsonify(list_student_questions(code))

@app.delete("/api/session/<code>/student_questions/<int:qid>")
def api_student_questions_delete(code, qid):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404

    # If the broadcast was showing this qid, clear it
    b_qid = r.get(K_broadcast_qid(code))
    if b_qid and b_qid.isdigit() and int(b_qid) == qid:
        pipe = r.pipeline()
        pipe.delete(K_broadcast(code))
        pipe.delete(K_broadcast_qid(code))
        pipe.execute()

    # Remove from inbox
    delete_student_question(code, qid)
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.getenv("PORT",5051))
    app.run(host="0.0.0.0", port=port)
