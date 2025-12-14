import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Set

from flask import request
from sqlalchemy import desc, func, or_

from app import db
from app.modules.auth.services import AuthenticationService
from app.modules.community.models import CommunityDatasetProposal, ProposalStatus
from app.modules.dataset.models import Author, DataSet, DSDownloadRecord, DSMetaData, DSViewRecord
from app.modules.dataset.repositories import (
    AuthorRepository,
    DataSetRepository,
    DOIMappingRepository,
    DSDownloadRecordRepository,
    DSMetaDataRepository,
    DSViewRecordRepository,
    IssueRepository,
)
from app.modules.datasetfile.repositories import DatasetFileMetaDataRepository, DatasetFileRepository
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
        self.dataset_file_repository = DatasetFileRepository()
        self.author_repository = AuthorRepository()
        self.dsmetadata_repository = DSMetaDataRepository()
        self.dataset_file_metadata_repository = DatasetFileMetaDataRepository()
        self.dsdownloadrecord_repository = DSDownloadRecordRepository()
        self.hubfiledownloadrecord_repository = HubfileDownloadRecordRepository()
        self.hubfilerepository = HubfileRepository()
        self.dsviewrecord_repository = DSViewRecordRepository()
        self.hubfileviewrecord_repository = HubfileViewRecordRepository()

    def move_dataset_files(self, dataset: DataSet):
        current_user = AuthenticationService().get_authenticated_user()
        source_dir = current_user.temp_folder()

        for dataset_file in dataset.dataset_files:
            csv_filename = dataset_file.file_metadata.csv_filename
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

    def count_dataset_files(self):
        return self.dataset_file_repository.count_files()

    def count_authors(self) -> int:
        return self.author_repository.count()

    def count_dsmetadata(self) -> int:
        return self.dsmetadata_repository.count()

    def total_dataset_downloads(self) -> int:
        return self.dsdownloadrecord_repository.total_dataset_downloads()

    def total_dataset_views(self) -> int:
        return self.dsviewrecord_repository.total_dataset_views()

    def count_user_datasets(self, user_id: int) -> int:
        return self.repository.count_by_user(user_id)

    def count_user_synchronized_datasets(self, user_id: int) -> int:
        return self.repository.count_synchronized_by_user(user_id)

    def count_user_dataset_downloads(self, user_id: int) -> int:
        """Return how many downloads the given user performed (datasets + files)."""
        dataset_archives = self.dsdownloadrecord_repository.count_downloads_performed_by_user(user_id)
        hubfile_files = self.hubfiledownloadrecord_repository.count_downloads_performed_by_user(user_id)
        return dataset_archives + hubfile_files

    def create_from_form(self, form, current_user, draft_mode: bool = False) -> DataSet:
        main_author = {
            "name": f"{current_user.profile.surname}, {current_user.profile.name}",
            "affiliation": current_user.profile.affiliation,
            "orcid": current_user.profile.orcid,
        }
        try:
            logger.info(f"Creating dsmetadata...: {form.get_dsmetadata()}")
            dsmetadata_data = form.get_dsmetadata()
            dsmetadata = self.dsmetadata_repository.create(**dsmetadata_data)
            # Build authors list and deduplicate by (name, orcid) to avoid duplicate main author
            raw_authors = [main_author] + form.get_authors()
            seen = set()
            for author_data in raw_authors:
                key = (author_data.get('name'), author_data.get('orcid'))
                if key in seen:
                    continue
                seen.add(key)
                author = self.author_repository.create(commit=False, ds_meta_data_id=dsmetadata.id, **author_data)
                dsmetadata.authors.append(author)

            dataset = self.create(
                commit=False,
                user_id=current_user.id,
                ds_meta_data_id=dsmetadata.id,
                draft_mode=draft_mode,
            )

            for dataset_file_form in form.dataset_files:
                csv_filename = dataset_file_form.csv_filename.data
                file_metadata = self.dataset_file_metadata_repository.create(
                    commit=False, **dataset_file_form.get_file_metadata()
                )
                for author_data in dataset_file_form.get_authors():
                    author = self.author_repository.create(
                        commit=False, fm_meta_data_id=file_metadata.id, **author_data
                    )
                    file_metadata.authors.append(author)

                dataset_file = self.dataset_file_repository.create(
                    commit=False, data_set_id=dataset.id, metadata_id=file_metadata.id
                )

                file_path = os.path.join(current_user.temp_folder(), csv_filename)
                checksum, size = calculate_checksum_and_size(file_path)

                file = self.hubfilerepository.create(
                    commit=False, name=csv_filename, checksum=checksum, size=size, dataset_file_id=dataset_file.id
                )
                dataset_file.files.append(file)
            self.repository.session.commit()
        except Exception as exc:
            logger.info(f"Exception creating dataset from form...: {exc}")
            self.repository.session.rollback()
            raise exc
        return dataset

    def create_new_version(self, dataset_id: int, form, current_user, version_increment_type: str = 'major') -> DataSet:
        """Create a new version of an existing dataset.

        Steps:
        - Load existing dataset and its metadata
        - Mark existing metadata `is_latest=False` and set its dataset_doi to a versioned DOI
        - Create new metadata with incremented version and assign the original (real) DOI to the new metadata
        - Create a new DataSet row pointing to the new metadata and create feature models/files from the provided form
        - Commit once
        """
        try:
            # load previous dataset and metadata
            prev_dataset = self.get_by_id(dataset_id)
            if not prev_dataset:
                raise ValueError(f"Dataset {dataset_id} not found")

            prev_meta = prev_dataset.ds_meta_data

            # build dsmetadata for new version from form
            dsmetadata_data = form.get_dsmetadata()

            # preserve original DOI: the 'real' DOI will be used for the new dataset
            original_doi = prev_meta.dataset_doi

            # increment version number based on type
            current_version = str(prev_meta.version)
            if '.' in current_version:
                parts = current_version.split('.')
                if len(parts) == 2:
                    major, minor = map(int, parts)
                else:
                    major, minor = map(int, parts[:2])
            else:
                major = int(float(current_version))
                minor = 0

            if version_increment_type == 'minor':
                minor += 1
            elif version_increment_type == 'major':
                major += 1
                minor = 0
            else:
                major += 1  # default to major

            new_version = f"{major}.{minor}"

            # create new metadata record; set dataset_doi to original_doi (if any)
            dsmetadata_data["version"] = new_version
            dsmetadata_data["is_latest"] = True
            dsmetadata_data["dataset_doi"] = original_doi
            new_meta = self.dsmetadata_repository.create(**dsmetadata_data)

            # attach authors (main + fm authors will be attached later for FMs)
            main_author = {
                "name": f"{current_user.profile.surname}, {current_user.profile.name}",
                "affiliation": current_user.profile.affiliation,
                "orcid": current_user.profile.orcid,
            }
            for author_data in [main_author] + form.get_authors():
                # Deduplicate dataset authors when creating new version
                # We'll build a deduplicated list first
                raw_auths = [main_author] + form.get_authors()
                seen_new = set()
            for author_data in raw_auths:
                key = (author_data.get('name'), author_data.get('orcid'))
                if key in seen_new:
                    continue
                seen_new.add(key)
                author = self.author_repository.create(commit=False, ds_meta_data_id=new_meta.id, **author_data)
                new_meta.authors.append(author)

            # update previous metadata: mark not latest and change its DOI to a versioned DOI
            if original_doi:
                prev_meta.dataset_doi = f"{original_doi}/v{int(prev_meta.version)}"
            prev_meta.is_latest = False

            # create new DataSet row
            dataset = self.create(
                commit=False, user_id=prev_dataset.user_id, ds_meta_data_id=new_meta.id, draft_mode=False
            )

            # create feature models and files from form for new dataset
            for feature_model in form.feature_models:
                csv_filename = feature_model.csv_filename.data
                fmmetadata = self.fmmetadata_repository.create(commit=False, **feature_model.get_fmmetadata())
                fm_seen = set()
                for author_data in feature_model.get_authors():
                    key = (author_data.get('name'), author_data.get('orcid'))
                    if key in fm_seen:
                        continue
                    fm_seen.add(key)
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

            # commit everything once
            self.repository.session.commit()
        except Exception as exc:
            logger.info(f"Exception creating new dataset version: {exc}")
            self.repository.session.rollback()
            raise exc
        return dataset
    
    def create_draft(self, current_user, data: dict = None) -> DataSet:
        try:
            title = (data or {}).get("title") or "Untitled Dataset"
            desc = (data or {}).get("desc") or ""
            data_category = (data or {}).get("data_category") or "NONE"

            dsmetadata = self.dsmetadata_repository.create(
                title=title,
                description=desc,
                data_category=data_category,
                publication_doi=None,
                dataset_doi=None,
                tags=(data or {}).get("tags"),
            )

            main_author = {
                "name": f"{current_user.profile.surname}, {current_user.profile.name}",
                "affiliation": current_user.profile.affiliation,
                "orcid": current_user.profile.orcid,
            }

            author = self.author_repository.create(commit=False, ds_meta_data_id=dsmetadata.id, **main_author)
            dsmetadata.authors.append(author)

            dataset = self.create(commit=False, user_id=current_user.id, ds_meta_data_id=dsmetadata.id, draft_mode=True)

            # Move CSV files from user's temp folder into persistent storage and create
            # corresponding feature model and hubfile records so the draft appears
            # with its files in the user's local datasets view.
            temp_dir = current_user.temp_folder()
            if os.path.isdir(temp_dir):
                for filename in sorted(os.listdir(temp_dir)):
                    if not filename.lower().endswith(".csv"):
                        continue

                    file_path = os.path.join(temp_dir, filename)
                    try:
                        checksum, size = calculate_checksum_and_size(file_path)

                        fmmetadata = self.fmmetadata_repository.create(
                            commit=False,
                            csv_filename=filename,
                            title="",
                            description="",
                            data_category=data_category,
                            publication_doi=None,
                            tags=None,
                            csv_version=None,
                        )

                        # create a minimal author for the feature model
                        fm_author = self.author_repository.create(commit=False, fm_meta_data_id=fmmetadata.id, **main_author)
                        fmmetadata.authors.append(fm_author)

                        fm = self.feature_model_repository.create(commit=False, data_set_id=dataset.id, fm_meta_data_id=fmmetadata.id)

                        hubfile = self.hubfilerepository.create(
                            commit=False, name=filename, checksum=checksum, size=size, feature_model_id=fm.id
                        )
                        fm.files.append(hubfile)

                        # save the actual file into storage
                        dest_relative = storage_service.dataset_file_path(current_user.id, dataset.id, filename)
                        storage_service.save_local_file(file_path, dest_relative)
                    except Exception:
                        logger.exception("Failed to move and register file %s into draft dataset", filename)

            self.repository.session.commit()
            return dataset
        except Exception as exc:
            logger.exception(f"Exception creating draft dataset: {exc}")
            self.repository.session.rollback()
            raise

    def delete_dataset(self, dataset):
        try:
            self.repository.session.delete(dataset)
            self.repository.session.commit()
        except Exception as exc:
            logger.exception(f"Exception deleting dataset: {exc}")
            self.repository.session.rollback()
            raise exc

    def delete_draft_dataset(self, dataset):
        if not dataset:
            return

        if not dataset.draft_mode:
            raise ValueError("Only draft datasets can be deleted using this endpoint")

        try:
            self.repository.session.delete(dataset)
            self.repository.session.commit()
        except Exception as exc:
            logger.exception(f"Exception deleting draft dataset: {exc}")
            self.repository.session.rollback()
            raise exc

    def update_dsmetadata(self, metadata_id, **kwargs):
        return self.dsmetadata_repository.update(metadata_id, **kwargs)

    def get_steamgameshub_doi(self, dataset: DataSet) -> str:
        domain = os.getenv("DOMAIN", "localhost")
        return f"http://{domain}/doi/{dataset.ds_meta_data.dataset_doi}"

    def change_draft_mode(self, dataset_id: int):
        dataset = self.get_by_id(dataset_id)
        if not dataset:
            raise ValueError("Dataset not found")

        new_value = not bool(dataset.draft_mode)
        return self.update(dataset_id, draft_mode=new_value)

    def trending_datasets(self, period_days: int = 7, by: str = "views", limit: int = 5):
        try:
            results = self._query_trending_metrics(period_days, by, limit)
            if not results:
                return []
            return self._attach_accepted_communities(results)
        except Exception:
            logger.exception("Error al calcular trending_datasets; usando fallback.")
        return self._fallback_trending(limit)

    def _query_trending_metrics(self, period_days: int, by: str, limit: int):
        since = datetime.now() - timedelta(days=period_days)
        session = self.repository.session
        metric_model = DSViewRecord if by == "views" else DSDownloadRecord if by == "downloads" else None
        if metric_model is None:
            return []

        ts_col_name = "view_date" if metric_model is DSViewRecord else "download_date"
        ts_col = getattr(metric_model, ts_col_name, None)
        if ts_col is None:
            raise AttributeError(f"{metric_model.__name__} no tiene '{ts_col_name}'")

        subq = (
            session.query(
                metric_model.dataset_id.label("dataset_id"),
                func.count(metric_model.id).label("metric"),
            )
            .filter(ts_col >= since)
            .group_by(metric_model.dataset_id)
            .subquery()
        )

        query = (
            session.query(DataSet, func.coalesce(subq.c.metric, 0).label("metric"))
            .outerjoin(subq, subq.c.dataset_id == DataSet.id)
            .order_by(desc("metric"))
            .limit(limit)
        )
        return query.all()

    def _attach_accepted_communities(self, results):
        session = self.repository.session
        enriched = []
        for dataset, metric in results:
            accepted_proposal = (
                session.query(CommunityDatasetProposal)
                .filter_by(dataset_id=dataset.id, status=ProposalStatus.ACCEPTED)
                .first()
            )
            dataset.accepted_community = accepted_proposal.community if accepted_proposal else None
            enriched.append((dataset, int(metric or 0)))
        return enriched

    def _fallback_trending(self, limit: int):
        try:
            recent = (
                self.repository.latest_synchronized()
                if hasattr(self.repository, "latest_synchronized")
                else self.latest_synchronized()
            )
            recent_list = list(recent)[:limit]
            for dataset in recent_list:
                dataset.accepted_community = None
            return [(dataset, 0) for dataset in recent_list]
        except Exception:
            logger.exception("Fallback de trending_datasets también ha fallado. Devolviendo lista vacía.")
            return []
        
    def rollback_to_previous_version(self, previous_version, current_dataset):
        try:
            previous_version.dataset_doi = previous_version.dataset_doi.rsplit("/v", 1)[0] if previous_version.dataset_doi else None
            previous_version.publication_doi = previous_version.publication_doi.rsplit("/v", 1)[0] if previous_version.publication_doi else None
            previous_version.is_latest = True

            self.delete_dataset(current_dataset)
            self.repository.session.commit()
        except Exception as exc:
            logger.exception(f"Exception rolling back to previous dataset version: {exc}")
            self.repository.session.rollback()
            raise exc
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

    def get_all_versions_by_doi(self, doi: str):
        return self.repository.get_all_versions_by_doi(doi)

    def get_all_versions_by_deposition_id(self, deposition_id: int):
        return self.repository.get_all_versions_by_deposition_id(deposition_id)
    
    def get_previous_version_by_deposition_id(self, deposition_id: int):
        return self.repository.get_previous_version_by_deposition_id(deposition_id)


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


class IssueService(BaseService):
    def __init__(self):
        super().__init__(IssueRepository())

    def list_for_dataset(self, dataset_id: int):
        return self.repository.list_by_dataset(dataset_id)

    def list_all(self):
        """Get all issues across all datasets, ordered by creation date (newest first)."""
        return self.repository.list_all()

    def open_or_close(self, issue_id: int):
        issue = self.repository.get_by_id(issue_id)
        if issue:
            issue.is_open = not issue.is_open
            self.repository.session.commit()
            return issue
        else:
            return None
