from flask import request, jsonify, Blueprint
from ..services.session import session_exists, start_window
from ..services.voting import read_stats, record_vote

ALLOWED_STATUSES = {"not_confused", "confused", "soso"}

voting_bp = Blueprint("voting_api", __name__, url_prefix= "/api")

@voting_bp.post("/api/session/<code>/start_window")
def api_start_window(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    start_window(code, seconds=60)
    return jsonify({"ok": True, "seconds": 60})


@voting_bp.get("/api/session/<code>/stats")
def api_stats(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    resp=jsonify(read_stats(code))
    resp.headers["Cache-Control"]="no-store"
    return resp

@voting_bp.post("/api/session/<code>/vote")
def api_vote(code):
    if not session_exists(code):
        return jsonify({"error": "session not found"}), 404
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").lower().replace("-", "_")
    voter_id = payload.get("voter_id")
    if status not in ALLOWED_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(ALLOWED_STATUSES)}"}), 400

    ok, reason = record_vote(code, status, voter_id)
    if not ok:
        http = 409 if reason == "already voted" else 403 if reason == "window closed" else 400
        return jsonify({"ok": False, "reason": reason}), http
    return jsonify({"ok": True})