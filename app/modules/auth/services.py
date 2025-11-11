import os
from flask_mail import Message
from flask_login import current_user, login_user
from flask import url_for
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from app import mail, db
from app.modules.auth.models import User, PasswordResetToken
from app.modules.auth.repositories import UserRepository
from app.modules.profile.models import UserProfile
from app.modules.profile.repositories import UserProfileRepository
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService
from werkzeug.security import generate_password_hash

class AuthenticationService(BaseService):
    def __init__(self):
        super().__init__(UserRepository())
        self.user_profile_repository = UserProfileRepository()

    def login(self, email, password, remember=True):
        user = self.repository.get_by_email(email)
        if user is not None and user.check_password(password):
            login_user(user, remember=remember)
            return True
        return False

    def is_email_available(self, email: str) -> bool:
        return self.repository.get_by_email(email) is None

    def create_with_profile(self, **kwargs):
        try:
            email = kwargs.pop("email", None)
            password = kwargs.pop("password", None)
            name = kwargs.pop("name", None)
            surname = kwargs.pop("surname", None)

            if not email:
                raise ValueError("Email is required.")
            if not password:
                raise ValueError("Password is required.")
            if not name:
                raise ValueError("Name is required.")
            if not surname:
                raise ValueError("Surname is required.")

            user_data = {"email": email, "password": password}

            profile_data = {
                "name": name,
                "surname": surname,
            }

            user = self.create(commit=False, **user_data)
            profile_data["user_id"] = user.id
            self.user_profile_repository.create(**profile_data)
            self.repository.session.commit()
        except Exception as exc:
            self.repository.session.rollback()
            raise exc
        return user

    def update_profile(self, user_profile_id, form):
        if form.validate():
            updated_instance = self.update(user_profile_id, **form.data)
            return updated_instance, None

        return None, form.errors

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

    def _hash_token(self,raw: str):
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def generate_reset_token(self,email: str, ttl_minutes: int = 15):
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
            subject="Reset your password",
            body=f"Use this link to reset your password: {reset_link}"
        )
    def send_email(self,to: str, subject: str, body: str):
        msg = Message(subject, recipients=[to], body=body)
        mail.send(msg)

    def validate_reset_token(self,raw_token: str):
        hashed = self._hash_token(raw_token)
        token = PasswordResetToken.query.filter_by(token_hash=hashed).first()
        if not token or token.is_expired or token.is_used:
            return None
        return token

    def consume_reset_token(self,raw_token: str, new_password: str):
        token = self.validate_reset_token(raw_token)
        if not token:
            return False
        token.user.password = generate_password_hash(new_password)
        token.mark_used()
        db.session.commit()
        return True