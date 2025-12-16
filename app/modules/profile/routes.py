from flask import redirect, render_template, request, url_for, abort
from flask_login import current_user, login_required

from app import db
from app.modules.auth.models import UserRole
from app.modules.auth.services import AuthenticationService
from app.modules.dataset.models import DataSet
from app.modules.profile import profile_bp
from app.modules.profile.forms import UserProfileForm
from app.modules.profile.services import UserProfileService


@profile_bp.route("/profile/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
def edit_profile(user_id):
    auth_service = AuthenticationService()
    if current_user.role == UserRole.ADMIN:
        profile = auth_service.get_profile_by_user_id(user_id)
    else:
        profile = auth_service.get_authenticated_user_profile()

    user = auth_service.repository.get_by_id(user_id) if current_user.role == UserRole.ADMIN else current_user
    if user.role == UserRole.ADMIN and current_user.id != user.id:
        abort(403, description="Unauthorized")
    # If profile does not exist, create a blank one for the user (including empty affiliation)
    if not profile:
        if user:
            # Crea el perfil en la base de datos si no existe
            auth_service.user_profile_repository.create(user_id=user.id, name="", surname="", affiliation="")
            auth_service.repository.session.commit()
            # Recupera el perfil recién creado desde la base de datos
            profile = auth_service.get_profile_by_user_id(user.id)
        else:
            return redirect(url_for("public.index"))

    form = UserProfileForm()
    if request.method == "POST":
        service = UserProfileService()
        result, errors = service.update_profile(profile.id, form)
        if result:
            from flask import flash

            flash("Profile updated successfully", "success")
            return redirect(url_for("profile.edit_profile", user_id=profile.user_id))
        else:
            # Si hay errores, renderizar el template pero siempre pasar profile
            if profile.affiliation is None:
                profile.affiliation = ""
            return render_template("profile/edit.html", form=form, profile=profile)

    # Asegura que affiliation nunca sea None
    if profile.affiliation is None:
        profile.affiliation = ""
    return render_template("profile/edit.html", form=form, profile=profile)


@profile_bp.route("/profile/summary")
@login_required
def my_profile():
    page = request.args.get("page", 1, type=int)
    per_page = 5

    user_datasets_pagination = (
        db.session.query(DataSet)
        .filter(DataSet.user_id == current_user.id)
        .order_by(DataSet.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    total_datasets_count = db.session.query(DataSet).filter(DataSet.user_id == current_user.id).count()

    print(user_datasets_pagination.items)

    return render_template(
        "profile/summary.html",
        user_profile=current_user.profile,
        user=current_user,
        datasets=user_datasets_pagination.items,
        pagination=user_datasets_pagination,
        total_datasets=total_datasets_count,
    )


@profile_bp.route("/profile/save_drafts", methods=["PUT"])
@login_required
def change_save_drafts():
    auth_service = AuthenticationService()
    profile = auth_service.get_authenticated_user_profile
    if not profile:
        return redirect(url_for("public.index"))

    service = UserProfileService()
    service.change_save_drafts(profile().id)

    return my_profile()
