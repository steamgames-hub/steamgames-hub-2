from flask import render_template, redirect, url_for, request
from flask_login import current_user, login_user
from datetime import datetime, timedelta
import random

from core.blueprints.base_blueprint import BaseBlueprint
from app.modules.auth.forms import LoginForm, SignupForm, TwoFactorForm
from app.modules.auth.models import User
from app import db, mail
from flask_mail import Message

auth_bp = BaseBlueprint("auth", __name__, template_folder="templates")

# Servicio de autenticación simplificado
class AuthenticationService:
    def is_email_available(self, email):
        return User.query.filter_by(email=email).first() is None

    def create_with_profile(self, name, surname, email, password, **kwargs):
        user = User(name=name, surname=surname, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    def login(self, email, password):
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            self.generate_2fa(user)
            return user
        return None

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

authentication_service = AuthenticationService()
