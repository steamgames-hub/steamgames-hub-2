from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user, login_required

from app.modules.auth import auth_bp
from app.modules.auth.forms import LoginForm, SignupForm
from app.modules.auth.services import AuthenticationService
from app.modules.profile.services import UserProfileService
from app.modules.auth.mail_util.token import confirm_token, generate_token
from app.modules.auth.mail import send_email
from app.modules.auth.models import User
from app import db

authentication_service = AuthenticationService()
user_profile_service = UserProfileService()


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
        return render_template("auth/verification_lockscreen.html", show_modal=True, modal_message="A verification email has been sent to your address.")

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


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("public.index"))

@auth_bp.route("/verify", methods=['GET', 'POST'])
@login_required
def send_verification_email(email=None):
    if email is None:
        email = current_user.email

    token = generate_token(email)
    confirm_url = url_for("auth.verify", token=token, _external=True)
    html = render_template("auth/verification_email.html", confirm_url=confirm_url)
    subject = "Please confirm your email"

    send_email(email, subject, html)
    return render_template("auth/verification_lockscreen.html", show_modal=True, modal_message="A verification email has been sent to your address.")
    
@auth_bp.route("/verify/<token>", methods=['GET', 'POST'])
@login_required
def verify(token):
    if current_user.verified:
        return redirect(url_for("public.index"))
    email = confirm_token(token)
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

def redirect_checks_verified(url, verified):
    if verified:
        return redirect(url)
    else:
        return render_template("auth/verification_lockscreen.html")