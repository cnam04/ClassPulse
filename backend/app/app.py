from flask import Flask, render_template,url_for, redirect, request
from string import ascii_uppercase
from random import choice
from threading import Lock
import time

app = Flask(__name__)

lock = Lock() # ensure threads don't overlap

#-------Session Storage--------#

sessions = {} # sessions storage

def gen_code():
    letters = ascii_uppercase
    return ''.join(choice(letters) for i in range(8))

def empty_confusion_counts():
    return {"not_confused" : 0, "confused" : 0, "so-so": 0}

def create_session():
    with lock:
        code = gen_code()
        while code in sessions: #jic
            code = gen_code()
        sessions[code] = {
            "locked": False,
            "participants":0,
            "confusion_vals" : empty_confusion_counts(),
            "window_active": False,
            "window_expires_at" : 0.0
        }
        return code
def get_session(code):
    return sessions.get(code)


# ----------- PAGES --------------------


@app.route('/')
def index():
    return render_template("index.html")

#----teacher----
@app.post("/teacher/start")
def teacher_start():
    code = create_session()
    return redirect(url_for("teacher_lobby", code=code))

@app.post("/teacher/<code>/lock")
def teacher_lock(code):
    s = get_session(code)
    if not s: return ("Session not found", 404)
    with lock:
        s["locked"]=True
    return redirect(url_for("teacher_understanding_check", code=code))
    

@app.get("/teacher/<code>")
def teacher_lobby(code):
    s = get_session(code)
    if not s: return ("Session not found", 404)
    return render_template("teacher_lobby.html", code=code, 
                           participants=s["participants"], 
                           locked = s["locked"])

@app.post("/teacher/<code>/check")
def call_understanding_check(code):
    s= get_session(code)
    if not s: return ("Session not found", 404)
    return render_template("teacher_understanding_check.html", code=code)

#----student----
@app.get("/student")
def student_join_page():
    return render_template("student_join.html", error=None)

@app.post("/student/join")
def student_join():
    code=(request.form.get("code")or "").strip()
    s= get_session(code)
    if not s: return render_template("student_join.html", error="Invalid Code")
    with lock:
        if s["locked"]:
            return render_template("student_join.html", error="Session has already started")
        s["participants"] += 1 
    return redirect(url_for("student_vote", code=code))

@app.get("/student/<code>/check")
def check_response(code):
    s= get_session(code)
    if not s: return("Session not found", 404)
    return render_template("student_vote.html",code=code)



if __name__ == '__main__':
    app.run(debug=True)
