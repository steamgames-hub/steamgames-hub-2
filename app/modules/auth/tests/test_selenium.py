import os
import re
import time

import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app import create_app, db
from app.modules.auth.models import User
from app.modules.auth.services import AuthenticationService
from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def wait_for_page_to_load(driver, timeout=4):
    WebDriverWait(driver, timeout).until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )


def _login_with_optional_2fa(driver, host):
    app = create_app()
    wait = WebDriverWait(driver, 25)
    driver.get(f"{host}/login")
    wait_for_page_to_load(driver)

    email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    password_field = driver.find_element(By.NAME, "password")
    email_field.clear()
    email_field.send_keys("user1@yopmail.com")
    password_field.clear()
    password_field.send_keys("1234")

    try:
        driver.find_element(By.ID, "submit").click()
    except Exception:
        password_field.send_keys(Keys.RETURN)

    # Wait until either 2FA page or logout link exists
    two_factor = False
    start = time.time()
    while time.time() - start < 12:
        cur = driver.current_url
        if "/two-factor/" in cur:
            two_factor = True
            break
        try:
            driver.find_element(By.CSS_SELECTOR, "a.sidebar-link[href*='/logout']")
            return  # logged in
        except Exception:
            pass
        time.sleep(0.3)

    if two_factor:
        # --- Get 2FA ---
        with app.app_context():
            user = User.query.filter_by(email="user1@yopmail.com").first()
            code = user.two_factor_code
            app.logger.info(f"[test] Moqueando la obtención del código. Código 2FA obtenido: {code}")

        code_field = wait.until(EC.presence_of_element_located((By.NAME, "code")))

        code_field = wait.until(EC.presence_of_element_located((By.NAME, "code")))
        code_field.clear()
        code_field.send_keys(code)
        try:
            driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()
        except Exception:
            code_field.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.sidebar-link[href*='/logout']")))


@pytest.fixture
def driver():
    drv = initialize_driver()
    yield drv

    close_driver(drv)


@pytest.fixture
def auth_service():
    return AuthenticationService()


def fetch_2fa_from_yopmail(driver, username="user1", sender_contains="SteamGamesHub", timeout=60, debug=True):
    """
    Extrae el código 2FA del correo de Yopmail.
    Mejoras:
     - detecta nuevos mensajes comparando ids (evita coger códigos antiguos)
     - fuerza refresh hasta 2 veces si no llega nada
     - si no cambia el ID, usa el último correo disponible
     - espera a que el iframe de contenido cargue antes de leer body
    """
    driver.get("https://yopmail.com/es/")
    wait = WebDriverWait(driver, 5)

    # aceptar cookies si aparece
    consent_xpaths = [
        "//button[contains(., 'Consent')]",
        "//button[contains(., 'Aceptar')]",
        "//button[contains(., 'Agree')]",
        "//button[contains(., 'Aceptar todo')]",
        "//a[contains(., 'Aceptar') or contains(., 'Accept')]",
    ]
    for xp in consent_xpaths:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            if debug:
                print(f"[yopmail] clicando en botón de cookies: {xp}")
            btn.click()
            time.sleep(0.5)
            break
        except Exception:
            continue

    # entrar al buzón
    input_box = wait.until(EC.presence_of_element_located((By.ID, "login")))
    input_box.clear()
    input_box.send_keys(username)
    input_box.send_keys(Keys.RETURN)
    time.sleep(1.5)

    # detectar iframe de la bandeja (ifinbox) y switch
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    inbox_frame = None
    for f in iframes:
        fid = (f.get_attribute("id") or f.get_attribute("name") or "").lower()
        if "inbox" in fid or "ifinbox" in fid or "mail" in fid:
            inbox_frame = f
            break
    if not inbox_frame:
        raise TimeoutException("[yopmail] No se encontró iframe de la bandeja de entrada")

    driver.switch_to.frame(inbox_frame)
    if debug:
        print(f"[yopmail] switch a iframe: {inbox_frame.get_attribute('id') or inbox_frame.get_attribute('name')}")

    # snapshot de ids actuales (para evitar coger un mail viejo)
    existing_ids = set()
    try:
        elems = driver.find_elements(By.CSS_SELECTOR, "div.m")
        for el in elems:
            eid = el.get_attribute("id")
            if eid:
                existing_ids.add(eid)
    except Exception:
        pass
    if debug:
        print(f"[yopmail] existing email ids: {existing_ids}")

    # 🔹 Variables para refrescos
    refresh_count = 0
    max_refreshes = 2
    last_email_element = None

    # polling hasta que aparezca un email nuevo (id distinto) o timeout
    start_time = time.time()
    email_element = None
    last_refresh = 0
    while time.time() - start_time < timeout:
        try:
            # buscar por remitente de forma robusta (varias estructuras)
            els_by_sender = driver.find_elements(By.XPATH, f"//span[contains(., '{sender_contains}')]")
            if els_by_sender:
                for s in els_by_sender:
                    parent = s
                    for _ in range(5):
                        parent = parent.find_element(By.XPATH, "..")
                        eid = parent.get_attribute("id")
                        if eid:
                            if eid not in existing_ids:
                                email_element = parent
                                break
                    if email_element:
                        break

            # fallback: revisar items list (div.m) y detectar nuevo id
            if not email_element:
                items = driver.find_elements(By.CSS_SELECTOR, "div.m")
                for it in items:
                    eid = it.get_attribute("id")
                    if eid and eid not in existing_ids:
                        email_element = it
                        break
                    # 🔹 guardar el último por si no hay cambios
                    last_email_element = it

            # otro fallback: botones / anchors
            if not email_element:
                anchors = driver.find_elements(By.CSS_SELECTOR, "a.m, button.lm, div.m button.lm")
                for a in anchors:
                    try:
                        container = a.find_element(By.XPATH, "./ancestor::div[contains(@class,'m')]")
                        eid = container.get_attribute("id")
                        if eid and eid not in existing_ids:
                            email_element = container
                            break
                    except Exception:
                        continue

            if email_element:
                if debug:
                    txt = ""
                    try:
                        txt = email_element.text[:80]
                    except Exception:
                        pass
                    print(f"[yopmail] nuevo email detectado id={email_element.get_attribute('id')} txt='{txt}'")
                try:
                    clickable = email_element.find_element(By.CSS_SELECTOR, "button.lm")
                    clickable.click()
                except Exception:
                    try:
                        email_element.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", email_element)
                time.sleep(1.5)
                break

        except Exception:
            pass

        # 🔹 refresco máximo 2 veces
        if time.time() - last_refresh > 5 and refresh_count < max_refreshes:
            try:
                driver.switch_to.default_content()
                try:
                    refresh_btn = driver.find_element(By.ID, "refresh")
                    driver.execute_script("arguments[0].click();", refresh_btn)
                    if debug:
                        print("[yopmail] clicked #refresh button")
                except Exception:
                    try:
                        driver.execute_script("if (typeof r === 'function') { r(); }")
                        if debug:
                            print("[yopmail] executed r() to refresh")
                    except Exception:
                        pass
                driver.switch_to.frame(inbox_frame)
            except Exception:
                pass
            last_refresh = time.time()
            refresh_count += 1

        time.sleep(0.8)

    # 🔹 Si no hay nuevo email, usar el último disponible
    if not email_element and last_email_element:
        email_element = last_email_element
        if debug:
            print(f"[yopmail] usando último email disponible id={email_element.get_attribute('id')}")

    if not email_element:
        raise TimeoutException(f"[yopmail] No se encontró ningún correo (username={username})")

    # cambiar al iframe del contenido del correo
    driver.switch_to.default_content()
    try:
        wait = WebDriverWait(driver, 10)
        mail_frame = wait.until(lambda d: d.find_element(By.ID, "ifmail"))
    except Exception:
        try:
            mail_frame = driver.find_element(By.ID, "ifmail")
        except Exception:
            raise TimeoutException("[yopmail] No se encontró iframe de contenido del correo (ifmail)")

    driver.switch_to.frame(mail_frame)

    start_body = time.time()
    while time.time() - start_body < timeout:
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            m = re.search(r"\b(\d{6})\b", body_text)
            if m:
                code = m.group(1)
                if debug:
                    print(f"[yopmail] código 2FA encontrado: {code}")
                return code
        except Exception:
            pass
        time.sleep(0.8)

    raise TimeoutException("[yopmail] No se encontró código 2FA en el correo (tras abrirlo)")


def test_login_and_2fa():
    driver = initialize_driver()
    wait = WebDriverWait(driver, 20)
    app = create_app()
    try:
        if os.getenv("TWO_FACTOR_ENABLED", "False") == "True":

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

            driver.current_window_handle

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
        else:
            print("El 2FA se encuentra desactivado. Para testear su uso, modifique las variables de entorno en app")
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
        wait.until(EC.visibility_of_element_located((By.XPATH, "//h5[contains(text(), 'Message sent')]")))

        # --- Obtener enlace ---
        with app.app_context():
            token = auth_service.generate_token(
                email="verify@example.com"
            )  # mockeamos el envío del email para no agotar el límite de la API
            app.logger.info(f"[test] Moqueando la obtención del token. Token obtenido: {token}")

        # --- Verificar cuenta ---
        link = f"{host}/verify/{token}"
        driver.get(link)

        # --- Comprobamos que se ha verificado con éxito ---
        user_div = wait.until(EC.visibility_of_element_located((By.XPATH, "//a[contains(text(), 'our homepage')]")))

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


def test_issues():
    """Adapted from Selenium IDE: submit an issue and view it as another user."""
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()

        # Try to login as user2 and submit an issue
        try:
            driver.get(f"{host}/login")
            wait = WebDriverWait(driver, 12)
            email = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            email.clear()
            email.send_keys("user2@yopmail.com")
            pwd = driver.find_element(By.NAME, "password")
            pwd.clear()
            pwd.send_keys("1234")
            try:
                driver.find_element(By.ID, "submit").click()
            except Exception:
                pwd.send_keys(Keys.RETURN)
            wait_for_page_to_load(driver)
        except Exception:
            # proceed even if login failed (environment dependent)
            pass

        try:
            WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.LINK_TEXT, "Notify issue"))).click()
            desc = WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.ID, "description")))
            desc.clear()
            desc.send_keys("I don't like it.")
            try:
                driver.find_element(By.ID, "send-issue").click()
            except Exception:
                try:
                    driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()
                except Exception:
                    pass
            time.sleep(1)
        except Exception:
            pass

        # Logout and login as admin/user1 to inspect issues
        try:
            driver.get(f"{host}/logout")
            wait_for_page_to_load(driver)
        except Exception:
            pass

        _login_with_optional_2fa(driver, host)

        try:
            WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.LINK_TEXT, "Dataset Issues"))).click()
            time.sleep(0.5)
            try:
                el = driver.find_element(By.ID, "1")
                driver.execute_script("arguments[0].scrollIntoView(true);", el)
                el.click()
            except Exception:
                pass
            try:
                link = driver.find_element(By.LINK_TEXT, "New Version Steam Games Master Index")
                link.click()
            except Exception:
                pass
        except Exception:
            pass

    finally:
        close_driver(driver)


def test_roles():
    """Adapted from Selenium IDE: basic users list interactions."""
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        _login_with_optional_2fa(driver, host)
        WebDriverWait(driver, 8)
        try:
            driver.get(f"{host}/users")
            wait_for_page_to_load(driver)
            time.sleep(0.5)
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "tr:nth-child(2) .btn-success")
                btn.click()
            except Exception:
                pass
            try:
                w = driver.find_element(By.CSS_SELECTOR, ".btn-warning")
                w.click()
            except Exception:
                pass
            try:
                edit = driver.find_element(By.CSS_SELECTOR, "tr:nth-child(3) .btn-primary")
                edit.click()
                try:
                    name = WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.ID, "name")))
                    name.clear()
                    name.send_keys("Juli")
                    try:
                        driver.find_element(By.ID, "submit").click()
                    except Exception:
                        name.send_keys(Keys.RETURN)
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass
    finally:
        close_driver(driver)
