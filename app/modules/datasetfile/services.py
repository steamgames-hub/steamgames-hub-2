from app.modules.datasetfile.repositories import DatasetFileMetaDataRepository, DatasetFileRepository
from app.modules.hubfile.services import HubfileService
from core.services.BaseService import BaseService


class DatasetFileService(BaseService):
    def __init__(self):
        super().__init__(DatasetFileRepository())
        self.hubfile_service = HubfileService()

    def total_dataset_file_views(self) -> int:
        return self.hubfile_service.total_hubfile_views()

    def total_dataset_file_downloads(self) -> int:
        return self.hubfile_service.total_hubfile_downloads()

    def count_dataset_files(self):
        return self.repository.count_files()

    class DatasetFileMetaDataService(BaseService):
        def __init__(self):
            super().__init__(DatasetFileMetaDataRepository())
