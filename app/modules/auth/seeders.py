from app.modules.auth.models import User, UserRole
from datetime import datetime, timedelta
from app.modules.profile.models import UserProfile
from core.seeders.BaseSeeder import BaseSeeder


class AuthSeeder(BaseSeeder):

    priority = 1  # Higher priority

    def run(self):

        # Seeding users
        users = [
            User(email="user1@yopmail.com", password="1234", role=UserRole.ADMIN, verified=True),
            User(email="user2@yopmail.com", password="1234", role=UserRole.CURATOR, verified=True),
            User(email="user3@yopmail.com", password="1234", verified=True)
        ]

        # Inserted users with their assigned IDs are returned by `self.seed`.
        seeded_users = self.seed(users)

        # Create profiles for each user inserted.
        user_profiles = []
        users_profile = [("John", "Doe", False), ("Jane", "Doe", True), ("Juliet", "Doe", True)]

        for user, profile in zip(seeded_users, users_profile):
            profile_data = {
                "user_id": user.id,
                "orcid": "",
                "affiliation": "Some University",
                "name": profile[0],
                "surname": profile[1],
                "save_drafts": profile[2],
            }
            user_profile = UserProfile(**profile_data)
            user_profiles.append(user_profile)

            # Código 2FA de prueba
            user.two_factor_code = "123456"
            user.two_factor_expires_at = datetime.utcnow() + timedelta(minutes=5)
            user.two_factor_verified = False

        # 3️⃣ Seeding user profiles
        self.seed(user_profiles)

