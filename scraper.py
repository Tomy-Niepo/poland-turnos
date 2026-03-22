import time
import base64
import io
import numpy as np
import cv2
import easyocr
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Initialize EasyOCR Reader (English)
# Note: This will download models (~150MB) on first run
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
        
        # Get the base64 source
        img_base64 = captcha_img.get_attribute("src")
        if "base64," in img_base64:
            base64_data = img_base64.split("base64,")[1]
            
            # Decode image to numpy array for OpenCV
            img_bytes = base64.b64decode(base64_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Pre-processing with OpenCV
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            # Rescale (upscale for better OCR)
            upscaled = cv2.resize(denoised, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            
            # Perform OCR using EasyOCR
            # allowlist restricts characters if you know it's only letters
            results = reader.readtext(upscaled, detail=0, allowlist='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
            captcha_text = "".join(results).strip()
            
            print(f"\n>>> EASYOCR RESULT: '{captcha_text}' <<<\n")
            
            # Locate input field
            print("Locating CAPTCHA input field (aria-label='Znaki z obrazka')...")
            captcha_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Znaki z obrazka']")))
            
            # Interaction: Click, Clear, Send Keys
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_input)
            time.sleep(1)
            captcha_input.click()
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            
            print(f"CAPTCHA field filled with: {captcha_text}")
            return True
    except Exception as e:
        print(f"Failed to solve CAPTCHA: {e}")
        return False

def main():
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        url = "https://secure.e-konsulat.gov.pl/placowki/164/sprawy-paszportowe/wizyty/formularz"
        print(f"Opening {url}...")
        driver.get(url)

        print("Waiting 8 seconds for page load...")
        time.sleep(8)

        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # Dropdowns
        all_selects = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-select")))
        if len(all_selects) >= 3:
            select_mat_option(driver, wait, all_selects[1], 2, "First Form Dropdown")
            time.sleep(5)
            all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
            if len(all_selects) >= 3:
                select_mat_option(driver, wait, all_selects[2], 2, "Second Form Dropdown")
        
        time.sleep(3)
        
        # OCR / CAPTCHA
        solve_captcha(driver, wait)

        print("\nAutomation steps completed. Session is now open for manual takeover.")
        print("Press Ctrl+C in this terminal to stop the script. The browser will remain open.")
        
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nScript stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
