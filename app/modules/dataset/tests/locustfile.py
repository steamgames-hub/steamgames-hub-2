from locust import HttpUser, TaskSet, task
from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token
import os

# Adjust to a valid path in your environment
locust_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(locust_file_dir, '..'))
CSV_FILE_PATH = os.path.join(project_root, "csv_examples/file1.csv")

class DatasetBehavior(TaskSet):

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
    def dataset_upload_get(self):
        """Access the dataset upload page"""

        response = self.client.get("/dataset/upload")
        get_csrf_token(response)

    @task
    def dataset_file_upload(self):
        """Uploads a CSV file to the /dataset/file/upload endpoint"""

        response = self.client.get("/dataset/upload")
        csrf_token = get_csrf_token(response)

        if not os.path.exists(CSV_FILE_PATH):
            print(f"Test CSV not found at {CSV_FILE_PATH}")
            return

        files = {"file": open(CSV_FILE_PATH, "rb")}
        headers = {"X-CSRFToken": csrf_token}
        response = self.client.post("/dataset/file/upload", files=files, headers=headers)
        if response.status_code != 200:
            print("File upload failed:", response.text)

    @task
    def dataset_clean_temp(self):
        """Cleans the user's temporary directory"""
        
        response = self.client.post("/dataset/file/clean_temp")
        if response.status_code != 200:
            print("Error cleaning temp folder:", response.text)

    @task
    def dataset_list(self):
        """Queries the list of datasets"""
        response = self.client.get("/dataset/list")
        get_csrf_token(response)
        if response.status_code != 200:
            print("Error in /dataset/list:", response.status_code)


class DatasetUser(HttpUser):
    tasks = [DatasetBehavior]
    host = get_host_for_locust_testing()