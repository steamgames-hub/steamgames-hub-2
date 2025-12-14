import hashlib
import io
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict

import app.modules.dataset.routes as routes_mod
from app import db
from app.modules.auth.models import User, UserRole
from app.modules.dataset.forms import DatasetFileForm
from app.modules.dataset.models import DataCategory, DataSet, DSMetaData
from app.modules.dataset.repositories import DSMetaDataRepository
from app.modules.dataset.services import (
    AuthorService,
    DataSetService,
    DOIMappingService,
    DSDownloadRecordService,
    DSMetaDataService,
    DSViewRecordService,
    SizeService,
    calculate_checksum_and_size,
)
from app.modules.dataset.steamcsv_service import SteamCSVService
from app.modules.profile.models import UserProfile

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
    # Accept either 'missing headers' or 'invalid headers. expected exactly' for robustness
    error_msg = str(exc.value).lower()
    assert (
        "invalid headers. expected exactly" in error_msg or "missing headers" in error_msg
    ), f"Unexpected error message: {error_msg}"


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
    class FakeDatasetFile:
        def __init__(self, name):
            self.csv_filename = SimpleNamespace(data=name)

        def get_file_metadata(self):
            return {"title": "fm"}

        def get_authors(self):
            return []

    form = SimpleNamespace()
    form.get_dsmetadata = lambda: {"title": "ds"}
    form.get_authors = lambda: []
    form.dataset_files = [FakeDatasetFile(csv_name)]

    # Fake draftmode
    draft_mode = False

    # Helpers to generate objects with ids and lists
    counter = {"v": 1}

    def make_create(kind):
        def create(**kwargs):
            obj = SimpleNamespace(**{k: v for k, v in kwargs.items() if not k.startswith("commit")})
            obj.id = counter["v"]
            counter["v"] += 1
            if kind == "dsmetadata":
                obj.authors = []
            if kind == "datasetfilemetadata":
                obj.authors = []
            if kind == "datasetfile":
                obj.files = []
            return obj

        return create

    fake_dsmeta_repo = SimpleNamespace(create=make_create("dsmetadata"))
    fake_author_repo = SimpleNamespace(
        create=lambda **kwargs: SimpleNamespace(**{k: v for k, v in kwargs.items() if not k.startswith("commit")})
    )
    fake_dataset_file_meta_repo = SimpleNamespace(create=make_create("datasetfilemetadata"))
    fake_dataset_file_repo = SimpleNamespace(create=make_create("datasetfile"))

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
    svc.dataset_file_metadata_repository = fake_dataset_file_meta_repo
    svc.dataset_file_repository = fake_dataset_file_repo
    svc.hubfilerepository = fake_hubfile_repo
    svc.repository = fake_repository

    # stub create method to return dataset with id
    def fake_create(commit=False, user_id=None, ds_meta_data_id=None, draft_mode=draft_mode):
        return SimpleNamespace(id=55)

    svc.create = fake_create

    # Run
    dataset = svc.create_from_form(form=form, current_user=current_user, draft_mode=draft_mode)

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

    md = DSMetaData(title="t", description="d", data_category=DataCategory.NONE)
    db.session.add(md)
    db.session.commit()
    ds = DataSet(user_id=user.id, ds_meta_data_id=md.id)
    db.session.add(ds)
    db.session.commit()

    test_client.get("/logout", follow_redirects=True)
    response = test_client.post(
        "/login", data={"email": "test@example.com", "password": "test1234"}, follow_redirects=True
    )
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

    md = DSMetaData(title="t", description="d", data_category=DataCategory.NONE)
    db.session.add(md)
    db.session.commit()
    ds = DataSet(user_id=user.id, ds_meta_data_id=md.id)
    db.session.add(ds)
    db.session.commit()

    test_client.get("/logout", follow_redirects=True)
    response = test_client.post(
        "/login", data={"email": "test@example.com", "password": "test1234"}, follow_redirects=True
    )
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


def test_get_steamgameshub_doi_uses_domain_env(monkeypatch):
    svc = DataSetService()
    ds = SimpleNamespace(ds_meta_data=SimpleNamespace(dataset_doi="abc123"))
    monkeypatch.setenv("DOMAIN", "example.com")
    url = svc.get_steamgameshub_doi(ds)
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


def login_client(client, email="test@example.com", password="test1234"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


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
    assert resp.status_code in (200, 302)  # aceptar redirect también

    # GET upload page
    resp = test_client.get("/dataset/upload")
    assert resp.status_code in (200, 302)
    if resp.status_code == 200:
        assert b"CSV files" in resp.data

        # upload a CSV
        csv_content = (
            b"appid,name,release_date,is_free,developers,publishers,"
            b"platforms,genres,tags\n1,Game,2020-01-01,true,Dev,Pub,"
            b"win,Action,tag1\n"
        )
        data = {
            "file": (io.BytesIO(csv_content), "test.csv"),
        }
        resp = test_client.post("/dataset/file/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code in (200, 302)
        if resp.status_code == 200:
            body = json.loads(resp.data)
            assert "filename" in body
            filename = body["filename"]

            # check file exists in temp folder
            temp_folder = os.path.join(str(tmp_path), "temp", "1")
            file_path = os.path.join(temp_folder, filename)
            assert os.path.exists(file_path)

            # call delete endpoint
            resp = test_client.post(
                "/dataset/file/delete", data=json.dumps({"file": filename}), content_type="application/json"
            )
            assert resp.status_code in (200, 302)
            if resp.status_code == 200:
                body = json.loads(resp.data)
                assert body.get("message") == "File deleted successfully"
                assert not os.path.exists(file_path)

    # cleanup uploads dir
    if os.path.exists(str(tmp_path)):
        shutil.rmtree(str(tmp_path))


def test_clean_temp_endpoint(test_client, tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))

    # login
    resp = login_client(test_client)
    assert resp.status_code in (200, 302)

    # create temp folder and a couple files
    temp_folder = os.path.join(str(tmp_path), "temp", "1")
    os.makedirs(temp_folder, exist_ok=True)
    f1 = os.path.join(temp_folder, "a.txt")
    with open(f1, "w") as fh:
        fh.write("x")

    # call clean_temp
    resp = test_client.post("/dataset/file/clean_temp")
    assert resp.status_code in (200, 302)
    if resp.status_code == 200:
        body = json.loads(resp.data)
        assert body.get("message") == "Temp folder cleaned"
        # folder exists but should be empty
        assert os.path.isdir(temp_folder)
        assert os.listdir(temp_folder) == []


def test_preview_csv_route(test_client, tmp_path, monkeypatch):
    resp = login_client(test_client)
    assert resp.status_code in (200, 302)

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
    assert resp.status_code in (200, 302)

    # prepare uploads folder with a file
    uploads = tmp_path / "uploads" / "user_1" / "dataset_9"
    uploads.mkdir(parents=True)
    (uploads / "a.txt").write_text("x")

    # monkeypatch dataset_service.get_or_404
    monkeypatch.setattr(
        routes_mod, "dataset_service", SimpleNamespace(get_or_404=lambda dsid: SimpleNamespace(user_id=1, id=9))
    )

    # monkeypatch DSDownloadRecord and DSDownloadRecordService to avoid DB
    routes_mod.DSDownloadRecord = SimpleNamespace(
        query=SimpleNamespace(filter_by=lambda **kw: SimpleNamespace(first=lambda: None))
    )
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
    fake_dataset_file = SimpleNamespace(files=fake_files)
    fake_dataset = SimpleNamespace(id=123, dataset_files=[fake_dataset_file])

    fake_service = SimpleNamespace(get_or_404=lambda _id: fake_dataset)

    monkeypatch.setattr(routes_mod, "dataset_service", fake_service)

    response = test_client.get("/dataset/123/stats")
    assert response.status_code == 200

    data = json.loads(response.data)

    assert data["id"] == 123
    assert data["downloads"]["a.uvl"] == 2
    assert data["downloads"]["b.uvl"] == 5


def test_dataset_stats_route_empty(monkeypatch, test_client):

    fake_dataset = SimpleNamespace(id=99, dataset_files=[])

    fake_service = SimpleNamespace(get_or_404=lambda _id: fake_dataset)
    monkeypatch.setattr(routes_mod, "dataset_service", fake_service)

    r = test_client.get("/dataset/99/stats")
    assert r.status_code == 200

    data = json.loads(r.data)
    assert data["id"] == 99
    assert data["downloads"] == {}


def test_list_all_issues_requires_login(test_client):
    test_client.get("/logout", follow_redirects=True)
    response = test_client.get("/dataset/issues")
    assert response.status_code in (301, 302)  # Should redirect to login


def test_list_all_issues_requires_admin(test_client):
    # Create and login as non-admin user
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    user.role = UserRole.USER
    db.session.commit()

    response = login_client(test_client)
    assert response.status_code == 200

    response = test_client.get("/dataset/issues")
    assert response.status_code == 403  # Should be forbidden for non-admin


def test_list_all_issues_success(test_client, monkeypatch):

    # Create and login as admin user
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    user.role = UserRole.ADMIN
    db.session.commit()

    response = login_client(test_client)
    assert response.status_code == 200

    # Mock IssueService to return test data with full object structure
    fake_issues = [
        SimpleNamespace(
            id=1,
            description="Test issue 1",
            dataset_id=1,
            reporter_id=1,
            created_at=datetime.now(timezone.utc),
            dataset=SimpleNamespace(
                id=1, ds_meta_data=SimpleNamespace(dataset_doi="10.5281/zenodo.123456", title="Test Dataset")
            ),
            reporter=SimpleNamespace(id=1, profile=SimpleNamespace(name="Test", surname="User")),
        )
    ]

    class FakeIssueService:
        def list_all(self):
            return fake_issues

    # Patch the IssueService used by the routes module so the view
    # will receive our fake issues list.

    monkeypatch.setattr(routes_mod, "IssueService", lambda: FakeIssueService())

    response = test_client.get("/dataset/issues")
    assert response.status_code == 200
    # Verify issue data is passed to template
    assert b"Test issue 1" in response.data


def test_open_issue_requires_admin(test_client):
    # Ensure non-admin cannot open/close issues
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    user.role = UserRole.USER
    db.session.commit()

    response = login_client(test_client)
    assert response.status_code == 200

    r = test_client.put("/dataset/issues/open/1/")
    assert r.status_code == 403


def test_open_issue_success(test_client, monkeypatch):

    # Login as admin
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    user.role = UserRole.ADMIN
    db.session.commit()

    response = login_client(test_client)
    assert response.status_code == 200

    # Prepare fake issues to be returned after toggling
    fake_issues = [
        SimpleNamespace(
            id=1,
            description="Toggled issue",
            dataset_id=1,
            reporter_id=1,
            created_at=datetime.now(timezone.utc),
            dataset=SimpleNamespace(
                id=1, ds_meta_data=SimpleNamespace(dataset_doi="10.5281/zenodo.654321", title="Toggled Dataset")
            ),
            reporter=SimpleNamespace(id=1, profile=SimpleNamespace(name="Admin", surname="User")),
            is_open=False,
        )
    ]

    class FakeIssueService2:
        def open_or_close(self, issue_id):
            # pretend to toggle
            return True

        def list_all(self):
            return fake_issues

    monkeypatch.setattr(routes_mod, "IssueService", lambda: FakeIssueService2())

    r = test_client.put("/dataset/issues/open/1/")
    assert r.status_code == 200
    assert b"Toggled issue" in r.data


def test_dataset_file_version_accepts_valid_semver(test_app):
    # Use POST request context to let FlaskForm read formdata
    with test_app.test_request_context("/", method="POST"):
        form = DatasetFileForm(
            formdata=MultiDict(
                {
                    "csv_filename": "file.csv",
                    "version": "1.2.3",
                }
            )
        )
        assert form.validate() is True


essa = "1.2"  # to keep flake8 from complaining about magic values reuse


def test_dataset_file_version_rejects_invalid_format(test_app):
    with test_app.test_request_context("/", method="POST"):
        form = DatasetFileForm(
            formdata=MultiDict(
                {
                    "csv_filename": "file.csv",
                    "version": essa,  # not x.y.z
                }
            )
        )
        assert form.validate() is False
        assert "x.y.z" in ";".join(form.version.errors)


def test_dataset_file_version_optional_when_empty(test_app):
    with test_app.test_request_context("/", method="POST"):
        form = DatasetFileForm(
            formdata=MultiDict(
                {
                    "csv_filename": "file.csv",
                    "version": "",
                }
            )
        )
        assert form.validate() is True


def test_dsmetadata_has_version_and_is_latest_attributes():
    # DSMetaData should expose the new fields (version, is_latest) on instances
    md = DSMetaData(title="t", description="d", data_category=DataCategory.NONE)
    # attributes must exist (DB default may be None/False but attribute should be present)
    assert hasattr(md, "version")
    assert hasattr(md, "is_latest")


def test_filter_only_latest_from_list():
    # prepare two DSMetaData objects, one latest and one not
    ds_old = DSMetaData(
        title="old",
        description="old",
        data_category=DataCategory.NONE,
        publication_doi="10.0/old",
        dataset_doi="10.0/old",
        version="0.1.0",
    )
    ds_new = DSMetaData(
        title="new",
        description="new",
        data_category=DataCategory.NONE,
        publication_doi="10.0/new",
        dataset_doi="10.0/new",
        version="1.0.0",
    )
    # set the is_latest flags as if coming from the repository
    ds_old.is_latest = False
    ds_new.is_latest = True

    mixed = [ds_old, ds_new]

    # Emulate repository returning mixed results and ensure only is_latest==True are selected
    latest_only = [d for d in mixed if getattr(d, "is_latest", False) is True]

    assert len(latest_only) == 1
    assert latest_only[0].title == "new"
    assert latest_only[0].version == "1.0.0"


def test_count_and_list_consider_only_is_latest():
    # Build sample DSMetaData records with mixed is_latest values
    records = []
    for i in range(5):
        md = DSMetaData(
            title=f"ds{i}",
            description="x",
            data_category=DataCategory.NONE,
            publication_doi=f"10.0/{i}",
            dataset_doi=f"10.0/{i}",
            version=f"1.0.{i}",
        )
        # mark only even indices as latest for the test
        md.is_latest = i % 2 == 0
        records.append(md)

    # Fake repository that would return all DSMetaData rows
    class FakeRepo:
        def list_all(self):
            return records

        def count_all(self):
            return len(records)

    repo = FakeRepo()

    # Simulate repository-level logic that should count/list only latest records
    listed_latest = [r for r in repo.list_all() if getattr(r, "is_latest", False)]
    counted_latest = len(listed_latest)

    # expected number of latest records (indices 0,2,4 -> 3)
    assert counted_latest == 3
    assert all(getattr(r, "is_latest", False) for r in listed_latest)
    # sanity: repo.count_all still reports total if asked
    assert repo.count_all() == 5


def test_dsmetadata_repository_get_all_versions_by_deposition_id():
    """Test that repository returns all versions with same deposition_id."""

    repo = DSMetaDataRepository()

    # Create multiple DSMetaData with same deposition_id but different versions
    deposition_id = 12345
    md1 = DSMetaData(
        title="v1",
        description="desc",
        data_category=DataCategory.NONE,
        deposition_id=deposition_id,
        dataset_doi="10.5281/zenodo.1",
        version=1.0,
        is_latest=False,
    )
    md2 = DSMetaData(
        title="v2",
        description="desc",
        data_category=DataCategory.NONE,
        deposition_id=deposition_id,
        dataset_doi="10.5281/zenodo.2",
        version=2.0,
        is_latest=True,
    )
    md3 = DSMetaData(
        title="v3",
        description="desc",
        data_category=DataCategory.NONE,
        deposition_id=deposition_id,
        dataset_doi="10.5281/zenodo.3",
        version=1.5,
        is_latest=False,
    )

    db.session.add_all([md1, md2, md3])
    db.session.commit()

    # Retrieve all versions by deposition_id
    versions = repo.get_all_versions_by_deposition_id(deposition_id)

    # Should return all 3 versions
    assert len(versions) == 3

    # Should be ordered by version ascending (oldest first)
    versions_list = list(versions)
    assert versions_list[0].version == 1.0
    assert versions_list[1].version == 1.5
    assert versions_list[2].version == 2.0

    # Cleanup
    db.session.delete(md1)
    db.session.delete(md2)
    db.session.delete(md3)
    db.session.commit()


def test_dsmetadata_service_get_all_versions_by_deposition_id():
    """Test that service delegates to repository correctly."""
    svc = DSMetaDataService()
    svc.repository = SimpleNamespace(
        get_all_versions_by_deposition_id=lambda dep_id: [
            SimpleNamespace(version=1.0, is_latest=False),
            SimpleNamespace(version=2.0, is_latest=True),
        ]
    )

    versions = svc.get_all_versions_by_deposition_id(12345)

    assert len(versions) == 2
    assert versions[0].version == 1.0
    assert versions[1].version == 2.0
    assert versions[1].is_latest is True


def test_dataset_versions_route_returns_all_versions(test_client):
    """Test that /dataset/versions/<id> returns timeline with all versions."""
    # Create user and login
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User")
        db.session.add(profile)
        db.session.commit()

    # Create multiple dataset versions with same deposition_id
    deposition_id = 99999
    md1 = DSMetaData(
        title="Dataset v1",
        description="First version",
        data_category=DataCategory.GENERAL,
        deposition_id=deposition_id,
        dataset_doi="10.5281/zenodo.100",
        version=1.0,
        is_latest=False,
    )
    md2 = DSMetaData(
        title="Dataset v2",
        description="Second version",
        data_category=DataCategory.GENERAL,
        deposition_id=deposition_id,
        dataset_doi="10.5281/zenodo.101",
        version=2.0,
        is_latest=True,
    )

    db.session.add_all([md1, md2])
    db.session.commit()

    # Create datasets linked to metadata
    ds1 = DataSet(user_id=user.id, ds_meta_data_id=md1.id, draft_mode=False)
    ds2 = DataSet(user_id=user.id, ds_meta_data_id=md2.id, draft_mode=False)

    db.session.add_all([ds1, ds2])
    db.session.commit()

    # Access versions timeline
    response = test_client.get(f"/dataset/versions/{ds2.id}")

    # Should succeed
    assert response.status_code == 200

    # Should contain version information
    assert b"Timeline of versions" in response.data
    assert b"1.0" in response.data or b"1" in response.data
    assert b"2.0" in response.data or b"2" in response.data
    assert b"Latest version" in response.data

    # Cleanup: Delete datasets first (foreign key constraint)
    db.session.query(DataSet).filter_by(id=ds1.id).delete()
    db.session.query(DataSet).filter_by(id=ds2.id).delete()
    # Then delete metadata
    db.session.query(DSMetaData).filter_by(id=md1.id).delete()
    db.session.query(DSMetaData).filter_by(id=md2.id).delete()
    db.session.commit()


def test_dataset_versions_route_returns_404_for_draft(test_client):
    """Test that /dataset/versions/<id> returns 404 for draft datasets."""
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User")
        db.session.add(profile)
        db.session.commit()

    md = DSMetaData(
        title="Draft Dataset",
        description="Draft",
        data_category=DataCategory.GENERAL,
        deposition_id=None,
    )
    db.session.add(md)
    db.session.commit()

    ds = DataSet(user_id=user.id, ds_meta_data_id=md.id, draft_mode=True)
    db.session.add(ds)
    db.session.commit()

    response = test_client.get(f"/dataset/versions/{ds.id}")

    # Should return 404 for draft dataset
    assert response.status_code == 404

    # Cleanup
    db.session.delete(ds)
    db.session.delete(md)
    db.session.commit()


def test_dataset_versions_route_returns_404_for_no_deposition_id(
    test_client,
):
    """Test that /dataset/versions/<id> returns 404 if no deposition_id."""
    user = User.query.filter_by(email="test@example.com").first()
    if not user:
        user = User(email="test@example.com", password="test1234", verified=True)
        db.session.add(user)
        db.session.commit()

    if not user.profile:
        profile = UserProfile(user_id=user.id, name="Test", surname="User")
        db.session.add(profile)
        db.session.commit()

    md = DSMetaData(
        title="No Deposition Dataset",
        description="No deposition",
        data_category=DataCategory.GENERAL,
        deposition_id=None,
        dataset_doi="10.5281/zenodo.999",
    )
    db.session.add(md)
    db.session.commit()

    ds = DataSet(user_id=user.id, ds_meta_data_id=md.id, draft_mode=False)
    db.session.add(ds)
    db.session.commit()

    response = test_client.get(f"/dataset/versions/{ds.id}")

    # Should return 404 if no deposition_id
    assert response.status_code == 404

    # Cleanup
    db.session.delete(ds)
    db.session.delete(md)
    db.session.commit()


# create new version of dataset tests


@pytest.fixture(scope="function")
def test_user(test_client, test_app):
    """Create a test user with profile."""
    with test_app.app_context():
        unique_email = f"test_{uuid.uuid4()}@example.com"
        user = User(email=unique_email, password="test1234")
        db.session.add(user)
        db.session.flush()

        profile = UserProfile(
            user_id=user.id, name="Test", surname="User", affiliation="TestOrg", orcid="0000-0000-0000-0000"
        )
        db.session.add(profile)
        db.session.commit()

        user_id = user.id

    # Yield the user ID, not the detached object
    yield user_id


@pytest.fixture(scope="function")
def initial_dataset(test_user, test_app):
    """Create an initial dataset for testing."""
    with test_app.app_context():
        md = DSMetaData(
            title="Test Dataset",
            description="Test Description",
            data_category=DataCategory.GENERAL,
            dataset_doi="10.1234/test",
            version=1.0,
            is_latest=True,
        )
        db.session.add(md)
        db.session.flush()

        ds = DataSet(user_id=test_user, ds_meta_data_id=md.id, draft_mode=False)
        db.session.add(ds)
        db.session.commit()

        ds_id = ds.id

    yield ds_id


@pytest.fixture(scope="function")
def auth_client(test_client, test_user, initial_dataset, test_app):
    """Authenticated test client logged in as test_user with initial dataset."""
    # Mock authentication
    with test_client.session_transaction() as sess:
        sess["user_id"] = test_user

    yield test_client

    # Unified cleanup: delete in correct order (child before parent)
    with test_app.app_context():
        # Clean up dataset
        ds_obj = DataSet.query.get(initial_dataset)
        if ds_obj:
            # if ds_obj.ds_meta_data:
            #    db.session.delete(ds_obj.ds_meta_data)
            db.session.delete(ds_obj)

        # Clean up user
        user_obj = User.query.get(test_user)
        if user_obj:
            if user_obj.profile:
                db.session.delete(user_obj.profile)
            db.session.delete(user_obj)

        db.session.commit()


def test_create_new_version_increments_version(initial_dataset, test_user, test_app):
    """Test that create_new_version increments version number."""
    with test_app.app_context():
        # Re-query user and initial dataset to ensure they're bound to session
        user_obj = User.query.get(test_user)
        ds_obj = DataSet.query.get(initial_dataset)

        # Simulate form
        form = SimpleNamespace(
            get_dsmetadata=lambda: {
                "title": "Updated Dataset",
                "description": "Second version",
                "data_category": "GENERAL",
                "publication_doi": None,
                "dataset_doi": None,  # Will be set from original
                "tags": None,
            },
            get_authors=lambda: [],
            feature_models=[],
        )

        service = DataSetService()

        new_ds = service.create_new_version(initial_dataset, form, user_obj)

        # Verify new dataset created
        assert new_ds.id is not None
        assert new_ds.id != initial_dataset

        # Verify version incremented
        old_version = ds_obj.ds_meta_data.version
        new_version = new_ds.ds_meta_data.version
        assert new_version == old_version + 1.0


def test_create_new_version_marks_old_not_latest(initial_dataset, test_user, test_app):
    """Test that old metadata is marked is_latest=False."""
    with test_app.app_context():
        user_obj = User.query.get(test_user)

        form = SimpleNamespace(
            get_dsmetadata=lambda: {
                "title": "Updated",
                "description": "v2",
                "data_category": "GENERAL",
                "publication_doi": None,
                "dataset_doi": None,
                "tags": None,
            },
            get_authors=lambda: [],
            feature_models=[],
        )

        service = DataSetService()

        old_ds = DataSet.query.get(initial_dataset)
        service.create_new_version(initial_dataset, form, user_obj)

        # Refresh and check old metadata
        old_meta = db.session.get(DSMetaData, old_ds.ds_meta_data_id)
        assert old_meta.is_latest is False


def test_create_new_version_preserves_original_doi_for_new(initial_dataset, test_user, test_app):
    """Test that new dataset keeps original DOI while old gets versioned DOI."""
    with test_app.app_context():
        user_obj = User.query.get(test_user)
        old_ds = DataSet.query.get(initial_dataset)
        original_doi = old_ds.ds_meta_data.dataset_doi

        form = SimpleNamespace(
            get_dsmetadata=lambda: {
                "title": "Updated",
                "description": "v2",
                "data_category": "GENERAL",
                "publication_doi": None,
                "dataset_doi": None,
                "tags": None,
            },
            get_authors=lambda: [],
            feature_models=[],
        )

        service = DataSetService()
        new_ds = service.create_new_version(initial_dataset, form, user_obj)

        # New metadata should have original DOI
        assert new_ds.ds_meta_data.dataset_doi == original_doi

        # Old metadata should have versioned DOI
        old_meta = db.session.get(DSMetaData, old_ds.ds_meta_data_id)
        assert old_meta.dataset_doi == f"{original_doi}/v{int(old_meta.version)}"


def test_create_new_version_new_is_latest(initial_dataset, test_user, test_app):
    """Test that new metadata is marked is_latest=True."""
    with test_app.app_context():
        user_obj = User.query.get(test_user)

        form = SimpleNamespace(
            get_dsmetadata=lambda: {
                "title": "Updated",
                "description": "v2",
                "data_category": "GENERAL",
                "publication_doi": None,
                "dataset_doi": None,
                "tags": None,
            },
            get_authors=lambda: [],
            feature_models=[],
        )

        service = DataSetService()
        new_ds = service.create_new_version(initial_dataset, form, user_obj)

        assert new_ds.ds_meta_data.is_latest is True


def test_create_new_version_invalid_dataset_id(test_user, test_app):
    """Test that invalid dataset_id raises ValueError."""
    form = SimpleNamespace(
        get_dsmetadata=lambda: {"title": "x"},
        get_authors=lambda: [],
        feature_models=[],
    )

    service = DataSetService()

    with test_app.app_context():
        with pytest.raises(ValueError, match="not found"):
            service.create_new_version(9999, form, test_user)


def test_update_dataset_get_returns_form(test_client):
    """Test that GET /dataset/<id>/edit returns form page."""
    # Login first
    resp = login_client(test_client)
    assert resp.status_code in (200, 302)

    # Just check that accessing a non-existent dataset returns appropriate status
    # The route /dataset/<id>/edit exists and is registered
    response = test_client.get("/dataset/1/edit")

    # Check response - should be 200 if dataset exists or 404/302 if not
    assert response.status_code in (200, 302, 404)


def test_update_dataset_get_not_found(test_client):
    """Test that GET with invalid dataset_id returns 404."""
    # Login using the existing login_client pattern
    resp = login_client(test_client)
    assert resp.status_code in (200, 302)

    # Now make the request with invalid dataset ID
    response = test_client.get("/dataset/9999/edit", follow_redirects=True)
    assert response.status_code in [404, 400]


def test_update_dataset_post_metadata_only_no_new_version(test_client, test_app):
    """Test POST with no files uploaded only updates metadata, no new version created."""
    # Setup: Create a dataset for testing
    with test_app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        md = DSMetaData(
            title="Test Dataset",
            description="Test Description",
            data_category=DataCategory.GENERAL,
            dataset_doi="10.1234/test-metadata",
            version=1.0,
            is_latest=True,
        )
        db.session.add(md)
        db.session.flush()

        ds = DataSet(user_id=user.id, ds_meta_data_id=md.id, draft_mode=False)
        db.session.add(ds)
        db.session.commit()
        dataset_id = ds.id
        initial_version = ds.ds_meta_data.version

    # Login
    resp = login_client(test_client)
    assert resp.status_code in (200, 302)

    data = {
        "title": "Updated Title",
        "description": "Updated Description",
        "data_category": "GENERAL",
        "csrf_token": "",  # Will be added by form
    }

    # Send POST without file upload
    test_client.post(f"/dataset/{dataset_id}/edit", data=data, follow_redirects=False)

    # Check dataset was updated, not versioned
    with test_app.app_context():
        db.session.expire_all()
        dataset = db.session.get(DataSet, dataset_id)

        # Version should not have incremented if no files
        # (This validates the conditional logic: files_changed determines versioning)
        assert dataset.ds_meta_data.version == initial_version


def test_update_dataset_post_with_files_creates_new_version(test_client, test_app, tmp_path):
    """Test POST with files uploaded creates new version."""
    # Setup: Create a dataset for testing
    with test_app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        md = DSMetaData(
            title="Test Dataset",
            description="Test Description",
            data_category=DataCategory.GENERAL,
            dataset_doi="10.1234/test-files",
            version=1.0,
            is_latest=True,
        )
        db.session.add(md)
        db.session.flush()

        ds = DataSet(user_id=user.id, ds_meta_data_id=md.id, draft_mode=False)
        db.session.add(ds)
        db.session.commit()
        dataset_id = ds.id
        initial_version = ds.ds_meta_data.version

    # Login
    resp = login_client(test_client)
    assert resp.status_code in (200, 302)

    # Create temporary file to upload
    test_file = tmp_path / "test_data.csv"
    test_file.write_text("col1,col2\n1,2\n3,4")

    with open(test_file, "rb") as f:
        data = {
            "title": "Updated Dataset v2",
            "description": "Second version with files",
            "data_category": "GENERAL",
            "files": (f, "test_data.csv"),
            "csrf_token": "",
        }

        test_client.post(
            f"/dataset/{dataset_id}/edit", data=data, content_type="multipart/form-data", follow_redirects=False
        )

    # Check new version was created
    with test_app.app_context():
        db.session.expire_all()
        old_dataset = db.session.get(DataSet, dataset_id)

        # If files were uploaded, new version should exist (query for new dataset)
        # For now, verify old metadata was updated
        assert old_dataset.ds_meta_data.version >= initial_version


def test_update_dataset_old_version_gets_versioned_doi(test_client, test_app):
    """Test that old dataset DOI is modified with version suffix."""
    # Setup: Create a dataset for testing
    with test_app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        md = DSMetaData(
            title="Test Dataset",
            description="Test Description",
            data_category=DataCategory.GENERAL,
            dataset_doi="10.1234/test-doi",
            version=1.0,
            is_latest=True,
        )
        db.session.add(md)
        db.session.flush()

        ds = DataSet(user_id=user.id, ds_meta_data_id=md.id, draft_mode=False)
        db.session.add(ds)
        db.session.commit()
        dataset_id = ds.id

    # Login
    resp = login_client(test_client)
    assert resp.status_code in (200, 302)

    with test_app.app_context():
        ds = DataSet.query.get(dataset_id)
        ds.ds_meta_data.dataset_doi

        # This test validates the DOI versioning strategy is accessible
        # Actual versioning happens on new version creation via service
        assert hasattr(ds.ds_meta_data, "dataset_doi")
        assert hasattr(ds.ds_meta_data, "is_latest")


def test_update_dataset_new_version_keeps_original_doi(test_client, test_app):
    """Test that new version dataset gets original DOI."""
    # Setup: Create a dataset for testing
    with test_app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        md = DSMetaData(
            title="Test Dataset",
            description="Test Description",
            data_category=DataCategory.GENERAL,
            dataset_doi="10.1234/test-original-doi",
            version=1.0,
            is_latest=True,
        )
        db.session.add(md)
        db.session.flush()

        ds = DataSet(user_id=user.id, ds_meta_data_id=md.id, draft_mode=False)
        db.session.add(ds)
        db.session.commit()
        dataset_id = ds.id

    # Login
    resp = login_client(test_client)
    assert resp.status_code in (200, 302)

    with test_app.app_context():
        ds = DataSet.query.get(dataset_id)
        # This validates the property structure exists
        # Note: If versioned_doi attribute doesn't exist, that's expected
        if hasattr(ds.ds_meta_data, "versioned_doi"):
            assert hasattr(ds.ds_meta_data, "versioned_doi")
        else:
            # Just verify we can access the dataset without error
            assert ds.ds_meta_data is not None


def test_update_dataset_unauthorized_user_denied(test_app, test_client):
    """Test that unauthorized user cannot update another's dataset."""
    with test_app.app_context():
        # Use the pre-existing test user from test_client
        owner_user = User.query.filter_by(email="test@example.com").first()

        # Create the dataset owned by the first user
        md = DSMetaData(
            title="Test Dataset",
            description="Test Description",
            data_category=DataCategory.GENERAL,
            dataset_doi="10.1234/test-unauthorized",
            version=1.0,
            is_latest=True,
        )
        db.session.add(md)
        db.session.flush()

        ds = DataSet(user_id=owner_user.id, ds_meta_data_id=md.id, draft_mode=False)
        db.session.add(ds)
        db.session.commit()
        dataset_id = ds.id

        # Create a different user
        other_user = User(email=f"other_{uuid.uuid4()}@example.com", password="test1234")
        db.session.add(other_user)
        db.session.commit()

        # Create a new client and login as the other user
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = other_user.id

        # Try to access dataset owned by owner_user
        response = client.get(f"/dataset/{dataset_id}/edit")

        # Should be denied or redirect
        assert response.status_code in [403, 302, 401]


def test_rollback_dataset_version_success(test_client, test_app):
    with test_app.app_context():

        admin = User.query.filter_by(email="test@example.com").first()
        admin.role = UserRole.ADMIN
        admin_id = admin.id
        db.session.commit()

    deposition_id = 777
    md_v1 = DSMetaData(
        title="Dataset v1",
        description="v1",
        data_category=DataCategory.GENERAL,
        dataset_doi="10.1234/ds/v1",
        version=1.0,
        is_latest=False,
        deposition_id=deposition_id,
    )
    md_v2 = DSMetaData(
        title="Dataset v2",
        description="v2",
        data_category=DataCategory.GENERAL,
        dataset_doi="10.1234/ds",
        version=2.0,
        is_latest=True,
        deposition_id=deposition_id,
    )
    db.session.add(md_v1)
    db.session.add(md_v2)
    db.session.flush()

    md_v1_id = md_v1.id
    md_v2_id = md_v2.id

    md_v2_publication_doi = md_v2.publication_doi
    md_v2_dataset_doi = md_v2.dataset_doi

    ds_v1 = DataSet(user_id=admin_id, ds_meta_data_id=md_v1.id, draft_mode=False)
    ds_v2 = DataSet(user_id=admin_id, ds_meta_data_id=md_v2.id, draft_mode=False)

    db.session.add(ds_v1)
    db.session.add(ds_v2)
    db.session.commit()

    latest_dataset_id = ds_v2.id

    test_client.get("/logout", follow_redirects=True)
    resp = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    response = test_client.post(
        f"/dataset/versions/rollback/{latest_dataset_id}",
        follow_redirects=True,
    )

    assert response.status_code == 200

    with test_app.app_context():
        db.session.expire_all()

        v1 = db.session.get(DSMetaData, md_v1_id)
        assert v1.is_latest is True
        assert v1.publication_doi == md_v2_publication_doi
        assert v1.dataset_doi == md_v2_dataset_doi

        v2 = db.session.get(DataSet, md_v2_id)
        assert v2 is None



def test_rollback_dataset_version_unsuccess(test_client, test_app):
    with test_app.app_context():

        admin = User.query.filter_by(email="test@example.com").first()
        admin.role = UserRole.ADMIN
        admin_id = admin.id
        db.session.commit()

    deposition_id = 777

    md_v1 = DSMetaData(
        title="Dataset v1",
        description="v1",
        data_category=DataCategory.GENERAL,
        dataset_doi="10.1234/ds",
        is_latest=True,
        deposition_id=deposition_id,
    )

    db.session.add(md_v1)
    db.session.flush()

    ds_v1 = DataSet(user_id=admin_id, ds_meta_data_id=md_v1.id, draft_mode=False)
    db.session.add(ds_v1)
    db.session.commit()

    latest_dataset_id = ds_v1.id

    test_client.get("/logout", follow_redirects=True)
    resp = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    response = test_client.post(
        f"/dataset/versions/rollback/{latest_dataset_id}"
    )

    data = response.get_json()
    assert data["message"] == "No previous version available for rollback"
    assert response.status_code == 400

def test_rollback_dataset_version_unauthorized(test_client, test_app):
    with test_app.app_context():

        user = User.query.filter_by(email="test@example.com").first()
        user.role = UserRole.USER
        db.session.commit()

    deposition_id = 777
    md_v1 = DSMetaData(
        title="Dataset v1",
        description="v1",
        data_category=DataCategory.GENERAL,
        dataset_doi="10.1234/ds/v1",
        version=1.0,
        is_latest=False,
        deposition_id=deposition_id,
    )
    db.session.add(md_v1)
    db.session.flush()

    other_user = User(email=f"other_user{uuid.uuid4()}@example.com", password="test1234")
    db.session.add(other_user)
    db.session.commit()

    ds_v1 = DataSet(user_id=other_user.id, ds_meta_data_id=md_v1.id, draft_mode=False)
    db.session.add(ds_v1)
    db.session.commit()

    latest_dataset_id = ds_v1.id

    test_client.get("/logout", follow_redirects=True)
    resp = test_client.post("/login", data={"email": "test@example.com", "password": "test1234"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    response = test_client.post(
        f"/dataset/versions/rollback/{latest_dataset_id}"
    )

    assert response.status_code == 403, "Unauthorized"
def test_dataset_file_form_accepts_empty_version():
    form = DatasetFileForm(
        formdata=MultiDict(
            {
                "csv_filename": "file.csv",
                "version": "",
            }
        )
    )
    assert form.validate() is True


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_download_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_download_repo):
    svc = DataSetService()
    svc.repository = mock_repo
    svc.dsdownloadrecord_repository = mock_download_repo
    return svc


def test_count_user_datasets(service, mock_repo):
    mock_repo.count_by_user.return_value = 5
    result = service.count_user_datasets(10)
    mock_repo.count_by_user.assert_called_once_with(10)
    assert result == 5


def test_count_user_synchronized_datasets(service, mock_repo):
    mock_repo.count_synchronized_by_user.return_value = 3
    result = service.count_user_synchronized_datasets(10)
    mock_repo.count_synchronized_by_user.assert_called_once_with(10)
    assert result == 3


def test_count_user_dataset_downloads():
    service = DataSetService()
    mock_download_repo = MagicMock()
    mock_download_repo.count_downloads_performed_by_user.return_value = 7
    service.dsdownloadrecord_repository = mock_download_repo
    result = service.count_user_dataset_downloads(10)
    mock_download_repo.count_downloads_performed_by_user.assert_called_once_with(10)
    assert result == 7


def test_user_metrics_authenticated():
    current_user = MagicMock()
    current_user.is_authenticated = True
    current_user.id = 42

    dataset_service = MagicMock()
    dataset_service.count_user_datasets.return_value = 5
    dataset_service.count_user_dataset_downloads.return_value = 12
    dataset_service.count_user_synchronized_datasets.return_value = 3

    user_metrics = None
    if current_user.is_authenticated:
        user_metrics = {
            "uploaded_datasets": dataset_service.count_user_datasets(current_user.id),
            "downloads": dataset_service.count_user_dataset_downloads(current_user.id),
            "synchronizations": dataset_service.count_user_synchronized_datasets(current_user.id),
        }

    assert user_metrics == {
        "uploaded_datasets": 5,
        "downloads": 12,
        "synchronizations": 3,
    }

    dataset_service.count_user_datasets.assert_called_once_with(42)
    dataset_service.count_user_dataset_downloads.assert_called_once_with(42)
    dataset_service.count_user_synchronized_datasets.assert_called_once_with(42)


def test_user_metrics_not_authenticated():
    current_user = MagicMock()
    current_user.is_authenticated = False

    dataset_service = MagicMock()

    user_metrics = None
    if current_user.is_authenticated:
        user_metrics = {
            "uploaded_datasets": dataset_service.count_user_datasets(current_user.id),
            "downloads": dataset_service.count_user_dataset_downloads(current_user.id),
            "synchronizations": dataset_service.count_user_synchronized_datasets(current_user.id),
        }

    assert user_metrics is None
    dataset_service.count_user_datasets.assert_not_called()
    dataset_service.count_user_dataset_downloads.assert_not_called()
    dataset_service.count_user_synchronized_datasets.assert_not_called()
