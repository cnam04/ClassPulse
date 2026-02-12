import os,redis

# ------- Session Storage -------- #
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(REDIS_URL, decode_responses=True)

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

