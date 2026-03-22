import time
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
    
    # Ensure the element is in view
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_element)
    time.sleep(1.5) 
    
    try:
        # Wait until it's actually clickable
        wait.until(EC.element_to_be_clickable(select_element))
        select_element.click()
        print(f"Clicked {description}. Waiting for options...")
    except Exception as e:
        print(f"Failed to click {description} using standard click: {e}")
        # Try JavaScript click as fallback
        driver.execute_script("arguments[0].click();", select_element)

    # Wait for the options to appear in the overlay
    time.sleep(2) # Wait for animation and population
    try:
        # Options are usually appended to the end of the body in a cdk-overlay-container
        options = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-option")))
        print(f"Found {len(options)} options for {description}.")
        if len(options) >= option_index:
            print(f"Selecting option {option_index} for {description}...")
            # Using JavaScript click for the option to avoid interception issues
            driver.execute_script("arguments[0].click();", options[option_index - 1])
            print(f"Option {option_index} selected for {description}.")
        else:
            print(f"Error: Found only {len(options)} options for {description}, needed {option_index}")
    except Exception as e:
        print(f"Error selecting option for {description}: {e}")

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

        # Initial wait for the page to load
        print("Waiting 8 seconds for page load...")
        time.sleep(8)

        # Scroll to the bottom to ensure all elements are rendered
        print("Scrolling to the bottom of the page...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # 1st Action: Targeting the SECOND dropdown on the page (skipping language)
        print("Locating form dropdowns (skipping language select)...")
        all_selects = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-select")))
        print(f"Found {len(all_selects)} total mat-select elements.")
        
        if len(all_selects) >= 2:
            # all_selects[0] is language, all_selects[1] is the first form dropdown
            select_mat_option(driver, wait, all_selects[1], 2, "First Form Dropdown (Index 1)")
        else:
            print(f"Error: Expected at least 2 dropdowns, found {len(all_selects)}.")

        # Wait for the next dropdown to populate
        print("Waiting 5 seconds for next dropdown to update...")
        time.sleep(5)

        # 2nd Action: Targeting the THIRD dropdown on the page
        print("Locating next form dropdown...")
        all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
        if len(all_selects) >= 3:
            # all_selects[2] is the second form dropdown
            select_mat_option(driver, wait, all_selects[2], 2, "Second Form Dropdown (Index 2)")
        else:
            print(f"Waiting for third mat-select to appear...")
            wait.until(lambda d: len(d.find_elements(By.TAG_NAME, "mat-select")) >= 3)
            all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
            select_mat_option(driver, wait, all_selects[2], 2, "Second Form Dropdown (Index 2)")

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
