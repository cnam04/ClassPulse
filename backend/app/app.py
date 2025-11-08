from flask import Flask, render_template,url_for
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

def empty_vote_counts():
    return {"not_confused" : 0, "confused" : 0, "so-so": 0}

def create_session():
    with lock:
        code = gen_code()
        while code in sessions: #jic
            code = gen_code()
        sessions[code] = {
            "locked": False,
            "participants":0,
            "votes" : empty_vote_counts(),
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
    return(
        {"code":code, "redirect": url_for("teacher_lobby", code=code)},
        201, # this is the "created" code
        {"Location": url_for("teacher_lobby", code=code)}
    )

if __name__ == '__main__':
    app.run(debug=True)
