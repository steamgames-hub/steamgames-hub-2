import os
import uuid
from datetime import datetime, timezone

from flask import jsonify, make_response, request, send_from_directory
from flask_login import current_user

from app import db
from app.modules.hubfile import hubfile_bp
from app.modules.hubfile.models import HubfileViewRecord
from app.modules.hubfile.services import HubfileDownloadRecordService, HubfileService


@hubfile_bp.route("/file/download/<int:file_id>", methods=["GET"])
def download_file(file_id):
    file = HubfileService().get_or_404(file_id)
    filename = file.name

    abs_file_path = os.path.abspath(HubfileService().get_path_by_hubfile(file))
    directory = os.path.dirname(abs_file_path)
    if not os.path.exists(abs_file_path):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "File not found on disk",
                    "path": abs_file_path,
                }
            ),
            404,
        )

    user_cookie = str(uuid.uuid4())

    HubfileDownloadRecordService().create(
        user_id=current_user.id if current_user.is_authenticated else None,
        file_id=file_id,
        download_date=datetime.now(timezone.utc),
        download_cookie=user_cookie,
    )

    HubfileDownloadRecordService().update_download_count(file_id)
    db.session.commit()

    resp = make_response(
        send_from_directory(
            directory=directory,
            path=filename,
            as_attachment=True,
        )
    )
    resp.set_cookie("file_download_cookie", user_cookie)

    return resp


@hubfile_bp.route("/file/view/<int:file_id>", methods=["GET"])
def view_file(file_id):
    file = HubfileService().get_or_404(file_id)

    file_path = HubfileService().get_path_by_hubfile(file)

    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            user_cookie = request.cookies.get("view_cookie")
            if not user_cookie:
                user_cookie = str(uuid.uuid4())

            uid = current_user.id if current_user.is_authenticated else None
            existing_record = HubfileViewRecord.query.filter_by(
                user_id=uid,
                file_id=file_id,
                view_cookie=user_cookie,
            ).first()

            if not existing_record:
                new_view_record = HubfileViewRecord(
                    user_id=uid,
                    file_id=file_id,
                    view_date=datetime.now(),
                    view_cookie=user_cookie,
                )
                db.session.add(new_view_record)
                db.session.commit()

            response = jsonify({"success": True, "content": content})
            if not request.cookies.get("view_cookie"):
                response = make_response(response)
                response.set_cookie(
                    "view_cookie",
                    user_cookie,
                    max_age=60 * 60 * 24 * 365 * 2,
                )

            return response
        else:
            return jsonify({"success": False, "error": "File not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
