from datetime import datetime
from flask import request, jsonify, render_template

from app.modules.explore import explore_bp
from app.modules.explore.forms import ExploreForm
from app.modules.explore.repositories import ExploreRepository

repo = ExploreRepository()


def serialize_dataset(d):
    """
    Para campos complejos como las fechas y los tags
    """
    if d is None:
        return {}
    if isinstance(d, dict):
        data = d.copy()
    elif hasattr(d, "to_dict") and callable(getattr(d, "to_dict")):
        data = d.to_dict()
    else:
        data = {
            "id": getattr(d, "id", None),
            "title": getattr(d, "title", None),
            "author": getattr(d, "author", None),
            "data_category": getattr(d, "data_category", None),
            "tags": getattr(d, "tags", []),
            "filenames": getattr(d, "filenames", []),
            "created_at": getattr(d, "created_at", None),
            "downloads": getattr(d, "downloads", None),
            "views": getattr(d, "views", None),
            "community": getattr(d, "community", None),
        }

    created = data.get("created_at") or data.get("created")
    if created and hasattr(created, "isoformat"):
        data["created_at"] = created.isoformat()

    if data.get("tags") is None:
        data["tags"] = []
    if data.get("filenames") is None:
        data["filenames"] = []
    return data


@explore_bp.route("/explore", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        payload = request.get_json() or {}

        def parse_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d").date() if s else None
            except Exception:
                return None

        results = repo.filter(
            query=payload.get("query", ""),
            sorting=payload.get("sorting", "newest"),
            author=payload.get("author"),
            data_category=payload.get("data_category", "any"),
            tags=payload.get("tags", []),
            filenames=payload.get("filenames", []),
            community=payload.get("community"),
            date_from=parse_date(payload.get("date_from")),
            date_to=parse_date(payload.get("date_to")),
            min_downloads=payload.get("min_downloads"),
            min_views=payload.get("min_views"),
        )

        return jsonify([serialize_dataset(d) for d in results])

    form = ExploreForm()
    return render_template("explore/index.html", form=form)
