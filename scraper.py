import time
import base64
import io
import os
import argparse
import numpy as np
import cv2
import easyocr
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Webhook URL for n8n
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

if not N8N_WEBHOOK_URL:
    print("WARNING: N8N_WEBHOOK_URL not found in environment variables.")

# Initialize EasyOCR Reader
print("Initializing EasyOCR...")
reader = easyocr.Reader(['en'])

def log(message, verbose=False):
    """Helper for conditional logging."""
    if verbose:
        print(f"[VERBOSE] {message}")
    else:
        print(message)

def select_mat_option(driver, wait, select_element, option_index, description="", verbose=False):
    """Helper to click a mat-select and choose an option by index."""
    log(f"Targeting dropdown: {description}", verbose)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_element)
    time.sleep(1.5) 
    try:
        wait.until(EC.element_to_be_clickable(select_element))
        select_element.click()
        log(f"Clicked {description}. Waiting for options...", verbose)
    except Exception as e:
        log(f"Failed to click {description}: {e}", verbose)
        driver.execute_script("arguments[0].click();", select_element)

    time.sleep(2)
    try:
        options = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-option")))
        if len(options) >= option_index:
            driver.execute_script("arguments[0].click();", options[option_index - 1])
            log(f"Option {option_index} selected for {description}.", verbose)
        else:
            log(f"Error: Found {len(options)} options, needed {option_index}", verbose)
    except Exception as e:
        log(f"Error selecting option: {e}", verbose)

def solve_captcha(driver, wait, verbose=False):
    """Finds the CAPTCHA image, performs OCR with EasyOCR, and fills the input field."""
    try:
        log("Locating CAPTCHA image...", verbose)
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
            
            log(f"\n>>> EASYOCR RESULT: '{captcha_text}' <<<\n", verbose)
            
            captcha_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Znaki z obrazka']")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_input)
            time.sleep(1)
            captcha_input.click()
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            
            log(f"CAPTCHA field filled.", verbose)
            return True
    except Exception as e:
        log(f"Failed to solve CAPTCHA: {e}", verbose)
        return False

def check_for_failure(driver, verbose=False):
    """Checks for error messages or popups indicating CAPTCHA failure."""
    error_keywords = ["Nieprawidłowy", "Błędne", "kod", "Błąd"]
    error_elements = driver.find_elements(By.XPATH, "//mat-snack-bar-container|//mat-dialog-container|//div[contains(@class, 'error')]")
    for element in error_elements:
        if element.is_displayed():
            log(f"Found error element text: {element.text}", verbose)
            if any(kw in element.text for kw in error_keywords):
                return True
    page_text = driver.page_source
    if "Nieprawidłowy kod" in page_text or "Błędne znaki" in page_text:
        log("Detected CAPTCHA error text in page source.", verbose)
        return True
    return False

def trigger_webhook(verbose=False):
    """Triggers the n8n webhook via a POST request."""
    try:
        log(f"Triggering n8n webhook at {N8N_WEBHOOK_URL}...", verbose)
        response = requests.post(N8N_WEBHOOK_URL, json={"status": "appointments_found", "source": "e-konsulat_automation"})
        if response.status_code == 200:
            log("Webhook triggered successfully.", verbose)
        else:
            log(f"Webhook failed with status code: {response.status_code}", verbose)
    except Exception as e:
        log(f"Error triggering webhook: {e}", verbose)

import time
import base64
import io
import os
import argparse
import multiprocessing
import numpy as np
import cv2
import easyocr
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Webhook URL for n8n
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

if not N8N_WEBHOOK_URL:
    print("WARNING: N8N_WEBHOOK_URL not found in environment variables.")

# Initialize EasyOCR Reader
print("Initializing EasyOCR...")
reader = easyocr.Reader(['en'])

def log(message, verbose=False, instance_id=None):
    """Helper for conditional logging with instance ID."""
    prefix = f"[Instance {instance_id}] " if instance_id is not None else ""
    if verbose:
        print(f"{prefix}[VERBOSE] {message}")
    else:
        print(f"{prefix}{message}")

def select_mat_option(driver, wait, select_element, option_index, description="", verbose=False, instance_id=None):
    """Helper to click a mat-select and choose an option by index."""
    log(f"Targeting dropdown: {description}", verbose, instance_id)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_element)
    time.sleep(1.5) 
    try:
        wait.until(EC.element_to_be_clickable(select_element))
        select_element.click()
        log(f"Clicked {description}. Waiting for options...", verbose, instance_id)
    except Exception as e:
        log(f"Failed to click {description}: {e}", verbose, instance_id)
        driver.execute_script("arguments[0].click();", select_element)

    time.sleep(2)
    try:
        options = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-option")))
        if len(options) >= option_index:
            driver.execute_script("arguments[0].click();", options[option_index - 1])
            log(f"Option {option_index} selected for {description}.", verbose, instance_id)
        else:
            log(f"Error: Found {len(options)} options, needed {option_index}", verbose, instance_id)
    except Exception as e:
        log(f"Error selecting option: {e}", verbose, instance_id)

def solve_captcha(driver, wait, verbose=False, instance_id=None):
    """Finds the CAPTCHA image, performs OCR with EasyOCR, and fills the input field."""
    try:
        log("Locating CAPTCHA image...", verbose, instance_id)
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
            
            log(f"\n>>> EASYOCR RESULT: '{captcha_text}' <<<\n", verbose, instance_id)
            
            captcha_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Znaki z obrazka']")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_input)
            time.sleep(1)
            captcha_input.click()
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            
            log(f"CAPTCHA field filled.", verbose, instance_id)
            return True
    except Exception as e:
        log(f"Failed to solve CAPTCHA: {e}", verbose, instance_id)
        return False

def check_for_failure(driver, verbose=False, instance_id=None):
    """Checks for error messages or popups indicating CAPTCHA failure."""
    error_keywords = ["Nieprawidłowy", "Błędne", "kod", "Błąd"]
    error_elements = driver.find_elements(By.XPATH, "//mat-snack-bar-container|//mat-dialog-container|//div[contains(@class, 'error')]")
    for element in error_elements:
        if element.is_displayed():
            log(f"Found error element text: {element.text}", verbose, instance_id)
            if any(kw in element.text for kw in error_keywords):
                return True
    page_text = driver.page_source
    if "Nieprawidłowy kod" in page_text or "Błędne znaki" in page_text:
        log("Detected CAPTCHA error text in page source.", verbose, instance_id)
        return True
    return False

def trigger_webhook(verbose=False, instance_id=None):
    """Triggers the n8n webhook via a POST request."""
    try:
        log(f"Triggering n8n webhook at {N8N_WEBHOOK_URL}...", verbose, instance_id)
        response = requests.post(N8N_WEBHOOK_URL, json={"status": "appointments_found", "source": "e-konsulat_automation", "instance": instance_id})
        if response.status_code == 200:
            log("Webhook triggered successfully.", verbose, instance_id)
        else:
            log(f"Webhook failed with status code: {response.status_code}", verbose, instance_id)
    except Exception as e:
        log(f"Error triggering webhook: {e}", verbose, instance_id)

def run_scraper(instance_id, args, stop_event):
    verbose = args.test
    chrome_options = Options()
    if not args.test:
        # If not testing, maybe we want headless to not clutter? 
        # But user didn't ask, so keeping visible for now.
        pass
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    
    # Optional: reduce log noise from selenium/chrome
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 20)

    url = "https://secure.e-konsulat.gov.pl/placowki/164/sprawy-paszportowe/wizyty/formularz"
    
    start_time = time.time()
    attempts = 0
    captcha_solved = 0

    try:
        while not stop_event.is_set():
            attempts += 1
            log(f"\n--- Starting attempt #{attempts} at {time.strftime('%H:%M:%S')} ---", verbose, instance_id)
            log(f"Opening {url}...", verbose, instance_id)
            driver.get(url)

            log("Waiting 8 seconds for page load...", verbose, instance_id)
            time.sleep(8)
            if stop_event.is_set(): break
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Handle dropdowns
            try:
                all_selects = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-select")))
                log(f"Found {len(all_selects)} mat-select elements.", verbose, instance_id)
                if len(all_selects) >= 3:
                    select_mat_option(driver, wait, all_selects[1], 2, "First Form Dropdown", verbose, instance_id)
                    time.sleep(5)
                    if stop_event.is_set(): break
                    all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
                    if len(all_selects) >= 3:
                        select_mat_option(driver, wait, all_selects[2], 2, "Second Form Dropdown", verbose, instance_id)
                else:
                    log("Could not find expected dropdowns. Refreshing...", verbose, instance_id)
                    if args.test: break
                    continue
            except Exception as e:
                log(f"Error selecting options: {e}. Refreshing...", verbose, instance_id)
                if args.test: break
                continue
            
            time.sleep(3)
            if stop_event.is_set(): break
            
            success = False
            while not stop_event.is_set():
                solve_captcha(driver, wait, verbose, instance_id)
                captcha_solved += 1
                log("Clicking 'Pobierz terminy wizyty'...", verbose, instance_id)
                try:
                    submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Pobierz terminy wizyty')]")))
                    driver.execute_script("arguments[0].click();", submit_button)
                except Exception as e:
                    log(f"Error finding submit button: {e}. Restarting process...", verbose, instance_id)
                    break # Restart whole process

                log("Waiting for response...", verbose, instance_id)
                time.sleep(5)
                if stop_event.is_set(): break
                
                # 1. Check for CAPTCHA failure
                if check_for_failure(driver, verbose, instance_id):
                    log("CAPTCHA failure detected. Retrying...", verbose, instance_id)
                    try:
                        captcha_img = driver.find_element(By.XPATH, "//img[@alt='Weryfikacja obrazkowa']")
                        captcha_img.click()
                        time.sleep(2)
                    except: pass
                    continue
                
                # 2. Check for "No appointments" text
                no_appointments_text = "Chwilowo wszystkie udostępnione terminy zostały zarezerwowane, prosimy spróbować umówić wizytę w terminie późniejszym."
                if no_appointments_text in driver.page_source:
                    log("\n[RESULT] No appointments available.", verbose, instance_id)
                    if args.test:
                        success = False
                        break # Break inner loop
                    else:
                        log("Refreshing page and restarting process...", verbose, instance_id)
                        break # Break inner loop to restart the whole process
                
                # 3. Check if the button is still there (another failure mode)
                try:
                    submit_button = driver.find_element(By.XPATH, "//button[contains(., 'Pobierz terminy wizyty')]")
                    if submit_button.is_displayed():
                        log("Submit button still present, retrying CAPTCHA...", verbose, instance_id)
                        continue
                except:
                    # Button is gone - potentially success!
                    log("\n[ALERT] Appointments might be available! Triggering webhook and leaving session open.", verbose, instance_id)
                    trigger_webhook(verbose, instance_id)
                    stop_event.set() # STOP ALL OTHER INSTANCES
                    success = True
                    break

            if args.test:
                # In test mode, we take a screenshot no matter what
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                os.makedirs("results", exist_ok=True)
                screenshot_name = f"results/test_result_inst{instance_id}_{timestamp}.png"
                try:
                    driver.save_screenshot(screenshot_name)
                    log(f"Test screenshot saved as {screenshot_name}", verbose, instance_id)
                except Exception as e:
                    log(f"Failed to save test screenshot: {e}", verbose, instance_id)
                
                end_time = time.time()
                duration = end_time - start_time
                log("\n" + "="*40, verbose, instance_id)
                log("TEST RUN SUMMARY", verbose, instance_id)
                log(f"Status: {'SUCCESS' if success else 'FAILURE/NO APPOINTMENTS'}", verbose, instance_id)
                log(f"Total time: {duration/60:.2f} minutes", verbose, instance_id)
                log(f"CAPTCHA attempts: {captcha_solved}", verbose, instance_id)
                log("="*40, verbose, instance_id)
                return

            if success:
                # This block only reached if not in test mode and success is True
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                os.makedirs("results", exist_ok=True)
                screenshot_name = f"results/appointments_found_inst{instance_id}_{timestamp}.png"
                try:
                    driver.save_screenshot(screenshot_name)
                    print(f"[Instance {instance_id}] Screenshot saved as {screenshot_name}")
                except Exception as e:
                    print(f"[Instance {instance_id}] Failed to save screenshot: {e}")

                end_time = time.time()
                duration = end_time - start_time
                print("\n" + "="*40)
                print(f"SUCCESSFUL RUN SUMMARY (Instance {instance_id})")
                print(f"Total time: {duration/60:.2f} minutes")
                print(f"Total attempts: {attempts}")
                print(f"CAPTCHA attempts: {captcha_solved}")
                print("="*40)
                # Keep browser open as before
                while True: time.sleep(1)

        if stop_event.is_set() and not success:
            log("Stopping instance because another one succeeded or user interrupted.", False, instance_id)
            driver.quit()

    except Exception as e:
        log(f"An error occurred: {e}", False, instance_id)
        driver.quit()

def main():
    parser = argparse.ArgumentParser(description="E-Konsulat Appointment Scraper")
    parser.add_argument("-t", "--test", action="store_true", help="Run once for testing, take a screenshot, and use extensive logging")
    parser.add_argument("-n", "--instances", type=int, default=1, help="Number of parallel instances to run")
    args = parser.parse_args()

    num_instances = args.instances
    print(f"Starting {num_instances} parallel instances...")

    stop_event = multiprocessing.Event()
    processes = []

    try:
        for i in range(num_instances):
            p = multiprocessing.Process(target=run_scraper, args=(i+1, args, stop_event))
            p.start()
            processes.append(p)
            time.sleep(2) # Stagger start to avoid collision on same resources/network

        # Wait for processes
        for p in processes:
            p.join()

    except KeyboardInterrupt:
        print("\nMain script interrupted by user. Stopping all instances...")
        stop_event.set()
        for p in processes:
            p.terminate()
            p.join()
        print("All instances stopped.")

if __name__ == "__main__":
    # Fix for multiprocessing with easyocr and spawn
    multiprocessing.freeze_support()
    main()
