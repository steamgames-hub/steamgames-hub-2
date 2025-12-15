from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing


class FakenodoBehaviour(TaskSet):
    """
    Locust user that exercises the /fakenodo/test endpoint which calls
    the service method `test_full_connection`.
    """

    @task
    def test_full_connection_endpoint(self):
        response = self.client.get("/fakenodo/test")
        if response.status_code != 200:
            print(f"Fakenodo test_full_connection failed: {response.status_code}")


class FakenodoUser(HttpUser):
    tasks = [FakenodoBehaviour]
    host = get_host_for_locust_testing()
