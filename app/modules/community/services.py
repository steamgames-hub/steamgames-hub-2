import os
from datetime import datetime
from typing import List

from flask import current_app
from PIL import Image
from werkzeug.utils import secure_filename

from app.modules.community.models import Community, ProposalStatus
from app.modules.community.repositories import CommunityProposalRepository, CommunityRepository
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService


class CommunityService(BaseService):
    def __init__(self):
        super().__init__(CommunityRepository())

    MAX_ICON_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_ICON_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    def _validate_icon_extension(self, filename: str):
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext not in self.ALLOWED_ICON_EXTS:
            raise ValueError("Invalid icon format. Allowed: png, jpg, jpeg, gif, webp.")

    def _validate_icon_size(self, icon_file):
        try:
            icon_file.stream.seek(0, os.SEEK_END)
            size = icon_file.stream.tell()
            icon_file.stream.seek(0)
        except Exception:
            size = None
        if size is not None and size > self.MAX_ICON_SIZE:
            raise ValueError("Icon file is too large (max 5MB).")

    def _validate_icon_integrity(self, icon_file):
        try:
            img = Image.open(icon_file.stream)
            img.verify()
        except Exception:
            try:
                icon_file.stream.seek(0)
            except Exception:
                pass
            raise ValueError("Invalid image file.")
        finally:
            try:
                icon_file.stream.seek(0)
            except Exception:
                pass

    def validate_icon_file(self, icon_file):
        if not icon_file or not icon_file.filename:
            raise ValueError("Icon image is required.")
        self._validate_icon_extension(icon_file.filename)
        self._validate_icon_size(icon_file)
        self._validate_icon_integrity(icon_file)

    def create_with_icon(self, name: str, description: str, responsible_user_id: int, icon_file) -> Community:
        # Validate icon before creating files on disk
        self.validate_icon_file(icon_file)
        community = self.repository.create(
            commit=False, name=name, description=description, responsible_user_id=responsible_user_id
        )
        self.repository.session.flush()

        if icon_file and icon_file.filename:
            filename = secure_filename(icon_file.filename)
            # Build an absolute base directory
            base_dir = os.getenv("WORKING_DIR")
            if not base_dir:
                # parent of app/ directory
                base_dir = os.path.abspath(os.path.join(current_app.root_path, os.pardir))

            dest_dir = os.path.join(base_dir, uploads_folder_name(), "communities", f"community_{community.id}")
            os.makedirs(dest_dir, exist_ok=True)
            icon_path = os.path.join(dest_dir, filename)
            icon_file.save(icon_path)
            community.icon_path = filename

        self.repository.session.commit()
        return community

    def list_all(self) -> List[Community]:
        return self.repository.model.query.order_by(self.repository.model.created_at.desc()).all()

    def list_by_responsible(self, user_id: int) -> List[Community]:
        return self.repository.by_responsible(user_id)


class CommunityProposalService(BaseService):
    def __init__(self):
        super().__init__(CommunityProposalRepository())

    def propose(self, dataset_id: int, community_id: int, user_id: int):
        """
        Returns (ok: bool, message: str).
        - If dataset already accepted in any community: block.
        - If existing rejected proposal: reopen as pending.
        - If existing pending: no-op.
        - Otherwise create new pending.
        """
        if self.repository.accepted_exists_for_dataset(dataset_id):
            return False, "This dataset is already in a community and cannot be proposed again."

        existing = self.repository.find_existing(dataset_id, community_id)
        if existing:
            if existing.status == ProposalStatus.REJECTED:
                existing.status = ProposalStatus.PENDING
                existing.decided_at = None
                self.repository.session.commit()
                return True, "Proposal resubmitted to the community."
            elif existing.status == ProposalStatus.PENDING:
                return False, "There is already a pending proposal for this community."
            else:
                return False, "This dataset is already in a community."

        self.repository.create(
            dataset_id=dataset_id,
            community_id=community_id,
            proposed_by_user_id=user_id,
            status=ProposalStatus.PENDING,
        )
        return True, "Proposal submitted to the community."

    def decide(self, proposal_id: int, accept: bool):
        """
        Returns (ok: bool, proposal: Optional[CommunityDatasetProposal], message: str)
        - If trying to accept and another accepted exists for the same dataset, block.
        - Otherwise update status and return ok.
        """
        proposal = self.repository.get_by_id(proposal_id)
        if not proposal:
            return False, None, "Proposal not found."

        if accept:
            existing = self.repository.get_accepted_for_dataset(proposal.dataset_id)
            if existing and existing.id != proposal.id:
                return False, proposal, "Dataset already belongs to another community."
            updated = self.repository.update(proposal_id, status=ProposalStatus.ACCEPTED, decided_at=datetime.utcnow())
            return True, updated, "Proposal accepted."
        else:
            updated = self.repository.update(proposal_id, status=ProposalStatus.REJECTED, decided_at=datetime.utcnow())
            return True, updated, "Proposal rejected."
