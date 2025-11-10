import hashlib
import os
import io
import json
import shutil
from types import SimpleNamespace
from pathlib import Path

import pytest

from flask import Flask

from app import db
from app.modules.auth.models import User, UserRole
from app.modules.profile.models import UserProfile
from app.modules.dataset.models import DSMetaData, PublicationType, DataSet
from app.modules.dataset.steamcsv_service import SteamCSVService

from app.modules.dataset.services import (
    calculate_checksum_and_size,
    DataSetService,
    DSMetaDataService,
    DSViewRecordService,
    DOIMappingService,
    AuthorService,
    DSDownloadRecordService,
    SizeService,
)

CSV_EXAMPLES_DIR = Path(__file__).parent.parent / "csv_examples"
CSV_FAILURE_DIR = Path(__file__).parent.parent / "csv_examples_failure"


def copy_examples_to(src_dir: Path, dst_dir: Path):
    dst_dir.mkdir(parents=True, exist_ok=True)
    for entry in src_dir.iterdir():
        if entry.is_file():
            shutil.copy(entry, dst_dir / entry.name)


def test_validate_folder_accepts_valid_csvs(tmp_path):
    """All CSVs in csv_examples should validate without raising."""
    copy_examples_to(CSV_EXAMPLES_DIR, tmp_path)

    svc = SteamCSVService()
    # Should not raise
    svc.validate_folder(str(tmp_path))


def test_validate_folder_no_csvs_raises(tmp_path):
    svc = SteamCSVService()
    # empty folder -> should raise about no csv files
    with pytest.raises(ValueError) as exc:
        svc.validate_folder(str(tmp_path))
    assert "No .csv files found" in str(exc.value)


def test_validate_folder_invalid_headers_failure(tmp_path):
    # Copy a failing CSV with wrong header order
    copy_examples_to(CSV_FAILURE_DIR, tmp_path)

    svc = SteamCSVService()
    with pytest.raises(ValueError) as exc:
        svc.validate_folder(str(tmp_path))

    # Should report invalid headers for at least one file
    assert "missing headers appid" in str(exc.value).lower()


def test_validate_folder_missing_data_rows(tmp_path):
    # Create a CSV with correct headers but no data rows
    tmp_dir = tmp_path
    fpath = tmp_dir / "SoloTieneCabeceras.csv"
    headers = ",".join(SteamCSVService.REQUIRED_HEADERS)
    fpath.write_text(headers + "\n")

    svc = SteamCSVService()
    with pytest.raises(ValueError) as exc:
        svc.validate_folder(str(tmp_dir))

    assert "must contain at least one data row" in str(exc.value).lower()

def test_calculate_checksum_and_size(tmp_path):
    p = tmp_path / "sample.bin"
    data = b"hello world"
    p.write_bytes(data)

    checksum, size = calculate_checksum_and_size(str(p))

    assert size == len(data)
    expected = hashlib.sha256(data).hexdigest()
    assert checksum == expected


@pytest.mark.parametrize(
    "size,expected",
    [
        (500, "500 bytes"),
        (2048, "2.0 KB"),
        (1024 * 1024 * 5, "5.0 MB"),
        (1024 * 1024 * 1024 * 2, "2.0 GB"),
    ],
)
def test_size_service_human_readable(size, expected):
    svc = SizeService()
    assert svc.get_human_readable_size(size) == expected


def test_create_from_form_with_mocks(tmp_path):
    # Prepare CSV in user's temp folder
    csv_name = "uploaded.csv"
    csv_path = tmp_path / csv_name
    csv_path.write_text("appid,name\n1,Game\n")

    # Fake current_user with profile and temp_folder
    current_user = SimpleNamespace()
    current_user.id = 10
    current_user.profile = SimpleNamespace(surname="S", name="N", affiliation="A", orcid="O")
    current_user.temp_folder = lambda: str(tmp_path)

    # Fake form
    class FakeFM:
        def __init__(self, name):
            self.csv_filename = SimpleNamespace(data=name)

        def get_fmmetadata(self):
            return {"title": "fm"}

        def get_authors(self):
            return []

    form = SimpleNamespace()
    form.get_dsmetadata = lambda: {"title": "ds"}
    form.get_authors = lambda: []
    form.feature_models = [FakeFM(csv_name)]

    # Helpers to generate objects with ids and lists
    counter = {"v": 1}

    def make_create(kind):
        def create(**kwargs):
            obj = SimpleNamespace(**{k: v for k, v in kwargs.items() if not k.startswith("commit")})
            obj.id = counter["v"]
            counter["v"] += 1
            if kind == "dsmetadata":
                obj.authors = []
            if kind == "fmmetadata":
                obj.authors = []
            if kind == "fm":
                obj.files = []
            return obj

        return create

    fake_dsmeta_repo = SimpleNamespace(create=make_create("dsmetadata"))
    fake_author_repo = SimpleNamespace(create=lambda **kwargs: SimpleNamespace(**{k: v for k, v in kwargs.items() if not k.startswith("commit")}))
    fake_fmmeta_repo = SimpleNamespace(create=make_create("fmmetadata"))
    fake_feature_repo = SimpleNamespace(create=make_create("fm"))

    created_hubfile = {}

    def hubfile_create(**kwargs):
        obj = SimpleNamespace(**{k: v for k, v in kwargs.items() if not k.startswith("commit")})
        created_hubfile["obj"] = obj
        return obj

    fake_hubfile_repo = SimpleNamespace(create=hubfile_create)

    # repository with session
    fake_repository = SimpleNamespace(session=SimpleNamespace(commit=lambda: None, rollback=lambda: None))

    svc = DataSetService()
    svc.dsmetadata_repository = fake_dsmeta_repo
    svc.author_repository = fake_author_repo
    svc.fmmetadata_repository = fake_fmmeta_repo
    svc.feature_model_repository = fake_feature_repo
    svc.hubfilerepository = fake_hubfile_repo
    svc.repository = fake_repository

    # stub create method to return dataset with id
    def fake_create(commit=False, user_id=None, ds_meta_data_id=None):
        return SimpleNamespace(id=55)

    svc.create = fake_create

    # Run
    dataset = svc.create_from_form(form=form, current_user=current_user)

    assert dataset.id == 55

    # Check hubfile created with checksum and size matching file content
    expected_checksum, expected_size = calculate_checksum_and_size(str(csv_path))
    hf = created_hubfile.get("obj")
    assert hf is not None
    assert hf.name == csv_name
    assert hf.checksum == expected_checksum
    assert hf.size == expected_size

def test_delete_dataset_success(test_client):

    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User")
        db.session.add(profile)
        db.session.commit()

    user.role = UserRole.ADMIN
    db.session.commit()

    md = DSMetaData(title="t", description="d", publication_type=PublicationType.NONE)
    db.session.add(md)
    db.session.commit()
    ds = DataSet(user_id=user.id, ds_meta_data_id=md.id)
    db.session.add(ds)
    db.session.commit()

    test_client.get("/logout", follow_redirects=True)
    response = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"}, follow_redirects=True)
    assert response.status_code == 200

    response = test_client.post(f"/dataset/delete/{ds.id}", follow_redirects=True)
    assert response.status_code == 200, "Delete request failed"

    deleted = db.session.get(DataSet, ds.id)
    assert deleted is None, "Dataset was not deleted"

def test_delete_dataset_unsuccessful(test_client):

    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User")
        db.session.add(profile)
        db.session.commit()

    user.role = UserRole.USER
    db.session.commit()

    md = DSMetaData(title="t", description="d", publication_type=PublicationType.NONE)
    db.session.add(md)
    db.session.commit()
    ds = DataSet(user_id=user.id, ds_meta_data_id=md.id)
    db.session.add(ds)
    db.session.commit()

    test_client.get("/logout", follow_redirects=True)
    response = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"}, follow_redirects=True)
    assert response.status_code == 200

    response = test_client.post(f"/dataset/delete/{ds.id}", follow_redirects=True)
    assert response.status_code == 403, "Delete request should have failed"

    deleted = db.session.get(DataSet, ds.id)
    assert deleted is not None, "Dataset was incorrectly deleted"


def test_dataset_service_delegations():
    svc = DataSetService()
    svc.repository = SimpleNamespace(
        get_synchronized=lambda uid: "sync",
        get_unsynchronized=lambda uid: "unsync",
        get_unsynchronized_dataset=lambda uid, dsid: "unsync_ds",
        latest_synchronized=lambda: "latest",
        count_synchronized_datasets=lambda: 7,
    )

    assert svc.get_synchronized(1) == "sync"
    assert svc.get_unsynchronized(1) == "unsync"
    assert svc.get_unsynchronized_dataset(1, 2) == "unsync_ds"
    assert svc.latest_synchronized() == "latest"
    assert svc.count_synchronized_datasets() == 7


def test_get_uvlhub_doi_uses_domain_env(monkeypatch):
    svc = DataSetService()
    ds = SimpleNamespace(ds_meta_data=SimpleNamespace(dataset_doi="abc123"))
    monkeypatch.setenv("DOMAIN", "example.com")
    url = svc.get_uvlhub_doi(ds)
    assert url == "http://example.com/doi/abc123"


def test_dsmetadata_service_delegation():
    svc = DSMetaDataService()
    svc.repository = SimpleNamespace(update=lambda mid, **kw: "ok", filter_by_doi=lambda doi: "found")
    assert svc.update(1, foo=1) == "ok"
    assert svc.filter_by_doi("x") == "found"


def test_dsviewrecordservice_create_cookie_present(monkeypatch):
    app = Flask(__name__)
    svc = DSViewRecordService()

    # monkeypatch methods
    called = {"create": False}

    def the_record_exists(dataset, user_cookie):
        return True

    def create_new_record(dataset, user_cookie):
        called["create"] = True

    svc.the_record_exists = the_record_exists
    svc.create_new_record = create_new_record

    with app.test_request_context("/", headers={"Cookie": "view_cookie=present-cookie"}):
        cookie = svc.create_cookie(dataset=SimpleNamespace())
        assert cookie == "present-cookie"
        # should not have created a new record since it exists
        assert called["create"] is False


def test_dsviewrecordservice_create_cookie_absent(monkeypatch):
    app = Flask(__name__)
    svc = DSViewRecordService()

    created = {"called": False, "cookie": None}

    def the_record_exists(dataset, user_cookie):
        return False

    def create_new_record(dataset, user_cookie):
        created["called"] = True
        created["cookie"] = user_cookie

    svc.the_record_exists = the_record_exists
    svc.create_new_record = create_new_record

    with app.test_request_context("/"):
        cookie = svc.create_cookie(dataset=SimpleNamespace())
        # should generate a uuid-like string
        assert isinstance(cookie, str) and len(cookie) > 0
        assert created["called"] is True
        assert created["cookie"] == cookie


def test_doi_mapping_service_get_new_doi():
    svc = DOIMappingService()
    svc.repository = SimpleNamespace(get_new_doi=lambda old: SimpleNamespace(dataset_doi_new="new-doi"))
    assert svc.get_new_doi("old") == "new-doi"
    svc.repository = SimpleNamespace(get_new_doi=lambda old: None)
    assert svc.get_new_doi("old") is None


def test_thin_wrapper_services_smoke():
    a = AuthorService()
    d = DSDownloadRecordService()
    # just ensure they expose a repository attribute
    assert hasattr(a, "repository")
    assert hasattr(d, "repository")


def login_client(client, email=None, password=None):
    test_email = email or os.getenv(
        "TEST_USER_EMAIL",
        "test@example.com",
    )
    test_password = password or os.getenv(
        "TEST_USER_PASSWORD",
        "test1234",
    )
    return client.post(
        "/login",
        data={"email": test_email, "password": test_password},
        follow_redirects=True,
    )


def test_get_upload_requires_login(test_client):
    # without login should redirect to login
    test_client.get("/logout", follow_redirects=True)
    resp = test_client.get("/dataset/upload")
    assert resp.status_code in (302, 301)


def test_upload_and_delete_csv_flow(test_client, tmp_path, monkeypatch):
    # make uploads go to tmp_path by setting UPLOADS_DIR
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))

    # login
    resp = login_client(test_client)
    assert resp.status_code == 200

    # GET upload page
    resp = test_client.get("/dataset/upload")
    assert resp.status_code == 200
    assert b"CSV files" in resp.data

    # upload a CSV
    csv_content = b"appid,name,release_date,is_free,developers,publishers,platforms,genres,tags\n1,Game,2020-01-01,true,Dev,Pub,win,Action,tag1\n"
    data = {
        "file": (io.BytesIO(csv_content), "test.csv"),
    }
    resp = test_client.post("/dataset/file/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert "filename" in body
    filename = body["filename"]

    # check file exists in temp folder
    temp_folder = os.path.join(str(tmp_path), "temp", "1")
    # the user created in conftest has id 1
    file_path = os.path.join(temp_folder, filename)
    assert os.path.exists(file_path)

    # call delete endpoint
    resp = test_client.post("/dataset/file/delete", data=json.dumps({"file": filename}), content_type="application/json")
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body.get("message") == "File deleted successfully"
    assert not os.path.exists(file_path)

    # cleanup uploads dir
    if os.path.exists(str(tmp_path)):
        import shutil

        shutil.rmtree(str(tmp_path))


def test_clean_temp_endpoint(test_client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))

    # login
    resp = login_client(test_client)
    assert resp.status_code == 200

    # create temp folder and a couple files
    temp_folder = os.path.join(str(tmp_path), "temp", "1")
    os.makedirs(temp_folder, exist_ok=True)
    f1 = os.path.join(temp_folder, "a.txt")
    with open(f1, "w") as fh:
        fh.write("x")

    # call clean_temp
    resp = test_client.post("/dataset/file/clean_temp")
    assert resp.status_code == 302



def test_preview_csv_route(test_client, tmp_path, monkeypatch):
    resp = login_client(test_client)
    assert resp.status_code == 200

    # create a temp csv
    f = tmp_path / "p.csv"
    f.write_text("appid,name\n1,Game\n")

    class FakeRepo:
        def get_or_404(self, file_id):
            return SimpleNamespace(get_path=lambda: str(f))

    # monkeypatch HubfileService to return fake repo
    monkeypatch.setattr("app.modules.dataset.routes.HubfileService", lambda: SimpleNamespace(repository=FakeRepo()))

    r = test_client.get("/dataset/file/preview/1")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert "headers" in data and "rows" in data


def test_download_dataset_route(test_client, tmp_path, monkeypatch):
    resp = login_client(test_client)
    assert resp.status_code == 200

    # prepare uploads folder with a file
    uploads = tmp_path / "uploads" / "user_1" / "dataset_9"
    uploads.mkdir(parents=True)
    (uploads / "a.txt").write_text("x")

    import app.modules.dataset.routes as routes_mod

    # monkeypatch dataset_service.get_or_404
    monkeypatch.setattr(routes_mod, "dataset_service", SimpleNamespace(get_or_404=lambda dsid: SimpleNamespace(user_id=1, id=9)))

    # monkeypatch DSDownloadRecord and DSDownloadRecordService to avoid DB
    routes_mod.DSDownloadRecord = SimpleNamespace(query=SimpleNamespace(filter_by=lambda **kw: SimpleNamespace(first=lambda: None)))
    monkeypatch.setattr(routes_mod, "DSDownloadRecordService", lambda: SimpleNamespace(create=lambda **kw: None))

    # set WORKING_DIR so uploads path resolves
    monkeypatch.setenv("WORKING_DIR", str(tmp_path))

    r = test_client.get("/dataset/download/9")
    assert r.status_code == 200
    # content-type should be application/zip
    assert r.headers.get("Content-Type") in ("application/zip", "application/octet-stream")
    
def test_dataset_stats_route(monkeypatch, test_client):
    fake_files = [
        SimpleNamespace(name="a.uvl", download_count=2),
        SimpleNamespace(name="b.uvl", download_count=5),
    ]
    fake_feature_model = SimpleNamespace(files=fake_files)
    fake_dataset = SimpleNamespace(id=123, feature_models=[fake_feature_model])

    fake_service = SimpleNamespace(get_or_404=lambda _id: fake_dataset)
    import app.modules.dataset.routes as routes_mod
    monkeypatch.setattr(routes_mod, "dataset_service", fake_service)

    response = test_client.get("/dataset/123/stats")
    assert response.status_code == 200

    data = json.loads(response.data)

    assert data["id"] == 123
    assert data["downloads"]["a.uvl"] == 2
    assert data["downloads"]["b.uvl"] == 5


def test_dataset_stats_route_empty(monkeypatch, test_client):

    from types import SimpleNamespace
    import json
    import app.modules.dataset.routes as routes_mod

    fake_dataset = SimpleNamespace(id=99, feature_models=[])

    fake_service = SimpleNamespace(get_or_404=lambda _id: fake_dataset)
    monkeypatch.setattr(routes_mod, "dataset_service", fake_service)

    r = test_client.get("/dataset/99/stats")
    assert r.status_code == 200

    data = json.loads(r.data)
    assert data["id"] == 99
    assert data["downloads"] == {}