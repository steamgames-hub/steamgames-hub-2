import os

from locust import HttpUser, TaskSet, task

from app import create_app, db
from app.modules.auth.models import User
from core.environment.host import get_host_for_locust_testing
from core.locust.common import fake, get_csrf_token

app = create_app(os.getenv("FLASK_ENV", "testing"))
app.app_context().push()


class SignupBehavior(TaskSet):
    def on_start(self):
        self.signup()

    @task
    def signup(self):
        response = self.client.get("/signup")
        csrf_token = get_csrf_token(response)

        response = self.client.post(
            "/signup", data={"email": fake.email(), "password": fake.password(), "csrf_token": csrf_token}
        )
        if response.status_code != 200:
            print(f"Signup failed: {response.status_code}")


class LoginBehavior(TaskSet):
    def on_start(self):
        self.ensure_logged_out()
        self.login_with_2fa()

    @task
    def ensure_logged_out(self):
        self.client.get("/logout")

    @task
    def login_with_2fa(self):
        response = self.client.get("/login")
        csrf_token = get_csrf_token(response)
        response = self.client.post(
            "/login",
            data={"email": "user1@yopmail.com", "password": "1234", "csrf_token": csrf_token},
            allow_redirects=False,
        )
        location = response.headers.get("Location", "")
        if "/two-factor/" in location:
            user_id = location.split("/two-factor/")[1]
            user = db.session.get(User, int(user_id))
            code = user.two_factor_code
            self.client.post(f"/two-factor/{user_id}", data={"code": code}, allow_redirects=True)

    @task
    def check_profile(self):
        self.client.get("/profile/summary")


class AuthUser(HttpUser):
    tasks = [SignupBehavior, LoginBehavior]
    min_wait = 5000
    max_wait = 9000
    host = get_host_for_locust_testing()
