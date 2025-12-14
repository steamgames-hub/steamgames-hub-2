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
        self.signup_with_verify()
        self.verify_invalid_token()

    @task
    def signup_with_verify(self):
        response = self.client.get("/signup")
        #csrf_token = get_csrf_token(response)

        response = self.client.post(
            "/signup", data={"email": fake.email(), "password": fake.password()}
        )
        if response.status_code != 200:
            print(f"Signup failed: {response.status_code}")
        
        response = self.client.get("/verify")
        if response.status_code != 200:
            print(f"Verification failed: {response.status_code}")
    
    @task
    def verify_invalid_token(self):
        response = self.client.get("/verify/invalid-token")


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
        app = create_app()
        response = self.client.post(
            "/login",
            data={"email": "user1@yopmail.com", "password": "1234"},
            allow_redirects=False,
        )
        location = response.headers.get("Location", "")
        if "/two-factor/" in location:
            user_id = location.split("/two-factor/")[1]
            with app.app_context():
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
