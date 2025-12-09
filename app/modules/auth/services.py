import hashlib
import os
import random
import secrets
from datetime import datetime, timedelta
from threading import Thread

from flask import current_app, render_template, url_for
from flask_login import current_user, login_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from werkzeug.security import generate_password_hash

from app import db, mail
from app.modules.auth.models import PasswordResetToken, User
from app.modules.auth.repositories import UserRepository
from app.modules.dataset.models import DataSet
from app.modules.profile.models import UserProfile
from app.modules.profile.repositories import UserProfileRepository
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService


class AuthenticationService(BaseService):
    def __init__(self):
        self.repository = UserRepository()
        self.user_profile_repository = UserProfileRepository()

    # --- Registro y verificación de email ---
    def is_email_available(self, email: str) -> bool:
        return self.repository.get_by_email(email) is None

    def create_with_profile(self, **kwargs):
        name = kwargs.pop("name", None)
        surname = kwargs.pop("surname", None)
        email = kwargs.pop("email", None)
        password = kwargs.pop("password", None)

        if not email:
            raise ValueError("Email is required.")
        if not password:
            raise ValueError("Password is required.")
        if not name:
            raise ValueError("Name is required.")
        if not surname:
            raise ValueError("Surname is required.")

        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()

        profile = UserProfile(user_id=user.id, name=name, surname=surname)
        db.session.add(profile)
        db.session.commit()
        return user

    # --- Login y 2FA ---
    def login(self, email, password):
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if current_app.config.get("TWO_FACTOR_ENABLED", True):
                self.generate_2fa(user)
            else:
                login_user(user)
            return user
        return None

    def generate_2fa(self, user):
        code = f"{random.randint(0, 999999):06d}"
        user.two_factor_code = code
        user.two_factor_expires_at = datetime.utcnow() + timedelta(minutes=5)
        db.session.commit()

        body = render_template("auth/two_factor_email.html", code=code)
        self.send_email(user.email, "Código 2FA", body)

    def verify_2fa(self, user, code):
        if user.two_factor_code == code and datetime.utcnow() < user.two_factor_expires_at:
            login_user(user)
            return True
        return False

    # --- Editar perdil ---
    def update_profile(self, user_profile_id, form):
        if form.validate():
            updated_instance = self.update(user_profile_id, **form.data)
            return updated_instance, None

        return None, form.errors

    # --- Perfil y sesión ---
    def get_authenticated_user(self) -> User | None:
        return current_user if current_user.is_authenticated else None

    def get_authenticated_user_profile(self) -> UserProfile | None:
        return current_user.profile if current_user.is_authenticated else None

    def temp_folder_by_user(self, user: User) -> str:
        return os.path.join(uploads_folder_name(), "temp", str(user.id))

    # --- Reset de contraseña ---
    def _hash_token(self, raw: str):
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def generate_reset_token(self, email: str, ttl_minutes: int = 15):
        user = self.repository.get_by_email(email)
        if not user:
            return
        raw_token = secrets.token_urlsafe(48)
        hashed = self._hash_token(raw_token)
        token = PasswordResetToken(
            user_id=user.id, token_hash=hashed, expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes)
        )
        db.session.add(token)
        db.session.commit()
        reset_link = url_for("auth.reset_password_form", token=raw_token, _external=True)
        body = f"Usa este enlace para restablecer tu contraseña: {reset_link}"
        self.send_email(user.email, "Restablecer contraseña", body)

    def validate_reset_token(self, raw_token: str):
        hashed = self._hash_token(raw_token)
        token = PasswordResetToken.query.filter_by(token_hash=hashed).first()
        if not token or token.is_expired or token.is_used:
            return None
        return token

    def consume_reset_token(self, raw_token: str, new_password: str):
        token = self.validate_reset_token(raw_token)
        if not token:
            return False
        token.user.password = generate_password_hash(new_password)
        token.mark_used()
        db.session.commit()
        return True

    # --- Verificación de email ---
    def generate_token(self, email):
        secret_key = current_app.config.get("SECRET_KEY")
        salt = current_app.config.get("SECURITY_PASSWORD_SALT")

        if not secret_key or not salt:
            raise RuntimeError("SECRET_KEY o SECURITY_PASSWORD_SALT no configuradas")

        serializer = URLSafeTimedSerializer(secret_key)
        return serializer.dumps(email, salt=salt)

    def confirm_token(self, token, expiration=3600):
        secret_key = current_app.config.get("SECRET_KEY")
        salt = current_app.config.get("SECURITY_PASSWORD_SALT")

        if not secret_key or not salt:
            raise RuntimeError("SECRET_KEY o SECURITY_PASSWORD_SALT no configuradas")

        serializer = URLSafeTimedSerializer(secret_key)
        try:
            email = serializer.loads(token, salt=salt, max_age=expiration)
            return email
        except Exception:
            return False

    def send_verification_email(self, email):
        token = self.generate_token(email)
        confirm_url = url_for("auth.verify", token=token, _external=True)
        html = render_template("auth/verification_email.html", confirm_url=confirm_url)
        subject = "SteamGames Hub: Please confirm your email"

        self.send_email(to=email, subject=subject, body=html)

    # --- Envío de correo con SendGrid ---
    def _send_via_sendgrid(self, to: str, subject: str, body: str):
        app = current_app._get_current_object()
        sg_api_key = app.config.get("SENDGRID_API_KEY")
        from_email = app.config.get("FROM_EMAIL") or app.config.get("MAIL_DEFAULT_SENDER")

        if not sg_api_key or not from_email:
            raise RuntimeError("SENDGRID_API_KEY o FROM_EMAIL no configuradas")

        message = Mail(from_email=from_email, to_emails=to, subject=subject, html_content=body)

        try:
            sg = SendGridAPIClient(sg_api_key)
            response = sg.send(message)
            app.logger.info(f"Correo enviado a {to} | Status: {response.status_code}")
        except Exception as e:
            app.logger.exception(f"Error enviando correo vía SendGrid: {e}")
            raise

    def send_email(self, to: str, subject: str, body: str):
        """
        Envía el correo en un Thread.
        Usa SendGrid si hay API key, o Flask-Mail si no.
        """
        app = current_app._get_current_object()

        def _send():
            with app.app_context():
                try:
                    if app.config.get("SENDGRID_API_KEY"):
                        self._send_via_sendgrid(to, subject, body)
                    else:
                        msg = Message(subject, recipients=[to], body=body)
                        mail.send(msg)
                except Exception as e:
                    app.logger.exception(f"Fallo al enviar correo a {to}: {e}")

        Thread(target=_send, daemon=True).start()

    # --- Gestión de roles ---
    def get_profile_by_user_id(self, user_id: int) -> UserProfile | None:
        user = self.repository.get_by_id(user_id)
        if user:
            return user.profile
        return None

    def upgrade_user_role(self, user: User):
        user.role = user.get_next_role()
        self.repository.session.add(user)
        self.repository.session.commit()

    def downgrade_user_role(self, user: User):
        user.role = user.get_previous_role()
        self.repository.session.add(user)
        self.repository.session.commit()

    def delete_user(self, user: User):
        # Borrar datasets y perfil del usuario antes de borrar el usuario
        datasets = self.repository.session.query(DataSet).filter_by(user_id=user.id).all()
        for ds in datasets:
            self.repository.session.delete(ds)
        profile = self.repository.session.query(UserProfile).filter_by(user_id=user.id).first()
        if profile:
            self.repository.session.delete(profile)
        self.repository.session.delete(user)
        self.repository.session.commit()


authentication_service = AuthenticationService()
