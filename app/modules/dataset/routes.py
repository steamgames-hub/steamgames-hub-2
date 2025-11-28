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
from app.modules.dataset.services import (
    AuthorService,
    DataSetService,
    DOIMappingService,
    DSDownloadRecordService,
    DSMetaDataService,
    DSViewRecordService,
)
from app.modules.community.services import CommunityService
from app.modules.community.repositories import CommunityProposalRepository
from app.modules.hubfile.services import HubfileService
from app.modules.fakenodo.services import FakenodoService
from app.modules.dataset.steamcsv_service import SteamCSVService
from core.storage import storage_service

logger = logging.getLogger(__name__)


dataset_service = DataSetService()
author_service = AuthorService()
dsmetadata_service = DSMetaDataService()
fakenodo_service = FakenodoService()
doi_mapping_service = DOIMappingService()
ds_view_record_service = DSViewRecordService()
community_service = CommunityService()
community_proposal_repo = CommunityProposalRepository()


def _write_dataset_zip(dataset, zip_path: str):
    dataset_dir = storage_service.dataset_subdir(dataset.user_id, dataset.id)
    stored_files = storage_service.list_files(dataset_dir)
    if not stored_files:
        raise FileNotFoundError("Dataset files not found")
    dataset_prefix = dataset_dir.replace("\\", "/")
    with ZipFile(zip_path, "w") as zipf:
        for stored_key in stored_files:
            normalized_key = stored_key.replace("\\", "/")
            if normalized_key.startswith(dataset_prefix):
                inner = normalized_key[len(dataset_prefix):].lstrip("/")
            else:
                inner = normalized_key
            arcname = os.path.join(f"dataset_{dataset.id}", inner)
            with storage_service.as_local_path(normalized_key) as local_file:
                zipf.write(local_file, arcname=arcname)


@dataset_bp.route("/dataset/upload", methods=["GET", "POST"])
@login_required
def create_dataset():
    form = DataSetForm()
    try:
        if request.method != "POST":
            try:
                temp_dir = current_user.temp_folder()
                if os.path.isdir(temp_dir):
                    csv_files = [f for f in os.listdir(temp_dir) if f.lower().endswith('.csv')]
                    if not csv_files:
                        try:
                            shutil.rmtree(temp_dir)
                            logger.info(
                                "[upload][cleanup] Removed empty temp folder for user %s: %s",
                                current_user.id,
                                temp_dir,
                            )
                        except Exception as cleanup_exc:
                            logger.warning(
                                "[upload][cleanup] Could not remove temp folder %s: %s",
                                temp_dir,
                                cleanup_exc,
                            )
            except Exception as diag_exc:
                logger.warning("[upload][cleanup] Could not inspect temp folder for diagnostics: %s", diag_exc)
    except Exception:
        pass
    if request.method == "POST":

        dataset = None

        if not form.validate_on_submit():
            messages = []
            try:
                for subform in getattr(form, "feature_models", []) or []:
                    version_errors = getattr(subform, "version", None).errors if hasattr(subform, "version") else []
                    if version_errors:
                        filename = getattr(getattr(subform, "csv_filename", None), "data", None) or "file"
                        messages.append(
                            f"Invalid version for '{filename}': must follow x.y.z (e.g., 1.2.3)"
                        )
            except Exception:
                pass

            if not messages and isinstance(form.errors, dict):
                for field, errs in form.errors.items():
                    if isinstance(errs, (list, tuple)):
                        for e in errs:
                            messages.append(f"{field}: {e}")
                    else:
                        messages.append(f"{field}: {errs}")

            message_text = "; ".join(messages) if messages else "Validation error"
            return jsonify({"message": message_text}), 400

        try:
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

        data = {}
        try:
            fakenodo_response_json = fakenodo_service.create_new_deposition(dataset)
            response_data = json.dumps(fakenodo_response_json)
            data = json.loads(response_data)
        except Exception as exc:
            data = {}
            fakenodo_response_json = {}
            logger.exception(f"Exception while create dataset data in Fakenodo {exc}")

        if data.get("conceptrecid"):
            deposition_id = data.get("id")

            dataset_service.update_dsmetadata(dataset.ds_meta_data_id, deposition_id=deposition_id)

            try:
                deposition_doi = fakenodo_service.get_doi(deposition_id)
                dataset_service.update_dsmetadata(dataset.ds_meta_data_id, dataset_doi=deposition_doi)
            except Exception as e:
                msg = f"it has not been possible upload feature models in Zenodo and update the DOI: {e}"
                return jsonify({"message": msg}), 200

        file_path = current_user.temp_folder()
        if os.path.exists(file_path) and os.path.isdir(file_path):
            shutil.rmtree(file_path)

        msg = "Everything works!"
        return jsonify({"message": msg}), 200

    return render_template("dataset/upload_dataset.html", form=form)


@dataset_bp.route("/dataset/list", methods=["GET", "POST"])
@login_required
def list_dataset():
    return render_template(
        "dataset/list_datasets.html",
        datasets=dataset_service.get_synchronized(current_user.id),
        local_datasets=dataset_service.get_unsynchronized(current_user.id),
    )


@dataset_bp.route("/dataset/file/upload", methods=["POST"])
@login_required
def upload():
    file = request.files["file"]
    temp_folder = current_user.temp_folder()

    if not file or not (file.filename.endswith(".csv")):
        return jsonify({"message": "No valid file"}), 400

    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    file_path = os.path.join(temp_folder, file.filename)

    if os.path.exists(file_path):
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
    try:
        temp_folder = current_user.temp_folder()
        if os.path.isdir(temp_folder):
            for entry in os.listdir(temp_folder):
                path = os.path.join(temp_folder, entry)
                try:
                    if os.path.isfile(path) or os.path.islink(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                except Exception as e:
                    logger.warning("[clean_temp] Could not remove %s: %s", path, e)
        return jsonify({"message": "Temp folder cleaned"}), 200
    except Exception as exc:
        logger.exception("[clean_temp] Exception cleaning temp folder: %s", exc)
        return jsonify({"error": str(exc)}), 500


@dataset_bp.route("/dataset/download/<int:dataset_id>", methods=["GET"])
def download_dataset(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"dataset_{dataset_id}.zip")
    try:
        _write_dataset_zip(dataset, zip_path)
    except FileNotFoundError:
        shutil.rmtree(temp_dir, ignore_errors=True)
        abort(404)

    user_cookie = str(uuid.uuid4())

    resp = make_response(
        send_from_directory(
            temp_dir,
            f"dataset_{dataset_id}.zip",
            as_attachment=True,
            mimetype="application/zip",
        )
    )
    resp.set_cookie("download_cookie", user_cookie)

    DSDownloadRecordService().create(
        user_id=current_user.id if current_user.is_authenticated else None,
        dataset_id=dataset_id,
        download_date=datetime.now(timezone.utc),
        download_cookie=user_cookie,
    )

    return resp


@dataset_bp.route("/doi/<path:doi>/", methods=["GET"])
def subdomain_index(doi):

    new_doi = doi_mapping_service.get_new_doi(doi)
    if new_doi:
        return redirect(url_for("dataset.subdomain_index", doi=new_doi), code=302)

    ds_meta_data = dsmetadata_service.filter_by_doi(doi)

    if not ds_meta_data:
        abort(404)

    dataset = ds_meta_data.data_set

    user_cookie = ds_view_record_service.create_cookie(dataset=dataset)
    FAKENODO_URL = os.getenv("FAKENODO_URL")
    accepted_proposal = community_proposal_repo.get_accepted_for_dataset(dataset.id)
    accepted_community = accepted_proposal.community if accepted_proposal else None
    can_propose = accepted_proposal is None
    related_datasets = dataset_service.get_related_datasets(dataset)
    resp = make_response(
        render_template(
            "dataset/view_dataset.html",
            dataset=dataset,
            fakenodo_url=FAKENODO_URL,
            communities=community_service.list_all(),
            accepted_community=accepted_community,
            can_propose=can_propose,
            related_datasets=related_datasets,
        )
    )
    resp.set_cookie("view_cookie", user_cookie)

    return resp


@dataset_bp.route("/dataset/unsynchronized/<int:dataset_id>/", methods=["GET"])
@login_required
def get_unsynchronized_dataset(dataset_id):

    dataset = dataset_service.get_unsynchronized_dataset(current_user.id, dataset_id)

    if not dataset:
        abort(404)
    FAKENODO_URL = os.getenv("FAKENODO_URL")
    accepted_proposal = community_proposal_repo.get_accepted_for_dataset(dataset.id)
    accepted_community = accepted_proposal.community if accepted_proposal else None
    can_propose = accepted_proposal is None
    related_datasets = dataset_service.get_related_datasets(dataset)
    return render_template(
        "dataset/view_dataset.html",
        dataset=dataset,
        fakenodo_url=FAKENODO_URL,
        communities=community_service.list_all(),
        accepted_community=accepted_community,
        can_propose=can_propose,
        related_datasets=related_datasets,
    )


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
