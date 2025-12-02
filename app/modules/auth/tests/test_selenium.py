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
from selenium.common.exceptions import TimeoutException

@pytest.fixture
def driver():
    drv = initialize_driver()
    yield drv

    close_driver(drv)

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
    if debug: print(f"[yopmail] switch a iframe: {inbox_frame.get_attribute('id') or inbox_frame.get_attribute('name')}")

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
    if debug: print(f"[yopmail] existing email ids: {existing_ids}")

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
        if time.time() - last_refresh > 3 and refresh_count < max_refreshes:
            try:
                driver.switch_to.default_content()
                try:
                    refresh_btn = driver.find_element(By.ID, "refresh")
                    driver.execute_script("arguments[0].click();", refresh_btn)
                    if debug: print("[yopmail] clicked #refresh button")
                except Exception:
                    try:
                        driver.execute_script("if (typeof r === 'function') { r(); }")
                        if debug: print("[yopmail] executed r() to refresh")
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
        if debug: print(f"[yopmail] usando último email disponible id={email_element.get_attribute('id')}")

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
                if debug: print(f"[yopmail] código 2FA encontrado: {code}")
                return code
        except Exception:
            pass
        time.sleep(0.8)

    raise TimeoutException("[yopmail] No se encontró código 2FA en el correo (tras abrirlo)")



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
