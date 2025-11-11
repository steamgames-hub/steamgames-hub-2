import os

from flask_login import current_user, login_user

from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository
from app.modules.dataset.models import DataSet
from app.modules.profile.models import UserProfile
from app.modules.profile.repositories import UserProfileRepository
from core.configuration.configuration import uploads_folder_name
from core.services.BaseService import BaseService


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
