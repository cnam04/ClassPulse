from ..models.redis_schema import r, K_poll, K_poll_voted

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