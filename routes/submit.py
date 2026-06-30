import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from audit.log import write_submission
from signals.pipeline import run_pipeline

submit_bp = Blueprint("submit", __name__)


@submit_bp.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    text = data.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "'text' is required and must be a non-empty string."}), 400

    creator_id = data.get("creator_id", "")
    if not isinstance(creator_id, str) or not creator_id.strip():
        return jsonify({"error": "'creator_id' is required and must be a non-empty string."}), 400

    text = text.strip()
    creator_id = creator_id.strip()

    try:
        result = run_pipeline(text)
    except EnvironmentError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception:
        return jsonify({"error": "Detection pipeline failed. Check your API key and network."}), 502

    content_id = "cont_" + str(uuid.uuid4())

    write_submission({
        "content_id":         content_id,
        "creator_id":         creator_id,
        "text":               text,
        "llm_score":          result["signal_1"]["score"],
        "llm_reason":         result["signal_1"].get("reason", ""),
        "stylometric_score":  result["signal_2"]["score"],
        "stylometric_reason": result["signal_2"].get("reason", ""),
        "attribution":        result["attribution_result"],
        "confidence":         result["confidence_score"],
        "label_text":         "Analysis in progress",  # placeholder — Milestone 5
        "status":             "classified",
        "timestamp":          datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    })

    return jsonify({
        "content_id":        content_id,
        "creator_id":        creator_id,
        "text":              text,
        "signal_1":          result["signal_1"],
        "signal_2":          result["signal_2"],
        "attribution_result": result["attribution_result"],
        "confidence_score":  result["confidence_score"],
        "combined_reason":   result["combined_reason"],
        "label_text":        "Analysis in progress",  # placeholder — Milestone 5
        "status":            "classified",
    }), 200
