from ..models.redis_schema import r, K_qperm, K_qseq, K_qhash, K_qindex
from time import time

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