import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.environment.host import get_host_for_selenium_testing
from core.selenium.common import close_driver, initialize_driver


def test_explore_page_filters():
    driver = initialize_driver()
    try:
        # --- 1. Ir a la página Explore ---
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/explore")

        # --- 2. Verificar encabezado principal ---
        heading = driver.find_element(By.XPATH, "//h1[contains(., 'Explore')]")
        assert heading.is_displayed(), "El encabezado 'Explore' no se muestra"

        # --- 3. Verificar existencia de campos de filtro ---
        filter_fields = ["query", "author", "tags", "filenames", "community"]
        for fid in filter_fields:
            el = driver.find_element(By.ID, fid)
            assert el.is_displayed(), f"El filtro '{fid}' no se encuentra visible"

        # --- 4. Escribir en filtros principales ---
        # Se escriben valores de prueba en author, tags y filenames (mejora sobre versión anterior)
        test_inputs = {
            "query": "Sample dataset 1",
            "author": "Author 1",
            "tags": "tag1, tag2",
            "filenames": "file1.csv, file2.csv",
        }

        for fid, value in test_inputs.items():
            el = driver.find_element(By.ID, fid)
            el.clear()
            el.send_keys(value)
            el.send_keys(Keys.RETURN)

        # --- 5. Rellenar fechas ---
        driver.find_element(By.ID, "date_from_day").send_keys("01")
        driver.find_element(By.ID, "date_from_month").send_keys("01")
        driver.find_element(By.ID, "date_from_year").send_keys("2020")

        driver.find_element(By.ID, "date_to_day").send_keys("10")
        driver.find_element(By.ID, "date_to_month").send_keys("12")
        driver.find_element(By.ID, "date_to_year").send_keys("2024")

        # --- 6. Rellenar filtros numéricos ---
        driver.find_element(By.ID, "min_downloads").send_keys("10")
        driver.find_element(By.ID, "min_views").send_keys("100")

        # --- 7. Esperar resultados y validar existencia de contador ---
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "results_number")))
        results = driver.find_element(By.ID, "results_number")
        assert results.is_displayed(), "No se muestra el contador de resultados"

        # --- 8. Limpiar filtros ---
        clear_btn = driver.find_element(By.ID, "clear-filters")
        clear_btn.click()

        # --- 9. Verificar que los campos se vacíen ---
        time.sleep(1)  # esperar reacción de la UI
        for fid in ["query", "author", "tags", "filenames"]:
            el = driver.find_element(By.ID, fid)
            assert el.get_attribute("value") == "", f"El campo '{fid}' no se limpió"

        print("✅ Test Explore completado correctamente: filtros y resultados funcionando.")
    finally:
        close_driver(driver)


test_explore_page_filters()
