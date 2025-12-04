from flask import render_template, redirect,url_for,request, Blueprint
from ..services.session import create_session, session_exists,inc_participants, is_locked, lock_session
from ..services.voting import read_stats

pages_bp = Blueprint("pages", __name__)

# ---- landing page ----
@pages_bp.route("/")
def index():
    return render_template("index.html")


# ---- teacher ----
@pages_bp.post("/teacher/start")
def teacher_start():
    code = create_session()
    return redirect(url_for("pages.teacher_lobby", code=code))


@pages_bp.get("/teacher/<code>")
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


@pages_bp.post("/teacher/<code>/lock")
def teacher_lock(code):
    if not session_exists(code):
        return ("Session not found", 404)
    lock_session(code)
    return redirect(url_for("pages.teacher_vote", code=code))


@pages_bp.get("/teacher/<code>/vote")
def teacher_vote(code):
    if not session_exists(code):
        return ("Session not found", 404)
    return render_template("teacher_vote.html", code=code)


# ---- student ----
@pages_bp.get("/student")
def student_join_page():
    return render_template("student_join.html", error=None)


@pages_bp.post("/student/join")
def student_join():
    code = (request.form.get("code") or "").strip()
    if not session_exists(code):
        return render_template("student_join.html", error="Invalid Code")
    if is_locked(code):
        return render_template("student_join.html", error="Session has already started")
    inc_participants(code)
    return redirect(url_for("pages.student_vote", code=code))

@pages_bp.get("/student/<code>/vote")
def student_vote(code):
    if not session_exists(code):
        return ("Session not found", 404)
    return render_template("student_vote.html", code=code)