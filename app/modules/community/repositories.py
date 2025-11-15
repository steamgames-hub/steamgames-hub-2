from typing import List, Optional

from core.repositories.BaseRepository import BaseRepository
from app.modules.community.models import Community, CommunityDatasetProposal, ProposalStatus


class CommunityRepository(BaseRepository[Community]):
    def __init__(self):
        super().__init__(Community)

    def by_responsible(self, user_id: int) -> List[Community]:
        return self.model.query.filter_by(responsible_user_id=user_id).order_by(self.model.created_at.desc()).all()


class CommunityProposalRepository(BaseRepository[CommunityDatasetProposal]):
    def __init__(self):
        super().__init__(CommunityDatasetProposal)

    def find_existing(self, dataset_id: int, community_id: int) -> Optional[CommunityDatasetProposal]:
        return (
            self.model.query.filter_by(dataset_id=dataset_id, community_id=community_id).first()
        )

    def by_community_and_status(self, community_id: int, status: str) -> List[CommunityDatasetProposal]:
        return self.model.query.filter_by(community_id=community_id, status=status).all()

    def accepted_exists_for_dataset(self, dataset_id: int) -> bool:
        return (
            self.model.query.filter_by(dataset_id=dataset_id, status=ProposalStatus.ACCEPTED).first() is not None
        )

    def get_accepted_for_dataset(self, dataset_id: int) -> Optional[CommunityDatasetProposal]:
        return self.model.query.filter_by(dataset_id=dataset_id, status=ProposalStatus.ACCEPTED).first()
