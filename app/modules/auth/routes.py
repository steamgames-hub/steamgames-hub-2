from flask import render_template, redirect, url_for, request
from app.modules.auth.models import User

from flask_login import current_user, logout_user, login_user
from app.modules.auth.forms import LoginForm
from app.modules.auth.services import AuthenticationService
from app.modules.auth.forms import TwoFactorForm
from app.modules.auth import auth_bp


auth_service = AuthenticationService()

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.index"))

    form = LoginForm()  # <-- Crear el formulario

    if form.validate_on_submit():
        user = auth_service.login(form.email.data, form.password.data)
        if user:
            # Redirigir a 2FA
            return redirect(url_for("auth.two_factor", user_id=user.id))
        return render_template("auth/login_form.html", form=form, error="Credenciales inválidas")

    return render_template("auth/login_form.html", form=form)  # <-- Pasar el form


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

        # Log user
        login_user(user, remember=True)
        return redirect(url_for("public.index"))

    return render_template("auth/signup_form.html", form=form)




@auth_bp.route("/two-factor/<int:user_id>", methods=["GET", "POST"])
def two_factor(user_id):
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("auth.login"))

    form = TwoFactorForm()  # <-- Crear instancia del formulario

    if form.validate_on_submit():
        if auth_service.verify_2fa(user, form.code.data):
            return redirect(url_for("public.index"))
        return render_template("auth/two_factor_form.html", form=form, error="Código inválido o expirado")

    return render_template("auth/two_factor_form.html", form=form)  # <-- Pasar form



@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("public.index"))

