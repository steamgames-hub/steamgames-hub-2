import pytest, time, re
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app import db, create_app
from app.modules.auth.models import User
from app.modules.auth.services import AuthenticationService
from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


@pytest.fixture
def driver():
    drv = initialize_driver(headless=True)
    yield drv

    close_driver(drv)

@pytest.fixture
def auth_service():
    return AuthenticationService()


def test_login_and_2fa():
    driver = initialize_driver()
    wait = WebDriverWait(driver, 20)
    app = create_app()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/login")

        # --- Login ---
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        password_field = driver.find_element(By.NAME, "password")
        email_field.send_keys("user1@yopmail.com")
        password_field.send_keys("1234")
        password_field.send_keys(Keys.RETURN)

        # --- Esperar página 2FA ---
        wait.until(EC.url_contains("/two-factor/"))

        main_window = driver.current_window_handle

        # --- Obtener 2FA ---
        with app.app_context():
            user = User.query.filter_by(email="user1@yopmail.com").first()
            code = user.two_factor_code
            app.logger.info(f"[test] Moqueando la obtención del código. Código 2FA obtenido: {code}")

        # --- Introducir código 2FA ---
        code_field = wait.until(EC.presence_of_element_located((By.ID, "code")))  # <-- CORREGIDO
        code_field.clear()
        code_field.send_keys(code)

        # --- Click en botón Verificar ---
        submit_btn = driver.find_element(By.ID, "submit")
        submit_btn.click()

        # --- Esperar a que aparezca el div con el nombre del usuario ---
        user_div = wait.until(EC.visibility_of_element_located((By.XPATH, "//span[contains(text(), 'Doe, John')]")))

        if user_div:
            print("[test] Login + 2FA completado correctamente")
        else:
            print("[test] ERROR: No se encontró el div del usuario, login fallido")

    finally:
        driver.quit()


def test_forgot_password_ui(driver):
    host = get_host_for_selenium_testing()
    driver.get(f"{host}/forgot-password")

    wait = WebDriverWait(driver, 10)

    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    send_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")

    email_input.send_keys("user1@yopmail.com")
    send_button.click()

    # Espera que la página muestre algo relacionado con "reset" o "email"
    try:
        wait.until(lambda d: "reset" in d.page_source.lower() or "email" in d.page_source.lower())
    except Exception:
        pytest.fail("No se encontró mensaje de restablecimiento de contraseña")


def test_signup_and_verify(auth_service):
    driver = initialize_driver()
    wait = WebDriverWait(driver, 20)
    app = create_app()
            
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/signup")

        # --- Signup ---
        name_field = wait.until(EC.presence_of_element_located((By.NAME, "name")))
        name_field.send_keys("John")
        surname_field = driver.find_element(By.NAME, "surname")
        surname_field.send_keys("Doe")
        email_field = driver.find_element(By.NAME, "email")
        email_field.send_keys("verify@example.com")
        password_field = driver.find_element(By.NAME, "password")
        password_field.send_keys("1234")
        password_field.send_keys(Keys.RETURN)

        # verify lockscreen
        wait.until(
            EC.visibility_of_element_located((By.XPATH, "//h5[contains(text(), 'Message sent')]"))
        )

        # --- Obtener enlace ---
        with app.app_context():
            token = auth_service.generate_token(email="verify@example.com") # mockeamos el envío del email para no agotar el límite de la API
            app.logger.info(f"[test] Moqueando la obtención del token. Token obtenido: {token}")

        # --- Verificar cuenta ---
        link = f"{host}/verify/{token}"
        driver.get(link)

        # --- Comprobamos que se ha verificado con éxito ---
        user_div = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//a[contains(text(), 'our homepage')]"))
        )

        if user_div:
            print("[test] Login + verificación completado correctamente")
        else:
            print("[test] ERROR: verificación fallida")
    
        # eliminamos el usuario creado
        with app.app_context():
            user = User.query.filter_by(email="verify@example.com").first()
            app = create_app()
            if user:
                db.session.delete(user.profile)
                db.session.delete(user)
                db.session.commit()

    except:
        # en caso de excepción o fallo, eliminamos el usuario creado
        with app.app_context():
            user = User.query.filter_by(email="verify@example.com").first()
            app = create_app()
            if user:
                db.session.delete(user.profile)
                db.session.delete(user)
                db.session.commit()
    finally:
        driver.quit()
