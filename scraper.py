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
    
    # Scroll and ensure clickable
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", select_element)
    time.sleep(1) 
    
    try:
        wait.until(EC.element_to_be_clickable(select_element))
        select_element.click()
        print(f"Clicked {description}. Waiting for options...")
    except Exception as e:
        print(f"Failed to click {description}: {e}")
        # Try JavaScript click as fallback
        driver.execute_script("arguments[0].click();", select_element)

    # Wait for the options to appear in the overlay
    time.sleep(1) # Wait for animation
    try:
        options = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-option")))
        if len(options) >= option_index:
            print(f"Selecting option {option_index} for {description}...")
            options[option_index - 1].click()
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

        # Wait 5 seconds for the page and Angular components to stabilize
        print("Waiting 5 seconds for page load...")
        time.sleep(5)

        # 1st Dropdown
        print("Locating first dropdown...")
        all_selects = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "mat-select")))
        if len(all_selects) > 0:
            select_mat_option(driver, wait, all_selects[0], 2, "First Dropdown")
        else:
            print("Error: No mat-select elements found.")

        # Wait for the second dropdown to populate (often dependent on the first)
        print("Waiting 3 seconds for second dropdown to update...")
        time.sleep(3)

        # 2nd Dropdown
        print("Locating second dropdown...")
        # Refresh the list of selects as the DOM may have changed
        all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
        if len(all_selects) >= 2:
            select_mat_option(driver, wait, all_selects[1], 2, "Second Dropdown")
        else:
            print(f"Waiting for second mat-select to appear (currently found {len(all_selects)})...")
            # Specific wait for at least two selects
            wait.until(lambda d: len(d.find_elements(By.TAG_NAME, "mat-select")) >= 2)
            all_selects = driver.find_elements(By.TAG_NAME, "mat-select")
            select_mat_option(driver, wait, all_selects[1], 2, "Second Dropdown")

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
