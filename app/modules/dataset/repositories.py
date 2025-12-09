import logging
from datetime import datetime, timezone
from typing import Optional

from flask_login import current_user
from sqlalchemy import desc, func

from app.modules.dataset.models import Author, DataSet, DOIMapping, DSDownloadRecord, DSMetaData, DSViewRecord, Issue
from core.repositories.BaseRepository import BaseRepository

logger = logging.getLogger(__name__)


class AuthorRepository(BaseRepository):
    def __init__(self):
        super().__init__(Author)


class DSDownloadRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSDownloadRecord)

    def total_dataset_downloads(self) -> int:
        max_id = self.model.query.with_entities(func.max(self.model.id)).scalar()
        return max_id if max_id is not None else 0


class DSMetaDataRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSMetaData)

    def filter_by_doi(self, doi: str) -> Optional[DSMetaData]:
        return self.model.query.filter_by(dataset_doi=doi).first()

    def get_all_versions_by_doi(self, doi: str):
        return self.model.query.filter_by(dataset_doi=doi).order_by(desc(self.model.version)).all()

    def get_all_versions_by_deposition_id(self, deposition_id: int):
        return self.model.query.filter_by(deposition_id=deposition_id).order_by(self.model.version.asc()).all()


class DSViewRecordRepository(BaseRepository):
    def __init__(self):
        super().__init__(DSViewRecord)

    def total_dataset_views(self) -> int:
        max_id = self.model.query.with_entities(func.max(self.model.id)).scalar()
        return max_id if max_id is not None else 0

    def the_record_exists(self, dataset: DataSet, user_cookie: str):
        return self.model.query.filter_by(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset.id,
            view_cookie=user_cookie,
        ).first()

    def create_new_record(self, dataset: DataSet, user_cookie: str) -> DSViewRecord:
        return self.create(
            user_id=current_user.id if current_user.is_authenticated else None,
            dataset_id=dataset.id,
            view_date=datetime.now(timezone.utc),
            view_cookie=user_cookie,
        )


class DataSetRepository(BaseRepository):
    def __init__(self):
        super().__init__(DataSet)

    def get_synchronized(self, current_user_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(
                DataSet.user_id == current_user_id,
                not DataSet.draft_mode,
                DSMetaData.dataset_doi.isnot(None),
            )
            .filter(DSMetaData.is_latest.is_(True))
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_unsynchronized(self, current_user_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(
                DataSet.user_id == current_user_id,
                not DataSet.draft_mode,
                DSMetaData.dataset_doi.is_(None),
            )
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_unsynchronized_dataset(self, current_user_id: int, dataset_id: int) -> DataSet:
        return (
            self.model.query.join(DSMetaData)
            .filter(DataSet.user_id == current_user_id, DataSet.id == dataset_id, DSMetaData.dataset_doi.is_(None))
            .first()
        )

    def count_synchronized_datasets(self):
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.isnot(None))
            .filter(DSMetaData.is_latest.is_(True))
            .count()
        )

    def latest_synchronized(self):
        return (
            self.model.query.join(DSMetaData)
            .filter(DSMetaData.dataset_doi.isnot(None))
            .filter(DSMetaData.is_latest.is_(True))
            .order_by(desc(self.model.id))
            .limit(5)
            .all()
        )


class DOIMappingRepository(BaseRepository):
    def __init__(self):
        super().__init__(DOIMapping)

    def get_new_doi(self, old_doi: str) -> str:
        return self.model.query.filter_by(dataset_doi_old=old_doi).first()


class IssueRepository(BaseRepository):
    def __init__(self):
        super().__init__(Issue)

    def list_by_dataset(self, dataset_id: int):
        return self.model.query.filter_by(dataset_id=dataset_id).order_by(Issue.created_at.desc()).all()

    def list_all(self):
        """Return all issues across all datasets, ordered by creation date (newest first)."""
        return self.model.query.order_by(Issue.created_at.desc()).all()
