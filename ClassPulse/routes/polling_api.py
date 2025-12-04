from flask import request, jsonify, Blueprint
from ..services.polling import poll_start, poll_stop, poll_vote, poll_read

polling_bp = Blueprint("polling_api", __name__, url_prefix= "/api")


@polling_bp.post("/session/<code>/poll/start")
def api_poll_start(code):
    q = (request.json or {}).get("question", "")
    poll_start(code, q)
    return jsonify({"ok": True})

@polling_bp.post("/session/<code>/poll/stop")
def api_poll_stop(code):
    poll_stop(code)
    return jsonify({"ok": True})

@polling_bp.get("/session/<code>/poll")
def api_poll_get(code):
    data = poll_read(code)
    resp = jsonify(data)
    resp.headers["Cache-Control"] = "no-store"
    return resp

@polling_bp.post("/session/<code>/poll/vote")
def api_poll_vote(code):
    payload = request.get_json(silent=True) or {}
    choice = (payload.get("choice") or "").lower()
    voter  = payload.get("voter_id")
    if choice not in ("yes","no"):
        return jsonify({"ok": False, "reason": "bad choice"}), 400
    ok, reason = poll_vote(code, choice, voter)
    if not ok:
        http = 409 if reason=="already voted" else 403 if reason=="not active" else 400
        return jsonify({"ok": False, "reason": reason}), http
    return jsonify({"ok": True})
