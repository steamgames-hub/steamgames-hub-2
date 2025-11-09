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
            "publication_type": getattr(d, "publication_type", None),
            "tags": getattr(d, "tags", []),
            "created_at": getattr(d, "created_at", None),
            "downloads": getattr(d, "downloads", None),
            "views": getattr(d, "views", None),
            "uvl": getattr(d, "uvl", None),
            "community": getattr(d, "community", None),
        }

    created = data.get("created_at") or data.get("created")
    if created and hasattr(created, "isoformat"):
        data["created_at"] = created.isoformat()

    if data.get("tags") is None:
        data["tags"] = []

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

        results = repo.filter( #TODO CAMBIAR LOS TIPOS DE PUBLICACION
            query=payload.get("query", ""),
            publication_type=payload.get("publication_type", "any"),
            sorting=payload.get("sorting", "newest"),
            author=payload.get("author"),
            tags=payload.get("tags", []),
            uvl=payload.get("uvl"),
            community=payload.get("community"),
            date_from=parse_date(payload.get("date_from")),
            date_to=parse_date(payload.get("date_to")),
            min_downloads=payload.get("min_downloads"),
            min_views=payload.get("min_views"),
        )

        return jsonify([serialize_dataset(d) for d in results])

    form = ExploreForm()
    return render_template("explore/index.html", form=form)
