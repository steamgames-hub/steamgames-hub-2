from datetime import datetime

from app import db


class Community(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    icon_path = db.Column(db.String(255), nullable=True)
    responsible_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    responsible = db.relationship("User", backref="communities_responsible")
    proposals = db.relationship(
        "CommunityDatasetProposal", backref="community", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"Community<{self.id}:{self.name}>"


class ProposalStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CommunityDatasetProposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.Integer, db.ForeignKey("data_set.id"), nullable=False)
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=False)
    proposed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ProposalStatus.PENDING)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    decided_at = db.Column(db.DateTime, nullable=True)

    dataset = db.relationship("DataSet", backref="community_proposals")
    proposed_by = db.relationship("User", backref="community_proposals_made")

    __table_args__ = (db.UniqueConstraint("dataset_id", "community_id", name="uq_dataset_community"),)

    def __repr__(self):
        return f"Proposal<ds={self.dataset_id}, community={self.community_id}, status={self.status}>"
