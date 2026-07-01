from flask import Blueprint, jsonify

from audit.log import clear_db, get_appeals_log, get_log

log_bp = Blueprint("log", __name__)


@log_bp.route("/log", methods=["GET"])
def retrieve_log():
    return jsonify({
        "entries": get_log(),
        "appeals": get_appeals_log(),
    })


@log_bp.route("/log", methods=["DELETE"])
def clear_log():
    counts = clear_db()
    return jsonify({
        "message": "All submissions and appeals have been deleted.",
        "submissions_deleted": counts["submissions_deleted"],
        "appeals_deleted": counts["appeals_deleted"],
    }), 200
