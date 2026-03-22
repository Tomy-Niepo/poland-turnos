import time
import base64
import io
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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
    """Finds the CAPTCHA image, performs OCR, and fills the input field."""
    try:
        print("Locating CAPTCHA image...")
        captcha_img = wait.until(EC.presence_of_element_located((By.XPATH, "//img[@alt='Weryfikacja obrazkowa']")))
        
        # Get the base64 source
        img_base64 = captcha_img.get_attribute("src")
        if "base64," in img_base64:
            base64_data = img_base64.split("base64,")[1]
            
            # Decode image
            img_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(img_bytes))
            
            # Basic Pre-processing to help Tesseract
            # Convert to grayscale and increase contrast
            image = image.convert('L')
            image = ImageOps.autocontrast(image)
            # Thresholding to binary (black/white)
            image = image.point(lambda x: 0 if x < 128 else 255, '1')
            
            # OCR config: single word, only alphanumeric
            captcha_text = pytesseract.image_to_string(image, config='--psm 8').strip()
            print(f"\n>>> OCR RESULT: '{captcha_text}' <<<\n")
            
            # Locate the input field using the provided aria-label
            print("Locating CAPTCHA input field (aria-label='Znaki z obrazka')...")
            # Using a specific selector based on user input
            captcha_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Znaki z obrazka']")))
            
            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_input)
            time.sleep(1)
            
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

        # Scroll to bottom to ensure everything is rendered
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # Handle dropdowns
        all_selects = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-select")))
        if len(all_selects) >= 3:
            select_mat_option(driver, wait, all_selects[1], 2, "First Form Dropdown")
            time.sleep(5)
            # Re-fetch as DOM updates
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
