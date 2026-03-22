import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def select_mat_option(driver, wait, select_element, option_index):
    """Helper to click a mat-select and choose an option by index."""
    print(f"Clicking dropdown...")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_element)
    time.sleep(1) # Small delay for stability
    select_element.click()
    
    # Wait for the options to appear in the overlay
    print(f"Waiting for options and selecting index {option_index}...")
    options = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-option")))
    
    if len(options) >= option_index:
        options[option_index - 1].click()
        print(f"Option {option_index} selected.")
    else:
        print(f"Error: Could not find option at index {option_index}")

def main():
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    # Adding some common headers to avoid being blocked immediately
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        url = "https://secure.e-konsulat.gov.pl/placowki/164/sprawy-paszportowe/wizyty/formularz"
        print(f"Opening {url}...")
        driver.get(url)

        # 1st Dropdown: Placówka/Service type
        print("Handling first dropdown...")
        first_select = wait.until(EC.element_to_be_clickable((By.TAG_NAME, "mat-select")))
        select_mat_option(driver, wait, first_select, 2)

        # Small wait for the second dropdown to potentially populate or become active
        time.sleep(2)

        # 2nd Dropdown: Next selection
        print("Handling second dropdown...")
        # We find all mat-selects again as the DOM might have updated
        all_selects = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-select")))
        if len(all_selects) >= 2:
            select_mat_option(driver, wait, all_selects[1], 2)
        else:
            print("Second mat-select not found yet, waiting...")
            # Fallback to wait specifically for a second one
            second_select = wait.until(lambda d: d.find_elements(By.TAG_NAME, "mat-select")[1])
            select_mat_option(driver, wait, second_select, 2)

        print("\nAutomation steps completed. Session is now open for manual takeover.")
        print("You can handle CAPTCHAs, images, or further form fields now.")
        print("Press Ctrl+C in this terminal to stop the script. The browser will remain open.")
        
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nScript stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
        # Even on error, keep the browser open for inspection if possible
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
