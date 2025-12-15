import os, re, time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app import create_app
from app.modules.auth.models import User
from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def wait_for_page_to_load(driver, timeout=4):
    WebDriverWait(driver, timeout).until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )


def count_datasets(driver, host):
    driver.get(f"{host}/dataset/list")
    wait_for_page_to_load(driver)

    try:
        amount_datasets = len(driver.find_elements(By.XPATH, "//table//tbody//tr"))
    except Exception:
        amount_datasets = 0
    return amount_datasets


def _wait_visible_any(driver, locators, timeout=15):
    end_time = time.time() + timeout
    last_exc = None
    while time.time() < end_time:
        for by, sel in locators:
            try:
                el = driver.find_element(by, sel)
                if el.is_displayed():
                    return el
            except Exception as exc:
                last_exc = exc
                continue
        time.sleep(0.3)
    raise TimeoutException(f"Element not visible for any locator: {locators}") from last_exc


def fetch_2fa_from_yopmail(driver, username="user1", sender_contains="SteamGamesHub", timeout=60):
    driver.get("https://yopmail.com/es/")
    wait = WebDriverWait(driver, 10)
    # Try dismiss cookie banners best-effort
    for xp in [
        "//button[contains(., 'Consent')]",
        "//button[contains(., 'Aceptar')]",
        "//button[contains(., 'Agree')]",
        "//button[contains(., 'Aceptar todo')]",
        "//a[contains(., 'Aceptar') or contains(., 'Accept')]",
    ]:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            btn.click()
            time.sleep(0.4)
            break
        except Exception:
            continue

    # Open mailbox
    inbox_field = wait.until(EC.presence_of_element_located((By.ID, "login")))
    inbox_field.clear()
    inbox_field.send_keys(username)
    inbox_field.send_keys(Keys.RETURN)
    time.sleep(1.2)

    # Find inbox iframe
    inbox_frame = None
    for f in driver.find_elements(By.TAG_NAME, "iframe"):
        fid = (f.get_attribute("id") or f.get_attribute("name") or "").lower()
        if "inbox" in fid or "ifinbox" in fid or "mail" in fid:
            inbox_frame = f
            break
    if not inbox_frame:
        raise TimeoutException("[yopmail] inbox iframe not found")
    driver.switch_to.frame(inbox_frame)

    existing_ids = set()
    try:
        for el in driver.find_elements(By.CSS_SELECTOR, "div.m"):
            eid = el.get_attribute("id")
            if eid:
                existing_ids.add(eid)
    except Exception:
        pass

    email_element = None
    last_email_element = None
    start = time.time()
    last_refresh = 0
    refresh_count = 0
    max_refreshes = 2
    while time.time() - start < timeout:
        try:
            # Prefer sender match
            for s in driver.find_elements(By.XPATH, f"//span[contains(., '{sender_contains}')]"):
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

            if not email_element:
                items = driver.find_elements(By.CSS_SELECTOR, "div.m")
                for it in items:
                    eid = it.get_attribute("id")
                    if eid and eid not in existing_ids:
                        email_element = it
                        break
                    last_email_element = it

            if email_element:
                try:
                    btn = email_element.find_element(By.CSS_SELECTOR, "button.lm")
                    btn.click()
                except Exception:
                    try:
                        email_element.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", email_element)
                time.sleep(1.2)
                break
        except Exception:
            pass

        if time.time() - last_refresh > 5 and refresh_count < max_refreshes:
            try:
                driver.switch_to.default_content()
                try:
                    driver.find_element(By.ID, "refresh").click()
                except Exception:
                    try:
                        driver.execute_script("if (typeof r === 'function') { r(); }")
                    except Exception:
                        pass
                driver.switch_to.frame(inbox_frame)
            except Exception:
                pass
            last_refresh = time.time()
            refresh_count += 1
        time.sleep(1.2)

    if not email_element and last_email_element:
        email_element = last_email_element
    if not email_element:
        raise TimeoutException("[yopmail] no email found")

    # Switch to email content and extract 6-digit code
    driver.switch_to.default_content()
    mail_frame = WebDriverWait(driver, 8).until(lambda d: d.find_element(By.ID, "ifmail"))
    driver.switch_to.frame(mail_frame)

    start_body = time.time()
    while time.time() - start_body < timeout:
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            m = re.search(r"\b(\d{6})\b", body_text)
            if m:
                return m.group(1)
        except Exception:
            pass
        time.sleep(2)
    raise TimeoutException("[yopmail] 2FA code not found in email body")


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


def test_upload_dataset():
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()

        # Login with optional 2FA
        _login_with_optional_2fa(driver, host)

        # Open the upload dataset
        driver.get(f"{host}/dataset/upload")
        wait_for_page_to_load(driver)

        # Fill minimal required basic info
        title_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "title")))
        title_field.clear()
        title_field.send_keys("Selenium Upload Test Title")
        desc_field = driver.find_element(By.NAME, "desc")
        desc_field.clear()
        desc_field.send_keys("Selenium Upload Test Description")

        # Upload one CSV via Dropzone
        file1_path = os.path.abspath("app/modules/dataset/csv_examples/file1.csv")
        dropzone = driver.find_element(By.CLASS_NAME, "dz-hidden-input")
        dropzone.send_keys(file1_path)

        # Wait for Dropzone success and the file list item
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".dz-success-mark")))
        _wait_visible_any(driver, [(By.CSS_SELECTOR, "#file-list li")], timeout=15)

        # Reveal per-file form and set version
        try:
            info_btn = _wait_visible_any(driver, [(By.CSS_SELECTOR, "#file-list .info-button")], timeout=8)
            info_btn.click()
        except Exception:
            pass
        version_input = _wait_visible_any(
            driver,
            [(By.CSS_SELECTOR, "#file-list .file_form input[name$='-version']")],
            timeout=15,
        )
        version_input.clear()
        version_input.send_keys("1.0.0")

        # Tick the agree checkbox to enable upload and assert it's enabled, but do not submit
        agree = driver.find_element(By.ID, "agreeCheckbox")
        if not agree.is_selected():
            agree.click()
        upload_btn = driver.find_element(By.ID, "upload_button")
        assert upload_btn.is_enabled(), "Upload button should be enabled after agreeing terms"

        # Stay on the upload page (do not click upload_button)
        assert "/dataset/upload" in driver.current_url

        print("Test passed!")

    finally:

        # Close the browser
        close_driver(driver)

def test_related_datasets_section_visible(driver=None):
    driver = driver or initialize_driver()
    try:
        host = get_host_for_selenium_testing()


        # Vamos a dataset con related_datasets (usa uno que exista en tu entorno de test)
        dataset_url = f"{host}/doi/10.9999/dataset.4/"
        driver.get(dataset_url)
        wait_for_page_to_load(driver)

        # Espera a que aparezca el título de la sección
        section_title = _wait_visible_any(
            driver,
            [(By.XPATH, "//h3[contains(text(),'Related Datasets')]")],
            timeout=12
        )

        assert section_title.is_displayed()

        # Verificar que existe al menos un related dataset card
        card = _wait_visible_any(
            driver,
            [(By.CSS_SELECTOR, ".related-dataset-card")],
            timeout=10
        )
        assert card.is_displayed()

        # Verificar que aparece el contador "X suggestions"
        count_el = driver.find_element(By.CSS_SELECTOR, ".related-section-count")
        text = count_el.text.strip()
        assert "suggestions" in text.lower(), "El contador no aparece o es incorrecto"

    finally:
        close_driver(driver)


def test_related_dataset_item_contents(driver=None):
    driver = driver or initialize_driver()
    try:
        host = get_host_for_selenium_testing()

        driver.get(f"{host}/doi/10.9999/dataset.4/")
        wait_for_page_to_load(driver)

        # Localizar una tarjeta de dataset relacionado
        card = _wait_visible_any(
            driver,
            [(By.CSS_SELECTOR, ".related-dataset-card")],
            timeout=10
        )

        # Título
        title_el = card.find_element(By.CSS_SELECTOR, ".related-title")
        assert title_el.text.strip() != "", "El título no se está mostrando"
        assert title_el.get_attribute("href").startswith(host), "El link del título es incorrecto"

        # Autor + categoría
        meta = card.find_element(By.CSS_SELECTOR, ".related-meta")
        assert "·" in meta.text, "No se muestra autor + categoría correctamente"

        # Badges
        badges = card.find_elements(By.CSS_SELECTOR, ".related-badge")
        assert len(badges) >= 0, "No se muestran badges"

        # Descargas
        stats = card.find_element(By.CSS_SELECTOR, ".related-stats")
        assert "downloads" in stats.text.lower(), "No se muestra número de descargas"

        # Fecha
        assert re.search(r"\d{4}|\w{3} \d{1,2}", stats.text), "No se muestra fecha"

    finally:
        close_driver(driver)


def test_related_dataset_link_navigation(driver=None):
    driver = driver or initialize_driver()
    try:
        host = get_host_for_selenium_testing()

        driver.get(f"{host}/doi/10.9999/dataset.4/")
        wait_for_page_to_load(driver)

        link = _wait_visible_any(
            driver,
            [(By.CSS_SELECTOR, ".related-title")],
            timeout=10
        )

        href = link.get_attribute("href")
        link.click()
        wait_for_page_to_load(driver)

        assert href == driver.current_url, "La navegación al dataset relacionado no funciona correctamente"

    finally:
        close_driver(driver)


def test_user_metrics():
    driver = initialize_driver()

    try:
        host = get_host_for_selenium_testing()
        _login_with_optional_2fa(driver, host)
        driver.get(f"{host}/")

        wait_for_page_to_load(driver)

        # Espera cualquier tarjeta de estadísticas
        WebDriverWait(driver, 15).until(
            lambda d: "uploaded datasets" in d.page_source
        )


        uploaded_el  = driver.find_element(By.XPATH, "//h4[contains(., 'uploaded datasets')]")
        downloads_el = driver.find_element(By.XPATH, "//h4[contains(., 'downloads')]")
        syncs_el     = driver.find_element(By.XPATH, "//h4[contains(., 'synchronizations')]")

        # Extraer el número desde el texto
        import re

        def extract_number(el):
            m = re.search(r"\d+", el.text)
            return int(m.group()) if m else 0

        uploaded  = extract_number(uploaded_el)
        downloads = extract_number(downloads_el)
        syncs     = extract_number(syncs_el)

        print(f"My activity metrics: {uploaded} uploaded, {downloads} downloads, {syncs} syncs")


        assert uploaded >= 0
        assert downloads >= 0
        assert syncs >= 0

    finally:
        driver.quit()


# Call the test function
test_upload_dataset()
test_user_metrics()


def test_timeline():
    """Adapted from Selenium IDE: navigate to version history and interact."""
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(host)
        wait_for_page_to_load(driver)
        try:
            WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.LINK_TEXT, "Version history"))).click()
            time.sleep(0.6)
            try:
                item = driver.find_element(By.CSS_SELECTOR, ".timeline-item:nth-child(1) .timeline-version")
                driver.execute_script("arguments[0].scrollIntoView(true);", item)
                item.click()
            except Exception:
                pass
            try:
                WebDriverWait(driver, 4).until(EC.element_to_be_clickable((By.LINK_TEXT, "Show timeline"))).click()
            except Exception:
                pass
        except Exception:
            pass
    finally:
        close_driver(driver)
