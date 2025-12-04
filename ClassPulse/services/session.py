from ..models.redis_schema import *
from string import ascii_uppercase
from random import choice
from time import time 

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

def window_state(code):
    meta = r.hgetall(K_meta(code)) or {}
    active = meta.get("window_active") == "1"
    expires_at = int(meta.get("window_expires_at") or 0)
    remaining = max(0, expires_at - int(time()))
    if active and remaining == 0:
        # lazily close the window
        r.hset(K_meta(code), "window_active", 0)
        active = False
    return active, remaining
