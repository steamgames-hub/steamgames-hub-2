import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver

TRENDING_LIST_SELECTOR = "[data-testid='trending-list-primary']"
TRENDING_ROW_SELECTOR = "[data-testid='trending-list-primary'] li"
TRENDING_BY_SELECT_ID = "trending-by"
TRENDING_PERIOD_SELECT_ID = "trending-period"


@pytest.fixture
def driver():
    drv = initialize_driver()
    yield drv
    close_driver(drv)


def _wait_for_trending_loaded(driver, timeout=20):
    """Wait until the trending widget has rendered at least once."""
    wait = WebDriverWait(driver, timeout)

    def _has_content(_driver):
        container = _driver.find_element(By.CSS_SELECTOR, TRENDING_LIST_SELECTOR)
        rows = _driver.find_elements(By.CSS_SELECTOR, TRENDING_ROW_SELECTOR)
        return bool(rows) or "No trending datasets yet." in container.text

    wait.until(_has_content)


def _snapshot_list(driver):
    return driver.find_element(By.CSS_SELECTOR, TRENDING_LIST_SELECTOR).text.strip()


def _ensure_rows(driver):
    rows = driver.find_elements(By.CSS_SELECTOR, TRENDING_ROW_SELECTOR)
    if not rows:
        pytest.skip("Trending widget has no data in the current environment.")
    return rows


def _change_select(driver, element_id, value):
    Select(driver.find_element(By.ID, element_id)).select_by_value(value)


def test_trending_widget_reacts_to_filters(driver):
    host = get_host_for_selenium_testing()
    driver.get(f"{host}/")

    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "trending-list")))
    _wait_for_trending_loaded(driver)
    _ensure_rows(driver)

    def _current_by(_driver):
        container = _driver.find_element(By.CSS_SELECTOR, TRENDING_LIST_SELECTOR)
        return container.get_attribute("data-by")

    WebDriverWait(driver, 10).until(lambda _driver: _current_by(_driver) in {"views", "downloads"})

    _change_select(driver, TRENDING_BY_SELECT_ID, "downloads")
    _change_select(driver, TRENDING_PERIOD_SELECT_ID, "month")

    WebDriverWait(driver, 20).until(lambda _driver: _current_by(_driver) == "downloads")
    updated_rows = driver.find_elements(By.CSS_SELECTOR, TRENDING_ROW_SELECTOR)
    assert updated_rows, "Trending list should remain populated after filter changes"


def test_trending_dataset_link_opens_details(driver):
    host = get_host_for_selenium_testing()
    driver.get(f"{host}/")

    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "trending-list")))
    _wait_for_trending_loaded(driver)
    rows = _ensure_rows(driver)

    first_link = rows[0].find_element(By.TAG_NAME, "a")
    href = first_link.get_attribute("href")
    assert href, "Trending dataset entries should have a link to the dataset detail page"

    first_link.click()
    WebDriverWait(driver, 20).until(EC.url_contains("/doi/"))
