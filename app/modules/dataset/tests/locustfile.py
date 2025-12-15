import os
import re

from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token
import json

# Adjust to a valid path in your environment
locust_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(locust_file_dir, ".."))
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

        headers = {"X-CSRFToken": csrf_token}
        with open(CSV_FILE_PATH, "rb") as csv_file:
            files = {"file": csv_file}
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

    @task(10)
    def get_user_metrics_from_index(self):
        print("Executing metrics task")
        """Accede a / y parsea métricas del usuario si está autenticado"""
        response = self.client.get("/")
        if response.status_code != 200:
            print("Failed to access index:", response.text)
            return

        html = response.text

        # Ejemplo usando regex para extraer métricas
        uploaded = re.search(r'Uploaded Datasets:\s*(\d+)', html)
        downloads = re.search(r'Downloads:\s*(\d+)', html)
        syncs = re.search(r'Synchronizations:\s*(\d+)', html)

        if uploaded and downloads and syncs:
            metrics = {
                "uploaded_datasets": int(uploaded.group(1)),
                "downloads": int(downloads.group(1)),
                "synchronizations": int(syncs.group(1)),
            }
            print("User metrics:", metrics)
        else:
            print("Metrics not found in index page.")

    @task(5)
    def get_report_page(self):
        """Load the report page for a dataset (renders a form)."""
        # Use dataset id 1 as an example; adjust if your test DB differs
        response = self.client.get("/dataset/report/1")
        if response.status_code != 200:
            print("/dataset/report/1 returned", response.status_code)

    @task(3)
    def list_issues(self):
        """Hit the admin issues listing endpoint."""
        response = self.client.get("/dataset/issues")
        if response.status_code != 200:
            print("GET /dataset/issues returned", response.status_code)

    @task(8)
    def create_issue(self):
        """POST a JSON issue payload to create an issue (curator-only normally)."""
        # fetch CSRF token from report page (or list) to be safe
        resp = self.client.get("/dataset/report/1")
        csrf = get_csrf_token(resp)
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers["X-CSRFToken"] = csrf

        payload = {"dataset_id": 1, "description": "Load test issue"}
        r = self.client.post("/dataset/issues", data=json.dumps(payload), headers=headers)
        if r.status_code not in (200, 201):
            print("POST /dataset/issues returned", r.status_code, r.text[:200])

    @task(2)
    def open_issue(self):
        """Toggle (open/close) an issue by id using PUT. Uses issue id 1 as example."""
        # Try to get CSRF token
        resp = self.client.get("/dataset/issues")
        csrf = get_csrf_token(resp)
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers["X-CSRFToken"] = csrf

        r = self.client.put(f"/dataset/issues/open/1/", headers=headers)
        if r.status_code != 200:
            print("PUT /dataset/issues/open/1 returned", r.status_code)



class DatasetUser(HttpUser):
    tasks = [DatasetBehavior]
    host = get_host_for_locust_testing()
