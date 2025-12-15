import csv
import json
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

from app.modules.auth.models import UserRole
from app.modules.community.models import ProposalStatus
from app.modules.community.repositories import CommunityProposalRepository
from app.modules.community.services import CommunityService
from app.modules.dataset import dataset_bp
from app.modules.dataset.forms import DataSetForm
from app.modules.dataset.models import DataSet
from app.modules.dataset.services import (
    DataSetService,
    DOIMappingService,
    DSDownloadRecordService,
    DSMetaDataService,
    DSViewRecordService,
    IssueService,
)
from app.modules.dataset.steamcsv_service import SteamCSVService
from app.modules.fakenodo.services import FakenodoService
from app.modules.hubfile.services import HubfileService
from core.storage import storage_service

logger = logging.getLogger(__name__)


dataset_service = DataSetService()
dsmetadata_service = DSMetaDataService()
fakenodo_service = FakenodoService()  # MOD: Fakenodo
doi_mapping_service = DOIMappingService()
ds_view_record_service = DSViewRecordService()
community_service = CommunityService()
community_proposal_repo = CommunityProposalRepository()


def _write_dataset_zip(dataset, zip_path: str):
    dataset_dir = storage_service.dataset_subdir(dataset.user_id, dataset.id)
    stored_files = storage_service.list_files(dataset_dir)
    if not stored_files:
        raise FileNotFoundError("Files not found")
    dataset_prefix = dataset_dir.replace("\\", "/")
    with ZipFile(zip_path, "w") as zipf:
        for stored_key in stored_files:
            normalized_key = stored_key.replace("\\", "/")
            if normalized_key.startswith(dataset_prefix):
                inner = normalized_key[len(dataset_prefix) :].lstrip("/")
            else:
                inner = normalized_key
            arcname = os.path.join(f"dataset_{dataset.id}", inner)
            with storage_service.as_local_path(normalized_key) as local_file:
                zipf.write(local_file, arcname=arcname)


@dataset_bp.route("/dataset/upload", methods=["GET", "POST"])
@login_required
def create_dataset():
    form = DataSetForm()
    if request.method != "POST":
        try:
            temp_dir = current_user.temp_folder()
            if os.path.isdir(temp_dir):
                csv_files = [f for f in os.listdir(temp_dir) if f.lower().endswith(".csv")]
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
    if request.method == "POST":

        dataset = None

        if not form.validate_on_submit():
            messages = []
            try:
                for subform in getattr(form, "dataset_files", []) or []:
                    version_errors = getattr(subform, "version", None).errors if hasattr(subform, "version") else []
                    if version_errors:
                        filename = getattr(getattr(subform, "csv_filename", None), "data", None) or "file"
                        messages.append(f"Invalid version for '{filename}': must follow x.y.z (e.g., 1.2.3)")
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
            dataset = dataset_service.create_from_form(form=form, current_user=current_user, draft_mode=False)
            logger.info(f"Created dataset: {dataset}")
            dataset_service.move_dataset_files(dataset)
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
                # If this upload was created by editing an existing draft, delete the original draft
                try:
                    editing_id = request.form.get("editing_dataset_id")
                    if editing_id:
                        try:
                            orig = dataset_service.get_by_id(int(editing_id))
                            if orig:
                                dataset_service.delete_draft_dataset(orig)
                        except Exception:
                            logger.exception("Could not delete original draft %s", editing_id)
                except Exception:
                    pass
            except Exception as e:
                msg = f"It has not been possible to upload files to Fakenodo and update the DOI: {e}"
                return jsonify({"message": msg}), 200

        file_path = current_user.temp_folder()
        if os.path.exists(file_path) and os.path.isdir(file_path):
            shutil.rmtree(file_path)

        msg = "Everything works!"
        return jsonify({"message": msg}), 200

    user_preference = current_user.profile.save_drafts

    return render_template("dataset/upload_dataset.html", form=form, save_drafts=user_preference)


@dataset_bp.route("/dataset/<int:dataset_id>/edit", methods=["GET", "POST"])
@login_required
def update_dataset(dataset_id):
    old_dataset = dataset_service.get_or_404(dataset_id)
    if not old_dataset:
        abort(404)

    form = DataSetForm()
    # Cleanup: if user has no CSV files in their temp folder, remove the temp folder
    try:
        # Only run cleanup on GET (when not posting the form)
        if request.method != "POST":
            try:
                temp_dir = current_user.temp_folder()
                if os.path.isdir(temp_dir):
                    csv_files = [f for f in os.listdir(temp_dir) if f.lower().endswith(".csv")]
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

            # returns the form pre-filled with existing dataset data
            try:
                # Load dataset and populate the form for editing
                ds = dataset_service.get_by_id(dataset_id)
                if ds:
                    md = ds.ds_meta_data
                    # basic metadata
                    form.title.data = getattr(md, "title", "")
                    form.desc.data = getattr(md, "description", "")
                    # data_category stored as Enum -> use its value
                    try:
                        form.data_category.data = md.data_category.value
                    except Exception:
                        # fallback if stored as string
                        form.data_category.data = getattr(md, "data_category", "")
                    form.publication_doi.data = getattr(md, "publication_doi", "")
                    form.dataset_doi.data = getattr(md, "dataset_doi", "")
                    form.tags.data = getattr(md, "tags", "")

                    # authors
                    try:
                        # clear existing entries then append
                        form.authors.entries = []
                        for a in getattr(md, "authors", []):
                            form.authors.append_entry()
                            last = form.authors.entries[-1].form
                            last.name.data = getattr(a, "name", "")
                            last.affiliation.data = getattr(a, "affiliation", "")
                            last.orcid.data = getattr(a, "orcid", "")
                    except Exception:
                        pass

                    # feature models
                    try:
                        form.feature_models.entries = []
                        for fm in getattr(ds, "feature_models", []):
                            meta = getattr(fm, "fm_meta_data", None)
                            form.feature_models.append_entry()
                            lastfm = form.feature_models.entries[-1].form
                            if meta:
                                lastfm.csv_filename.data = getattr(meta, "csv_filename", "")
                                lastfm.title.data = getattr(meta, "title", "")
                                lastfm.desc.data = getattr(meta, "description", "")
                                try:
                                    lastfm.data_category.data = meta.data_category.value
                                except Exception:
                                    lastfm.data_category.data = getattr(meta, "data_category", "")
                                lastfm.publication_doi.data = getattr(meta, "publication_doi", "")
                                lastfm.tags.data = getattr(meta, "tags", "")
                                lastfm.version.data = getattr(meta, "csv_version", "")
                                # fm authors
                                try:
                                    lastfm.authors.entries = []
                                    for a in getattr(meta, "authors", []):
                                        lastfm.authors.append_entry()
                                        lasta = lastfm.authors.entries[-1].form
                                        lasta.name.data = getattr(a, "name", "")
                                        lasta.affiliation.data = getattr(a, "affiliation", "")
                                        lasta.orcid.data = getattr(a, "orcid", "")
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    # If editing a published dataset, copy existing files to temp folder
                    if not ds.draft_mode:
                        try:
                            temp_dir = current_user.temp_folder()
                            if not os.path.exists(temp_dir):
                                os.makedirs(temp_dir, exist_ok=True)
                            for fm in ds.feature_models:
                                filename = fm.fm_meta_data.csv_filename
                                stored_key = storage_service.dataset_file_path(ds.user_id, ds.id, filename)
                                with storage_service.as_local_path(stored_key) as local_file_path:
                                    shutil.copy(local_file_path, os.path.join(temp_dir, filename))
                        except Exception:
                            logger.exception("Could not copy stored files to temp folder for editing published dataset")
            except Exception:
                # don't block rendering on prefill errors
                logger.exception("Error pre-filling dataset edit form")
    except Exception:
        # Be defensive: never let cleanup prevent rendering the page
        pass

    if request.method == "POST":
        dataset = None

        if not form.validate_on_submit():
            # Build user-friendly error message, especially for version field in files
            messages = []
            try:
                # Iterate FeatureModel subforms to collect version-specific errors with filenames
                for subform in getattr(form, "feature_models", []) or []:
                    version_errors = getattr(subform, "version", None).errors if hasattr(subform, "version") else []
                    if version_errors:
                        filename = getattr(getattr(subform, "csv_filename", None), "data", None) or "file"
                        messages.append(f"Invalid version for '{filename}': must follow x.y.z (e.g., 1.2.3)")
            except Exception:
                # be defensive; fall back to generic errors
                pass

            # Fallback: include any remaining form.errors in a readable way
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
            # Validate pending files in temp folder (Steam CSV only)
            # Diagnostics: log temp folder contents
            try:
                temp_dir = current_user.temp_folder()
                dir_list = []
                if os.path.isdir(temp_dir):
                    dir_list = sorted(os.listdir(temp_dir))
                logger.info("[upload] temp_folder='%s', files=%s", temp_dir, dir_list)

                # If user uploaded files (temp folder not empty) -> create new version
                files_changed = len(dir_list) > 0
            except Exception as diag_exc:
                logger.warning("[upload] Could not inspect temp folder for diagnostics: %s", diag_exc)
                files_changed = False
            service = SteamCSVService()
            try:
                service.validate_folder(current_user.temp_folder())
            except ValueError as verr:
                return jsonify({"message": str(verr)}), 400

            logger.info("Creating/updating dataset...")

            # For published datasets, always create a new version
            # For drafts, if files changed, create new version; else update in-place
            version_increment_type = request.form.get("version_increment_type", "major")
            if not old_dataset.draft_mode or files_changed:
                dataset = dataset_service.create_new_version(dataset_id, form, current_user, version_increment_type)
                logger.info(f"Created new dataset version: {dataset}")
                # move uploaded feature model files into storage
                dataset_service.move_dataset_files(dataset)
            else:
                # Draft without file changes: update metadata in-place
                dsmetadata_data = form.get_dsmetadata()
                dataset = dataset_service.get_by_id(dataset_id)
                dataset_service.update_dsmetadata(dataset.ds_meta_data_id, **dsmetadata_data)
                logger.info(f"Updated dataset metadata for dataset_id={dataset_id}")
        except Exception as exc:
            logger.exception(f"Exception while create dataset data in local {exc}")
            return jsonify({"Exception while create dataset data in local: ": str(exc)}), 400

        # send dataset as deposition to Zenodo
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

            # update dataset with deposition id in Zenodo
            dataset_service.update_dsmetadata(dataset.ds_meta_data_id, deposition_id=deposition_id)

            try:
                deposition_doi = fakenodo_service.get_doi(deposition_id)
                print("DOI:")
                print(deposition_doi)
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

    return render_template("dataset/upload_dataset.html", form=form, save_drafts=False, editing_dataset=ds)


@dataset_bp.route("/dataset/draft/save", methods=["POST"])
@login_required
def save_draft():
    data = request.get_json() or {}
    try:
        dataset = dataset_service.create_draft(current_user=current_user, data=data)
        logger.info("Creating dataset...")
        dataset = dataset_service.create_from_form(form=form, current_user=current_user, draft_mode=True)
        logger.info(f"Created dataset: {dataset}")
        dataset_service.move_dataset_files(dataset)
    except Exception as exc:
        logger.exception(f"Exception while saving draft dataset: {exc}")
        return jsonify({"message": str(exc)}), 400

    return jsonify({"id": dataset.id, "message": "Draft created"}), 200


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
@login_required
def delete():
    data = request.get_json()
    filename = data.get("file")
    temp_folder = current_user.temp_folder()
    filepath = os.path.join(temp_folder, filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"message": "File deleted successfully"}), 200

    return jsonify({"error": "File not found"}), 404


@dataset_bp.route("/dataset/<int:dataset_id>/file/delete", methods=["POST"])
@login_required
def delete_dataset_file(dataset_id):
    dataset = dataset_service.get_by_id(dataset_id)
    if not dataset:
        return jsonify({"message": "Dataset not found"}), 404

    # Only owner or admin can delete files
    if getattr(current_user, "id", None) != dataset.user_id and getattr(current_user, "role", None) != UserRole.ADMIN:
        return jsonify({"message": "Forbidden"}), 403

    data = request.get_json()
    filename = data.get("file")
    if not filename:
        return jsonify({"message": "Filename required"}), 400

    try:
        # Find the feature model with this filename
        fm_to_delete = None
        for fm in dataset.feature_models:
            if fm.fm_meta_data.csv_filename == filename:
                fm_to_delete = fm
                break

        if not fm_to_delete:
            return jsonify({"message": "File not found in dataset"}), 404

        # Delete the file from storage
        stored_key = storage_service.dataset_file_path(dataset.user_id, dataset.id, filename)
        storage_service.delete_file(stored_key)

        # Delete from DB
        dataset_service.feature_model_repository.delete(fm_to_delete.id)

        return jsonify({"message": "File deleted successfully"})
    except Exception as exc:
        logger.exception(f"Error deleting file {filename} from dataset {dataset_id}: {exc}")
        return jsonify({"message": str(exc)}), 500


@dataset_bp.route("/dataset/<int:dataset_id>/draft/delete", methods=["DELETE"])
@login_required
def delete_draft(dataset_id):
    dataset = dataset_service.get_by_id(dataset_id)
    if not dataset:
        return jsonify({"message": "Dataset not found"}), 404

    # Only owner or admin can delete a draft
    if getattr(current_user, "id", None) != dataset.user_id and getattr(current_user, "role", None) != UserRole.ADMIN:
        return jsonify({"message": "Forbidden"}), 403

    if not getattr(dataset, "draft_mode", False):
        return jsonify({"message": "Dataset is not a draft"}), 400

    try:
        dataset_service.delete_draft_dataset(dataset)
        return jsonify({"message": "Draft deleted"}), 200
    except Exception as exc:
        logger.exception(f"Error deleting draft {dataset_id}: {exc}")
        return jsonify({"message": str(exc)}), 500


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

    return jsonify({"message": "Temp folder cleaned"}), 302


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


@dataset_bp.route("/dataset/<int:dataset_id>/stats", methods=["GET"])
def get_dataset_stats(dataset_id):
    dataset = dataset_service.get_or_404(dataset_id)

    downloads = {hubfile.name: hubfile.download_count or 0 for df in dataset.dataset_files for hubfile in df.files}

    response = {"id": dataset.id, "downloads": downloads}

    return jsonify(response), 200


@dataset_bp.route("/doi/<path:doi>/", methods=["GET"])
def subdomain_index(doi):

    new_doi = doi_mapping_service.get_new_doi(doi)
    if new_doi:
        return redirect(url_for("dataset.subdomain_index", doi=new_doi), code=302)

    ds_meta_data = dsmetadata_service.filter_by_doi(doi)

    if not ds_meta_data:
        abort(404)

    dataset = ds_meta_data.data_set

    versions = []
    deposition_id = getattr(dataset.ds_meta_data, "deposition_id", None)

    if deposition_id:
        versions_meta = dsmetadata_service.get_all_versions_by_deposition_id(deposition_id)
        for meta in versions_meta:
            ds = DataSet.query.filter_by(ds_meta_data_id=meta.id).first()
            if ds:
                versions.append(
                    {
                        "version": meta.version,
                        "is_latest": meta.is_latest,
                        "dataset_id": ds.id,
                        "metadata": meta,
                        "created_at": ds.created_at,
                    }
                )

    user_cookie = ds_view_record_service.create_cookie(dataset=dataset)
    FAKENODO_URL = os.getenv("FAKENODO_URL")
    accepted_proposal = community_proposal_repo.get_accepted_for_dataset(dataset.id)
    accepted_community = accepted_proposal.community if accepted_proposal else None
    can_propose = accepted_proposal is None
    communities = community_service.list_all()
    proposals = community_proposal_repo.model.query.filter_by(dataset_id=dataset.id).all()
    pending_proposals = [proposal for proposal in proposals if proposal.status == ProposalStatus.PENDING]
    rejected_proposals = [proposal for proposal in proposals if proposal.status == ProposalStatus.REJECTED]
    blocked_ids = {proposal.community_id for proposal in pending_proposals}
    if accepted_community:
        blocked_ids.add(accepted_community.id)
    available_communities = [community for community in communities if community.id not in blocked_ids]
    related_datasets = dataset_service.get_related_datasets(dataset)
    resp = make_response(
        render_template(
            "dataset/view_dataset.html",
            dataset=dataset,
            versions=versions,
            fakenodo_url=FAKENODO_URL,
            communities=communities,
            available_communities=available_communities,
            accepted_community=accepted_community,
            can_propose=can_propose,
            pending_proposals=pending_proposals,
            rejected_proposals=rejected_proposals,
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
    communities = community_service.list_all()
    proposals = community_proposal_repo.model.query.filter_by(dataset_id=dataset.id).all()
    pending_proposals = [proposal for proposal in proposals if proposal.status == ProposalStatus.PENDING]
    rejected_proposals = [proposal for proposal in proposals if proposal.status == ProposalStatus.REJECTED]
    blocked_ids = {proposal.community_id for proposal in pending_proposals}
    if accepted_community:
        blocked_ids.add(accepted_community.id)
    available_communities = [community for community in communities if community.id not in blocked_ids]
    related_datasets = dataset_service.get_related_datasets(dataset)
    return render_template(
        "dataset/view_dataset.html",
        dataset=dataset,
        fakenodo_url=FAKENODO_URL,
        communities=communities,
        available_communities=available_communities,
        accepted_community=accepted_community,
        can_propose=can_propose,
        pending_proposals=pending_proposals,
        rejected_proposals=rejected_proposals,
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


@dataset_bp.route("/dataset/<int:dataset_id>/draft_mode", methods=["PUT"])
@login_required
def change_draft_mode(dataset_id):
    dataset = dataset_service.get_by_id(dataset_id)
    if not dataset or dataset.user_id != current_user.id:
        abort(404)

    dataset_service.change_draft_mode(dataset_id)
    return list_dataset()


@dataset_bp.route("/dataset/<int:dataset_id>/draft/edit", methods=["GET"])
@login_required
def edit(dataset_id):
    # Render the upload form pre-filled with the draft dataset so the user can edit and upload normally.
    dataset = dataset_service.get_unsynchronized_dataset(current_user.id, dataset_id)
    if not dataset:
        abort(404)

    # Build form pre-filled
    form = DataSetForm()
    try:
        form.title.data = dataset.ds_meta_data.title
        form.desc.data = dataset.ds_meta_data.description
        # DataCategory stored as enum name; the form expects the enum value
        try:
            form.data_category.data = dataset.ds_meta_data.data_category.value
        except Exception:
            form.data_category.data = None
        form.publication_doi.data = dataset.ds_meta_data.publication_doi
        form.dataset_doi.data = dataset.ds_meta_data.dataset_doi
        form.tags.data = dataset.ds_meta_data.tags

        # Authors - populate FieldList of FormField correctly
        # Clear existing entries and append new ones
        try:
            # reset entries
            form.authors.entries = []
        except Exception:
            pass
        for author in dataset.ds_meta_data.authors:
            entry = form.authors.append_entry()
            try:
                # entry is a FormField; inner form fields are under entry.form
                entry.form.name.data = author.name
                entry.form.affiliation.data = author.affiliation
                entry.form.orcid.data = author.orcid
            except Exception:
                # best-effort: try legacy attribute names
                try:
                    entry.name.data = author.name
                    entry.affiliation.data = author.affiliation
                    entry.orcid.data = author.orcid
                except Exception:
                    logger.exception("Could not populate author form entry for dataset %s", dataset_id)

        # Feature models: prepare a simple representation for the template to render
        editing_files = []
        for idx, fm in enumerate(dataset.feature_models):
            fm_md = fm.fm_meta_data
            filename = fm_md.csv_filename
            editing_files.append(
                {
                    "csv_filename": filename,
                    "title": fm_md.title,
                    "description": fm_md.description,
                    "data_category": getattr(fm_md.data_category, "value", None),
                    "publication_doi": fm_md.publication_doi,
                    "tags": fm_md.tags,
                    "version": fm_md.csv_version,
                }
            )

            # Copy stored file into user's temp folder so the upload flow can find it
            try:
                temp_dir = current_user.temp_folder()
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir, exist_ok=True)
                stored_key = storage_service.dataset_file_path(dataset.user_id, dataset.id, filename)
                with storage_service.as_local_path(stored_key) as local_file_path:
                    shutil.copy(local_file_path, os.path.join(temp_dir, filename))
            except Exception:
                logger.exception("Could not copy stored file %s to temp folder for editing", filename)

    except Exception:
        logger.exception("Error preparing edit form for dataset %s", dataset_id)
        return list_dataset()

    user_preference = current_user.profile.save_drafts
    return render_template(
        "dataset/upload_dataset.html",
        form=form,
        save_drafts=user_preference,
        editing_dataset=dataset,
        editing_files=editing_files,
    )


@dataset_bp.route("/dataset/issues", methods=["POST"])
@login_required
def create_issue():
    """Endpoint for curators to report issues of datasets.

    JSON body expected: { "dataset_id": int, "description": str }
    Only users with role == 'curator' are allowed to create issues.
    """
    data = request.get_json() or {}
    dataset_id = data.get("dataset_id")
    description = data.get("description")

    if not dataset_id or not description:
        return jsonify({"message": "dataset_id and description are required"}), 400

    # role check
    if getattr(current_user, "role", "") != UserRole.CURATOR:
        return jsonify({"message": "Forbidden"}), 403

    # create issue

    svc = IssueService()
    issue = svc.create(commit=True, description=description, dataset_id=dataset_id, reporter_id=current_user.id)

    return jsonify({"id": issue.id, "dataset_id": issue.dataset_id, "description": issue.description}), 201


@dataset_bp.route("/dataset/issues", methods=["GET"])
@login_required
def list_all_issues():
    """Admin-only page to list and review all dataset issues."""
    # Only admins can access this page
    if current_user.role != UserRole.ADMIN:
        abort(403)

    issue_service = IssueService()
    issues = issue_service.list_all()
    return render_template("dataset/list_issues.html", issues=issues)


@dataset_bp.route("/dataset/report/<int:dataset_id>", methods=["GET"])
@login_required
def report_dataset(dataset_id: int):
    """Render a simple page where a curator can describe an issue for a dataset.

    The form on this page will POST to `/dataset/issues` (JSON) to create the issue.
    """
    # Only curators may access the report page
    if current_user.role != UserRole.CURATOR:
        abort(403)

    dataset = dataset_service.get_or_404(dataset_id)
    return render_template("dataset/notify_issue.html", dataset=dataset)


@dataset_bp.route("/dataset/versions/<int:dataset_id>", methods=["GET"])
def dataset_versions(dataset_id):
    """Display version history timeline for a dataset."""
    dataset = dataset_service.get_by_id(dataset_id)

    # Get the deposition_id and fetch all versions
    deposition_id = dataset.ds_meta_data.deposition_id
    if not deposition_id:
        abort(404)

    # Get all versions ordered by version ascending (oldest first)
    versions_meta = dsmetadata_service.get_all_versions_by_deposition_id(deposition_id)

    # For each version, find the corresponding dataset
    versions = []
    for meta in versions_meta:
        ds = DataSet.query.filter_by(ds_meta_data_id=meta.id).first()
        if ds:
            versions.append(
                {
                    "version": meta.version,
                    "is_latest": meta.is_latest,
                    "dataset_id": ds.id,
                    "metadata": meta,
                    "created_at": ds.created_at,
                }
            )

    return render_template("dataset/versions_timeline.html", dataset=dataset, versions=versions)


@dataset_bp.route("/dataset/issues/open/<int:issue_id>/", methods=["PUT"])
@login_required
def open_issue(issue_id):
    """Endpoint for administrators to open or close issues.

    Only users with role == 'administrator' are allowed to create issues.
    """

    # role check
    if getattr(current_user, "role", "") != UserRole.ADMIN:
        return jsonify({"message": "Forbidden"}), 403

    issue_service = IssueService()
    issue_service.open_or_close(issue_id)
    issues = issue_service.list_all()
    return render_template("dataset/list_issues.html", issues=issues)


@dataset_bp.route("/dataset/view/<int:dataset_id>", methods=["GET"])
def view_dataset_by_id(dataset_id):
    dataset = dataset_service.get_by_id(dataset_id)
    if not dataset or dataset.draft_mode:
        abort(404)

    doi = getattr(dataset.ds_meta_data, "dataset_doi", None)
    if doi:
        return redirect(url_for("dataset.subdomain_index", doi=doi))

    versions = []
    deposition_id = getattr(dataset.ds_meta_data, "deposition_id", None)
    if deposition_id:
        versions_meta = dsmetadata_service.get_all_versions_by_deposition_id(deposition_id)
        for meta in versions_meta:
            ds = DataSet.query.filter_by(ds_meta_data_id=meta.id).first()
            if ds:
                versions.append(
                    {
                        "version": meta.version,
                        "is_latest": meta.is_latest,
                        "dataset_id": ds.id,
                        "metadata": meta,
                        "created_at": ds.created_at,
                    }
                )

    return render_template("dataset/view_dataset.html", dataset=dataset, versions=versions)


@dataset_bp.route("/dataset/versions/rollback/<int:dataset_id>", methods=["POST"])
@login_required
def rollback_dataset_version(dataset_id):

    current_dataset = dataset_service.get_by_id(dataset_id)

    if current_user.role != UserRole.ADMIN and current_dataset.user_id != current_user.id:
        abort(403, description="Unauthorized")

    deposition_id = current_dataset.ds_meta_data.deposition_id
    if not deposition_id:
        abort(404)

    previous_version = dsmetadata_service.get_previous_version_by_deposition_id(deposition_id)
    if not previous_version:
        return jsonify({"message": "No previous version available for rollback"}), 400

    try:
        dataset_service.rollback_to_previous_version(previous_version, current_dataset)
        return redirect(url_for("dataset.subdomain_index", doi=previous_version.dataset_doi))
    except Exception as exc:
        logger.exception(f"Exception while rolling back dataset version: {exc}")
        return jsonify({"Exception while rolling back dataset version: ": str(exc)}), 400
