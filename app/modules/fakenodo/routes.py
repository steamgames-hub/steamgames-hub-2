from flask import render_template

from app.modules.fakenodo import fakenodo_bp
from app.modules.fakenodo.services import FakenodoService


@fakenodo_bp.route("/zenodo", methods=["GET"])
def index():
    return render_template("zenodo/index.html")


@fakenodo_bp.route("/zenodo/test", methods=["GET"])
def zenodo_test() -> dict:
    service = FakenodoService()
    return service.test_full_connection()
