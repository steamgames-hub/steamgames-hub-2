import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def test_login_and_check_element():

    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Open the login page
        driver.get(f"{host}/login")

        # Wait a little while to make sure the page has loaded completely
        time.sleep(4)

        # Find the username and password field and enter the values
        email_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")

        email_field.send_keys("user1@example.com")
        password_field.send_keys("1234")

        # Send the form
        password_field.send_keys(Keys.RETURN)

        # Wait a little while to ensure that the action has been completed
        time.sleep(4)

        try:

            driver.find_element(By.XPATH, "//h1[contains(@class, 'h2 mb-3') and contains(., 'Latest datasets')]")
            print("Test passed!")

        except NoSuchElementException:
            raise AssertionError("Test failed!")

    finally:

        # Close the browser
        close_driver(driver)


def test_forgot_password_ui():
    """Check that the forgot password page renders correctly."""
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/forgot-password")
        time.sleep(3)

        email_input = driver.find_element(By.NAME, "email")
        send_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']") 

        email_input.send_keys("user1@example.com")
        send_button.click()
        time.sleep(2)

        assert "reset" in driver.page_source.lower() or "email" in driver.page_source.lower()

    except NoSuchElementException as e:
        raise AssertionError(f"Missing element: {e}")
    finally:
        close_driver(driver)

# Call the test function
test_login_and_check_element()
test_forgot_password_ui()
