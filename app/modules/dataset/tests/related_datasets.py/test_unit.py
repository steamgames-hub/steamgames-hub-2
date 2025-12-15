from datetime import datetime
from types import SimpleNamespace

from app.modules.dataset.services import DataSetService

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def make_dataset(
    ds_id,
    title="T",
    authors=None,
    tags="",
    category="cat",
    doi="doi",
    created_at=None,
):
    """Utility to build a fake dataset with metadata using SimpleNamespace, mimicking the ORM."""
    if authors is None:
        authors = []

    meta = SimpleNamespace(
        title=title,
        authors=authors,
        tags=tags,
        data_category=SimpleNamespace(name=category),
        dataset_doi=doi,
    )

    ds = SimpleNamespace(id=ds_id, ds_meta_data=meta, created_at=created_at or datetime(2024, 1, 1))
    return ds


def fake_query_result(ids):
    """Simulate query returning dataset ids (list of tuples or objects)."""
    return [(i,) for i in ids]


def test_normalize_values_removes_empty_and_lowercases():
    svc = DataSetService()
    values = ["Alberto ", None, "  ", "PedRO", "PEDro"]
    result = svc._normalize_values(values)
    assert result == {"alberto", "pedro"}


def test_normalize_tags_splits_and_normalizes():
    svc = DataSetService()
    tags = "TERROR, avenTURA , Puzzles ,"
    assert svc._normalize_tags(tags) == {"terror", "aventura", "puzzles"}


def test_normalize_tags_empty():
    svc = DataSetService()
    assert svc._normalize_tags("") == set()
    assert svc._normalize_tags(None) == set()


def test_fetch_author_related_ids_no_authors(monkeypatch):
    svc = DataSetService()

    # No authors → expect empty result
    ids = svc._fetch_author_related_ids(1, set(), set())
    assert ids == set()


def test_fetch_author_related_ids_matches(monkeypatch):
    svc = DataSetService()

    # Fake SQLAlchemy query chain
    class FakeQuery:
        def __init__(self):
            pass

        def join(self, *a, **kw):
            return self

        def filter(self, *a, **kw):
            return self

        def distinct(self):
            return self

        def all(self):
            return fake_query_result([10, 11])

    monkeypatch.setattr("app.modules.dataset.services.db.session.query", lambda *a, **kw: FakeQuery())

    out = svc._fetch_author_related_ids(dataset_id=1, author_names={"alice"}, author_orcids=set())
    assert out == {10, 11}


def test_fetch_tag_related_ids_no_tags():
    svc = DataSetService()
    result = svc._fetch_tag_related_ids(1, set())
    assert result == set()


def test_fetch_tag_related_ids_matches(monkeypatch):
    svc = DataSetService()

    class FakeQuery:
        def join(self, *a, **kw):
            return self

        def filter(self, *a, **kw):
            return self

        def distinct(self):
            return self

        def all(self):
            return fake_query_result([20, 21])

    monkeypatch.setattr("app.modules.dataset.services.db.session.query", lambda *args, **kwargs: FakeQuery())

    result = svc._fetch_tag_related_ids(1, {"ml"})
    assert result == {20, 21}


def test_fetch_community_related_ids_no_communities():
    svc = DataSetService()
    assert svc._fetch_community_related_ids(1, set()) == set()


def test_fetch_community_related_ids_matches(monkeypatch):
    svc = DataSetService()

    class FakeQuery:
        def join(self, *a, **kw):
            return self

        def filter(self, *a, **kw):
            return self

        def distinct(self):
            return self

        def all(self):
            return fake_query_result([30, 31])

    monkeypatch.setattr("app.modules.dataset.services.db.session.query", lambda *a, **kw: FakeQuery())

    out = svc._fetch_community_related_ids(1, {100})
    assert out == {30, 31}


def test_get_related_datasets_no_dataset():
    svc = DataSetService()
    assert svc.get_related_datasets(None) == []


def test_get_related_datasets_no_metadata():
    svc = DataSetService()
    ds = SimpleNamespace(ds_meta_data=None)
    assert svc.get_related_datasets(ds) == []
