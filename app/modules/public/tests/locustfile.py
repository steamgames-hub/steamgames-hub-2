from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing


class PublicBehavior(TaskSet):
    def on_start(self):
        # Warm up cache and CDN layers by loading the landing page once per user
        self.client.get("/")

    @task(3)
    def homepage_latest_and_trending(self):
        response = self.client.get("/")
        if response.status_code != 200:
            response.failure("Landing page returned unexpected status")

    @task(2)
    def trending_views_week(self):
        response = self.client.get("/trending_datasets", params={"by": "views", "period": "week", "limit": 5})
        if response.status_code != 200:
            response.failure("Trending views endpoint failed")

    @task(1)
    def trending_downloads_month(self):
        response = self.client.get("/trending_datasets", params={"by": "downloads", "period": "month", "limit": 5})
        if response.status_code != 200:
            response.failure("Trending downloads endpoint failed")


class PublicUser(HttpUser):
    tasks = [PublicBehavior]
    min_wait = 2000
    max_wait = 5000
    host = get_host_for_locust_testing()
