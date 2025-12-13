from flask import render_template

from app.modules.datasetfile import datasetfile_bp


@datasetfile_bp.route("/dataset-files", methods=["GET"])
def index():
    return render_template("datasetfile/index.html")
