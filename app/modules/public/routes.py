import logging

from flask import jsonify, render_template, request, url_for
from flask_login import current_user
from app.modules.dataset.services import DataSetService
from app.modules.datasetfile.services import DatasetFileService
from app.modules.public import public_bp

logger = logging.getLogger(__name__)


@public_bp.route("/")
def index():
    logger.info("Access index")
    dataset_service = DataSetService()
    dataset_file_service = DatasetFileService()

    datasets_counter = dataset_service.count_synchronized_datasets()
    dataset_files_counter = dataset_file_service.count_dataset_files()

    total_dataset_downloads = dataset_service.total_dataset_downloads()
    total_dataset_file_downloads = dataset_file_service.total_dataset_file_downloads()

    total_dataset_views = dataset_service.total_dataset_views()
    total_dataset_file_views = dataset_file_service.total_dataset_file_views()

    latest = dataset_service.latest_synchronized()

    try:
        trending_raw = dataset_service.trending_datasets(period_days=7, by="views", limit=5)
    except Exception:
        logger.exception("Error obteniendo trending datasets")
        trending_raw = []
    trending = []
    for item in trending_raw:
        if isinstance(item, (list, tuple)):
            dataset = item[0]
            metric = int(item[1]) if len(item) > 1 else 0
        else:
            dataset = item
            metric = 0
        trending.append((dataset, metric))

    # Personal dashboard metrics (only when authenticated)
    user_metrics = None
    if current_user.is_authenticated:
        user_metrics = {
            "uploaded_datasets": dataset_service.count_user_datasets(current_user.id),
            "downloads": dataset_service.count_user_dataset_downloads(current_user.id),
            "synchronizations": dataset_service.count_user_synchronized_datasets(current_user.id),
        }

    return render_template(
        "public/index.html",
        datasets=latest,
        datasets_counter=datasets_counter,
        dataset_files_counter=dataset_files_counter,
        total_dataset_downloads=total_dataset_downloads,
        total_dataset_file_downloads=total_dataset_file_downloads,
        total_dataset_views=total_dataset_views,
        total_dataset_file_views=total_dataset_file_views,
        user_metrics=user_metrics,
        trending_datasets=trending,
    )


@public_bp.route("/trending_datasets")
def trending_datasets_api():
    dataset_service = DataSetService()

    by = request.args.get("by", "views")
    period = request.args.get("period", "week")
    try:
        limit = int(request.args.get("limit", 5))
    except ValueError:
        limit = 5

    period_days = 7 if period == "week" else 30

    try:
        raw = dataset_service.trending_datasets(period_days=period_days, by=by, limit=limit)
    except Exception:
        logger.exception("Error en dataset_service.trending_datasets")
        raw = []

    result = []
    for item in raw:
        if isinstance(item, (tuple, list)):
            dataset = item[0]
            metric = item[1] if len(item) > 1 else 0
        else:
            dataset = item
            metric = 0

        try:
            title = dataset.ds_meta_data.title
        except Exception:
            title = getattr(dataset, "title", "Untitled")

        try:
            first_author = dataset.ds_meta_data.authors[0].name if dataset.ds_meta_data.authors else ""
        except Exception:
            first_author = ""

        community_name = ""
        community_url = ""
        try:
            if hasattr(dataset, "accepted_community") and dataset.accepted_community:
                community = dataset.accepted_community
                community_name = getattr(community, "name", "") or ""
                try:
                    community_url = url_for("community.view_community", community_id=community.id)
                except Exception:
                    community_url = ""
        except Exception:
            community_name = ""
            community_url = ""

        try:
            url = dataset.get_steamgameshub_doi()
        except Exception:
            try:
                url = url_for("dataset.view", dataset_id=dataset.id)
            except Exception:
                url = f"/dataset/{dataset.id}"

        result.append(
            {
                "id": dataset.id,
                "title": title,
                "first_author": first_author,
                "community_name": community_name,
                "community_url": community_url,
                "metric": int(metric or 0),
                "url": url,
            }
        )

    return jsonify({"by": by, "period": period, "items": result})
