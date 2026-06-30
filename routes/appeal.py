import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from audit.log import get_submission, update_submission_status, write_appeal

appeal_bp = Blueprint("appeal", __name__)


@appeal_bp.route("/appeal", methods=["POST"])
def submit_appeal():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    content_id = data.get("content_id", "")
    if not isinstance(content_id, str) or not content_id.strip():
        return jsonify({"error": "'content_id' is required and must be a non-empty string."}), 400

    creator_reasoning = data.get("creator_reasoning", "")
    if not isinstance(creator_reasoning, str) or not creator_reasoning.strip():
        return jsonify({"error": "'creator_reasoning' is required and must be a non-empty string."}), 400

    content_id = content_id.strip()
    creator_reasoning = creator_reasoning.strip()
    creator_id = str(data.get("creator_id", "")).strip()
    context = str(data.get("context", "")).strip()

    submission = get_submission(content_id)
    if not submission:
        return jsonify({"error": f"No submission found for content_id '{content_id}'."}), 404

    appeal_id = "appeal_" + str(uuid.uuid4())
    timestamp = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

    update_submission_status(content_id, "under review")

    write_appeal({
        "appeal_id":        appeal_id,
        "content_id":       content_id,
        "creator_id":       creator_id,
        "appeal_reasoning": creator_reasoning,
        "context":          context,
        "status":           "under review",
        "timestamp":        timestamp,
    })

    return jsonify({
        "appeal_id":        appeal_id,
        "content_id":       content_id,
        "status":           "under review",
        "message":          "Appeal received. The submission has been flagged for human review.",
        "timestamp":        timestamp,
    }), 200
