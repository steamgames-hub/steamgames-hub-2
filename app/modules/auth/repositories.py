from app.modules.auth.models import User
from core.repositories.BaseRepository import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__(User)

    def get_by_email(self, email: str):
        return self.model.query.filter_by(email=email).first()
