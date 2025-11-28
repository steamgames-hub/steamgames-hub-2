from datetime import datetime, timedelta
import sys
from types import ModuleType, SimpleNamespace
from typing import Optional

from app import db
from app.modules.auth.models import User
from app.modules.community.models import Community, CommunityDatasetProposal, ProposalStatus
from app.modules.dataset.models import (
    Author,
    DataCategory,
    DataSet,
    DSMetaData,
    DSDownloadRecord,
    DSViewRecord,
)


class _FakeSendGridAPIClient:
    def __init__(self, *args, **kwargs):  # pragma: no cover - test stub
        pass

    def send(self, message):  # pragma: no cover - test stub
        return SimpleNamespace(status_code=202)


class _FakeMail:
    def __init__(self, *args, **kwargs):  # pragma: no cover - test stub
        pass


if "sendgrid" not in sys.modules:  # pragma: no cover - module availability guard
    sendgrid_module = ModuleType("sendgrid")
    sendgrid_module.SendGridAPIClient = _FakeSendGridAPIClient
    sys.modules["sendgrid"] = sendgrid_module
else:  # pragma: no cover
    setattr(sys.modules["sendgrid"], "SendGridAPIClient", getattr(sys.modules["sendgrid"], "SendGridAPIClient", _FakeSendGridAPIClient))

helpers_module = ModuleType("sendgrid.helpers")
mail_module = ModuleType("sendgrid.helpers.mail")
mail_module.Mail = _FakeMail
helpers_module.mail = mail_module
sys.modules["sendgrid.helpers"] = helpers_module
sys.modules["sendgrid.helpers.mail"] = mail_module

from app.modules.dataset.services import DataSetService


def _create_user(email: str) -> User:
    user = User(email=email, password="pass1234")
    db.session.add(user)
    db.session.flush()
    return user


def _create_dataset(owner: User, title: str) -> DataSet:
    meta = DSMetaData(
        title=title,
        description=f"{title} description",
        data_category=DataCategory.GENERAL,
        dataset_doi=f"{title.lower().replace(' ', '-')}-doi",
    )
    db.session.add(meta)
    db.session.flush()

    author = Author(
        name=f"{title} Author",
        affiliation="Steam Labs",
        orcid="0000-0000",
        ds_meta_data=meta,
    )
    db.session.add(author)
    db.session.flush()

    dataset = DataSet(user_id=owner.id, ds_meta_data_id=meta.id)
    db.session.add(dataset)
    db.session.flush()
    return dataset


def _create_community(responsible: User, name: str) -> Community:
    community = Community(name=name, description=f"{name} description", responsible_user_id=responsible.id)
    db.session.add(community)
    db.session.flush()
    return community


def _accept_dataset(dataset: DataSet, community: Community, proposer: User) -> None:
    proposal = CommunityDatasetProposal(
        dataset_id=dataset.id,
        community_id=community.id,
        proposed_by_user_id=proposer.id,
        status=ProposalStatus.ACCEPTED,
    )
    db.session.add(proposal)


def _add_views(dataset: DataSet, amount: int, base_time: Optional[datetime] = None, offset_hours: int = 0):
    now = base_time or datetime.utcnow()
    for idx in range(amount):
        db.session.add(
            DSViewRecord(
                dataset_id=dataset.id,
                view_cookie=f"view-{dataset.id}-{offset_hours}-{idx}",
                view_date=now - timedelta(hours=offset_hours + idx),
            )
        )


def _add_downloads(dataset: DataSet, amount: int, base_time: Optional[datetime] = None, offset_hours: int = 0):
    now = base_time or datetime.utcnow()
    for idx in range(amount):
        db.session.add(
            DSDownloadRecord(
                dataset_id=dataset.id,
                download_cookie=f"down-{dataset.id}-{offset_hours}-{idx}",
                download_date=now - timedelta(hours=offset_hours + idx),
            )
        )


def test_trending_datasets_service_counts_views_and_assigns_community(test_client, clean_database):
    with test_client.application.app_context():
        owner = _create_user("views-owner@example.com")
        ds_popular = _create_dataset(owner, "Dataset Alpha")
        ds_secondary = _create_dataset(owner, "Dataset Beta")

        community = _create_community(owner, "Elite Lab")
        _accept_dataset(ds_popular, community, owner)

        now = datetime.utcnow()
        _add_views(ds_popular, 3, base_time=now)
        _add_views(ds_secondary, 2, base_time=now, offset_hours=2)
        # Older view should not count for the 7-day window
        db.session.add(
            DSViewRecord(
                dataset_id=ds_secondary.id,
                view_cookie="view-old",
                view_date=now - timedelta(days=60),
            )
        )
        db.session.commit()

        svc = DataSetService()
        results = svc.trending_datasets(period_days=7, by="views", limit=5)

        ids = [item[0].id for item in results]
        assert ids[:2] == [ds_popular.id, ds_secondary.id]
        assert results[0][1] == 3
        assert results[1][1] == 2
        assert results[0][0].accepted_community.id == community.id


def test_trending_datasets_service_counts_downloads_with_limit(test_client, clean_database):
    with test_client.application.app_context():
        owner = _create_user("downloads-owner@example.com")
        ds_top = _create_dataset(owner, "Dataset Gamma")
        ds_other = _create_dataset(owner, "Dataset Delta")

        now = datetime.utcnow()
        _add_downloads(ds_top, 4, base_time=now)
        _add_downloads(ds_other, 1, base_time=now)
        db.session.add(
            DSDownloadRecord(
                dataset_id=ds_top.id,
                download_cookie="down-old",
                download_date=now - timedelta(days=40),
            )
        )
        db.session.commit()

        svc = DataSetService()
        results = svc.trending_datasets(period_days=7, by="downloads", limit=1)

        assert len(results) == 1
        assert results[0][0].id == ds_top.id
        assert results[0][1] == 4


def test_trending_datasets_service_fallback_when_query_fails(monkeypatch):
    svc = DataSetService()

    class BrokenSession:
        def query(self, *args, **kwargs):  # pragma: no cover - simple stub
            raise RuntimeError("boom")

    fallback_dataset = SimpleNamespace(id=777)

    svc.repository = SimpleNamespace(session=BrokenSession(), latest_synchronized=lambda: [fallback_dataset])

    data = svc.trending_datasets(period_days=7, by="views", limit=1)

    assert data == [(fallback_dataset, 0)]
    assert hasattr(fallback_dataset, "accepted_community")
    assert fallback_dataset.accepted_community is None


def test_trending_datasets_api_returns_expected_payload(test_client, clean_database):
    with test_client.application.app_context():
        owner = _create_user("api-owner@example.com")
        ds_top = _create_dataset(owner, "Trending API One")
        ds_second = _create_dataset(owner, "Trending API Two")
        community = _create_community(owner, "API Community")
        _accept_dataset(ds_top, community, owner)

        now = datetime.utcnow()
        _add_views(ds_top, 2, base_time=now)
        _add_views(ds_second, 1, base_time=now)
        db.session.commit()

        ds_top_id = ds_top.id
        ds_second_id = ds_second.id
        ds_top_title = ds_top.ds_meta_data.title
        ds_second_title = ds_second.ds_meta_data.title
        ds_top_author = ds_top.ds_meta_data.authors[0].name
        ds_second_author = ds_second.ds_meta_data.authors[0].name
        community_name = community.name

    response = test_client.get("/trending_datasets?by=views&period=week&limit=2")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["by"] == "views"
    assert payload["period"] == "week"
    assert len(payload["items"]) == 2

    first, second = payload["items"]
    assert first["id"] == ds_top_id
    assert first["title"] == ds_top_title
    assert first["first_author"] == ds_top_author
    assert first["community_name"] == community_name
    assert first["metric"] == 2
    assert isinstance(first["url"], str) and first["url"]

    assert second["id"] == ds_second_id
    assert second["title"] == ds_second_title
    assert second["first_author"] == ds_second_author
    assert second["community_name"] == ""
    assert second["metric"] == 1
