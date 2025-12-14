from datetime import datetime

from app.modules.auth.models import User
from app.modules.community.models import Community, CommunityDatasetProposal, ProposalStatus
from app.modules.dataset.models import DataSet
from core.seeders.BaseSeeder import BaseSeeder


class CommunitySeeder(BaseSeeder):

    # Ensure this runs after users (1) and datasets (2)
    priority = 3

    def run(self):
        # Pick first two users as responsibles if available
        users = User.query.order_by(User.id).limit(2).all()
        if not users:
            return

        payload = []
        names = [
            ("Open Datasets", "A community for general open datasets."),
            ("Steam Analytics", "Community for Steam analysis datasets."),
        ]

        for idx, (name, desc) in enumerate(names):
            responsible = users[min(idx, len(users) - 1)]
            payload.append(Community(name=name, description=desc, responsible_user_id=responsible.id, icon_path=None))

        # Seed communities
        seeded_communities = self.seed(payload)

        # Optionally seed dataset proposals: some accepted, some pending
        datasets = DataSet.query.order_by(DataSet.id.asc()).all()
        if not datasets or not seeded_communities:
            # Nothing else to relate if datasets or communities are missing
            return

        proposals = self._build_proposals(datasets, seeded_communities)
        if proposals:
            self.seed(proposals)

    def _build_proposals(self, datasets, communities):
        proposals = []
        plan = []
        if len(communities) >= 1:
            plan.append((0, communities[0], ProposalStatus.ACCEPTED))
            plan.append((2, communities[0], ProposalStatus.ACCEPTED))
        if len(communities) >= 2:
            plan.append((1, communities[1], ProposalStatus.PENDING))
            plan.append((3, communities[1], ProposalStatus.ACCEPTED))
            plan.append((4, communities[1], ProposalStatus.PENDING))

        for dataset_idx, community, status in plan:
            if dataset_idx >= len(datasets):
                continue
            proposals.append(self._make_proposal(datasets[dataset_idx], community, status))
        return proposals

    def _make_proposal(self, dataset: DataSet, community: Community, status: str):
        decided_at = datetime.utcnow() if status == ProposalStatus.ACCEPTED else None
        return CommunityDatasetProposal(
            dataset_id=dataset.id,
            community_id=community.id,
            proposed_by_user_id=dataset.user_id,
            status=status,
            decided_at=decided_at,
        )
