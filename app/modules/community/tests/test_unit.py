import io
import tempfile
import uuid

import pytest

from app import db
from app.modules.auth.models import User
from app.modules.community.models import Community, CommunityDatasetProposal, ProposalStatus
from app.modules.community.services import CommunityProposalService, CommunityService
from app.modules.dataset.models import DataCategory, DataSet, DSMetaData


class DummyFile:
    """Mimic a Werkzeug FileStorage subset for validation tests."""

    def __init__(self, filename: str, stream: io.BytesIO):
        self.filename = filename
        self.stream = stream

    def save(self, dst_path: str):
        # Emulate FileStorage.save
        if hasattr(self.stream, "seek"):
            try:
                self.stream.seek(0)
            except Exception:
                pass
        data = self.stream.read() if hasattr(self.stream, "read") else bytes(self.stream)
        with open(dst_path, "wb") as f:
            f.write(data)


def _png_bytes(size=(8, 8)) -> bytes:
    try:
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", size, (10, 20, 30)).save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
            b"\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
            b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
        )


@pytest.fixture()
def services():
    return CommunityService(), CommunityProposalService()


def test_validate_icon_file_ok(services):
    svc, _ = services
    data = _png_bytes()
    f = DummyFile("icon.png", io.BytesIO(data))
    svc.validate_icon_file(f)


def test_validate_icon_file_bad_extension(services):
    svc, _ = services
    data = _png_bytes()
    f = DummyFile("icon.txt", io.BytesIO(data))
    with pytest.raises(ValueError):
        svc.validate_icon_file(f)


def test_validate_icon_file_too_large(services):
    svc, _ = services
    big = io.BytesIO(b"0" * (svc.MAX_ICON_SIZE + 1))
    f = DummyFile("icon.png", big)
    with pytest.raises(ValueError):
        svc.validate_icon_file(f)


def test_validate_icon_file_invalid_image(services):
    svc, _ = services
    bad = io.BytesIO(b"not-an-image")
    f = DummyFile("icon.png", bad)
    with pytest.raises(ValueError):
        svc.validate_icon_file(f)


def test_create_with_icon_saves_file(test_client, services, monkeypatch):
    svc, _ = services
    unique = uuid.uuid4().hex[:6]
    user = User(email=f"owner+{unique}@example.com", password="x")
    try:
        user.two_factor_verified = True
    except Exception:
        pass
    db.session.add(user)
    db.session.commit()

    tmpdir = tempfile.mkdtemp()
    monkeypatch.setenv("WORKING_DIR", tmpdir)

    data = _png_bytes()
    file = DummyFile("logo.png", io.BytesIO(data))
    community = svc.create_with_icon("Comm A", "Desc", user.id, file)

    assert community.icon_path == "logo.png"
    assert community is not None
    assert community.id is not None


def _mk_dataset(user: User) -> DataSet:
    meta = DSMetaData(title="DS", description="desc", data_category=DataCategory.GENERAL, dataset_doi=None)
    ds = DataSet(user_id=user.id, ds_meta_data=meta)
    db.session.add(meta)
    db.session.add(ds)
    db.session.commit()
    return ds


def test_propose_logic(create_and_accept_flow=False):
    # placeholder for potential extended flow test
    pass


def _setup_users_and_ds():
    suf = uuid.uuid4().hex[:6]
    owner = User(email=f"ds+{suf}@ex.com", password="x")
    resp = User(email=f"resp+{suf}@ex.com", password="x")
    # ensure 2FA is considered verified to avoid auth redirects in routes that check it
    try:
        owner.two_factor_verified = True
        resp.two_factor_verified = True
    except Exception:
        pass
    db.session.add_all([owner, resp])
    db.session.commit()
    ds = _mk_dataset(owner)
    c1 = Community(name="C1", description="d", responsible_user_id=resp.id)
    c2 = Community(name="C2", description="d", responsible_user_id=resp.id)
    db.session.add_all([c1, c2])
    db.session.commit()
    return owner, resp, ds, c1, c2


def test_proposal_new_and_pending_noop(test_client, services):
    _, psvc = services
    owner, _, ds, c1, _ = _setup_users_and_ds()
    ok, msg = psvc.propose(ds.id, c1.id, owner.id)
    assert ok and "submitted" in msg
    p = CommunityDatasetProposal.query.filter_by(dataset_id=ds.id, community_id=c1.id).first()
    assert p and p.status == ProposalStatus.PENDING
    ok2, msg2 = psvc.propose(ds.id, c1.id, owner.id)
    assert not ok2 and "pending" in msg2


def test_reject_then_resubmit_and_accept(test_client, services):
    _, psvc = services
    owner, _, ds, c1, _ = _setup_users_and_ds()
    psvc.propose(ds.id, c1.id, owner.id)
    p = CommunityDatasetProposal.query.filter_by(dataset_id=ds.id, community_id=c1.id).first()
    ok2, updated, _ = psvc.decide(p.id, accept=False)
    assert ok2 and updated.status == ProposalStatus.REJECTED
    ok3, msg3 = psvc.propose(ds.id, c1.id, owner.id)
    assert ok3 and "resubmitted" in msg3
    ok4, updated2, _ = psvc.decide(p.id, accept=True)
    assert ok4 and updated2.status == ProposalStatus.ACCEPTED


def test_block_propose_after_accept_and_block_second_accept(test_client, services):
    _, psvc = services
    owner, _, ds, c1, c2 = _setup_users_and_ds()
    psvc.propose(ds.id, c1.id, owner.id)
    p = CommunityDatasetProposal.query.filter_by(dataset_id=ds.id, community_id=c1.id).first()
    psvc.decide(p.id, accept=True)
    ok5, msg5 = psvc.propose(ds.id, c2.id, owner.id)
    assert not ok5 and "already in a community" in msg5
    p2 = CommunityDatasetProposal(dataset_id=ds.id, community_id=c2.id, proposed_by_user_id=owner.id)
    db.session.add(p2)
    db.session.commit()
    ok6, _, msg6 = psvc.decide(p2.id, accept=True)
    assert not ok6 and "already belongs" in msg6
