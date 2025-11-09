from app.modules.auth.models import User
from app.modules.profile.models import UserProfile
from core.seeders.BaseSeeder import BaseSeeder


class AuthSeeder(BaseSeeder):

    priority = 1  # Higher priority

    def run(self):

        # Seeding users
        users = [
            User(email="user1@example.com", password="1234", role="admin", verified=True),
            User(email="user2@example.com", password="1234", role="curator", verified=True),
            User(email="user3@example.com", password="1234", verified=True),
            User(email="user4@example.com", password="1234", role="guest", verified=True),
        ]

        # Inserted users with their assigned IDs are returned by `self.seed`.
        seeded_users = self.seed(users)

        # Create profiles for each user inserted.
        user_profiles = []
        users_profile = [("John", "Doe", False), ("Jane", "Doe", True), ("Juliet", "Doe", True), ("Jack", "Doe", False)]

        for user, profile in zip(seeded_users, users_profile):
            profile_data = {
                "user_id": user.id,
                "orcid": "",
                "affiliation": "Some University",
                "name": profile[0],
                "surname": profile[1],
                "save_drafts": profile[2]
            }
            user_profile = UserProfile(**profile_data)
            user_profiles.append(user_profile)

        # Seeding user profiles
        self.seed(user_profiles)
