import os

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.modules.community import community_bp
from app.modules.community.forms import CommunityForm
from app.modules.community.models import ProposalStatus
from app.modules.community.services import CommunityProposalService, CommunityService
from app.modules.dataset.services import DataSetService
from core.services.MailService import MailService
from core.storage import storage_service

community_service = CommunityService()
proposal_service = CommunityProposalService()
dataset_service = DataSetService()


@community_bp.route("/community", methods=["GET"])  # list
def list_communities():
    communities = community_service.list_all()
    return render_template("community/list.html", communities=communities)


@community_bp.route("/community/create", methods=["GET", "POST"])  # create
@login_required
def create_community():
    form = CommunityForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            return render_template("community/create.html", form=form), 400

        icon_file = request.files.get("icon")
        if not icon_file or not icon_file.filename:
            flash("Icon image is required.", "error")
            return render_template("community/create.html", form=form), 400
        community = community_service.create_with_icon(
            name=form.name.data,
            description=form.description.data,
            responsible_user_id=current_user.id,
            icon_file=icon_file,
        )
        return redirect(url_for("community.view_community", community_id=community.id))

    return render_template("community/create.html", form=form)


@community_bp.route("/community/<int:community_id>", methods=["GET"])  # view
def view_community(community_id: int):
    community = community_service.get_or_404(community_id)

    pending = []
    accepted = []
    if current_user.is_authenticated and current_user.id == community.responsible_user_id:
        # show proposals for responsible
        pending = [p for p in community.proposals if p.status == ProposalStatus.PENDING]
        accepted = [p for p in community.proposals if p.status == ProposalStatus.ACCEPTED]

    return render_template(
        "community/view.html",
        community=community,
        pending_proposals=pending,
        accepted_proposals=accepted,
    )


@community_bp.route("/community/<int:community_id>/proposals/<int:proposal_id>/accept", methods=["POST"])  # accept
@login_required
def accept_proposal(community_id: int, proposal_id: int):
    community = community_service.get_or_404(community_id)
    if current_user.id != community.responsible_user_id:
        abort(403)
    ok, proposal, msg = proposal_service.decide(proposal_id, accept=True)
    if not ok:
        flash(msg, "error")
        return redirect(url_for("community.view_community", community_id=community_id))
    # notify proposer by email (best-effort)
    try:
        user = proposal.proposed_by
        if user and user.email:
            title = proposal.dataset.ds_meta_data.title
            cname = community.name
            body_text = "Good news! Your dataset '" + title + "' has been accepted into the community '" + cname + "'."
            MailService().send_email(user.email, f"Your dataset was accepted into '{cname}'", body_text)
    except Exception:
        pass
    return redirect(url_for("community.view_community", community_id=community_id))


@community_bp.route("/community/<int:community_id>/proposals/<int:proposal_id>/reject", methods=["POST"])  # reject
@login_required
def reject_proposal(community_id: int, proposal_id: int):
    community = community_service.get_or_404(community_id)
    if current_user.id != community.responsible_user_id:
        abort(403)
    ok, proposal, msg = proposal_service.decide(proposal_id, accept=False)
    if not ok:
        flash(msg, "error")
        return redirect(url_for("community.view_community", community_id=community_id))
    # notify proposer by email (best-effort)
    try:
        user = proposal.proposed_by
        if user and user.email:
            title = proposal.dataset.ds_meta_data.title
            cname = community.name
            body_text = (
                "Your dataset '" + title + "' was not accepted into the community '" + cname + "'. "
                "You can propose it again later."
            )
            MailService().send_email(user.email, f"Your dataset was rejected from '{cname}'", body_text)
    except Exception:
        pass
    return redirect(url_for("community.view_community", community_id=community_id))


@community_bp.route("/community/propose", methods=["POST"])  # propose dataset to community
@login_required
def propose_dataset_to_community():
    dataset_id = int(request.form.get("dataset_id"))
    community_id = int(request.form.get("community_id"))
    # only dataset owner can propose
    dataset = dataset_service.get_or_404(dataset_id)
    if dataset.user_id != current_user.id:
        abort(403)
    ok, msg = proposal_service.propose(dataset_id=dataset_id, community_id=community_id, user_id=current_user.id)
    flash(msg, "success" if ok else "error")
    # Redirect back to appropriate view
    if dataset.ds_meta_data.dataset_doi is None:
        return redirect(url_for("dataset.get_unsynchronized_dataset", dataset_id=dataset_id))
    else:
        return redirect(url_for("dataset.subdomain_index", doi=dataset.ds_meta_data.dataset_doi))


@community_bp.route("/community/icon/<int:community_id>")
def community_icon(community_id: int):
    community = community_service.get_or_404(community_id)
    if not community.icon_path:
        abort(404)
    relative_path = storage_service.community_icon_path(
        community.id,
        community.icon_path,
    )
    local_path = storage_service.ensure_local_copy(relative_path)
    if not os.path.exists(local_path):
        abort(404)
    return send_file(local_path)


@community_bp.route("/community/mine", methods=["GET"])
@login_required
def my_communities():
    communities = community_service.list_by_responsible(current_user.id)
    return render_template("community/list.html", communities=communities)
