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

        proposals = []

        # Helper to create a proposal safely
        def make_proposal(ds: DataSet, community: Community, status: str):
            decided_at = datetime.utcnow() if status == ProposalStatus.ACCEPTED else None
            return CommunityDatasetProposal(
                dataset_id=ds.id,
                community_id=community.id,
                proposed_by_user_id=ds.user_id,
                status=status,
                decided_at=decided_at,
            )

        # Compose a small, deterministic set of proposals
        # - First dataset accepted in first community (if both exist)
        # - Second dataset pending in second community (if exists)
        # - Third dataset pending in first community (if exists)
        c1 = seeded_communities[0] if len(seeded_communities) >= 1 else None
        c2 = seeded_communities[1] if len(seeded_communities) >= 2 else None

        if c1 and len(datasets) >= 1:
            proposals.append(make_proposal(datasets[0], c1, ProposalStatus.ACCEPTED))

        if c2 and len(datasets) >= 2:
            proposals.append(make_proposal(datasets[1], c2, ProposalStatus.PENDING))

        if c1 and len(datasets) >= 3:
            proposals.append(make_proposal(datasets[2], c1, ProposalStatus.PENDING))

        if proposals:
            self.seed(proposals)
