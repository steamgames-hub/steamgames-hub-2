import re
import time
import pytest
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver

@pytest.fixture
def driver():
    drv = initialize_driver()
    yield drv

    close_driver(drv)
import time
import re
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ------------------------------------------
# Función para extraer el código 2FA de Yopmail
# ------------------------------------------
def fetch_2fa_from_yopmail(driver, username="user1", sender_contains="SteamGamesHub", timeout=60, debug=True):
    """
    Extrae el código 2FA del correo de Yopmail.
    """
    driver.get("https://yopmail.com/es/")
    wait = WebDriverWait(driver, 5)

    # --- Aceptar cookies/consentimiento ---
    consent_xpaths = [
        "//button[contains(., 'Consent')]",
        "//button[contains(., 'Aceptar')]",
        "//button[contains(., 'Agree')]",
        "//button[contains(., 'Aceptar todo')]",
        "//a[contains(., 'Aceptar') or contains(., 'Accept')]"
    ]
    for xp in consent_xpaths:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            if debug: print(f"[yopmail] clicando en botón de cookies: {xp}")
            btn.click()
            time.sleep(0.5)
            break
        except Exception:
            continue

    # --- Entrar al buzón ---
    input_box = wait.until(EC.presence_of_element_located((By.ID, "login")))
    input_box.clear()
    input_box.send_keys(username)
    input_box.send_keys(Keys.RETURN)
    time.sleep(2)

    # --- Detectar iframe de la bandeja ---
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    inbox_frame = None
    for f in iframes:
        fid = f.get_attribute("id") or f.get_attribute("name") or ""
        if "inbox" in fid.lower() or "ifinbox" in fid.lower() or "mail" in fid.lower():
            inbox_frame = f
            break
    if not inbox_frame:
        raise TimeoutException("[yopmail] No se encontró iframe de la bandeja de entrada")

    driver.switch_to.frame(inbox_frame)
    if debug: print(f"[yopmail] switch a iframe: {inbox_frame.get_attribute('id')}")

    # --- Buscar email ---
    start_time = time.time()
    email_element = None
    while time.time() - start_time < timeout:
        try:
            # Buscar por remitente
            els = driver.find_elements(By.XPATH, f"//span[contains(., '{sender_contains}')]")
            if els:
                email_element = els[0]
                if debug: print(f"[yopmail] email encontrado por remitente: {els[0].text[:30]}")
                email_element.click()
                time.sleep(2)  # <-- ESPERA para que cargue iframe del correo
                break

            # Fallback: primer email disponible
            els_any = driver.find_elements(By.CSS_SELECTOR, "div.m button.lm")
            if els_any:
                email_element = els_any[0]
                if debug: print(f"[yopmail] email fallback encontrado: {els_any[0].text[:30]}")
                email_element.click()
                time.sleep(2)  # <-- ESPERA para que cargue iframe del correo
                break

        except Exception:
            pass
        time.sleep(1)

    if not email_element:
        raise TimeoutException(f"[yopmail] No se encontró ningún correo en {timeout} segundos (username={username})")

    # --- Cambiar al iframe del contenido del correo ---
    driver.switch_to.default_content()
    mail_frame = driver.find_element(By.ID, "ifmail")
    driver.switch_to.frame(mail_frame)

    # Esperar hasta que aparezca un 6-dígitos en el body
    start_time = time.time()
    body_text = ""
    while time.time() - start_time < timeout:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        m = re.search(r"\b(\d{6})\b", body_text)
        if m:
            code = m.group(1)
            if debug: print(f"[yopmail] código 2FA encontrado: {code}")
            return code
        time.sleep(1)

    raise TimeoutException("[yopmail] No se encontró código 2FA en el correo")




def test_login_and_2fa():
    driver = initialize_driver()
    wait = WebDriverWait(driver, 20)
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

        # --- Abrir Yopmail en nueva pestaña ---
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])

        # --- Obtener 2FA ---
        code = fetch_2fa_from_yopmail(driver, username="user1", sender_contains="SteamGamesHub")

        # --- Cerrar pestaña Yopmail y volver a principal ---
        driver.close()
        driver.switch_to.window(main_window)

        # --- Introducir código 2FA ---
        code_field = wait.until(EC.presence_of_element_located((By.ID, "code")))  # <-- CORREGIDO
        code_field.clear()
        code_field.send_keys(code)

        # --- Click en botón Verificar ---
        submit_btn = driver.find_element(By.ID, "submit")
        submit_btn.click()
        
        # --- Esperar a que aparezca el div con el nombre del usuario ---
        user_div = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//span[contains(text(), 'Doe, John')]"))
        )

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
        wait.until(
            lambda d: "reset" in d.page_source.lower() or "email" in d.page_source.lower()
        )
    except:
        pytest.fail("No se encontró mensaje de restablecimiento de contraseña")
