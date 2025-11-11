from app.modules.explore.repositories import ExploreRepository
from core.services.BaseService import BaseService


class ExploreService(BaseService):
    def __init__(self):
        super().__init__(ExploreRepository())

    def filter(self, query="", sorting="newest", data_category="any", tags=[], **kwargs):
        return self.repository.filter(query, sorting, data_category, tags, **kwargs)
