from flask import request, jsonify, Blueprint
from ..models.redis_schema import r, K_broadcast, K_broadcast_qid, K_qindex
from ..services.session import session_exists
from ..services.questions import get_qperm, set_qperm, add_student_question, list_student_questions, delete_student_question

questions_bp = Blueprint("questions_api", __name__, url_prefix= "/api")

@questions_bp.get("/session/<code>/question")
def api_get_broadcast(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    text = r.get(K_broadcast(code)) or ""
    qid  = r.get(K_broadcast_qid(code)) or ""
    return jsonify({"text": text, "qid": int(qid) if qid.isdigit() else None})

@questions_bp.post("/session/<code>/question")
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

@questions_bp.get("/session/<code>/qperm")
def api_qperm_get(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    return jsonify({"allow": get_qperm(code)})

@questions_bp.post("/session/<code>/qperm")
def api_qperm_set(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    payload = request.get_json(silent=True) or {}
    allow = bool(payload.get("allow"))
    set_qperm(code, allow)
    return jsonify({"ok": True, "allow": allow})


@questions_bp.post("/session/<code>/student_question")
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


@questions_bp.get("/session/<code>/student_questions")
def api_student_questions_list(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    return jsonify(list_student_questions(code))

@questions_bp.delete("/session/<code>/student_questions/<int:qid>")
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