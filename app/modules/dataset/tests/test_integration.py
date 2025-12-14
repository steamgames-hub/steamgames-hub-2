import io
import tempfile
import uuid
from contextlib import contextmanager
import pytest
from app import db
from app.modules.auth.models import User
from app.modules.dataset.models import DataCategory, DataSet, DSMetaData

import types

class _Field:
    def __init__(self):
        self.data = None
        self.errors = []

class _Entry:
    def __init__(self, form):
        self.form = form

class _ListField:
    def __init__(self, factory):
        self.entries = []
        self._factory = factory

    def append_entry(self):
        self.entries.append(_Entry(self._factory()))

try:
    from app.modules.profile.models import Profile
except Exception:
    Profile = None


@pytest.fixture(autouse=True)
def _workdir(monkeypatch):
    monkeypatch.setenv("WORKING_DIR", tempfile.mkdtemp())
    yield

@pytest.fixture()
def users(clean_database):
    suf = uuid.uuid4().hex[:6]
    owner = User(email=f"owner+{suf}@test.com", password="1234")
    other = User(email=f"other+{suf}@test.com", password="1234")

    if hasattr(owner, "two_factor_verified"):
        owner.two_factor_verified = True
    if hasattr(other, "two_factor_verified"):
        other.two_factor_verified = True

    ProfileCls = User.profile.property.mapper.class_

    def ensure_profile(u: User, base: str):
        if getattr(u, "profile", None) is None:
            u.profile = ProfileCls()
        if hasattr(u.profile, "name"):
            u.profile.name = base
        if hasattr(u.profile, "surname"):
            u.profile.surname = "Test"
        if hasattr(u.profile, "save_drafts"):
            u.profile.save_drafts = False

    ensure_profile(owner, "Owner")
    ensure_profile(other, "Other")

    db.session.add_all([owner, other])
    db.session.commit()
    return owner, other

def make_dataset(owner: User, doi: str | None = None) -> DataSet:
    meta = DSMetaData(
        title="DS X",
        description="d",
        data_category=DataCategory.GENERAL,
        dataset_doi=doi,
    )
    ds = DataSet(user_id=owner.id, ds_meta_data=meta)

    if hasattr(ds, "draft_mode"):
        ds.draft_mode = False

    db.session.add_all([meta, ds])
    db.session.commit()
    return ds


@contextmanager
def force_login(client, user):
    """Authenticate a user in the test client session bypassing the UI/2FA flow."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    yield


def test_get_upload_page_ok_authenticated(test_client, users):
    owner, _ = users
    with force_login(test_client, owner):
        r = test_client.get("/dataset/upload")
    assert r.status_code == 200


def test_list_dataset_page_ok_authenticated(test_client, users):
    owner, _ = users
    with force_login(test_client, owner):
        r = test_client.get("/dataset/list")
    assert r.status_code == 200


def test_file_upload_rejects_non_csv(test_client, users):
    owner, _ = users
    with force_login(test_client, owner):
        r = test_client.post(
            "/dataset/file/upload",
            data={"file": (io.BytesIO(b"hello"), "not_csv.txt")},
            content_type="multipart/form-data",
        )
    assert r.status_code == 400
    assert r.get_json()["message"] == "No valid file"


def test_file_upload_renames_duplicate_csv(test_client, users):
    owner, _ = users
    csv_bytes = b"a,b\n1,2\n"

    with force_login(test_client, owner):
        r1 = test_client.post(
            "/dataset/file/upload",
            data={"file": (io.BytesIO(csv_bytes), "sample.csv")},
            content_type="multipart/form-data",
        )
    assert r1.status_code == 200
    f1 = r1.get_json()["filename"]

    with force_login(test_client, owner):
        r2 = test_client.post(
            "/dataset/file/upload",
            data={"file": (io.BytesIO(csv_bytes), "sample.csv")},
            content_type="multipart/form-data",
        )
    assert r2.status_code == 200
    f2 = r2.get_json()["filename"]

    assert f2 != f1
    assert f2.startswith("sample")
    assert f2.endswith(".csv")


def test_clean_temp_redirects(test_client, users):
    owner, _ = users
    with force_login(test_client, owner):
        r = test_client.post("/dataset/file/clean_temp", follow_redirects=False)
    assert r.status_code == 302


def test_delete_dataset_forbidden_for_non_admin(test_client, users):
    owner, _ = users
    ds = make_dataset(owner)

    with force_login(test_client, owner):
        r = test_client.post(f"/dataset/delete/{ds.id}")

    assert r.status_code == 403


def test_create_issue_missing_fields_returns_400(test_client, users):
    owner, _ = users
    with force_login(test_client, owner):
        r = test_client.post("/dataset/issues", json={})
    assert r.status_code == 400
    assert "required" in r.get_json()["message"]


def test_create_issue_non_curator_returns_403(test_client, users):
    owner, _ = users
    with force_login(test_client, owner):
        r = test_client.post("/dataset/issues", json={"dataset_id": 1, "description": "bug"})
    assert r.status_code == 403
    assert r.get_json()["message"] == "Forbidden"


def test_report_dataset_requires_curator_returns_403(test_client, users):
    owner, _ = users
    ds = make_dataset(owner)

    with force_login(test_client, owner):
        r = test_client.get(f"/dataset/report/{ds.id}")

    assert r.status_code == 403


def test_list_all_issues_requires_admin_returns_403(test_client, users):
    owner, _ = users
    with force_login(test_client, owner):
        r = test_client.get("/dataset/issues")
    assert r.status_code == 403


def test_dataset_versions_without_deposition_returns_404(test_client, users):
    owner, _ = users
    ds = make_dataset(owner)
    r = test_client.get(f"/dataset/versions/{ds.id}")
    assert r.status_code == 404


def test_download_dataset_forces_404_when_no_files(test_client, users, monkeypatch):
    owner, _ = users
    ds = make_dataset(owner)

    import app.modules.dataset.routes as dataset_routes

    monkeypatch.setattr(dataset_routes.storage_service, "list_files", lambda _p: [])

    r = test_client.get(f"/dataset/download/{ds.id}")
    assert r.status_code == 404


def test_view_dataset_redirects_to_doi_when_present(test_client, users):
    owner, _ = users
    doi = "10.9999/test-doi"
    ds = make_dataset(owner, doi=doi)

    r = test_client.get(f"/dataset/view/{ds.id}", follow_redirects=False)
    assert r.status_code == 302
    assert f"/doi/{doi}/" in r.headers.get("Location", "")

def test_get_upload_triggers_cleanup_and_renders(test_client, users, monkeypatch, tmp_path):
    from app.modules.dataset import routes as dataset_routes
    owner, _ = users

    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    monkeypatch.setattr(owner, "temp_folder", lambda: str(temp_dir), raising=False)

    removed = {"called": False}
    monkeypatch.setattr(dataset_routes.shutil, "rmtree", lambda p: removed.__setitem__("called", True))

    monkeypatch.setattr(dataset_routes, "render_template", lambda *a, **k: "OK")

    with force_login(test_client, owner):
        r = test_client.get("/dataset/upload")

    assert r.status_code == 200
    assert removed["called"] is True
    
def test_post_upload_invalid_form_returns_version_message(test_client, users, monkeypatch):
    from app.modules.dataset import routes as dataset_routes
    owner, _ = users

    class V: errors = ["bad"]
    class CsvName: data = "file.csv"
    class Subform:
        version = V()
        csv_filename = CsvName()

    class FakeForm:
        def __init__(self):
            self.dataset_files = [Subform()]
            self.errors = {}
        def validate_on_submit(self):
            return False

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)

    with force_login(test_client, owner):
        r = test_client.post("/dataset/upload", data={})

    assert r.status_code == 400
    assert "Invalid version" in r.get_json()["message"]

def test_post_upload_validate_folder_valueerror_returns_400(test_client, users, monkeypatch, tmp_path):
    from app.modules.dataset import routes as dataset_routes
    owner, _ = users

    class FakeForm:
        def __init__(self):
            self.errors = {}
        def validate_on_submit(self):
            return True

    class FakeSteam:
        def validate_folder(self, p):
            raise ValueError("Bad CSV")

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)
    monkeypatch.setattr(dataset_routes, "SteamCSVService", FakeSteam)

    monkeypatch.setattr(owner, "temp_folder", lambda: str(tmp_path), raising=False)

    with force_login(test_client, owner):
        r = test_client.post("/dataset/upload", data={})

    assert r.status_code == 400
    assert r.get_json()["message"] == "Bad CSV"

def test_post_upload_create_from_form_exception_returns_400(test_client, users, monkeypatch, tmp_path):
    from app.modules.dataset import routes as dataset_routes
    owner, _ = users

    class FakeForm:
        def __init__(self):
            self.errors = {}
        def validate_on_submit(self):
            return True

    class OkSteam:
        def validate_folder(self, p): return None

    class FakeDatasetService:
        def create_from_form(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)
    monkeypatch.setattr(dataset_routes, "SteamCSVService", OkSteam)
    monkeypatch.setattr(dataset_routes, "dataset_service", FakeDatasetService())

    monkeypatch.setattr(owner, "temp_folder", lambda: str(tmp_path), raising=False)

    with force_login(test_client, owner):
        r = test_client.post("/dataset/upload", data={})

    assert r.status_code == 400
    assert "Exception while create dataset data in local" in list(r.get_json().keys())[0]

def test_post_upload_happy_path_updates_doi_and_cleans_temp(test_client, users, monkeypatch, tmp_path):
    from app.modules.dataset import routes as dataset_routes
    import types

    owner, _ = users

    class FakeForm:
        def __init__(self):
            self.errors = {}
        def validate_on_submit(self):
            return True

    class OkSteam:
        def validate_folder(self, p): return None

    calls = {"update": [], "move": 0}
    dataset = types.SimpleNamespace(ds_meta_data_id=123)

    class FakeDatasetService:
        def create_from_form(self, **kwargs):
            return dataset
        def move_dataset_files(self, ds):
            calls["move"] += 1
        def update_dsmetadata(self, meta_id, **kwargs):
            calls["update"].append((meta_id, kwargs))
        def get_by_id(self, _id): return None
        def delete_draft_dataset(self, orig): pass

    class FakeFakenodo:
        def create_new_deposition(self, ds):
            return {"conceptrecid": 1, "id": 99}
        def get_doi(self, deposition_id):
            return "10.1234/1"

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)
    monkeypatch.setattr(dataset_routes, "SteamCSVService", OkSteam)
    monkeypatch.setattr(dataset_routes, "dataset_service", FakeDatasetService())
    monkeypatch.setattr(dataset_routes, "fakenodo_service", FakeFakenodo())

    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    monkeypatch.setattr(owner, "temp_folder", lambda: str(temp_dir), raising=False)
    monkeypatch.setattr(dataset_routes.os.path, "exists", lambda p: True)
    monkeypatch.setattr(dataset_routes.os.path, "isdir", lambda p: True)

    removed = {"called": False}
    monkeypatch.setattr(dataset_routes.shutil, "rmtree", lambda p: removed.__setitem__("called", True))

    with force_login(test_client, owner):
        r = test_client.post("/dataset/upload", data={})

    assert r.status_code == 200
    assert r.get_json()["message"] == "Everything works!"
    assert calls["move"] == 1
    assert removed["called"] is True
    assert len(calls["update"]) >= 2

def test_get_edit_prefills_form_and_runs_cleanup(test_client, users, monkeypatch, tmp_path):
    from app.modules.dataset import routes as dataset_routes

    owner, _ = users
    dataset_id = 123

    md = types.SimpleNamespace(
        title="My Title",
        description="My Desc",
        data_category=types.SimpleNamespace(value="CAT"),
        publication_doi="10.pub/xx",
        dataset_doi="10.ds/yy",
        tags="a,b",
        authors=[
            types.SimpleNamespace(name="Ana", affiliation="US", orcid="0000")
        ],
    )

    fm_meta = types.SimpleNamespace(
        csv_filename="fm.csv",
        title="FM Title",
        description="FM Desc",
        data_category=types.SimpleNamespace(value="FM_CAT"),
        publication_doi="10.pub/fm",
        tags="x,y",
        csv_version="1.2.3",
        authors=[
            types.SimpleNamespace(name="Bob", affiliation="Lab", orcid="1111")
        ],
    )

    ds = types.SimpleNamespace(ds_meta_data=md, feature_models=[types.SimpleNamespace(fm_meta_data=fm_meta)])

    class FakeDatasetService:
        def get_or_404(self, _id): return ds
        def get_by_id(self, _id): return ds

    monkeypatch.setattr(dataset_routes, "dataset_service", FakeDatasetService())

    def make_author_form():
        f = types.SimpleNamespace(name=_Field(), affiliation=_Field(), orcid=_Field())
        return f

    def make_fm_author_form():
        f = types.SimpleNamespace(name=_Field(), affiliation=_Field(), orcid=_Field())
        return f

    def make_fm_form():
        f = types.SimpleNamespace(
            csv_filename=_Field(),
            title=_Field(),
            desc=_Field(),
            data_category=_Field(),
            publication_doi=_Field(),
            tags=_Field(),
            version=_Field(),
            authors=_ListField(make_fm_author_form),
        )
        return f

    class FakeForm:
        def __init__(self):
            self.title = _Field()
            self.desc = _Field()
            self.data_category = _Field()
            self.publication_doi = _Field()
            self.dataset_doi = _Field()
            self.tags = _Field()
            self.authors = _ListField(make_author_form)
            self.feature_models = _ListField(make_fm_form)

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)

    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    monkeypatch.setattr(owner, "temp_folder", lambda: str(temp_dir), raising=False)

    removed = {"called": False}
    monkeypatch.setattr(dataset_routes.shutil, "rmtree", lambda p: removed.__setitem__("called", True))

    def fake_render(template, **ctx):
        form = ctx["form"]
        assert form.title.data == "My Title"
        assert form.desc.data == "My Desc"
        assert form.data_category.data == "CAT"
        assert form.publication_doi.data == "10.pub/xx"
        assert form.dataset_doi.data == "10.ds/yy"
        assert form.tags.data == "a,b"

        assert len(form.authors.entries) == 1
        assert form.authors.entries[0].form.name.data == "Ana"

        assert len(form.feature_models.entries) == 1
        fm_form = form.feature_models.entries[0].form
        assert fm_form.csv_filename.data == "fm.csv"
        assert fm_form.version.data == "1.2.3"
        assert len(fm_form.authors.entries) == 1
        assert fm_form.authors.entries[0].form.name.data == "Bob"

        return "OK"

    monkeypatch.setattr(dataset_routes, "render_template", fake_render)

    with force_login(test_client, owner):
        r = test_client.get(f"/dataset/{dataset_id}/edit")

    assert r.status_code == 200
    assert removed["called"] is True

def test_get_edit_404_when_missing(test_client, users, monkeypatch):
    from app.modules.dataset import routes as dataset_routes
    owner, _ = users

    class FakeDatasetService:
        def get_or_404(self, _id): return None

    monkeypatch.setattr(dataset_routes, "dataset_service", FakeDatasetService())

    with force_login(test_client, owner):
        r = test_client.get("/dataset/999/edit")

    assert r.status_code == 404

def test_post_edit_invalid_form_returns_version_message(test_client, users, monkeypatch):
    from app.modules.dataset import routes as dataset_routes
    owner, _ = users

    class V: errors = ["bad"]
    class CsvName: data = "fm.csv"
    class Subform:
        version = V()
        csv_filename = CsvName()

    class FakeForm:
        def __init__(self):
            self.feature_models = [Subform()]
            self.errors = {}
        def validate_on_submit(self): return False

    class FakeDatasetService:
        def get_or_404(self, _id): return object()

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)
    monkeypatch.setattr(dataset_routes, "dataset_service", FakeDatasetService())

    with force_login(test_client, owner):
        r = test_client.post("/dataset/1/edit", data={})

    assert r.status_code == 400
    assert "Invalid version" in r.get_json()["message"]

def test_post_edit_validate_folder_valueerror_returns_400(test_client, users, monkeypatch, tmp_path):
    from app.modules.dataset import routes as dataset_routes
    owner, _ = users

    class FakeForm:
        def __init__(self):
            self.errors = {}
        def validate_on_submit(self): return True

    class FakeSteam:
        def validate_folder(self, p):
            raise ValueError("Bad CSV")

    class FakeDatasetService:
        def get_or_404(self, _id): return object()

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)
    monkeypatch.setattr(dataset_routes, "SteamCSVService", FakeSteam)
    monkeypatch.setattr(dataset_routes, "dataset_service", FakeDatasetService())

    monkeypatch.setattr(owner, "temp_folder", lambda: str(tmp_path), raising=False)

    with force_login(test_client, owner):
        r = test_client.post("/dataset/1/edit", data={})

    assert r.status_code == 400
    assert r.get_json()["message"] == "Bad CSV"

def test_post_edit_files_changed_creates_new_version(test_client, users, monkeypatch, tmp_path):
    import types
    from app.modules.dataset import routes as dataset_routes
    from app.modules.auth.models import User

    owner, _ = users
    dataset_id = 7

    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    (temp_dir / "x.csv").write_text("a,b\n1,2\n")

    monkeypatch.setattr(User, "temp_folder", lambda self: str(temp_dir), raising=False)

    class FakeForm:
        def __init__(self):
            self.errors = {}
        def validate_on_submit(self): return True
        def get_dsmetadata(self): return {"title": "noop"}

    class OkSteam:
        def validate_folder(self, p): return None

    calls = {"new_version": 0, "move": 0, "update": []}
    dataset = types.SimpleNamespace(ds_meta_data_id=123)

    class FakeDatasetService:
        def get_or_404(self, _id): return object()
        def create_new_version(self, *args, **kwargs):
            calls["new_version"] += 1
            return dataset
        def move_feature_models(self, ds): calls["move"] += 1
        def update_dsmetadata(self, meta_id, **kwargs): calls["update"].append((meta_id, kwargs))

    class FakeFakenodo:
        def create_new_deposition(self, ds): return {"conceptrecid": 1, "id": 99}
        def get_doi(self, dep_id): return "10.1234/99"

    removed = {"called": False}
    monkeypatch.setattr(dataset_routes.shutil, "rmtree", lambda p: removed.__setitem__("called", True))

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)
    monkeypatch.setattr(dataset_routes, "SteamCSVService", OkSteam)
    monkeypatch.setattr(dataset_routes, "dataset_service", FakeDatasetService())
    monkeypatch.setattr(dataset_routes, "fakenodo_service", FakeFakenodo())

    with force_login(test_client, owner):
        r = test_client.post(f"/dataset/{dataset_id}/edit", data={})

    assert r.status_code == 200
    assert r.get_json()["message"] == "Everything works!"
    assert calls["new_version"] == 1
    assert calls["move"] == 1
    assert removed["called"] is True
    assert any("deposition_id" in kw for _, kw in calls["update"])
    assert any("dataset_doi" in kw for _, kw in calls["update"])

def test_post_edit_no_files_updates_metadata_in_place(test_client, users, monkeypatch, tmp_path):
    from app.modules.dataset import routes as dataset_routes
    owner, _ = users
    dataset_id = 8

    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    monkeypatch.setattr(owner, "temp_folder", lambda: str(temp_dir), raising=False)

    class FakeForm:
        def __init__(self):
            self.errors = {}
        def validate_on_submit(self): return True
        def get_dsmetadata(self): return {"title": "Updated!"}

    class OkSteam:
        def validate_folder(self, p): return None

    ds = types.SimpleNamespace(ds_meta_data_id=555)

    calls = {"new_version": 0, "update": []}
    class FakeDatasetService:
        def get_or_404(self, _id): return object()
        def get_by_id(self, _id): return ds
        def create_new_version(self, *a, **k):
            calls["new_version"] += 1
            return None
        def update_dsmetadata(self, meta_id, **kwargs):
            calls["update"].append((meta_id, kwargs))

    class FakeFakenodo:
        def create_new_deposition(self, ds): return {}

    monkeypatch.setattr(dataset_routes, "DataSetForm", FakeForm)
    monkeypatch.setattr(dataset_routes, "SteamCSVService", OkSteam)
    monkeypatch.setattr(dataset_routes, "dataset_service", FakeDatasetService())
    monkeypatch.setattr(dataset_routes, "fakenodo_service", FakeFakenodo())
    monkeypatch.setattr(dataset_routes.shutil, "rmtree", lambda p: None)

    with force_login(test_client, owner):
        r = test_client.post(f"/dataset/{dataset_id}/edit", data={})

    assert r.status_code == 200
    assert calls["new_version"] == 0
    assert any(meta_id == 555 and kw.get("title") == "Updated!" for meta_id, kw in calls["update"])
