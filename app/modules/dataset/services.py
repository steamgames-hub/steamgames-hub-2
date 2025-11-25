import hashlib
import logging
import os
import uuid
from typing import Optional

from flask import request
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from app.modules.dataset.models import DSDownloadRecord

from app.modules.community.models import CommunityDatasetProposal

from app.modules.auth.services import AuthenticationService
from app.modules.dataset.models import DataSet, DSMetaData, DSViewRecord
from app.modules.dataset.repositories import (
    AuthorRepository,
    DataSetRepository,
    DOIMappingRepository,
    DSDownloadRecordRepository,
    DSMetaDataRepository,
    DSViewRecordRepository,
)
from app.modules.featuremodel.repositories import FeatureModelRepository, FMMetaDataRepository
from app.modules.hubfile.repositories import (
    HubfileDownloadRecordRepository,
    HubfileRepository,
    HubfileViewRecordRepository,
)
from core.services.BaseService import BaseService
from core.storage import storage_service

logger = logging.getLogger(__name__)


def calculate_checksum_and_size(file_path):
    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as file:
        content = file.read()
        hash_sha256 = hashlib.sha256(content).hexdigest()
        return hash_sha256, file_size


class DataSetService(BaseService):
    def __init__(self):
        super().__init__(DataSetRepository())
        self.feature_model_repository = FeatureModelRepository()
        self.author_repository = AuthorRepository()
        self.dsmetadata_repository = DSMetaDataRepository()
        self.fmmetadata_repository = FMMetaDataRepository()
        self.dsdownloadrecord_repository = DSDownloadRecordRepository()
        self.hubfiledownloadrecord_repository = HubfileDownloadRecordRepository()
        self.hubfilerepository = HubfileRepository()
        self.dsviewrecord_repostory = DSViewRecordRepository()
        self.hubfileviewrecord_repository = HubfileViewRecordRepository()

    def move_feature_models(self, dataset: DataSet):
        current_user = AuthenticationService().get_authenticated_user()
        source_dir = current_user.temp_folder()

        for feature_model in dataset.feature_models:
            csv_filename = feature_model.fm_meta_data.csv_filename
            src_path = os.path.join(source_dir, csv_filename)
            dest_relative = storage_service.dataset_file_path(
                current_user.id,
                dataset.id,
                csv_filename,
            )
            storage_service.save_local_file(src_path, dest_relative)

    def get_synchronized(self, current_user_id: int) -> DataSet:
        return self.repository.get_synchronized(current_user_id)

    def get_unsynchronized(self, current_user_id: int) -> DataSet:
        return self.repository.get_unsynchronized(current_user_id)

    def get_unsynchronized_dataset(self, current_user_id: int, dataset_id: int) -> DataSet:
        return self.repository.get_unsynchronized_dataset(current_user_id, dataset_id)

    def latest_synchronized(self):
        return self.repository.latest_synchronized()

    def count_synchronized_datasets(self):
        return self.repository.count_synchronized_datasets()

    def count_feature_models(self):
        return self.feature_model_service.count_feature_models()

    def count_authors(self) -> int:
        return self.author_repository.count()

    def count_dsmetadata(self) -> int:
        return self.dsmetadata_repository.count()

    def total_dataset_downloads(self) -> int:
        return self.dsdownloadrecord_repository.total_dataset_downloads()

    def total_dataset_views(self) -> int:
        return self.dsviewrecord_repostory.total_dataset_views()

    def create_from_form(self, form, current_user) -> DataSet:
        main_author = {
            "name": f"{current_user.profile.surname}, {current_user.profile.name}",
            "affiliation": current_user.profile.affiliation,
            "orcid": current_user.profile.orcid,
        }
        try:
            logger.info(f"Creating dsmetadata...: {form.get_dsmetadata()}")
            dsmetadata_data = form.get_dsmetadata()
            dsmetadata = self.dsmetadata_repository.create(**dsmetadata_data)
            for author_data in [main_author] + form.get_authors():
                author = self.author_repository.create(commit=False, ds_meta_data_id=dsmetadata.id, **author_data)
                dsmetadata.authors.append(author)

            dataset = self.create(commit=False, user_id=current_user.id, ds_meta_data_id=dsmetadata.id)

            for feature_model in form.feature_models:
                csv_filename = feature_model.csv_filename.data
                fmmetadata = self.fmmetadata_repository.create(commit=False, **feature_model.get_fmmetadata())
                for author_data in feature_model.get_authors():
                    author = self.author_repository.create(commit=False, fm_meta_data_id=fmmetadata.id, **author_data)
                    fmmetadata.authors.append(author)

                fm = self.feature_model_repository.create(
                    commit=False, data_set_id=dataset.id, fm_meta_data_id=fmmetadata.id
                )

                # associated files in feature model
                file_path = os.path.join(current_user.temp_folder(), csv_filename)
                checksum, size = calculate_checksum_and_size(file_path)

                file = self.hubfilerepository.create(
                    commit=False, name=csv_filename, checksum=checksum, size=size, feature_model_id=fm.id
                )
                fm.files.append(file)
            self.repository.session.commit()
        except Exception as exc:
            logger.info(f"Exception creating dataset from form...: {exc}")
            self.repository.session.rollback()
            raise exc
        return dataset

    def update_dsmetadata(self, metadata_id, **kwargs):
        return self.dsmetadata_repository.update(metadata_id, **kwargs)

    def get_uvlhub_doi(self, dataset: DataSet) -> str:
        domain = os.getenv("DOMAIN", "localhost")
        return f"http://{domain}/doi/{dataset.ds_meta_data.dataset_doi}"

    def trending_datasets(self, period_days: int = 7, by: str = "views", limit: int = 5):
        try:
            since = datetime.now() - timedelta(days=period_days)
            session = self.repository.session

            if by == "views":
                ts_col = getattr(DSViewRecord, "view_date", None)
                if ts_col is None:
                    raise AttributeError("DSViewRecord no tiene 'view_date'")

                subq = (
                    session.query(
                        DSViewRecord.dataset_id.label("dataset_id"),
                        func.count(DSViewRecord.id).label("metric"),
                    )
                    .filter(ts_col >= since)
                    .group_by(DSViewRecord.dataset_id)
                    .subquery()
                )

                q = (
                    session.query(DataSet, func.coalesce(subq.c.metric, 0).label("metric"))
                    .outerjoin(subq, subq.c.dataset_id == DataSet.id)
                    .order_by(desc("metric"))
                    .limit(limit)
                )
                results = q.all()

            elif by == "downloads":
                ts_col = getattr(DSDownloadRecord, "download_date", None)
                if ts_col is None:
                    raise AttributeError("DSDownloadRecord no tiene 'download_date'")

                subq = (
                    session.query(
                        DSDownloadRecord.dataset_id.label("dataset_id"),
                        func.count(DSDownloadRecord.id).label("metric"),
                    )
                    .filter(ts_col >= since)
                    .group_by(DSDownloadRecord.dataset_id)
                    .subquery()
                )

                q = (
                    session.query(DataSet, func.coalesce(subq.c.metric, 0).label("metric"))
                    .outerjoin(subq, subq.c.dataset_id == DataSet.id)
                    .order_by(desc("metric"))
                    .limit(limit)
                )
                results = q.all()
            else:
                results = []

            # Agregar comunidad aceptada a cada dataset
            trending_with_community = []
            for dataset, metric in results:
                accepted_proposal = (
                    session.query(CommunityDatasetProposal)
                    .filter_by(dataset_id=dataset.id, status="accepted")
                    .first()
                )
                dataset.accepted_community = accepted_proposal.community if accepted_proposal else None
                trending_with_community.append((dataset, int(metric or 0)))

            return trending_with_community

        except Exception:
            logger.exception("Error al calcular trending_datasets; usando fallback.")

        try:
            recent = (
                self.repository.latest_synchronized()
                if hasattr(self.repository, "latest_synchronized")
                else self.latest_synchronized()
            )

            recent = list(recent)[:limit]
            for d in recent:
                d.accepted_community = None
            return [(d, 0) for d in recent]
        except Exception:
            logger.exception("Fallback de trending_datasets también ha fallado. Devolviendo lista vacía.")
            return []


class AuthorService(BaseService):
    def __init__(self):
        super().__init__(AuthorRepository())


class DSDownloadRecordService(BaseService):
    def __init__(self):
        super().__init__(DSDownloadRecordRepository())


class DSMetaDataService(BaseService):
    def __init__(self):
        super().__init__(DSMetaDataRepository())

    def update(self, metadata_id, **kwargs):
        return self.repository.update(metadata_id, **kwargs)

    def filter_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return self.repository.filter_by_doi(doi)


class DSViewRecordService(BaseService):
    def __init__(self):
        super().__init__(DSViewRecordRepository())

    def the_record_exists(self, dataset: DataSet, user_cookie: str):
        return self.repository.the_record_exists(dataset, user_cookie)

    def create_new_record(self, dataset: DataSet, user_cookie: str) -> DSViewRecord:
        return self.repository.create_new_record(dataset, user_cookie)

    def create_cookie(self, dataset: DataSet) -> str:

        user_cookie = request.cookies.get("view_cookie")
        if not user_cookie:
            user_cookie = str(uuid.uuid4())

        existing_record = self.the_record_exists(dataset=dataset, user_cookie=user_cookie)

        if not existing_record:
            self.create_new_record(dataset=dataset, user_cookie=user_cookie)

        return user_cookie


class DOIMappingService(BaseService):
    def __init__(self):
        super().__init__(DOIMappingRepository())

    def get_new_doi(self, old_doi: str) -> str:
        doi_mapping = self.repository.get_new_doi(old_doi)
        if doi_mapping:
            return doi_mapping.dataset_doi_new
        else:
            return None


class SizeService:

    def __init__(self):
        pass

    def get_human_readable_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} bytes"
        elif size < 1024**2:
            return f"{round(size / 1024, 2)} KB"
        elif size < 1024**3:
            return f"{round(size / (1024 ** 2), 2)} MB"
        else:
            return f"{round(size / (1024 ** 3), 2)} GB"
