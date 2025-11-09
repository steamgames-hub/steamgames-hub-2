from datetime import datetime, timedelta
from app.modules.auth.models import User
from app.modules.profile.models import UserProfile
from core.seeders.BaseSeeder import BaseSeeder


class AuthSeeder(BaseSeeder):

    priority = 1  # Higher priority

    def run(self):
        # 1️⃣ Seeding users
        users = [
            User(email="user1@yopmail.com", password="1234"),
            User(email="user2@yopmail.com", password="1234"),
        ]

        # Insert users and get the saved objects with IDs
        seeded_users = self.seed(users)

        # 2️⃣ Crear perfiles y asignar código 2FA de prueba
        user_profiles = []
        names = [("John", "Doe"), ("Jane", "Doe")]

        for user, name in zip(seeded_users, names):
            # Perfil
            profile_data = {
                "user_id": user.id,
                "orcid": "",
                "affiliation": "Some University",
                "name": name[0],
                "surname": name[1],
            }
            user_profile = UserProfile(**profile_data)
            user_profiles.append(user_profile)

            # Código 2FA de prueba
            user.two_factor_code = "123456"
            user.two_factor_expires_at = datetime.utcnow() + timedelta(minutes=5)
            user.two_factor_verified = False

        # 3️⃣ Seeding user profiles
        self.seed(user_profiles)

