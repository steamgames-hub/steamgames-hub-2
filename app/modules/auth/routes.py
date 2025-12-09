import logging

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from app import db
from app.modules.auth import auth_bp
from app.modules.auth.forms import LoginForm, SignupForm, TwoFactorForm
from app.modules.auth.models import User, UserRole
from app.modules.auth.services import authentication_service  # ✅ importamos la instancia global
from app.modules.profile.services import UserProfileService

user_profile_service = UserProfileService()

logger = logging.getLogger(__name__)


# -------------------------------------
# LOGIN
# -------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = LoginForm()

    if form.validate_on_submit():
        user = authentication_service.login(form.email.data, form.password.data)
        if user:
            if not user.verified:
                session["email"] = form.email.data
                session["password"] = form.password.data
                send_verification_email(email=form.email.data)
                return render_template(
                    "auth/verification_lockscreen.html",
                    show_modal=True,
                    modal_message=(
                        "A verification email has been sent to your address. "
                        "Make sure to check your spam folder before resending the email."
                    ),
                )
            else:
                if current_app.config.get("TWO_FACTOR_ENABLED", True):
                    return redirect(url_for("auth.two_factor", user_id=user.id))
                else:
                    return redirect(url_for("public.index"))
        else:
            return render_template("auth/login_form.html", form=form, error="Credenciales inválidas")

    return render_template("auth/login_form.html", form=form)


# -------------------------------------
# SIGNUP
# -------------------------------------
@auth_bp.route("/signup/", methods=["GET", "POST"])
def show_signup_form():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data
        session["email"] = email
        if not authentication_service.is_email_available(email):
            return render_template("auth/signup_form.html", form=form, error=f"Email {email} en uso")

        try:
            authentication_service.create_with_profile(**form.data)
        except Exception as exc:
            msg = f"Error creando usuario: {exc}"
            return render_template("auth/signup_form.html", form=form, error=msg)

        send_verification_email(email=email)
        return render_template(
            "auth/verification_lockscreen.html",
            show_modal=True,
            modal_message=(
                "Se ha enviado un correo electrónico de verificación a tu dirección. "
                "Asegúrate de revisar tu carpeta de correo no deseado antes de reenviarlo."
            ),
        )

    return render_template("auth/signup_form.html", form=form)


# -------------------------------------
# TWO-FACTOR AUTH
# -------------------------------------
@auth_bp.route("/two-factor/<int:user_id>", methods=["GET", "POST"])
def two_factor(user_id):
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("auth.login"))

    form = TwoFactorForm()

    if form.validate_on_submit():
        if authentication_service.verify_2fa(user, form.code.data):
            return redirect(url_for("public.index"))
        return render_template("auth/two_factor_form.html", form=form, error="Código inválido o expirado")

    return render_template("auth/two_factor_form.html", form=form)


# -------------------------------------
# LOGOUT
# -------------------------------------
@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("public.index"))


# -------------------------------------
# EMAIL VERIFICATION
# -------------------------------------
@auth_bp.route("/verify", methods=["GET", "POST"])
def send_verification_email(email=None):
    if email is None:
        email = session.get("email")

    try:
        authentication_service.send_verification_email(email)
    except Exception as exc:
        logger.exception(f"Exception while sending verification email: {exc}")
        return render_template(
            "auth/verification_lockscreen.html",
            show_modal=True,
            modal_message="Error sending verification email, please, try again later.",
        )

    return render_template(
        "auth/verification_lockscreen.html",
        show_modal=True,
        modal_message=(
            "A verification email has been sent to your address. "
            "Make sure to check your spam folder before resending the email."
        ),
    )


@auth_bp.route("/verify/<path:token>", methods=["GET", "POST"])
def verify(token):
    email = authentication_service.confirm_token(token)
    if not email:
        return render_template(
            "auth/verification_lockscreen.html",
            show_modal=True,
            modal_message="The confirmation link is invalid or has expired.",
        )

    user = User.query.filter_by(email=session.get("email")).first_or_404()
    if user.email == email:
        user.verify_user()
        try:
            db.session.add(user)
            db.session.commit()
            session.clear()
        except Exception as exc:
            db.session.rollback()
            return render_template(
                "auth/verification_lockscreen.html", show_modal=True, modal_message=f"Error verifying account: {exc}"
            )

        next_url = url_for("public.index")
        if current_app.config.get("TWO_FACTOR_ENABLED", True):
            authentication_service.generate_2fa(
                user=user
            )  # Generamos el doble factor para mejorar la experiencia de usuario
            next_url = url_for("auth.two_factor", user_id=user.id)
        return render_template("auth/verification_success.html", url=next_url)

    return render_template(
        "auth/verification_lockscreen.html",
        show_modal=True,
        modal_message="The confirmation link is invalid or has expired.",
    )


# -------------------------------------
# USER MANAGEMENT
# -------------------------------------
@auth_bp.route("/user/upgrade/<int:user_id>", methods=["POST"])
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


@auth_bp.route("/user/downgrade/<int:user_id>", methods=["POST"])
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


# -------------------------------------
# PASSWORD RESET
# -------------------------------------
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        authentication_service.generate_reset_token(email)
        flash("Si el email existe, se ha enviado un enlace de recuperación.", "info")
        return render_template("auth/forgot_password.html")
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password_form():
    token = request.args.get("token") or request.form.get("token")

    if request.method == "GET":
        if not authentication_service.validate_reset_token(token):
            return render_template("auth/reset_invalid.html"), 400
        return render_template("auth/reset_password.html", token=token)

    new_password = request.form.get("password")
    confirm = request.form.get("confirm")

    if new_password != confirm:
        flash("Las contraseñas no coinciden.", "error")
        return render_template("auth/reset_password.html", token=token)

    if authentication_service.consume_reset_token(token, new_password):
        flash("Contraseña actualizada correctamente. Inicia sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_invalid.html"), 400
