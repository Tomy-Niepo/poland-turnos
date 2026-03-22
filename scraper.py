import time
import base64
import io
import os
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

def select_mat_option(driver, wait, select_element, option_index, description=""):
    """Helper to click a mat-select and choose an option by index."""
    print(f"Targeting dropdown: {description}")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_element)
    time.sleep(1.5) 
    try:
        wait.until(EC.element_to_be_clickable(select_element))
        select_element.click()
        print(f"Clicked {description}. Waiting for options...")
    except Exception as e:
        print(f"Failed to click {description}: {e}")
        driver.execute_script("arguments[0].click();", select_element)

    time.sleep(2)
    try:
        options = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-option")))
        if len(options) >= option_index:
            driver.execute_script("arguments[0].click();", options[option_index - 1])
            print(f"Option {option_index} selected for {description}.")
        else:
            print(f"Error: Found {len(options)} options, needed {option_index}")
    except Exception as e:
        print(f"Error selecting option: {e}")

def solve_captcha(driver, wait):
    """Finds the CAPTCHA image, performs OCR with EasyOCR, and fills the input field."""
    try:
        print("Locating CAPTCHA image...")
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
            
            print(f"\n>>> EASYOCR RESULT: '{captcha_text}' <<<\n")
            
            captcha_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Znaki z obrazka']")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_input)
            time.sleep(1)
            captcha_input.click()
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            
            print(f"CAPTCHA field filled.")
            return True
    except Exception as e:
        print(f"Failed to solve CAPTCHA: {e}")
        return False

def check_for_failure(driver):
    """Checks for error messages or popups indicating CAPTCHA failure."""
    error_keywords = ["Nieprawidłowy", "Błędne", "kod", "Błąd"]
    error_elements = driver.find_elements(By.XPATH, "//mat-snack-bar-container|//mat-dialog-container|//div[contains(@class, 'error')]")
    for element in error_elements:
        if element.is_displayed():
            if any(kw in element.text for kw in error_keywords):
                return True
    page_text = driver.page_source
    if "Nieprawidłowy kod" in page_text or "Błędne znaki" in page_text:
        return True
    return False

def trigger_webhook():
    """Triggers the n8n webhook via a POST request."""
    try:
        print(f"Triggering n8n webhook at {N8N_WEBHOOK_URL}...")
        response = requests.post(N8N_WEBHOOK_URL, json={"status": "appointments_found", "source": "e-konsulat_automation"})
        if response.status_code == 200:
            print("Webhook triggered successfully.")
        else:
            print(f"Webhook failed with status code: {response.status_code}")
    except Exception as e:
        print(f"Error triggering webhook: {e}")

def main():
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 20)

    url = "https://secure.e-konsulat.gov.pl/placowki/164/sprawy-paszportowe/wizyty/formularz"
    
    start_time = time.time()
    attempts = 0
    captcha_solved = 0

    try:
        while True:
            attempts += 1
            print(f"\n--- Starting attempt #{attempts} at {time.strftime('%H:%M:%S')} ---")
            print(f"Opening {url}...")
            driver.get(url)

            print("Waiting 8 seconds for page load...")
            time.sleep(8)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Handle dropdowns
            try:
                all_selects = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-select")))
                if len(all_selects) >= 3:
                    select_mat_option(driver, wait, all_selects[1], 2, "First Form Dropdown")
                    time.sleep(5)
                    all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
                    if len(all_selects) >= 3:
                        select_mat_option(driver, wait, all_selects[2], 2, "Second Form Dropdown")
                else:
                    print("Could not find expected dropdowns. Refreshing...")
                    continue
            except Exception as e:
                print(f"Error selecting options: {e}. Refreshing...")
                continue
            
            time.sleep(3)
            
            success = False
            while True:
                solve_captcha(driver, wait)
                captcha_solved += 1
                print("Clicking 'Pobierz terminy wizyty'...")
                try:
                    submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Pobierz terminy wizyty')]")))
                    driver.execute_script("arguments[0].click();", submit_button)
                except Exception as e:
                    print(f"Error finding submit button: {e}. Restarting process...")
                    break # Restart whole process

                print("Waiting for response...")
                time.sleep(5)
                
                # 1. Check for CAPTCHA failure
                if check_for_failure(driver):
                    print("CAPTCHA failure detected. Retrying...")
                    try:
                        captcha_img = driver.find_element(By.XPATH, "//img[@alt='Weryfikacja obrazkowa']")
                        captcha_img.click()
                        time.sleep(2)
                    except: pass
                    continue
                
                # 2. Check for "No appointments" text
                no_appointments_text = "Chwilowo wszystkie udostępnione terminy zostały zarezerwowane, prosimy spróbować umówić wizytę w terminie późniejszym."
                if no_appointments_text in driver.page_source:
                    print("\n[RESULT] No appointments available. Refreshing page and restarting process...")
                    break # Break inner loop to restart the whole process
                
                # 3. Check if the button is still there (another failure mode)
                try:
                    submit_button = driver.find_element(By.XPATH, "//button[contains(., 'Pobierz terminy wizyty')]")
                    if submit_button.is_displayed():
                        print("Submit button still present, retrying CAPTCHA...")
                        continue
                except:
                    # Button is gone - potentially success!
                    print("\n[ALERT] Appointments might be available! Triggering webhook and leaving session open.")
                    trigger_webhook()
                    success = True
                    break

            if success:
                end_time = time.time()
                duration = end_time - start_time
                print("\n" + "="*40)
                print("SUCCESSFUL RUN SUMMARY")
                print(f"Total time: {duration/60:.2f} minutes")
                print(f"Total attempts: {attempts}")
                print(f"CAPTCHA attempts: {captcha_solved}")
                print("="*40)
                return # Stop script

    except KeyboardInterrupt:
        end_time = time.time()
        duration = end_time - start_time
        print("\n" + "="*40)
        print("RUN SUMMARY (Interrupted by user)")
        print(f"Total time: {duration/60:.2f} minutes")
        print(f"Total attempts (refreshes): {attempts}")
        print(f"Total CAPTCHA attempts: {captcha_solved}")
        print("="*40)
        print("Script stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
        # On fatal error, keep browser open for inspection
        while True: time.sleep(1)

    except KeyboardInterrupt:
        print("\nScript stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
        # On fatal error, keep browser open for inspection
        while True: time.sleep(1)

if __name__ == "__main__":
    main()
