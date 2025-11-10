import json
import csv
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from zipfile import ZipFile

from flask import (
    abort,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from app.modules.dataset import dataset_bp
from app.modules.dataset.forms import DataSetForm
from app.modules.dataset.models import DSDownloadRecord
from app.modules.dataset.services import (
    AuthorService,
    DataSetService,
    DOIMappingService,
    DSDownloadRecordService,
    DSMetaDataService,
    DSViewRecordService,
    IncidentService,
)
from app.modules.hubfile.services import HubfileService
from app.modules.zenodo.services import ZenodoService
from app.modules.dataset.steamcsv_service import SteamCSVService
from app.modules.auth.models import UserRole

logger = logging.getLogger(__name__)


author_service = AuthorService()
dsmetadata_service = DSMetaDataService()
zenodo_service = ZenodoService()
doi_mapping_service = DOIMappingService()
dataset_service = DataSetService()
ds_view_record_service = DSViewRecordService()


# Dataset type selection removed: Steam CSV only


@dataset_bp.route("/dataset/upload", methods=["GET", "POST"])
@login_required
def create_dataset():
    form = DataSetForm()
    if request.method == "POST":

        dataset = None

        if not form.validate_on_submit():
            return jsonify({"message": form.errors}), 400

        try:
            # Validate pending files in temp folder (Steam CSV only)
            # Diagnostics: log temp folder contents
            try:
                temp_dir = current_user.temp_folder()
                dir_list = []
                if os.path.isdir(temp_dir):
                    dir_list = sorted(os.listdir(temp_dir))
                logger.info("[upload] temp_folder='%s', files=%s", temp_dir, dir_list)
            except Exception as diag_exc:
                logger.warning("[upload] Could not inspect temp folder for diagnostics: %s", diag_exc)
            service = SteamCSVService()
            try:
                service.validate_folder(current_user.temp_folder())
            except ValueError as verr:
                return jsonify({"message": str(verr)}), 400

            logger.info("Creating dataset...")
            dataset = dataset_service.create_from_form(form=form, current_user=current_user)
            logger.info(f"Created dataset: {dataset}")
            dataset_service.move_feature_models(dataset)
        except Exception as exc:
            logger.exception(f"Exception while create dataset data in local {exc}")
            return jsonify({"Exception while create dataset data in local: ": str(exc)}), 400

        # send dataset as deposition to Zenodo
        data = {}
        try:
            zenodo_response_json = zenodo_service.create_new_deposition(dataset)
            response_data = json.dumps(zenodo_response_json)
            data = json.loads(response_data)
        except Exception as exc:
            data = {}
            zenodo_response_json = {}
            logger.exception(f"Exception while create dataset data in Zenodo {exc}")

        if data.get("conceptrecid"):
            deposition_id = data.get("id")

            # update dataset with deposition id in Zenodo
            dataset_service.update_dsmetadata(dataset.ds_meta_data_id, deposition_id=deposition_id)

            try:
                # iterate for each feature model (one feature model = one request to Zenodo)
                for feature_model in dataset.feature_models:
                    zenodo_service.upload_file(dataset, deposition_id, feature_model)

                # publish deposition
                zenodo_service.publish_deposition(deposition_id)

                # update DOI
                deposition_doi = zenodo_service.get_doi(deposition_id)
                dataset_service.update_dsmetadata(dataset.ds_meta_data_id, dataset_doi=deposition_doi)
            except Exception as e:
                msg = f"it has not been possible upload feature models in Zenodo and update the DOI: {e}"
                return jsonify({"message": msg}), 200

        # Delete temp folder
        file_path = current_user.temp_folder()
        if os.path.exists(file_path) and os.path.isdir(file_path):
            shutil.rmtree(file_path)

        msg = "Everything works!"
        return jsonify({"message": msg}), 200

    user_preference = current_user.profile.save_drafts

    return render_template("dataset/upload_dataset.html", form=form, save_drafts=user_preference)


@dataset_bp.route("/dataset/list", methods=["GET", "POST"])
@login_required
def list_dataset():
    return render_template(
        "dataset/list_datasets.html",
        datasets=dataset_service.get_synchronized(current_user.id),
        local_datasets=dataset_service.get_unsynchronized(current_user.id),
    )


@dataset_bp.route("/dataset/delete/<int:dataset_id>", methods=["POST"])
@login_required
def delete_dataset(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)

    if current_user.role != UserRole.ADMIN:
        abort(403, description="Unauthorized")

    try:
        dataset_service.delete_dataset(dataset)
        return redirect(url_for("public.index"))
    except Exception as exc:
        logger.exception(f"Exception while deleting dataset {exc}")
        return jsonify({"Exception while deleting dataset: ": str(exc)}), 400


@dataset_bp.route("/dataset/file/upload", methods=["POST"])
@login_required
def upload():
    file = request.files["file"]
    temp_folder = current_user.temp_folder()

    if not file or not (file.filename.endswith(".csv")):
        return jsonify({"message": "No valid file"}), 400

    # create temp folder
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    file_path = os.path.join(temp_folder, file.filename)

    if os.path.exists(file_path):
        # Generate unique filename (by recursion)
        base_name, extension = os.path.splitext(file.filename)
        i = 1
        while os.path.exists(os.path.join(temp_folder, f"{base_name} ({i}){extension}")):
            i += 1
        new_filename = f"{base_name} ({i}){extension}"
        file_path = os.path.join(temp_folder, new_filename)
    else:
        new_filename = file.filename

    try:
        file.save(file_path)
    except Exception as e:
        return jsonify({"message": str(e)}), 500

    return (
        jsonify({"message": "File uploaded and validated successfully", "filename": new_filename}),
        200,
    )


@dataset_bp.route("/dataset/file/delete", methods=["POST"])
def delete():
    data = request.get_json()
    filename = data.get("file")
    temp_folder = current_user.temp_folder()
    filepath = os.path.join(temp_folder, filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"message": "File deleted successfully"})

    return jsonify({"error": "Error: File not found"})


@dataset_bp.route("/dataset/file/clean_temp", methods=["POST"])
@login_required
def clean_temp():
    """Remove files inside the current user's temp folder but keep the folder.

    Returns JSON with a friendly message. This mirrors the JS action in the
    upload template which calls this endpoint.
    """
    temp_folder = current_user.temp_folder()

    try:
        if os.path.exists(temp_folder) and os.path.isdir(temp_folder):
            for name in os.listdir(temp_folder):
                path = os.path.join(temp_folder, name)
                try:
                    if os.path.isfile(path) or os.path.islink(path):
                        os.remove(path)
                    else:
                        shutil.rmtree(path)
                except Exception:
                    # best-effort: ignore failures to remove individual items
                    continue
        # Ensure the directory exists afterwards
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder, exist_ok=True)
    except Exception as exc:
        logger.exception("Error cleaning temp folder: %s", exc)
        return jsonify({"message": str(exc)}), 500

    # Redirect back to the upload page (this mirrors the original UI flow)
    return redirect(url_for("dataset.create_dataset")), 302


@dataset_bp.route("/dataset/download/<int:dataset_id>", methods=["GET"])
def download_dataset(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)

    file_path = f"uploads/user_{dataset.user_id}/dataset_{dataset.id}/"

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"dataset_{dataset_id}.zip")

    with ZipFile(zip_path, "w") as zipf:
        for subdir, _, files in os.walk(file_path):
            for file in files:
                full_path = os.path.join(subdir, file)

                relative_path = os.path.relpath(full_path, file_path)

                zipf.write(
                    full_path,
                    arcname=os.path.join(os.path.basename(zip_path[:-4]), relative_path),
                )

    user_cookie = request.cookies.get("download_cookie")
    if not user_cookie:
        user_cookie = str(uuid.uuid4())  # Generate a new unique identifier if it does not exist
        # Save the cookie to the user's browser
        resp = make_response(
            send_from_directory(
                temp_dir,
                f"dataset_{dataset_id}.zip",
                as_attachment=True,
                mimetype="application/zip",
            )
        )
        resp.set_cookie("download_cookie", user_cookie)
    else:
        resp = send_from_directory(
            temp_dir,
            f"dataset_{dataset_id}.zip",
            as_attachment=True,
            mimetype="application/zip",
        )

    # Check if the download record already exists for this cookie
    existing_record = DSDownloadRecord.query.filter_by(
        user_id=current_user.id if current_user.is_authenticated else None,
        dataset_id=dataset_id,
        download_cookie=user_cookie,
    ).first()

    if not existing_record:
        # Record the download in your database
        DSDownloadRecordService().create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset_id,
            download_date=datetime.now(timezone.utc),
            download_cookie=user_cookie,
        )

    return resp

@dataset_bp.route("/dataset/<int:dataset_id>/stats", methods=["GET"])
def get_dataset_stats(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)

    downloads = {
        hubfile.name: hubfile.download_count or 0
        for fm in dataset.feature_models
        for hubfile in fm.files
    }

    response = {
        "id": dataset.id,
        "downloads": downloads
    }

    return jsonify(response), 200


@dataset_bp.route("/doi/<path:doi>/", methods=["GET"])
def subdomain_index(doi):

    # Check if the DOI is an old DOI
    new_doi = doi_mapping_service.get_new_doi(doi)
    if new_doi:
        # Redirect to the same path with the new DOI
        return redirect(url_for("dataset.subdomain_index", doi=new_doi), code=302)

    # Try to search the dataset by the provided DOI (which should already be the new one)
    ds_meta_data = dsmetadata_service.filter_by_doi(doi)

    if not ds_meta_data:
        abort(404)

    # Get dataset
    dataset = ds_meta_data.data_set

    # Save the cookie to the user's browser
    user_cookie = ds_view_record_service.create_cookie(dataset=dataset)
    resp = make_response(render_template("dataset/view_dataset.html", dataset=dataset))
    resp.set_cookie("view_cookie", user_cookie)

    return resp


@dataset_bp.route("/dataset/unsynchronized/<int:dataset_id>/", methods=["GET"])
@login_required
def get_unsynchronized_dataset(dataset_id):

    # Get dataset
    dataset = dataset_service.get_unsynchronized_dataset(current_user.id, dataset_id)

    if not dataset:
        abort(404)

    return render_template("dataset/view_dataset.html", dataset=dataset)


@dataset_bp.route("/dataset/file/preview/<int:file_id>", methods=["GET"])
def preview_csv(file_id: int):
    """Return a small preview (headers + up to 50 rows) for a CSV file."""
    hubfile_service = HubfileService()
    hubfile = hubfile_service.repository.get_or_404(file_id)
    file_path = hubfile.get_path()

    headers = []
    rows = []
    try:
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0:
                    headers = row
                else:
                    rows.append(row)
                if len(rows) >= 50:
                    break
    except Exception as exc:
        logger.exception("Error generating CSV preview: %s", exc)
        return jsonify({"message": str(exc)}), 400

    return jsonify({"headers": headers, "rows": rows})


@dataset_bp.route("/dataset/incidents", methods=["POST"])
@login_required
def create_incident():
    """Endpoint para que un curator notifique una incidencia sobre un dataset.

    JSON body expected: { "dataset_id": int, "description": str }
    Only users with role == 'curator' are allowed to create incidents.
    """
    data = request.get_json() or {}
    dataset_id = data.get("dataset_id")
    description = data.get("description")

    if not dataset_id or not description:
        return jsonify({"message": "dataset_id and description are required"}), 400

    # role check
    if getattr(current_user, "role", "") != UserRole.CURATOR:
        return jsonify({"message": "Forbidden"}), 403

    # create incident

    svc = IncidentService()
    incident = svc.create(commit=True, description=description, dataset_id=dataset_id, reporter_id=current_user.id)

    return jsonify({"id": incident.id, "dataset_id": incident.dataset_id, "description": incident.description}), 201


@dataset_bp.route("/dataset/incidents", methods=["GET"])
@login_required
def list_all_incidents():
    """Admin-only page to list and review all dataset incidents."""
    # Only admins can access this page
    if current_user.role != UserRole.ADMIN:
        abort(403)

    incident_service = IncidentService()
    incidents = incident_service.list_all()
    return render_template("dataset/list_incidents.html", incidents=incidents)


@dataset_bp.route("/dataset/report/<int:dataset_id>", methods=["GET"])
@login_required
def report_dataset(dataset_id: int):
    """Render a simple page where a curator can describe an issue for a dataset.

    The form on this page will POST to `/dataset/incidents` (JSON) to create the incident.
    """
    # Only curators may access the report page
    if current_user.role != UserRole.CURATOR:
        abort(403)

    dataset = dataset_service.get_or_404(dataset_id)
    return render_template("dataset/notify_issue.html", dataset=dataset)


@dataset_bp.route("/dataset/incidents/open/<int:issue_id>/", methods=["PUT"])
@login_required
def open_incident(issue_id):
    """Endpoint para que un administrador abra o cierre una incidencia.

    Only users with role == 'administrator' are allowed to create incidents.
    """

    # role check
    if getattr(current_user, "role", "") != UserRole.ADMIN:
        return jsonify({"message": "Forbidden"}), 403

    incident_service = IncidentService()
    incident_service.open_or_close(issue_id)
    incidents = incident_service.list_all()
    return render_template("dataset/list_incidents.html", incidents=incidents)