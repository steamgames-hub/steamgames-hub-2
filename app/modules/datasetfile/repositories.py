from app.modules.datasetfile.models import DatasetFile, DatasetFileMetaData
from core.repositories.BaseRepository import BaseRepository


class DatasetFileRepository(BaseRepository):
    def __init__(self):
        super().__init__(DatasetFile)

    def count_files(self) -> int:
        return self.model.query.count()


class DatasetFileMetaDataRepository(BaseRepository):
    def __init__(self):
        super().__init__(DatasetFileMetaData)
