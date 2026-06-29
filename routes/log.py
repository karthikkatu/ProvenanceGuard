from flask import Blueprint, jsonify

from audit.log import get_log

log_bp = Blueprint("log", __name__)


@log_bp.route("/log", methods=["GET"])
def retrieve_log():
    return jsonify({"entries": get_log()})
