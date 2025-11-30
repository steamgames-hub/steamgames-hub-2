from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Enum as SQLAlchemyEnum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class UserRole(Enum):
    ADMIN = "admin"
    CURATOR = "curator"
    USER = "user"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    verified = db.Column(db.Boolean, nullable=False, default=False)
    role = db.Column(SQLAlchemyEnum(UserRole), default=UserRole.USER)

    data_sets = db.relationship("DataSet", backref="user", lazy=True)
    profile = db.relationship("UserProfile", backref="user", uselist=False)

    two_factor_code = db.Column(db.String(6), nullable=True)
    two_factor_expires_at = db.Column(db.DateTime, nullable=True)
    two_factor_verified = db.Column(db.Boolean, default=False)

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if "password" in kwargs:
            self.set_password(kwargs["password"])
            
        if "verified" in kwargs:
            self.verified = kwargs["verified"]

    def __repr__(self):
        return f"<User {self.email}>"

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def temp_folder(self) -> str:
        from app.modules.auth.services import AuthenticationService

        return AuthenticationService().temp_folder_by_user(self)
    
    def verify_user(self):
        self.verified = True

    def get_next_role(self):
        if self.role == UserRole.USER:
            return UserRole.CURATOR
        elif self.role == UserRole.CURATOR:
            return UserRole.ADMIN
        return self.role
    
    def get_previous_role(self):
        if self.role == UserRole.ADMIN:
            return UserRole.CURATOR
        elif self.role == UserRole.CURATOR:
            return UserRole.USER
        return self.role

class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token_hash = db.Column(db.String(256), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="password_reset_tokens")

    @property
    def is_expired(self):
         return datetime.utcnow() > self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    def mark_used(self):
        self.used_at = datetime.now(timezone.utc)
