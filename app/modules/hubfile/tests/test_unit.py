import pytest

from app import db
from app.modules.dataset.models import DataCategory, DataSet, DSMetaData
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from app.modules.hubfile.models import Hubfile
from app.modules.hubfile.services import HubfileDownloadRecordService


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extends the test_client fixture to add additional specific data for module testing.
    """
    with test_client.application.app_context():
        # Add HERE new elements to the database that you want to exist in the test context.
        # DO NOT FORGET to use db.session.add(<element>) and db.session.commit() to save the data.
        pass

    yield test_client


def test_sample_assertion(test_client):
    """
    Sample test to verify that the test framework and environment are working correctly.
    It does not communicate with the Flask application; it only performs a simple assertion to
    confirm that the tests in this module can be executed.
    """
    greeting = "Hello, World!"
    assert greeting == "Hello, World!", "The greeting does not coincide with 'Hello, World!'"


def test_get_version_label_prefers_manual_version():
    hf = Hubfile()
    hf.name = "x.csv"
    hf.checksum = "abcdef1234567890"
    hf.size = 10
    fm = FeatureModel()
    fm.fm_meta_data = FMMetaData(csv_version="1.2.3")
    hf.feature_model = fm

    assert hf.get_version_label() == "1.2.3"


def test_get_version_label_falls_back_to_short_checksum():
    hf = Hubfile()
    hf.name = "x.csv"
    hf.checksum = "abcdef1234567890"
    hf.size = 10
    fm = FeatureModel()
    fm.fm_meta_data = FMMetaData(csv_version=None)
    hf.feature_model = fm

    assert hf.get_version_label() == "abcdef1"


def test_download_count_increments(test_client):
    with test_client.application.app_context():
        try:
            meta = DSMetaData(
                title="dummy metadata",
                description="test description",
                data_category=DataCategory.GENERAL,
            )
            db.session.add(meta)
            db.session.commit()

            dataset = DataSet(user_id=1, ds_meta_data_id=meta.id)
            db.session.add(dataset)
            db.session.commit()

            fm = FeatureModel(data_set_id=dataset.id)
            db.session.add(fm)
            db.session.commit()

            hubfile = Hubfile(
                name="test_file.txt",
                checksum="abc123",
                size=123,
                feature_model_id=fm.id,
                download_count=0,
            )
            db.session.add(hubfile)
            db.session.commit()

            service = HubfileDownloadRecordService()
            service.update_download_count(hubfile.id)
            service.update_download_count(hubfile.id)
            db.session.commit()

            db.session.refresh(hubfile)
            assert hubfile.download_count == 2

        finally:
            db.session.rollback()
            db.session.query(Hubfile).delete()
            db.session.query(FeatureModel).delete()
            db.session.query(DataSet).delete()
            db.session.query(DSMetaData).delete()
            db.session.commit()
