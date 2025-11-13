from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import fake, get_csrf_token


class ExploreBehavior(TaskSet):
    def on_start(self):
        # simple get to explore page
        self.client.get("/explore")

    @task(3)
    def simple_search(self):
        resp = self.client.get("/explore")
        csrf = get_csrf_token(resp)
        payload = {"query": "steam", "sorting": "newest", "csrf_token": csrf}
        r = self.client.post("/explore", json=payload)
        if r.status_code != 200:
            print(f"Explore search failed: {r.status_code}")

    @task(1)
    def advanced_search_tags_and_author(self):
        resp = self.client.get("/explore")
        csrf = get_csrf_token(resp)
        payload = {
            "query": "",
            "author": fake.name(),
            "tags": ",".join(fake.words(nb=2)),
            "min_downloads": fake.random_int(0, 10),
            "min_views": fake.random_int(0, 100),
            "csrf_token": csrf
        }
        r = self.client.post("/explore", json=payload)
        if r.status_code != 200:
            r.failure(f"Explore advanced search failed: {r.status_code}")


class ExploreUser(HttpUser):
    tasks = [ExploreBehavior]
    min_wait = 3000
    max_wait = 7000
    host = get_host_for_locust_testing()
