from flask import redirect, render_template, abort, request, url_for, jsonify
from flask_login import current_user, login_user, logout_user, login_required

from app.modules.auth import auth_bp
from app.modules.auth.forms import LoginForm, SignupForm
from app.modules.auth.services import AuthenticationService
from app.modules.profile.services import UserProfileService
from app.modules.auth.models import User, UserRole
from app import db

import logging

authentication_service = AuthenticationService()
user_profile_service = UserProfileService()

logger = logging.getLogger(__name__)

@auth_bp.route("/signup/", methods=["GET", "POST"])
def show_signup_form():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data
        if not authentication_service.is_email_available(email):
            return render_template("auth/signup_form.html", form=form, error=f"Email {email} in use")

        try:
            user = authentication_service.create_with_profile(**form.data)
        except Exception as exc:
            return render_template("auth/signup_form.html", form=form, error=f"Error creating user: {exc}")

        login_user(user, remember=True)
        send_verification_email()
        return render_template("auth/verification_lockscreen.html", show_modal=True, modal_message="A verification email has been sent to your address. Make sure to check your spam folder before resending the email.")

    return render_template("auth/signup_form.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect_checks_verified(url_for("public.index"), current_user.verified)
    
    form = LoginForm()
    if request.method == "POST" and form.validate_on_submit():
        if authentication_service.login(form.email.data, form.password.data):
            return redirect_checks_verified(url_for("public.index"), current_user.verified)
        return render_template("auth/login_form.html", form=form, error="Invalid credentials")

    return render_template("auth/login_form.html", form=form)

# Auxiliary function to minimize code duplication and complexity
def redirect_checks_verified(url, verified):
    if verified:
        return redirect(url)
    else:
        return render_template("auth/verification_lockscreen.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("public.index"))

@auth_bp.route("/verify", methods=['GET', 'POST'])
@login_required
def send_verification_email(email=None):
    if email is None:
        email = current_user.email

    try:
        authentication_service.send_verification_email(email)
    except Exception as exc:
        logger.exception(f"Exception while sending verification email: {exc}")
        return render_template("auth/verification_lockscreen.html", show_modal=True, modal_message=f"Error sending verification email, please, try again later.")
    
    return render_template("auth/verification_lockscreen.html", show_modal=True, modal_message="A verification email has been sent to your address. Make sure to check your spam folder before resending the email.")
    
@auth_bp.route("/verify/<token>", methods=['GET', 'POST'])
@login_required
def verify(token):
    if current_user.verified:
        return redirect(url_for("public.index"))
    email = authentication_service.confirm_token(token)
    if not email:
        return render_template("auth/verification_lockscreen.html", show_modal=True, modal_message="The confirmation link is invalid or has expired.")

    user = User.query.filter_by(email=current_user.email).first_or_404()
    if user.email == email:
        user.verify_user()
        try:
            db.session.add(user)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            return render_template("auth/verification_lockscreen.html", show_modal=True, modal_message=f"Error verifying account: {exc}")
        return render_template("auth/verification_success.html")

    return render_template("auth/verification_lockscreen.html", show_modal=True, modal_message="The confirmation link is invalid or has expired.")

@auth_bp.route("/user/upgrade/<int:user_id>", methods=['POST'])
@login_required
def upgrade_user_role(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user.role == UserRole.ADMIN:
        abort(403, description="Unauthorized")  
    try:
        authentication_service.upgrade_user_role(user)
        msg = f"User {user.email} upgraded to role {user.role.value}"
        return jsonify({"message": msg}), 200
    except Exception as exc:
        logger.exception(f"Exception while upgrading user role {exc}")
        return jsonify({"Exception while upgrading user role: ": str(exc)}), 400


@auth_bp.route("/user/downgrade/<int:user_id>", methods=['POST'])
@login_required
def downgrade_user_role(user_id):
    user = User.query.get_or_404(user_id)

    if not current_user.role == UserRole.ADMIN:
        abort(403, description="Unauthorized")  
    try:
        authentication_service.downgrade_user_role(user)
        msg = f"User {user.email} downgraded to role {user.role.value}"
        return jsonify({"message": msg}), 200
    except Exception as exc:
        logger.exception(f"Exception while downgrading user role {exc}")
        return jsonify({"Exception while downgrading user role: ": str(exc)}), 400


@auth_bp.route("/users", methods=["GET"])
@login_required
def list_all_users():
    if current_user.role != UserRole.ADMIN:
        abort(403)
    users = User.query.all()
    return render_template("auth/list_users.html", users=users)


@auth_bp.route("/user/delete/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if current_user.role != UserRole.ADMIN:
        abort(403, description="Unauthorized")
    try:
        authentication_service.delete_user(user)
        return jsonify({"message": f"User {user.email} deleted"}), 200
    except Exception as exc:
        logger.exception(f"Exception while deleting user {exc}")
        return jsonify({"Exception while deleting user: ": str(exc)}), 400
