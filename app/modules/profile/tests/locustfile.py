import os
import re

from locust import HttpUser, TaskSet, task

from app import create_app, db
from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token

# Adjust to a valid path in your environment
app = create_app(os.getenv("FLASK_ENV", "testing"))
app.app_context().push()


class ProfilePreferencesBehaviour(TaskSet):

    def on_start(self):
        # Simulate login if necessary before accessing protected endpoints
        self.login()

    def login(self):
        """Simulate login to get session and cookies"""

        response = self.client.get("/login")
        csrf_token = get_csrf_token(response)
        payload = {
            "email": "testuser@example.com",
            "password": "testpassword",
            "csrf_token": csrf_token,
        }
        r = self.client.post("/login", data=payload)
        if r.status_code != 200:
            print("Error during login:", r.status_code, r.text)
    

    @task
    def change_save_draft_preference(self):
        """Change and save the 'save draft' preference in user profile"""

        response = self.client.put("/profile/save_drafts")
        get_csrf_token(response)
    
    @task
    def edit_profile_task(self):
        """Load edit profile form and submit updated profile data"""
        user_id = 1
        edit_get = self.client.get(f"/profile/edit/{user_id}")
        if edit_get.status_code != 200:
            print("Failed to load edit profile page", edit_get.status_code)
            return

        csrf = get_csrf_token(edit_get)
        payload = {
            "name": "Locust",
            "surname": "Tester",
            "affiliation": "Load Testing Org",
            "csrf_token": csrf,
        }
        edit_post = self.client.post(f"/profile/edit/{user_id}", data=payload, allow_redirects=True)
        if edit_post.status_code not in (200, 302):
            print("Edit profile submit failed", edit_post.status_code, edit_post.text)
    
class ProfileUser(HttpUser):
    tasks = [ProfilePreferencesBehaviour]
    host = get_host_for_locust_testing()