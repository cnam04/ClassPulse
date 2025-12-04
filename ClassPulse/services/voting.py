from ..models.redis_schema import r, K_voted, K_votes, K_meta
from .session import window_state

def record_vote(code, status, voter_id):
    # one vote per window; accept outside of a window if you want—here we enforce only within/while open
    if not voter_id:
        return False, "missing voter_id"

    # already voted this window?
    if r.sismember(K_voted(code), voter_id):
        return False, "already voted"

    active, remaining = window_state(code)
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
    active, remaining = window_state(code)
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
