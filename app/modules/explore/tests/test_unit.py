import pytest
from datetime import datetime
from app import db
from app.modules.explore.repositories import ExploreRepository
from app.modules.auth.models import User
from app.modules.dataset.models import (
    DataSet, DSMetaData, Author, DSDownloadRecord, DSViewRecord, DataCategory
)
from app.modules.featuremodel.models import FeatureModel, FMMetaData


@pytest.fixture(scope="module")
def repo():
    return ExploreRepository()


@pytest.fixture(scope="function")
def populated_db(test_client, clean_database):
    """
    Prepara datasets para probar los filtros del explorador.
    """
    with test_client.application.app_context():

        user = User(email="owner@example.com", password="pass1234")
        db.session.add(user)
        db.session.flush()

        # Dataset 1: author Alice, tags "action,indie", filename games.csv, created 2020-01-15
        md1 = DSMetaData(
            title="Dataset One",
            description="First dataset",
            tags="action,indie",
            data_category=DataCategory.NONE
        )
        db.session.add(md1)
        db.session.flush()

        a1 = Author(name="Alice Wonderland", affiliation="Gaming Lab", orcid="0000-0001", ds_meta_data=md1)
        db.session.add(a1)
        db.session.flush()

        ds1 = DataSet(user_id=user.id, ds_meta_data_id=md1.id, created_at=datetime(2020, 1, 15))
        db.session.add(ds1)
        db.session.flush()

        fm1_meta = FMMetaData(
            csv_filename="games.csv",
            title="FM1",
            description="FM1 desc",
            tags="indie,action",
            data_category=DataCategory.NONE
        )
        db.session.add(fm1_meta)
        db.session.flush()

        fm1 = FeatureModel(data_set_id=ds1.id, fm_meta_data=fm1_meta)
        db.session.add(fm1)

        for i in range(3):
            db.session.add(DSViewRecord(user_id=None, dataset_id=ds1.id, view_cookie=f"vc{i}"))
        for i in range(2):
            db.session.add(DSDownloadRecord(user_id=None, dataset_id=ds1.id, download_cookie=f"dc{i}"))

        # Dataset 2: author Bob, tags "rpg", filename monsters.csv, created 2021-06-10
        md2 = DSMetaData(
            title="Dataset Two",
            description="Second dataset",
            tags="rpg",
            data_category=DataCategory.NONE
        )
        db.session.add(md2)
        db.session.flush()

        a2 = Author(name="Bob Builder", affiliation="Construct Inc", orcid="0000-0002", ds_meta_data=md2)
        db.session.add(a2)
        db.session.flush()

        ds2 = DataSet(user_id=user.id, ds_meta_data_id=md2.id, created_at=datetime(2021, 6, 10))
        db.session.add(ds2)
        db.session.flush()

        fm2_meta = FMMetaData(
            csv_filename="monsters.csv",
            title="FM2",
            description="FM2 desc",
            tags="rpg",
            data_category=DataCategory.NONE
        )
        db.session.add(fm2_meta)
        db.session.flush()

        fm2 = FeatureModel(data_set_id=ds2.id, fm_meta_data=fm2_meta)
        db.session.add(fm2)

        # Dataset 3: no tags, recent date
        md3 = DSMetaData(
            title="Dataset Three",
            description="Third dataset",
            tags="",
            data_category=DataCategory.NONE
        )
        db.session.add(md3)
        db.session.flush()

        a3 = Author(name="Charlie", affiliation="Misc", orcid=None, ds_meta_data=md3)
        db.session.add(a3)
        db.session.flush()

        ds3 = DataSet(user_id=user.id, ds_meta_data_id=md3.id, created_at=datetime.utcnow())
        db.session.add(ds3)

        db.session.commit()

    yield


def test_repo_search_by_author(repo, populated_db):
    results = repo.filter(author="Alice")
    assert len(results) >= 1
    titles = [r.ds_meta_data.title for r in results]
    assert any(t == "Dataset One" for t in titles)


def test_repo_search_by_tags(repo, populated_db):
    results = repo.filter(tags="indie")
    assert len(results) >= 1
    titles = [r.ds_meta_data.title for r in results]
    assert "Dataset One" in titles


def test_repo_search_by_filenames(repo, populated_db):
    results = repo.filter(filenames="games.csv")
    assert len(results) == 1
    assert results[0].ds_meta_data.title == "Dataset One"


def test_repo_search_by_date_range(repo, populated_db):
    results = repo.filter(date_from=datetime(2020, 1, 1).date(), date_to=datetime(2020, 12, 31).date())
    titles = [r.ds_meta_data.title for r in results]
    assert "Dataset One" in titles
    assert "Dataset Two" not in titles


def test_repo_search_by_min_views_and_downloads(repo, populated_db):
    results = repo.filter(min_views=3, min_downloads=2)
    titles = [r.ds_meta_data.title for r in results]
    assert "Dataset One" in titles

    results = repo.filter(min_views=10)
    titles = [r.ds_meta_data.title for r in results]
    assert "Dataset One" not in titles


def test_repo_search_by_author_strict(repo, populated_db):
    # Filtramos por "Alice" -> esperamos exactamente 1 dataset: "Dataset One"
    results = repo.filter(author="Alice")
    titles = [r.ds_meta_data.title for r in results]

    assert len(results) == 1, f"Expected exactly 1 result for author Alice, got {len(results)}: {titles}"

    # Ese resultado debe ser Dataset One
    assert titles == ["Dataset One"]


def test_repo_search_by_tags_strict(repo, populated_db):
    results = repo.filter(tags="indie")
    titles = [r.ds_meta_data.title for r in results]

    # Esperamos exactamente 1 resultado
    assert len(results) == 1, f"Expected exactly 1 result for tag 'indie', got {len(results)}: {titles}"

    # Debe ser Dataset One
    assert titles == ["Dataset One"]


def test_repo_search_by_date_range_strict(repo, populated_db):
    # Rango que sólo incluye Dataset One (2020)
    results = repo.filter(date_from=datetime(2020, 1, 1).date(), date_to=datetime(2020, 12, 31).date())
    titles = sorted([r.ds_meta_data.title for r in results])

    assert titles == ["Dataset One"], f"Expected only ['Dataset One'] in 2020 range, got: {titles}"


def test_repo_search_by_min_views_and_downloads_strict(repo, populated_db):
    results = repo.filter(min_views=3, min_downloads=2)
    titles = sorted([r.ds_meta_data.title for r in results])
    assert titles == ["Dataset One"], f"Expected only ['Dataset One'] for min_views=3,min_downloads=2, got: {titles}"

    results = repo.filter(min_views=10)
    assert len(results) == 0, f"Expected 0 results for min_views=10, got {len(results)}"


def test_explore_route_post_returns_json_strict(test_client, populated_db):
    # POST a /explore con author=Alice -> esperar lista con exactamente Dataset One
    payload = {
        "query": "",
        "sorting": "newest",
        "author": "Alice",
    }
    resp = test_client.post("/explore", json=payload)
    assert resp.status_code == 200

    data = resp.get_json()
    assert isinstance(data, list), "Expected JSON list from /explore"

    titles = sorted([d.get("title") for d in data])
    assert titles == ["Dataset One"], f"Expected response titles to be ['Dataset One'], got: {titles}"


def test_repo_search_by_query(repo, populated_db):
    # Buscar palabra "dataset" -> debería devolver todos los datasets
    results = repo.filter(query="Dataset")
    titles = sorted([r.ds_meta_data.title for r in results])
    assert "Dataset One" in titles
    assert "Dataset Two" in titles
    assert "Dataset Three" in titles

    # Buscar palabra específica que solo está en Dataset Two
    results = repo.filter(query="Second")
    titles = [r.ds_meta_data.title for r in results]
    assert titles == ["Dataset Two"]


def test_repo_search_by_multiple_tags_or(repo, populated_db):
    # Tag "indie" o "rpg" -> debe devolver Dataset One y Dataset Two
    results = repo.filter(tags="indie,rpg")
    titles = sorted([r.ds_meta_data.title for r in results])
    assert "Dataset One" in titles
    assert "Dataset Two" in titles


def test_repo_search_by_multiple_filenames_or(repo, populated_db):
    # Filenames "games.csv" o "monsters.csv" -> debe devolver Dataset One y Dataset Two
    results = repo.filter(filenames="games.csv,monsters.csv")
    titles = sorted([r.ds_meta_data.title for r in results])
    assert "Dataset One" in titles
    assert "Dataset Two" in titles


def test_repo_search_author_and_tag(repo, populated_db):
    # Alice + tag indie -> solo Dataset One
    results = repo.filter(author="Alice", tags="indie")
    titles = sorted([r.ds_meta_data.title for r in results])
    assert titles == ["Dataset One"], f"Expected only Dataset One for author Alice + tag indie, got: {titles}"


def test_repo_sorting_newest_oldest(repo, populated_db):
    newest = repo.filter(sorting="newest")
    oldest = repo.filter(sorting="oldest")

    assert len(newest) >= 1 and len(oldest) >= 1

    # newest[0] created_at >= last element in oldest
    newest_first = newest[0].created_at
    oldest_first = oldest[0].created_at

    assert newest_first >= oldest_first, "Expected newest first to be same or newer than oldest first"
