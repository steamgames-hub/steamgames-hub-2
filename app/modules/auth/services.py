import os
import random
import secrets
import hashlib
from datetime import datetime, timedelta
from flask import url_for, current_app
from flask_mail import Message
from flask_login import current_user, login_user
from flask import url_for, current_app
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from app import mail, db
from werkzeug.security import generate_password_hash
from app import db, mail
from app.modules.auth.models import User, PasswordResetToken
from app.modules.auth.repositories import UserRepository
from app.modules.profile.models import UserProfile
from app.modules.profile.repositories import UserProfileRepository
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService
from werkzeug.security import generate_password_hash
from threading import Thread
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class AuthenticationService(BaseService):
    def __init__(self):
        self.repository = UserRepository()
        self.user_profile_repository = UserProfileRepository()

    # --- Registro y verificación de email ---
    def is_email_available(self, email: str) -> bool:
        return self.repository.get_by_email(email) is None

    def create_with_profile(self, **kwargs):
        # Extraemos los campos del perfil
        name = kwargs.pop("name", None)
        surname = kwargs.pop("surname", None)
        email = kwargs.pop("email", None)
        password = kwargs.pop("password", None)

        if not email or not password or not name or not surname:
            raise ValueError("Email, password, name y surname son requeridos.")

        # Creamos el User
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()  # Necesario para que user.id exista

        # Creamos el UserProfile
        profile = UserProfile(user_id=user.id, name=name, surname=surname)
        db.session.add(profile)
        db.session.commit()
        return user


    # --- Login y autenticación ---


    def login(self, email, password):
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if current_app.config.get("TWO_FACTOR_ENABLED", True):
                self.generate_2fa(user)
            else:
                login_user(user)  # login directo en tests
            return user
        return None


    # --- Doble factor ---
    def generate_2fa(self, user):
        code = f"{random.randint(0, 999999):06d}"
        user.two_factor_code = code
        user.two_factor_expires_at = datetime.utcnow() + timedelta(minutes=5)
        db.session.commit()

        msg = Message(
            "Código 2FA",
            recipients=[user.email],
            body=f"Tu código de verificación es: {code}\nVálido por 5 minutos."
        )
        mail.send(msg)

    def verify_2fa(self, user, code):
        if user.two_factor_code == code and datetime.utcnow() < user.two_factor_expires_at:
            login_user(user)
            return True
        return False

    # --- Perfil y sesión ---
    def get_authenticated_user(self) -> User | None:
        if current_user.is_authenticated:
            return current_user
        return None

    def get_authenticated_user_profile(self) -> UserProfile | None:
        if current_user.is_authenticated:
            return current_user.profile
        return None

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
            user_id=user.id,
            token_hash=hashed,
            expires_at=datetime.now() + timedelta(minutes=ttl_minutes)
        )
        db.session.add(token)
        db.session.commit()
        reset_link = url_for("auth.reset_password_form", token=raw_token, _external=True)
        self.send_email(
            to=user.email,
            subject="Restablecer contraseña",
            body=f"Usa este enlace para restablecer tu contraseña: {reset_link}"
        )

    def _send_via_sendgrid(self, to: str, subject: str, body: str):
        app = current_app._get_current_object()  # obtenemos el contexto de Flask para logging
        sg_api_key = os.environ.get("SENDGRID_API_KEY")
        if not sg_api_key:
            raise RuntimeError("SENDGRID_API_KEY no configurada")

        from_email = os.environ.get("FROM_EMAIL")
        message = Mail(
            from_email=from_email,
            to_emails=to,
            subject=subject,
            html_content=body
        )
        try:
            sg = SendGridAPIClient(sg_api_key)
            response = sg.send(message)
            # Log del resultado
            app.logger.info(
                "Correo enviado via SendGrid a %s | Status: %s | Body: %s",
                to, response.status_code, response.body.decode() if response.body else "empty"
            )
            return response.status_code, response.body, response.headers
        except Exception as e:
            app.logger.exception("Error enviando correo vía SendGrid a %s: %s", to, e)
            raise e

    def send_email(self, to: str, subject: str, body: str):
        """
        Envía el correo en un Thread. Si hay SENDGRID_API_KEY usa la API,
        en caso contrario intenta usar el mail (Flask-Mail) para entornos locales.
        """
        app = current_app._get_current_object()

        def _send(app, to, subject, body):
            try:
                with app.app_context():
                    # Prioriza la API de SendGrid si está configurada
                    if os.environ.get("SENDGRID_API_KEY"):
                        try:
                            # llamamos al método de instancia
                            self._send_via_sendgrid(to, subject, body)
                        except Exception as e:
                            app.logger.exception("SendGrid API error: %s", e)
                            # No reintentar por SMTP aquí, solo log
                    else:
                        # fallback a Flask-Mail (p. ej. desarrollo local)
                        msg = Message(subject, recipients=[to], body=body)
                        mail.send(msg)
            except Exception as e:
                app.logger.exception("Error enviando correo de recuperación: %s", e)

        Thread(target=_send, args=(app, to, subject, body), daemon=True).start()

    def validate_reset_token(self, raw_token: str):
    def validate_reset_token(self, raw_token: str):
        hashed = self._hash_token(raw_token)
        token = PasswordResetToken.query.filter_by(token_hash=hashed).first()
        if not token or token.is_expired or token.is_used:
            return None
        return token

    def consume_reset_token(self, raw_token: str, new_password: str):
    def consume_reset_token(self, raw_token: str, new_password: str):
        token = self.validate_reset_token(raw_token)
        if not token:
            return False
        token.user.password = generate_password_hash(new_password)
        token.mark_used()
        db.session.commit()
        return True


authentication_service = AuthenticationService()
