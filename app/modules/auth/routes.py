from flask import redirect, render_template, request, url_for, flash
from flask_login import current_user, login_user, logout_user

from app.modules.auth import auth_bp
from app.modules.auth.forms import LoginForm, SignupForm, TwoFactorForm
from app.modules.auth.models import User
from app.modules.auth.services import authentication_service  # ✅ importamos la instancia global

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
            return redirect(url_for("auth.two_factor", user_id=user.id))
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
        if not authentication_service.is_email_available(email):
            return render_template("auth/signup_form.html", form=form, error=f"Email {email} en uso")

        try:
            user = authentication_service.create_with_profile(**form.data)
        except Exception as exc:
            return render_template("auth/signup_form.html", form=form, error=f"Error creando usuario: {exc}")

        login_user(user, remember=True)
        return redirect(url_for("public.index"))

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
