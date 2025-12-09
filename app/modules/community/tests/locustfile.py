import base64
import os
import random
import re

from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import get_csrf_token

# Adjust to a valid path in your environment
locust_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(locust_file_dir, ".."))
ICON_DIR = os.path.join(project_root, "img_examples")
ICON_FILE_PATH = os.path.join(ICON_DIR, "icon.png")

# 1x1 PNG (transparent), base64-encoded to avoid extra deps
PNG_1x1_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAuMBg7zY6y8AAAAASUVORK5CYII="

COMMUNITY_LINK_RE = re.compile(r"/community/(\d+)")


class CommunityBehavior(TaskSet):

    def on_start(self):
        # Simulate login if necessary before accessing protected endpoints
        self.login()
        self._ensure_icon_example()

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

    def _ensure_icon_example(self) -> None:
        """Ensure example icon exists on disk so upload task always has a file."""
        try:
            os.makedirs(ICON_DIR, exist_ok=True)
            if not os.path.exists(ICON_FILE_PATH):
                with open(ICON_FILE_PATH, "wb") as fh:
                    fh.write(base64.b64decode(PNG_1x1_BASE64))
        except Exception as e:
            print(f"Failed to prepare icon example: {e}")

    @task
    def community_list(self):
        """Access the community list page"""

        response = self.client.get("/community")
        get_csrf_token(response)
        if response.status_code != 200:
            print("Error in /community:", response.status_code)

    @task
    def community_view_random(self):
        """Open a random community detail page parsed from the list."""
        listing = self.client.get("/community")
        if listing.status_code != 200:
            return
        ids = [int(m.group(1)) for m in COMMUNITY_LINK_RE.finditer(listing.text)]
        if not ids:
            return
        cid = random.choice(ids)
        self.client.get(f"/community/{cid}")

    @task
    def community_icon_random(self):
        """Fetch a random community icon (404 tolerated)."""
        listing = self.client.get("/community")
        if listing.status_code != 200:
            return
        ids = [int(m.group(1)) for m in COMMUNITY_LINK_RE.finditer(listing.text)]
        if not ids:
            return
        cid = random.choice(ids)
        self.client.get(f"/community/icon/{cid}")

    @task
    def community_create_get(self):
        """Access the community create page"""

        response = self.client.get("/community/create")
        get_csrf_token(response)

    @task
    def community_create_post(self):
        """Create a community with optional icon upload"""

        response = self.client.get("/community/create")
        csrf_token = get_csrf_token(response)

        files = None
        if os.path.exists(ICON_FILE_PATH):
            files = {"icon": open(ICON_FILE_PATH, "rb")}

        data = {
            "name": f"Locust Community {random.randint(1, 1_000_000)}",
            "description": "Load-generated community",
            "csrf_token": csrf_token,
        }
        resp = self.client.post("/community/create", data=data, files=files)
        if files and hasattr(files.get("icon"), "close"):
            files["icon"].close()
        if resp.status_code not in (200, 302):
            print("Community create failed:", resp.status_code, resp.text[:200])

    @task
    def community_mine(self):
        """Access the user's own communities"""

        response = self.client.get("/community/mine")
        get_csrf_token(response)
        if response.status_code != 200:
            print("Error in /community/mine:", response.status_code)

    @task
    def community_propose_best_effort(self):
        """Try to propose a random dataset to a random (preferably own) community."""
        lst = self.client.get("/dataset/list")
        if lst.status_code != 200:
            return
        dataset_links = re.findall(r'href="(/dataset/[^\"]+)"', lst.text)
        if not dataset_links:
            return
        for link in dataset_links[:5]:
            page = self.client.get(link)
            if page.status_code != 200:
                continue
            m_ds = re.search(r'name="dataset_id" value="(\d+)"', page.text)
            m_sel = re.search(r'<select[^>]*name="community_id"[^>]*>(.*?)</select>', page.text, flags=re.S)
            if not (m_ds and m_sel):
                continue
            dataset_id = int(m_ds.group(1))
            option_ids = [int(x) for x in re.findall(r'<option value="(\d+)"', m_sel.group(1))]
            if not option_ids:
                continue
            csrf = None
            try:
                csrf = get_csrf_token(page)
            except Exception:
                pass
            community_id = random.choice(option_ids)
            payload = {"dataset_id": str(dataset_id), "community_id": str(community_id)}
            if csrf:
                payload["csrf_token"] = csrf
            self.client.post("/community/propose", data=payload)
            break

    @task
    def community_accept_or_reject_best_effort(self):
        """As community owner, accept or reject a pending proposal if present."""
        mine = self.client.get("/community/mine")
        if mine.status_code != 200:
            return
        ids = [int(m.group(1)) for m in COMMUNITY_LINK_RE.finditer(mine.text)]
        if not ids:
            return
        cid = random.choice(ids)
        page = self.client.get(f"/community/{cid}")
        if page.status_code != 200:
            return
        m = re.search(rf"/community/{cid}/proposals/(\d+)/(accept|reject)", page.text)
        if not m:
            return
        pid, action = m.group(1), m.group(2)
        csrf = None
        try:
            csrf = get_csrf_token(page)
        except Exception:
            pass
        url = f"/community/{cid}/proposals/{pid}/{action}"
        data = {"csrf_token": csrf} if csrf else None
        self.client.post(url, data=data)


class CommunityUser(HttpUser):
    tasks = [CommunityBehavior]
    host = get_host_for_locust_testing()
