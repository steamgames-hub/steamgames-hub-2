import hashlib
import os
import uuid
from contextlib import contextmanager

import pytest

from app import db
from app.modules.auth.models import User
from app.modules.dataset.models import DataCategory, DataSet, DSMetaData
from app.modules.datasetfile.models import DatasetFile
from app.modules.hubfile.models import Hubfile, HubfileDownloadRecord, HubfileViewRecord
from app.modules.hubfile.services import HubfileService

DOWNLOAD_URL = "/file/download/{id}"
VIEW_URL = "/file/view/{id}"


@contextmanager
def force_login(test_client, user):
    """Authenticate a user in the test client session bypassing the UI/2FA flow."""
    with test_client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    yield


def _patch_storage_to_tmp(monkeypatch, tmp_path):
    def fake_get_path_by_hubfile(self, hubfile: Hubfile):
        return str(tmp_path / hubfile.name)

    monkeypatch.setattr(HubfileService, "get_path_by_hubfile", fake_get_path_by_hubfile)


def _extract_cookie_value(set_cookie_headers, key):
    for h in set_cookie_headers:
        if h.startswith(f"{key}="):
            return h.split(";", 1)[0].split("=", 1)[1]
    return None


@pytest.fixture()
def user(clean_database):
    suf = uuid.uuid4().hex[:6]
    u = User(email=f"hubfile+{suf}@test.com", password="1234")
    try:
        u.two_factor_verified = True
    except Exception:
        pass
    db.session.add(u)
    db.session.commit()
    return u


def make_dataset(owner: User) -> DataSet:
    meta = DSMetaData(
        title="DS Hubfile",
        description="d",
        data_category=DataCategory.GENERAL,
        dataset_doi=None,
    )
    ds = DataSet(user_id=owner.id, ds_meta_data=meta)
    db.session.add_all([meta, ds])
    db.session.commit()
    return ds


@pytest.fixture()
def feature_model(user, clean_database):
    ds = make_dataset(user)
    fm = DatasetFile(data_set_id=ds.id)
    db.session.add(fm)
    db.session.commit()
    return fm


def _create_valid_hubfile(feature_model, name: str, content: bytes) -> Hubfile:
    checksum = hashlib.sha256(content).hexdigest()
    hf = Hubfile(
        name=name,
        checksum=checksum,
        size=len(content),
        dataset_file_id=feature_model.id,
        download_count=0,
    )
    db.session.add(hf)
    db.session.commit()
    return hf


def _write_disk_file_for(hubfile: Hubfile, content: bytes):
    abs_path = os.path.abspath(HubfileService().get_path_by_hubfile(hubfile))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(content)


def _write_disk_text_for(hubfile: Hubfile, text: str):
    path = HubfileService().get_path_by_hubfile(hubfile)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------
# DOWNLOAD endpoint tests
# ---------------------------


@pytest.fixture(scope="session")
def test_download_cookie_and_records(test_client, monkeypatch, tmp_path, clean_database, feature_model, user):
    """
    Covers:
    - missing cookie -> new cookie set
    - record is created once per cookie, not duplicated on repeat download
    - authenticated request path is exercised
    """
    _patch_storage_to_tmp(monkeypatch, tmp_path)

    content = b"mew hubfile content\n"
    filename = f"{uuid.uuid4()}.uvl"
    hubfile = _create_valid_hubfile(feature_model, filename, content)
    _write_disk_file_for(hubfile, content)

    # 1) First download (no cookie provided) -> sets cookie + creates record
    r1 = test_client.get(DOWNLOAD_URL.format(id=hubfile.id))
    assert r1.status_code == 200
    assert r1.data == content

    cookie1 = _extract_cookie_value(r1.headers.getlist("Set-Cookie"), key="file_download_cookie")
    assert cookie1, r1.headers.getlist("Set-Cookie")

    db.session.expire_all()
    rec1 = HubfileDownloadRecord.query.filter_by(file_id=hubfile.id, download_cookie=cookie1).first()
    assert rec1 is not None

    # 2) Second download with same cookie -> should NOT duplicate record
    test_client.set_cookie("file_download_cookie", cookie1)
    r2 = test_client.get(DOWNLOAD_URL.format(id=hubfile.id))
    assert r2.status_code == 200
    assert r2.data == content

    db.session.expire_all()
    recs_cookie1 = HubfileDownloadRecord.query.filter_by(file_id=hubfile.id, download_cookie=cookie1).all()
    assert len(recs_cookie1) == 1

    # 3) Authenticated download with a NEW cookie -> creates a second record (cookie2)
    cookie2 = str(uuid.uuid4()) + "1"
    test_client.set_cookie("file_download_cookie", cookie2)

    with force_login(test_client, user):
        r3 = test_client.get(DOWNLOAD_URL.format(id=hubfile.id))
    assert r3.status_code == 200
    assert r3.data == content

    db.session.expire_all()
    rec2 = HubfileDownloadRecord.query.filter_by(file_id=hubfile.id, download_cookie=cookie2).first()
    assert rec2 is not None

    # Total records should now be 2 (one per cookie)
    recs_total = HubfileDownloadRecord.query.filter_by(file_id=hubfile.id).all()
    assert len(recs_total) == 2

    # 4) Repeat AUTH with same cookie2 -> should NOT duplicate cookie2 record
    with force_login(test_client, user):
        r4 = test_client.get(DOWNLOAD_URL.format(id=hubfile.id))
    assert r4.status_code == 200

    db.session.expire_all()
    recs_cookie2 = HubfileDownloadRecord.query.filter_by(file_id=hubfile.id, download_cookie=cookie2).all()
    assert len(recs_cookie2) == 1


def test_download_failure_cases(test_client, monkeypatch, tmp_path, clean_database, feature_model):
    _patch_storage_to_tmp(monkeypatch, tmp_path)

    # A) wrong id -> get_or_404 should 404 (likely HTML)
    r0 = test_client.get(DOWNLOAD_URL.format(id=999999999))
    assert r0.status_code == 404

    # B) file exists in DB but missing on disk -> JSON 404 with specific message
    content = b"x"
    filename = f"{uuid.uuid4()}.uvl"
    hubfile = _create_valid_hubfile(feature_model, filename, content)

    r = test_client.get(DOWNLOAD_URL.format(id=hubfile.id))
    assert r.status_code == 404

    data = r.get_json()
    assert data["success"] is False
    assert data["error"] == "File not found on disk"
    assert "path" in data

    db.session.expire_all()
    recs = HubfileDownloadRecord.query.filter_by(file_id=hubfile.id).all()
    assert recs == []


# ---------------------------
# VIEW endpoint tests
# ---------------------------


def test_view_cookie_and_records(test_client, monkeypatch, tmp_path, clean_database, feature_model, user):
    """
    Covers:
    - reads file content and returns JSON
    - sets view_cookie if missing
    - creates HubfileViewRecord once per cookie, no duplicates on repeat
    - exercises authenticated branch (with a new cookie)
    """
    _patch_storage_to_tmp(monkeypatch, tmp_path)

    text = "mew view content 😺\n"
    content_bytes = text.encode("utf-8")
    filename = f"{uuid.uuid4()}.uvl"

    hubfile = _create_valid_hubfile(feature_model, filename, content_bytes)
    _write_disk_text_for(hubfile, text)

    # 1) First view (no cookie) -> sets cookie + creates record
    r1 = test_client.get(VIEW_URL.format(id=hubfile.id))
    assert r1.status_code == 200

    j1 = r1.get_json()
    assert j1["success"] is True
    assert j1["content"] == text

    cookie1 = _extract_cookie_value(r1.headers.getlist("Set-Cookie"), key="view_cookie")
    assert cookie1, r1.headers.getlist("Set-Cookie")

    db.session.expire_all()
    rec1 = HubfileViewRecord.query.filter_by(file_id=hubfile.id, view_cookie=cookie1).first()
    assert rec1 is not None

    # 2) Second view with same cookie -> no new record
    test_client.set_cookie("view_cookie", cookie1)
    r2 = test_client.get(VIEW_URL.format(id=hubfile.id))
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert j2["success"] is True
    assert j2["content"] == text

    db.session.expire_all()
    recs_cookie1 = HubfileViewRecord.query.filter_by(file_id=hubfile.id, view_cookie=cookie1).all()
    assert len(recs_cookie1) == 1

    # 3) Auth view with NEW cookie -> creates a second record (cookie2)
    cookie2 = str(uuid.uuid4())
    test_client.set_cookie("view_cookie", cookie2)
    with force_login(test_client, user):
        r3 = test_client.get(VIEW_URL.format(id=hubfile.id))
    assert r3.status_code == 200
    j3 = r3.get_json()
    assert j3["success"] is True
    assert j3["content"] == text

    db.session.expire_all()
    rec2 = HubfileViewRecord.query.filter_by(file_id=hubfile.id, view_cookie=cookie2).first()
    assert rec2 is not None

    # Total records should now be 2 (one per cookie)
    recs_total = HubfileViewRecord.query.filter_by(file_id=hubfile.id).all()
    assert len(recs_total) == 2


def test_view_failure_cases(test_client, monkeypatch, tmp_path, clean_database, feature_model):
    _patch_storage_to_tmp(monkeypatch, tmp_path)

    # A) wrong id -> get_or_404 should 404 (likely HTML)
    r0 = test_client.get(VIEW_URL.format(id=999999999))
    assert r0.status_code == 404

    # B) file exists in DB but missing on disk -> JSON 404
    content = b"x"
    filename = f"{uuid.uuid4()}.uvl"
    hubfile = _create_valid_hubfile(feature_model, filename, content)

    r = test_client.get(VIEW_URL.format(id=hubfile.id))
    assert r.status_code == 404
    data = r.get_json()
    assert data["success"] is False
    assert data["error"] == "File not found"

    db.session.expire_all()
    recs = HubfileViewRecord.query.filter_by(file_id=hubfile.id).all()
    assert recs == []
