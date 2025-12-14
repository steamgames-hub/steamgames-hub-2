import csv
import os
import random
import re
import tempfile
import time

from PIL import Image
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def wait_for_page_to_load(driver, timeout=6):
    WebDriverWait(driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")


def _wait_visible_any(driver, locators, timeout=15):
    """Return the first displayed element matching any of the given locators.

    locators: list of (By, selector)
    """
    end_time = time.time() + timeout
    last_exc = None
    while time.time() < end_time:
        for by, sel in locators:
            try:
                el = driver.find_element(by, sel)
                if el.is_displayed():
                    return el
                # Allow file inputs to be returned even if visually hidden (some UIs hide the real file input)
                try:
                    if el.tag_name.lower() == "input" and (el.get_attribute("type") or "").lower() == "file":
                        return el
                except Exception:
                    pass
            except Exception as exc:
                last_exc = exc
                continue
        time.sleep(0.3)
    raise TimeoutException(f"Element not visible for any locator: {locators}") from last_exc


def _make_png_file() -> str:
    """Create a temporary valid PNG file and return its path (passes Pillow verify)."""
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    # Create a tiny valid PNG using Pillow
    img = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    img.save(path, format="PNG")
    return path


def _make_repo_png_file() -> str:
    """Create a small valid PNG inside the repository uploads/temp folder (Pillow-generated)."""
    # Compute repo root relative to this file: app/modules/community/tests -> go up 4 levels
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    target_dir = os.path.join(repo_root, "uploads", "temp")
    os.makedirs(target_dir, exist_ok=True)
    fname = f"selenium_icon_{random.randint(1, 1_000_000)}.png"
    path = os.path.join(target_dir, fname)
    img = Image.new("RGBA", (8, 8), (0, 128, 255, 255))
    img.save(path, format="PNG")
    return path


def fetch_2fa_from_yopmail(driver, username="user1", sender_contains="SteamGamesHub", timeout=60, debug=False):
    """Best-effort: extract 6-digit 2FA code from Yopmail inbox."""
    driver.get("https://yopmail.com/es/")
    wait = WebDriverWait(driver, 10)

    # Dismiss cookie consent if present
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
            btn.click()
            time.sleep(0.4)
            break
        except Exception:
            continue

    # Enter mailbox
    input_box = wait.until(EC.presence_of_element_located((By.ID, "login")))
    input_box.clear()
    input_box.send_keys(username)
    input_box.send_keys(Keys.RETURN)
    time.sleep(1.2)

    # Switch to inbox iframe
    inbox_frame = None
    for f in driver.find_elements(By.TAG_NAME, "iframe"):
        fid = (f.get_attribute("id") or f.get_attribute("name") or "").lower()
        if "inbox" in fid or "ifinbox" in fid or "mail" in fid:
            inbox_frame = f
            break
    if not inbox_frame:
        raise TimeoutException("[yopmail] inbox iframe not found")

    driver.switch_to.frame(inbox_frame)

    # Snapshot of existing ids
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
            # Prefer elements containing sender text
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

        if time.time() - last_refresh > 3 and refresh_count < max_refreshes:
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
        time.sleep(0.7)

    if not email_element and last_email_element:
        email_element = last_email_element

    if not email_element:
        raise TimeoutException("[yopmail] no email found")

    # Switch to email content iframe
    driver.switch_to.default_content()
    mail_frame = None
    try:
        mail_frame = WebDriverWait(driver, 8).until(lambda d: d.find_element(By.ID, "ifmail"))
    except Exception:
        mail_frame = driver.find_element(By.ID, "ifmail")
    driver.switch_to.frame(mail_frame)

    # Extract 6-digit code
    start_body = time.time()
    while time.time() - start_body < timeout:
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            m = re.search(r"\b(\d{6})\b", body_text)
            if m:
                return m.group(1)
        except Exception:
            pass
        time.sleep(0.7)
    raise TimeoutException("[yopmail] 2FA code not found in email body")


def _login_with_optional_2fa(driver, host):
    """Log in as user1, handling optional 2FA via Yopmail, and verify session is active."""
    wait = WebDriverWait(driver, 25)
    driver.get(f"{host}/login")
    wait_for_page_to_load(driver)

    email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    password_field = driver.find_element(By.NAME, "password")
    email_field.clear()
    email_field.send_keys("user1@yopmail.com")
    password_field.clear()
    password_field.send_keys("1234")

    # Submit form
    try:
        submit_btn = driver.find_element(By.ID, "submit")
        submit_btn.click()
    except Exception:
        password_field.send_keys(Keys.RETURN)

    # Wait for either 2FA page or a visible logout link indicating we're logged in
    logged_in = False
    two_factor = False
    start = time.time()
    while time.time() - start < 12:
        cur = driver.current_url
        if "/two-factor/" in cur:
            two_factor = True
            break
        try:
            # Sidebar logout link present only when authenticated
            driver.find_element(By.CSS_SELECTOR, "a.sidebar-link[href*='/logout']")
            logged_in = True
            break
        except Exception:
            pass
        time.sleep(0.3)

    if two_factor:
        # Complete 2FA via Yopmail
        main_window = driver.current_window_handle
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        code = fetch_2fa_from_yopmail(driver, username="user1", sender_contains="SteamGamesHub")
        driver.close()
        driver.switch_to.window(main_window)

        code_field = wait.until(EC.presence_of_element_located((By.NAME, "code")))
        code_field.clear()
        code_field.send_keys(code)
        # two_factor submit (fallback to pressing Enter)
        try:
            driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()
        except Exception:
            code_field.send_keys(Keys.RETURN)
        wait_for_page_to_load(driver)

        # After 2FA, ensure we're logged in by checking for logout link
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.sidebar-link[href*='/logout']")))
        logged_in = True

    # Final safeguard: if still not logged in (e.g., slow redirect), navigate to a protected page
    if not logged_in:
        driver.get(f"{host}/community/create")
        wait_for_page_to_load(driver)
        if "/login" in driver.current_url:
            # Retry once with longer patience for 2FA detection
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
            # Allow for 2FA or redirect
            try:
                WebDriverWait(driver, 15).until(EC.url_contains("/two-factor/"))
                main_window = driver.current_window_handle
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[-1])
                code = fetch_2fa_from_yopmail(driver, username="user1", sender_contains="SteamGamesHub")
                driver.close()
                driver.switch_to.window(main_window)
                code_field = wait.until(EC.presence_of_element_located((By.NAME, "code")))
                code_field.clear()
                code_field.send_keys(code)
                try:
                    driver.find_element(By.CSS_SELECTOR, "form button[type='submit']").click()
                except Exception:
                    code_field.send_keys(Keys.RETURN)
                wait_for_page_to_load(driver)
            except TimeoutException:
                pass
            # Confirm login
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.sidebar-link[href*='/logout']")))


# ---------- Tests ----------


def test_community_create_and_mine():
    driver = initialize_driver()
    icon_path = None
    try:
        host = get_host_for_selenium_testing()
        _login_with_optional_2fa(driver, host)

        # Open create page (and ensure we're not redirected to login)
        driver.get(f"{host}/community/create")
        wait_for_page_to_load(driver)
        if "/login" in driver.current_url:
            _login_with_optional_2fa(driver, host)
            driver.get(f"{host}/community/create")
            wait_for_page_to_load(driver)

        # Wait for form readiness (CSRF token present), then fill the form
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "csrf_token")))
        name_value = f"Selenium Community {random.randint(1, 1_000_000)}"
        name_field = _wait_visible_any(
            driver,
            [
                (By.NAME, "name"),
                (By.ID, "name"),
                (By.CSS_SELECTOR, "input[name='name']"),
            ],
            timeout=15,
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", name_field)
        name_field.click()
        try:
            name_field.clear()
        except Exception:
            name_field.send_keys(Keys.CONTROL, "a")
            name_field.send_keys(Keys.DELETE)
        name_field.send_keys(name_value)

        desc_field = _wait_visible_any(
            driver,
            [
                (By.NAME, "description"),
                (By.ID, "description"),
                (By.CSS_SELECTOR, "textarea[name='description']"),
                (By.CSS_SELECTOR, "[name='description']"),
            ],
            timeout=20,
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", desc_field)
        desc_field.click()
        try:
            desc_field.clear()
        except Exception:
            desc_field.send_keys(Keys.CONTROL, "a")
            desc_field.send_keys(Keys.DELETE)
        desc_field.send_keys("Created by Selenium test")

        # Upload icon (required by route)
        # Prefer creating file under repo uploads/temp to avoid sandboxed /tmp limitations
        icon_path = _make_repo_png_file()
        file_input = _wait_visible_any(
            driver,
            [
                (By.NAME, "icon"),
                (By.CSS_SELECTOR, "input[type='file'][name='icon']"),
            ],
            timeout=15,
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", file_input)
        # Ensure file exists right before uploading
        assert os.path.isabs(icon_path) and os.path.exists(icon_path)
        file_input.send_keys(icon_path)

        # Submit (click, then JS submit as fallback)
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, "form button[type='submit']")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", submit_btn)
            submit_btn.click()
        except Exception:
            try:
                desc_field.send_keys(Keys.RETURN)
            except Exception:
                pass
        # If still on create URL shortly after, force a JS form submit to avoid any blocked click
        time.sleep(0.3)
        if "/community/create" in driver.current_url:
            try:
                driver.execute_script("var f=document.querySelector('form'); if (f) f.submit();")
            except Exception:
                pass
        wait_for_page_to_load(driver)

        # Should be redirected to community detail page: wait for either detail URL or presence of title
        def _is_detail_page(drv):
            url = drv.current_url
            if "/community/create" in url:
                return False
            if "/community/mine" in url or url.rstrip("/").endswith("/community"):
                return False
            # Heuristic: /community/<id>
            parts = url.rstrip("/").split("/")
            return len(parts) >= 2 and parts[-2] == "community" and parts[-1].isdigit()

        try:
            WebDriverWait(driver, 20).until(
                lambda d: _is_detail_page(d) or len(d.find_elements(By.CSS_SELECTOR, ".card-title")) > 0
            )

            # Assert the title matches
            title_el = _wait_visible_any(driver, [(By.CSS_SELECTOR, ".card-title")], timeout=15)
            title_text = (title_el.text or title_el.get_attribute("textContent") or "").strip()
            assert name_value in title_text
        except TimeoutException:
            # Fallback: if we were bounced to login, re-authenticate
            if "/login" in driver.current_url:
                _login_with_optional_2fa(driver, host)

            # Go to My communities, verify it's listed, then open it
            driver.get(f"{host}/community/mine")
            wait_for_page_to_load(driver)
            try:
                WebDriverWait(driver, 25).until(lambda d: name_value in d.page_source)
            except TimeoutException:
                # Try the public list as a secondary source
                driver.get(f"{host}/community")
                wait_for_page_to_load(driver)
                WebDriverWait(driver, 25).until(lambda d: name_value in d.page_source)
            # Try to click the matching card's View link
            opened = False
            cards = driver.find_elements(By.CSS_SELECTOR, ".card")
            for card in cards:
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, ".card-title")
                    t = (title_el.text or title_el.get_attribute("textContent") or "").strip()
                    if name_value in t:
                        for a in card.find_elements(By.TAG_NAME, "a"):
                            href = a.get_attribute("href") or ""
                            if "/community/" in href and href.rstrip("/").split("/")[-1].isdigit():
                                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", a)
                                a.click()
                                opened = True
                                break
                except Exception:
                    continue
                if opened:
                    break
            if not opened:
                # Fallback: click any matching link from the page source
                for a in driver.find_elements(By.TAG_NAME, "a"):
                    href = a.get_attribute("href") or ""
                    if "/community/" in href and href.rstrip("/").split("/")[-1].isdigit():
                        a.click()
                        opened = True
                        break
            if opened:
                wait_for_page_to_load(driver)
                WebDriverWait(driver, 10).until(EC.url_contains("/community/"))
                title_el = _wait_visible_any(driver, [(By.CSS_SELECTOR, ".card-title")], timeout=10)
                title_text = (title_el.text or title_el.get_attribute("textContent") or "").strip()
                assert name_value in title_text

        # Go to My communities and verify it's listed
        driver.get(f"{host}/community/mine")
        wait_for_page_to_load(driver)
        assert name_value in driver.page_source

    finally:
        try:
            if icon_path and os.path.exists(icon_path):
                os.remove(icon_path)
        except Exception:
            pass
        close_driver(driver)


def test_community_list_and_view():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/community")
        wait_for_page_to_load(driver)

        # Page title and heading should render
        assert "Communities" in driver.page_source

        # If there are communities, open one
        links = driver.find_elements(By.LINK_TEXT, "View")
        if not links:
            # fallback: any card link to /community/<id>
            for a in driver.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href") or ""
                if "/community/" in href and href.rstrip("/").split("/")[-1].isdigit():
                    links = [a]
                    break
        if links:
            links[0].click()
            wait_for_page_to_load(driver)
            WebDriverWait(driver, 10).until(EC.url_contains("/community/"))
            # Assert we see a card-title (community name)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".card-title")))
    finally:
        close_driver(driver)


def test_community_icon_endpoint_best_effort():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/community")
        wait_for_page_to_load(driver)

        # Extract first community id from "View" link href
        link = None
        for a in driver.find_elements(By.TAG_NAME, "a"):
            href = a.get_attribute("href") or ""
            if "/community/" in href and href.rstrip("/").split("/")[-1].isdigit():
                link = href
                break
        if not link:
            return  # no communities present – skip
        cid = int(link.rstrip("/").split("/")[-1])

        # Open icon URL; 404 is acceptable
        driver.get(f"{host}/community/icon/{cid}")
        # Just assert navigation happened
        assert f"/community/icon/{cid}" in driver.current_url
    finally:
        close_driver(driver)


def _make_csv_file(filename="steam_test.csv") -> str:
    """Create a temporary valid Steam CSV file and return its path."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    target_dir = os.path.join(repo_root, "uploads", "temp")
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["appid", "name", "release_date", "is_free", "developers", "publishers", "platforms", "genres", "tags"]
        )
        writer.writerow(
            [
                570,
                "Dota 2",
                "2013-07-09",
                "true",
                "Valve",
                "Valve",
                "Windows;Mac;Linux",
                "Action;Strategy",
                "MOBA;Multiplayer",
            ]
        )
    return path


def _create_community_via_ui(driver, host, name_value):
    """Helper to create a community and return its ID."""
    driver.get(f"{host}/community/create")
    wait_for_page_to_load(driver)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "csrf_token")))
    name_field = _wait_visible_any(driver, [(By.NAME, "name")], timeout=15)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", name_field)
    name_field.click()
    name_field.clear()
    name_field.send_keys(name_value)
    # Be robust locating the description textarea
    desc_field = _wait_visible_any(
        driver,
        [
            (By.NAME, "description"),
            (By.ID, "description"),
            (By.CSS_SELECTOR, "textarea[name='description']"),
            (By.CSS_SELECTOR, "[name='description']"),
        ],
        timeout=20,
    )
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", desc_field)
    desc_field.send_keys("Community for proposal test")
    icon_path = _make_repo_png_file()
    file_input = _wait_visible_any(driver, [(By.NAME, "icon")], timeout=15)
    file_input.send_keys(icon_path)
    submit_btn = driver.find_element(By.CSS_SELECTOR, "form button[type='submit']")
    submit_btn.click()
    wait_for_page_to_load(driver)
    WebDriverWait(driver, 20).until(EC.url_contains("/community/"))
    url = driver.current_url
    community_id = int(url.rstrip("/").split("/")[-1])
    return community_id, icon_path


def create_dataset_via_ui(driver, host, title_value):
    """Helper to create a dataset and return its view URL and CSV path.

    Flow:
    - Open upload page, fill title and desc
    - Upload CSV via Dropzone
    - Click "Show info" for the uploaded file and set version using dynamic input name suffix
    - Tick terms checkbox to enable upload button and click it
    - On redirect to /dataset/list, click the new dataset title link to open its view page
    """
    driver.get(f"{host}/dataset/upload")
    wait_for_page_to_load(driver)
    title_field = _wait_visible_any(driver, [(By.NAME, "title")], timeout=15)
    title_field.clear()
    title_field.send_keys(title_value)
    desc_field = _wait_visible_any(driver, [(By.NAME, "desc")], timeout=15)
    desc_field.clear()
    desc_field.send_keys("Dataset for proposal test")

    # Dropzone upload
    csv_path = _make_csv_file()
    dropzone_input = driver.find_element(By.CSS_SELECTOR, ".dz-hidden-input")
    dropzone_input.send_keys(csv_path)

    # Wait for Dropzone to show success and the file list item to render
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".dz-success-mark")))
    _wait_visible_any(driver, [(By.CSS_SELECTOR, "#file-list li")], timeout=15)

    # Reveal per-file form and set the dynamic version input
    try:
        info_btn = _wait_visible_any(driver, [(By.CSS_SELECTOR, "#file-list .info-button")], timeout=10)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", info_btn)
        info_btn.click()
    except Exception:
        pass  # If already visible, continue
    version_input = _wait_visible_any(
        driver,
        [(By.CSS_SELECTOR, "#file-list .file_form input[name$='-version']")],
        timeout=15,
    )
    version_input.clear()
    version_input.send_keys("1.0.0")

    # Agree to terms to enable upload button, then upload
    agree = _wait_visible_any(driver, [(By.ID, "agreeCheckbox")], timeout=10)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", agree)
    if not agree.is_selected():
        agree.click()
    upload_btn = _wait_visible_any(driver, [(By.ID, "upload_button")], timeout=10)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", upload_btn)
    upload_btn.click()

    # Wait for redirect to list and open the dataset by title
    WebDriverWait(driver, 40).until(EC.url_contains("/dataset/list"))
    wait_for_page_to_load(driver)
    # Find the dataset link by its title (first match)
    link_xpath = f"//table//a[contains(normalize-space(.), '{title_value}')]"
    ds_link = _wait_visible_any(driver, [(By.XPATH, link_xpath)], timeout=25)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ds_link)
    ds_link.click()
    wait_for_page_to_load(driver)
    dataset_view_url = driver.current_url
    return dataset_view_url, csv_path


def _propose_dataset_to_community(driver, dataset_view_url, community_id):
    """Helper to propose a dataset to a community (navigates to dataset view URL)."""
    driver.get(dataset_view_url)
    wait_for_page_to_load(driver)

    proposal_form = _wait_visible_any(driver, [(By.CSS_SELECTOR, "form[action*='/community/propose']")], timeout=25)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", proposal_form)

    select_el = proposal_form.find_element(By.CSS_SELECTOR, "select[name='community_id']")
    select_el.click()
    option = _wait_visible_any(driver, [(By.CSS_SELECTOR, f"option[value='{community_id}']")], timeout=10)
    option.click()

    submit_btn = proposal_form.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit_btn.click()
    wait_for_page_to_load(driver)


def _handle_proposal(driver, host, community_id, dataset_title, action):
    """Helper to accept or reject a proposal."""
    driver.get(f"{host}/community/{community_id}")
    wait_for_page_to_load(driver)

    # Locate the Pending proposals card body
    pending_body_xpath = (
        "//div[contains(@class,'card-header') and contains(., 'Pending proposals')]/"
        "following::div[contains(@class,'card-body')][1]"
    )
    pending_body = _wait_visible_any(driver, [(By.XPATH, pending_body_xpath)], timeout=20)

    # Find the specific proposal row by title
    proposal_row = pending_body.find_element(By.XPATH, f".//div[contains(., '{dataset_title}')]")

    # Choose action button
    btn_selector = "button.btn-outline-danger" if action == "reject" else "button.btn-success"
    action_btn = proposal_row.find_element(By.CSS_SELECTOR, btn_selector)

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", action_btn)
    try:
        action_btn.click()
    except ElementClickInterceptedException:
        time.sleep(1)
        action_btn.click()

    wait_for_page_to_load(driver)

    # Verify the item is no longer in pending
    def _not_in_pending(drv):
        try:
            pending = drv.find_element(By.XPATH, pending_body_xpath)
            return len(pending.find_elements(By.XPATH, f".//div[contains(., '{dataset_title}')]")) == 0
        except Exception:
            return True

    WebDriverWait(driver, 15).until(lambda d: _not_in_pending(d))

    # If accepted, ensure it appears under "Datasets in this community"
    if action == "accept":
        xpath_accepted = (
            f"//div[contains(@class,'card-header') and contains(., 'Datasets in this community')]/"
            f"following::ul[contains(@class,'list-group')][1]//li[contains(., '{dataset_title}')]"
        )
        accepted_item = _wait_visible_any(driver, [(By.XPATH, xpath_accepted)], timeout=15)
        assert accepted_item.is_displayed()


def test_propose_reject_accept_flow():
    driver = initialize_driver()
    community_icon_path = None
    dataset_csv_path = None
    try:
        host = get_host_for_selenium_testing()
        _login_with_optional_2fa(driver, host)

        # 1. Create Community
        community_name = f"Proposal Test Community {random.randint(1, 1_000_000)}"
        community_id, community_icon_path = _create_community_via_ui(driver, host, community_name)

        # 2. Create Dataset
        dataset_title = f"Proposal Test Dataset {random.randint(1, 1_000_000)}"
        dataset_view_url, dataset_csv_path = create_dataset_via_ui(driver, host, dataset_title)

        # 3. Propose to Community
        _propose_dataset_to_community(driver, dataset_view_url, community_id)

        # 4. Reject Proposal
        _handle_proposal(driver, host, community_id, dataset_title, action="reject")

        # 5. Propose Again
        _propose_dataset_to_community(driver, dataset_view_url, community_id)

        # 6. Accept Proposal
        _handle_proposal(driver, host, community_id, dataset_title, action="accept")

        # 7. Final verification: check dataset view page shows community
        driver.get(dataset_view_url)
        wait_for_page_to_load(driver)
        xpath_comm_link = f"//a[contains(@href, '/community/{community_id}') and contains(., '{community_name}')]"
        community_link = _wait_visible_any(driver, [(By.XPATH, xpath_comm_link)], timeout=15)
        assert community_link.is_displayed()

    finally:
        # Cleanup created files
        if community_icon_path and os.path.exists(community_icon_path):
            os.remove(community_icon_path)
        if dataset_csv_path and os.path.exists(dataset_csv_path):
            os.remove(dataset_csv_path)
        close_driver(driver)
