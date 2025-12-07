from sqlalchemy import func

from app.modules.featuremodel.models import FeatureModel, FMMetaData
from core.repositories.BaseRepository import BaseRepository


class FeatureModelRepository(BaseRepository):
    def __init__(self):
        super().__init__(FeatureModel)

    def count_feature_models(self) -> int:
        return self.model.query.count()
        


class FMMetaDataRepository(BaseRepository):
    def __init__(self):
        super().__init__(FMMetaData)
