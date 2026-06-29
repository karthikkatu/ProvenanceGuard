import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from audit.log import write_submission
from signals.llm_classifier import analyze_with_groq

submit_bp = Blueprint("submit", __name__)


def _attribution_from_signal(score: float) -> str:
    """
    Map a signal 1 score to an attribution label.
    Milestone 4 replaces this with calibrated confidence scoring over both signals.
    Thresholds match planning.md so the replacement is a drop-in.
    """
    if score < 0.45:
        return "human"
    if score < 0.70:
        return "uncertain"
    return "ai"


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
        signal_1 = analyze_with_groq(text)
    except EnvironmentError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception:
        return jsonify({"error": "Signal 1 failed. Check your API key and network."}), 502

    content_id = "cont_" + str(uuid.uuid4())
    attribution_result = _attribution_from_signal(signal_1["score"])

    # Placeholders — replaced in Milestone 4 (confidence) and Milestone 5 (labels).
    confidence_score = 0.5
    label_text = "Analysis in progress"

    write_submission({
        "content_id": content_id,
        "creator_id": creator_id,
        "text": text,
        "llm_score": signal_1["score"],
        "llm_reason": signal_1.get("reason", ""),
        "attribution": attribution_result,
        "confidence": confidence_score,
        "label_text": label_text,
        "status": "pending_analysis",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    })

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "text": text,
        "signal_1_result": signal_1,
        "attribution_result": attribution_result,
        "confidence_score": confidence_score,
        "label_text": label_text,
        "status": "pending_analysis",
    }), 200
