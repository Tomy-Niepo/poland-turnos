import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def main():
    # Configure Chrome options to keep the browser open
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)

    # Initialize the WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Open a sample URL (e.g., Google or a target of your choice)
        url = "https://www.google.com"
        print(f"Opening {url}...")
        driver.get(url)

        # Handle cookie consent if it appears (example of pressing a button)
        try:
            # This is a common pattern for Google cookie consent in some regions
            reject_button = driver.find_element(By.XPATH, "//button[contains(., 'Reject all')]")
            reject_button.click()
            print("Clicked 'Reject all' button.")
        except Exception:
            print("No cookie consent button found or already handled.")

        # Keep the session open for manual takeover
        print("Session is now open. You can take over the browser.")
        print("Press Ctrl+C in this terminal to close the script, but the browser will stay open due to 'detach' option.")
        
        # Wait indefinitely to keep the script running if needed, 
        # though 'detach' keeps the browser alive.
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("
Script stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
