from flask import Flask, render_template, url_for, redirect, request, jsonify
from string import ascii_uppercase
from random import choice
from threading import Lock
from time import time 

app = Flask(__name__)


ALLOWED_STATUSES = {"not_confused", "confused", "soso"}

lock = Lock()

# ------- Session Storage -------- #
sessions = {}  # code -> session dict


def gen_code():
    letters = ascii_uppercase
    return "".join(choice(letters) for _ in range(8))


def empty_counts():
    return {"not_confused": 0, "confused": 0, "soso": 0}


def create_session():
    with lock:
        code = gen_code()
        while code in sessions:
            code = gen_code()
        sessions[code] = {
            "locked": False,
            "participants": 0,
            "votes": empty_counts(), 
            "window_active": False,
            "window_expires_at": 0.0,
        }
        return code


def get_session(code):
    return sessions.get(code)


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
    s = get_session(code)
    if not s:
        return ("Session not found", 404)
    return render_template(
        "teacher_lobby.html",
        code=code,
        participants=s["participants"],
        locked=s["locked"],
    )


@app.post("/teacher/<code>/lock")
def teacher_lock(code):
    s = get_session(code)
    if not s:
        return ("Session not found", 404)
    with lock:
        s["locked"] = True
    # Redirect to the teacher's understanding-check page
    return redirect(url_for("teacher_vote", code=code))


@app.get("/teacher/<code>/vote")
def teacher_vote(code):
    s = get_session(code)
    if not s:
        return ("Session not found", 404)
    return render_template("teacher_vote.html", code=code)


# ---- student ----
@app.get("/student")
def student_join_page():
    return render_template("student_join.html", error=None)


@app.post("/student/join")
def student_join():
    code = (request.form.get("code") or "").strip()
    s = get_session(code)
    if not s:
        return render_template("student_join.html", error="Invalid Code")
    with lock:
        if s["locked"]:
            return render_template(
                "student_join.html", error="Session has already started"
            )
        s["participants"] += 1
    # Send them to the vote page
    return redirect(url_for("student_vote", code=code))


@app.get("/student/<code>/vote")
def student_vote(code):
    s = get_session(code)
    if not s:
        return ("Session not found", 404)
    return render_template("student_vote.html", code=code)


#------voting--------
@app.post("/api/session/<code>/start_window")
def api_start_window(code):
    s = get_session(code)
    if not s:
        return jsonify({"error": "session not found"}), 404
    with lock:
        s["votes"] = empty_counts()  # fresh question segment
        s["window_active"] = True
        s["window_expires_at"] = time() + 60.0
    return jsonify({"ok": True, "seconds": 60})


@app.get("/api/session/<code>/stats")
def api_stats(code):
    s = get_session(code)
    if not s:
        return jsonify({"error": "session not found"}), 404
    with lock:
        remaining = 0
        if s["window_active"]:
            remaining = max(0, int(s["window_expires_at"] - time()))
            if remaining == 0:
                s["window_active"] = False
        data = {
            **s["votes"],
            "participants": s["participants"],
            "locked": s["locked"],
            "window_active": s["window_active"],
            "window_seconds_remaining": remaining,
        }
    return jsonify(data)


@app.post("/api/session/<code>/vote")
def api_vote(code):
    s = get_session(code)
    if not s:
        return jsonify({"error": "session not found"}), 404

    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").lower().replace("-", "_")

    if status not in ALLOWED_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(ALLOWED_STATUSES)}"}), 400

    with lock:
        if s["window_active"] and time() > s["window_expires_at"]:
            s["window_active"] = False
            return jsonify({"ok": False, "reason": "window closed"}), 403

        s["votes"][status] += 1

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
