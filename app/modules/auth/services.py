import os
from flask import current_app, render_template, url_for
from itsdangerous import URLSafeTimedSerializer

from flask_login import current_user, login_user

from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository
from app.modules.profile.models import UserProfile
from app.modules.profile.repositories import UserProfileRepository
from app.modules.dataset.models import DataSet
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail



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

    # Token auxiliary functions
    def generate_token(self, email):
        serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY"))
        return serializer.dumps(email, salt=os.getenv("SECURITY_PASSWORD_SALT"))


    def confirm_token(self, token, expiration=3600):
        serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY"))
        try:
            email = serializer.loads(
                token, salt=os.getenv("SECURITY_PASSWORD_SALT"), max_age=expiration
            )
            return email
        except Exception:
            return False
        
    # Verification email sending
    def send_verification_email(self, email):
        token = self.generate_token(email)
        confirm_url = url_for("auth.verify", token=token, _external=True)
        html = render_template("auth/verification_email.html", confirm_url=confirm_url)
        subject = "Please confirm your email"

        self.send_email(email, subject, html)
    
    def send_email(self, email, subject, html):
        app = current_app._get_current_object()
        sg_api_key = os.environ.get("SENDGRID_API_KEY")
        from_email = os.environ.get("MAIL_USER")

        if not sg_api_key or not from_email:
            raise RuntimeError("SENDGRID_API_KEY o MAIL_USER no configuradas")

        message = Mail(
            from_email=from_email,
            to_emails=email,
            subject=subject,
            html_content=html
        )

        try:
            sg = SendGridAPIClient(sg_api_key)
            response = sg.send(message)
            app.logger.info(f"Correo enviado a {email} | Status: {response.status_code}")
        except Exception as e:
            app.logger.exception(f"Error enviando correo vía SendGrid: {e}")
            raise