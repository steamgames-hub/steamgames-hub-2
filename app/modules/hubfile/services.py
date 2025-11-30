import os

from app.modules.auth.models import User
from app.modules.dataset.models import DataSet
from app.modules.hubfile.models import Hubfile
from app.modules.hubfile.repositories import (
    HubfileDownloadRecordRepository,
    HubfileRepository,
    HubfileViewRecordRepository,
)
from core.services.BaseService import BaseService
from core.storage import storage_service


class HubfileService(BaseService):
    def __init__(self):
        super().__init__(HubfileRepository())
        self.hubfile_view_record_repository = HubfileViewRecordRepository()
        self.hubfile_download_record_repository = (
            HubfileDownloadRecordRepository()
        )

    def get_owner_user_by_hubfile(self, hubfile: Hubfile) -> User:
        return self.repository.get_owner_user_by_hubfile(hubfile)

    def get_dataset_by_hubfile(self, hubfile: Hubfile) -> DataSet:
        return self.repository.get_dataset_by_hubfile(hubfile)

    def _relative_path(self, hubfile: Hubfile) -> str:
        hubfile_user = self.get_owner_user_by_hubfile(hubfile)
        hubfile_dataset = self.get_dataset_by_hubfile(hubfile)
        return storage_service.dataset_file_path(
            hubfile_user.id,
            hubfile_dataset.id,
            hubfile.name,
        )

    def get_path_by_hubfile(self, hubfile: Hubfile) -> str:
        relative_path = self._relative_path(hubfile)
        return storage_service.ensure_local_copy(relative_path)

    def get_relative_path_by_hubfile(self, hubfile: Hubfile) -> str:
        return self._relative_path(hubfile)

    def total_hubfile_views(self) -> int:
        return self.hubfile_view_record_repository.total_hubfile_views()

    def total_hubfile_downloads(self) -> int:
        hubfile_download_record_repository = HubfileDownloadRecordRepository()
        return hubfile_download_record_repository.total_hubfile_downloads()


class HubfileDownloadRecordService(BaseService):
    def __init__(self):
        super().__init__(HubfileDownloadRecordRepository())

    def update_download_count(self, file_id: int):
        hubfile = Hubfile.query.get(file_id)
        if not hubfile:
            return None

        hubfile.download_count = (hubfile.download_count or 0) + 1
        return hubfile.download_count
