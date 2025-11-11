import os
import random
import secrets
import hashlib
from datetime import datetime, timedelta
from flask import url_for
from flask_mail import Message
from flask_login import current_user, login_user
from werkzeug.security import generate_password_hash
from app import db, mail
from app.modules.auth.models import User, PasswordResetToken
from app.modules.auth.repositories import UserRepository
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
            self.generate_2fa(user)
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

    def send_email(self, to: str, subject: str, body: str):
        msg = Message(subject, recipients=[to], body=body)
        mail.send(msg)

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


authentication_service = AuthenticationService()
