import time
import base64
import os
import multiprocessing
import numpy as np
import cv2
import easyocr
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
if not N8N_WEBHOOK_URL:
    print("WARNING: N8N_WEBHOOK_URL not found in environment variables.")


def log_listener(queue, log_file_path):
    """Listens for log messages on a queue and writes them to a file and console."""
    with open(log_file_path, "a", encoding="utf-8") as f:
        while True:
            try:
                record = queue.get()
                if record is None:
                    break
                f.write(record['text'] + "\n")
                f.flush()
                print(record['color_text'])
            except Exception as e:
                print(f"Logging error: {e}")


def log(message, verbose=False, instance_id=None, log_queue=None):
    """Helper for conditional logging with instance ID, color coding, and queue support."""
    RESET = "\033[0m"
    COLORS = [
        "\033[36m", "\033[35m", "\033[32m", "\033[33m",
        "\033[34m", "\033[31m", "\033[96m", "\033[95m",
        "\033[92m", "\033[93m", "\033[94m", "\033[91m",
    ]

    color = ""
    prefix = ""
    reset = ""

    if instance_id is not None:
        color = COLORS[(instance_id - 1) % len(COLORS)]
        prefix = f"[Instance {instance_id}] "
        reset = RESET

    plain_prefix = f"[Instance {instance_id}] " if instance_id is not None else ""
    verbose_tag = "[VERBOSE] " if verbose else ""

    plain_text = f"{plain_prefix}{verbose_tag}{message}"
    color_text = f"{color}{prefix}{verbose_tag}{message}{reset}"

    if log_queue:
        log_queue.put({'text': plain_text, 'color_text': color_text})
    else:
        print(color_text)


def select_mat_option(driver, wait, select_element, option_index, description="", verbose=False, instance_id=None, log_queue=None):
    """Helper to click a mat-select and choose an option by index."""
    log(f"Targeting dropdown: {description}", verbose, instance_id, log_queue)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_element)
    time.sleep(0.5)
    try:
        wait.until(EC.element_to_be_clickable(select_element))
        select_element.click()
        log(f"Clicked {description}. Waiting for options...", verbose, instance_id, log_queue)
    except Exception as e:
        log(f"Failed to click {description}: {e}", verbose, instance_id, log_queue)
        driver.execute_script("arguments[0].click();", select_element)

    time.sleep(0.5)
    try:
        options = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-option")))
        if len(options) >= option_index:
            driver.execute_script("arguments[0].click();", options[option_index - 1])
            log(f"Option {option_index} selected for {description}.", verbose, instance_id, log_queue)
        else:
            log(f"Error: Found {len(options)} options, needed {option_index}", verbose, instance_id, log_queue)
    except Exception as e:
        log(f"Error selecting option: {e}", verbose, instance_id, log_queue)


def solve_captcha(driver, wait, reader, verbose=False, instance_id=None, log_queue=None):
    """Finds the CAPTCHA image, performs OCR with EasyOCR, and fills the input field."""
    try:
        log("Locating CAPTCHA image...", verbose, instance_id, log_queue)
        captcha_img = wait.until(EC.presence_of_element_located((By.XPATH, "//img[@alt='Weryfikacja obrazkowa']")))

        img_base64 = captcha_img.get_attribute("src")
        if "base64," in img_base64:
            base64_data = img_base64.split("base64,")[1]
            img_bytes = base64.b64decode(base64_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            upscaled = cv2.resize(denoised, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

            results = reader.readtext(upscaled, detail=0, allowlist='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
            captcha_text = "".join(results).strip()

            log(f">>> EASYOCR RESULT: '{captcha_text}' <<<", verbose, instance_id, log_queue)

            captcha_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Znaki z obrazka']")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_input)
            time.sleep(0.3)
            captcha_input.click()
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)

            log("CAPTCHA field filled.", verbose, instance_id, log_queue)
            return True
    except Exception as e:
        log(f"Failed to solve CAPTCHA: {e}", verbose, instance_id, log_queue)
        return False


def check_for_failure(driver, verbose=False, instance_id=None, log_queue=None):
    """Checks for error messages or popups indicating CAPTCHA failure."""
    error_keywords = ["Nieprawidłowy", "Błędne", "kod", "Błąd"]
    error_elements = driver.find_elements(By.XPATH, "//mat-snack-bar-container|//mat-dialog-container|//div[contains(@class, 'error')]")
    for element in error_elements:
        if element.is_displayed():
            log(f"Found error element text: {element.text}", verbose, instance_id, log_queue)
            if any(kw in element.text for kw in error_keywords):
                return True
    page_text = driver.page_source
    if "Nieprawidłowy kod" in page_text or "Błędne znaki" in page_text:
        log("Detected CAPTCHA error text in page source.", verbose, instance_id, log_queue)
        return True
    return False


def trigger_webhook(verbose=False, instance_id=None, log_queue=None):
    """Triggers the n8n webhook via a POST request."""
    try:
        log(f"Triggering n8n webhook at {N8N_WEBHOOK_URL}...", verbose, instance_id, log_queue)
        response = requests.post(N8N_WEBHOOK_URL, json={"status": "appointments_found", "source": "e-konsulat_automation", "instance": instance_id})
        if response.status_code == 200:
            log("Webhook triggered successfully.", verbose, instance_id, log_queue)
        else:
            log(f"Webhook failed with status code: {response.status_code}", verbose, instance_id, log_queue)
    except Exception as e:
        log(f"Error triggering webhook: {e}", verbose, instance_id, log_queue)


def run_scraper(instance_id, config, stop_event, driver_path, log_queue):
    """
    Run a single scraper attempt. No outer loop — checks once.

    config: dict with keys:
        - verbose (bool): enable verbose logging
        - test (bool): test mode

    Returns a dict with result info:
        - status: 'no_appointments' | 'appointments_found' | 'error'
        - attempts: number of CAPTCHA attempts
        - duration: time in seconds
        - screenshot: path to screenshot if saved
    """
    verbose = config.get('verbose', False)
    test_mode = config.get('test', False)

    log(f"Initializing EasyOCR for Instance {instance_id}...", verbose, instance_id, log_queue)
    reader = easyocr.Reader(['en'], gpu=False)

    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 15)

    url = "https://secure.e-konsulat.gov.pl/placowki/164/sprawy-paszportowe/wizyty/formularz"

    start_time = time.time()
    captcha_attempts = 0
    result = {'status': 'error', 'attempts': 0, 'duration': 0, 'screenshot': None}

    try:
        if stop_event.is_set():
            driver.quit()
            result['status'] = 'stopped'
            return result

        log(f"Opening {url}...", verbose, instance_id, log_queue)
        driver.get(url)

        # Wait for page elements instead of fixed sleep
        log("Waiting for page to load...", verbose, instance_id, log_queue)
        wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-select")))
        time.sleep(1)
        if stop_event.is_set():
            driver.quit()
            result['status'] = 'stopped'
            return result

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)

        # Handle initial dropdowns
        try:
            all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
            log(f"Found {len(all_selects)} mat-select elements.", verbose, instance_id, log_queue)
            if len(all_selects) >= 3:
                select_mat_option(driver, wait, all_selects[1], 2, "First Form Dropdown", verbose, instance_id, log_queue)
                time.sleep(1)
                if stop_event.is_set():
                    driver.quit()
                    result['status'] = 'stopped'
                    return result
                all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
                if len(all_selects) >= 3:
                    select_mat_option(driver, wait, all_selects[2], 2, "Second Form Dropdown", verbose, instance_id, log_queue)
            else:
                log("Could not find expected dropdowns.", verbose, instance_id, log_queue)
                result['status'] = 'error'
                result['duration'] = time.time() - start_time
                driver.quit()
                return result
        except Exception as e:
            log(f"Error selecting options: {e}", verbose, instance_id, log_queue)
            result['status'] = 'error'
            result['duration'] = time.time() - start_time
            driver.quit()
            return result

        time.sleep(1)
        if stop_event.is_set():
            driver.quit()
            result['status'] = 'stopped'
            return result

        # CAPTCHA retry loop (single attempt at checking appointments, but CAPTCHA may need retries)
        success = False
        while not stop_event.is_set():
            solve_captcha(driver, wait, reader, verbose, instance_id, log_queue)
            captcha_attempts += 1
            log("Clicking 'Pobierz terminy wizyty'...", verbose, instance_id, log_queue)
            try:
                submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Pobierz terminy wizyty')]")))
                driver.execute_script("arguments[0].click();", submit_button)
            except Exception as e:
                log(f"Error finding submit button: {e}", verbose, instance_id, log_queue)
                break

            log("Waiting for response...", verbose, instance_id, log_queue)
            time.sleep(2)
            if stop_event.is_set():
                break

            # 1. Check for CAPTCHA failure
            if check_for_failure(driver, verbose, instance_id, log_queue):
                log("CAPTCHA failure detected. Retrying...", verbose, instance_id, log_queue)
                try:
                    captcha_img = driver.find_element(By.XPATH, "//img[@alt='Weryfikacja obrazkowa']")
                    captcha_img.click()
                    time.sleep(0.5)
                except:
                    pass
                continue

            # 2. Check for "No appointments" text
            no_appointments_text = "Chwilowo wszystkie udostępnione terminy zostały zarezerwowane, prosimy spróbować umówić wizytę w terminie późniejszym."
            if no_appointments_text in driver.page_source:
                log("[RESULT] No appointments available.", verbose, instance_id, log_queue)
                success = False
                break

            # 3. Check for appointment dropdowns (5+ mat-selects)
            current_selects = driver.find_elements(By.TAG_NAME, "mat-select")
            if len(current_selects) >= 5:
                log(f"[ALERT] {len(current_selects)} dropdowns found! Appointments are available!", verbose, instance_id, log_queue)

                # Auto-select first option in the two new appointment dropdowns
                try:
                    log("Selecting first option in Appointment Dropdown 1...", verbose, instance_id, log_queue)
                    select_mat_option(driver, wait, current_selects[3], 1, "Appointment Dropdown 1", verbose, instance_id, log_queue)
                    time.sleep(0.5)

                    # Re-query after DOM change
                    current_selects = driver.find_elements(By.TAG_NAME, "mat-select")
                    log("Selecting first option in Appointment Dropdown 2...", verbose, instance_id, log_queue)
                    select_mat_option(driver, wait, current_selects[4], 1, "Appointment Dropdown 2", verbose, instance_id, log_queue)
                    time.sleep(0.5)

                    # Click the submit/confirm button
                    log("Clicking submit/confirm button...", verbose, instance_id, log_queue)
                    confirm_btn = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(., 'Zatwierdź') or contains(., 'Rezerwuj') or contains(., 'Zapisz') or contains(., 'Potwierdź')]")
                    ))
                    driver.execute_script("arguments[0].click();", confirm_btn)
                    time.sleep(1)
                    log("Appointment submitted!", verbose, instance_id, log_queue)
                except Exception as e:
                    log(f"Error during appointment auto-submit: {e}", verbose, instance_id, log_queue)

                trigger_webhook(verbose, instance_id, log_queue)
                stop_event.set()
                success = True
                break

            # 4. Check if submit button still present (retry CAPTCHA)
            try:
                submit_button = driver.find_element(By.XPATH, "//button[contains(., 'Pobierz terminy wizyty')]")
                if submit_button.is_displayed():
                    log("Submit button still present, retrying CAPTCHA...", verbose, instance_id, log_queue)
                    continue
            except:
                log("Button gone, waiting for dropdowns...", verbose, instance_id, log_queue)
                time.sleep(1)
                continue

        # Save results
        duration = time.time() - start_time
        result['attempts'] = captcha_attempts
        result['duration'] = duration

        if success:
            result['status'] = 'appointments_found'
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            os.makedirs("results", exist_ok=True)
            screenshot_name = f"results/appointments_found_inst{instance_id}_{timestamp}.png"
            try:
                driver.save_screenshot(screenshot_name)
                result['screenshot'] = screenshot_name
                log(f"Screenshot saved as {screenshot_name}", False, instance_id, log_queue)
            except Exception as e:
                log(f"Failed to save screenshot: {e}", False, instance_id, log_queue)

            log("\n" + "=" * 40, False, instance_id, log_queue)
            log("SUCCESSFUL RUN SUMMARY", False, instance_id, log_queue)
            log(f"Total time: {duration / 60:.2f} minutes", False, instance_id, log_queue)
            log(f"CAPTCHA attempts: {captcha_attempts}", False, instance_id, log_queue)
            log("=" * 40, False, instance_id, log_queue)

            # Keep browser open
            while not stop_event.is_set():
                time.sleep(1)
        else:
            result['status'] = 'no_appointments'
            if test_mode:
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                os.makedirs("results", exist_ok=True)
                screenshot_name = f"results/test_result_inst{instance_id}_{timestamp}.png"
                try:
                    driver.save_screenshot(screenshot_name)
                    result['screenshot'] = screenshot_name
                    log(f"Test screenshot saved as {screenshot_name}", verbose, instance_id, log_queue)
                except Exception as e:
                    log(f"Failed to save test screenshot: {e}", verbose, instance_id, log_queue)

            log("\n" + "=" * 40, False, instance_id, log_queue)
            log("RUN SUMMARY", False, instance_id, log_queue)
            log(f"Status: {'NO APPOINTMENTS' if result['status'] == 'no_appointments' else result['status']}", False, instance_id, log_queue)
            log(f"Total time: {duration / 60:.2f} minutes", False, instance_id, log_queue)
            log(f"CAPTCHA attempts: {captcha_attempts}", False, instance_id, log_queue)
            log("=" * 40, False, instance_id, log_queue)
            driver.quit()

    except Exception as e:
        log(f"An error occurred: {e}", False, instance_id, log_queue)
        result['status'] = 'error'
        result['duration'] = time.time() - start_time
        result['attempts'] = captcha_attempts
        try:
            driver.quit()
        except:
            pass

    return result


def main():
    """CLI entry point — still works for direct command-line usage."""
    import argparse
    parser = argparse.ArgumentParser(description="E-Konsulat Appointment Scraper")
    parser.add_argument("-t", "--test", action="store_true", help="Run once with verbose logging")
    parser.add_argument("-n", "--instances", type=int, default=1, help="Number of parallel instances")
    args = parser.parse_args()

    config = {'verbose': args.test, 'test': args.test}
    num_instances = args.instances

    os.makedirs("logs", exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_file_path = f"logs/log_{timestamp}.txt"

    log_queue = multiprocessing.Queue()
    listener = multiprocessing.Process(target=log_listener, args=(log_queue, log_file_path))
    listener.start()

    log(f"Starting {num_instances} instance(s)...", log_queue=log_queue)
    log(f"Log file: {log_file_path}", log_queue=log_queue)

    print("Pre-installing ChromeDriver...")
    driver_path = ChromeDriverManager().install()
    print(f"Driver installed at: {driver_path}")

    stop_event = multiprocessing.Event()
    processes = []

    try:
        for i in range(num_instances):
            p = multiprocessing.Process(target=run_scraper, args=(i + 1, config, stop_event, driver_path, log_queue))
            p.start()
            processes.append(p)
            if i < num_instances - 1:
                time.sleep(1)

        for p in processes:
            p.join()

    except KeyboardInterrupt:
        log("\nInterrupted by user. Stopping all instances...", log_queue=log_queue)
        stop_event.set()
        for p in processes:
            p.terminate()
            p.join()
        log("All instances stopped.", log_queue=log_queue)
    finally:
        log_queue.put(None)
        listener.join()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
