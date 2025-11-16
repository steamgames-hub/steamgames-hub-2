import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime
from typing import List, Optional, Set

from flask import request
from sqlalchemy import func, or_

from app import db

from app.modules.auth.services import AuthenticationService
from app.modules.dataset.models import Author, DataSet, DSMetaData, DSDownloadRecord, DSViewRecord
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
from app.modules.community.models import CommunityDatasetProposal, ProposalStatus
from core.services.BaseService import BaseService

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

        working_dir = os.getenv("WORKING_DIR", "")
        from core.configuration.configuration import uploads_folder_name
        dest_dir = os.path.join(
            working_dir,
            uploads_folder_name(),
            f"user_{current_user.id}",
            f"dataset_{dataset.id}",
        )

        os.makedirs(dest_dir, exist_ok=True)

        for feature_model in dataset.feature_models:
            csv_filename = feature_model.fm_meta_data.csv_filename
            shutil.move(os.path.join(source_dir, csv_filename), dest_dir)

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

    def get_related_datasets(self, dataset: DataSet, limit: int = 3) -> List[dict]:
        if not dataset or not dataset.ds_meta_data:
            return []

        ds_metadata = dataset.ds_meta_data
        author_names = self._normalize_values(author.name for author in ds_metadata.authors)
        author_orcids = self._normalize_values(author.orcid for author in ds_metadata.authors)
        tags = self._normalize_tags(ds_metadata.tags)
        community_ids = self._accepted_community_ids(dataset.id)

        candidate_ids = set()
        candidate_ids |= self._fetch_author_related_ids(dataset.id, author_names, author_orcids)
        candidate_ids |= self._fetch_tag_related_ids(dataset.id, tags)
        candidate_ids |= self._fetch_community_related_ids(dataset.id, community_ids)

        if not candidate_ids:
            return []

        return self._build_related_dataset_payload(candidate_ids, limit)

    def _normalize_values(self, values) -> Set[str]:
        return {value.strip().lower() for value in values if value and value.strip()}

    def _normalize_tags(self, tags: Optional[str]) -> Set[str]:
        if not tags:
            return set()
        return self._normalize_values(tag for tag in tags.split(","))

    def _accepted_community_ids(self, dataset_id: int) -> Set[int]:
        proposals = CommunityDatasetProposal.query.filter(
            CommunityDatasetProposal.dataset_id == dataset_id,
            CommunityDatasetProposal.status == ProposalStatus.ACCEPTED,
        ).all()
        return {proposal.community_id for proposal in proposals}

    def _fetch_author_related_ids(
        self, dataset_id: int, author_names: Set[str], author_orcids: Set[str]
    ) -> Set[int]:
        if not (author_names or author_orcids):
            return set()

        author_filters = []
        if author_names:
            author_filters.append(func.lower(Author.name).in_(author_names))
        if author_orcids:
            author_filters.append(func.lower(Author.orcid).in_(author_orcids))

        query = (
            db.session.query(DataSet.id)
            .join(DSMetaData, DataSet.ds_meta_data_id == DSMetaData.id)
            .join(Author, Author.ds_meta_data_id == DSMetaData.id)
            .filter(DataSet.id != dataset_id, DSMetaData.dataset_doi.isnot(None))
            .filter(or_(*author_filters))
        )
        return {row[0] for row in query.distinct().all()}

    def _fetch_tag_related_ids(self, dataset_id: int, tags: Set[str]) -> Set[int]:
        if not tags:
            return set()

        tag_filters = [func.lower(DSMetaData.tags).like(f"%{tag}%") for tag in tags]
        query = (
            db.session.query(DataSet.id)
            .join(DSMetaData, DataSet.ds_meta_data_id == DSMetaData.id)
            .filter(DataSet.id != dataset_id, DSMetaData.dataset_doi.isnot(None))
            .filter(or_(*tag_filters))
        )
        return {row[0] for row in query.distinct().all()}

    def _fetch_community_related_ids(self, dataset_id: int, community_ids: Set[int]) -> Set[int]:
        if not community_ids:
            return set()

        query = (
            db.session.query(DataSet.id)
            .join(CommunityDatasetProposal, CommunityDatasetProposal.dataset_id == DataSet.id)
            .join(DSMetaData, DataSet.ds_meta_data_id == DSMetaData.id)
            .filter(
                DataSet.id != dataset_id,
                DSMetaData.dataset_doi.isnot(None),
                CommunityDatasetProposal.status == ProposalStatus.ACCEPTED,
                CommunityDatasetProposal.community_id.in_(community_ids),
            )
        )
        return {row[0] for row in query.distinct().all()}

    def _build_related_dataset_payload(self, candidate_ids: Set[int], limit: int) -> List[dict]:
        if not candidate_ids:
            return []

        datasets = (
            DataSet.query.join(DSMetaData)
            .filter(DataSet.id.in_(candidate_ids), DSMetaData.dataset_doi.isnot(None))
            .all()
        )

        download_counts = {
            dataset_id: count
            for dataset_id, count in (
                db.session.query(DSDownloadRecord.dataset_id, func.count(DSDownloadRecord.id))
                .filter(DSDownloadRecord.dataset_id.in_(candidate_ids))
                .group_by(DSDownloadRecord.dataset_id)
                .all()
            )
        }

        accepted_map = {
            proposal.dataset_id: proposal.community
            for proposal in CommunityDatasetProposal.query.filter(
                CommunityDatasetProposal.dataset_id.in_(candidate_ids),
                CommunityDatasetProposal.status == ProposalStatus.ACCEPTED,
            ).all()
        }

        datasets.sort(
            key=lambda ds: (
                download_counts.get(ds.id, 0),
                ds.created_at or datetime.min,
            ),
            reverse=True,
        )

        limit_value = limit if isinstance(limit, int) and limit > 0 else 3

        related_items = []
        for related in datasets[:limit_value]:
            related_items.append(
                {
                    "dataset": related,
                    "download_count": download_counts.get(related.id, 0),
                    "accepted_community": accepted_map.get(related.id),
                }
            )

        return related_items


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
