import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def main():
    # Configure Chrome options to keep the browser open
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)

    # Initialize the WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Navigate to the target URL
        url = "https://recetario.com.ar/es"
        print(f"Opening {url}...")
        driver.get(url)

        # Wait for the 'Solicitá una demo' button to be clickable
        print("Waiting for 'Solicitá una demo' button...")
        wait = WebDriverWait(driver, 10)
        
        # Use XPath to find the button by its text content
        # This is more robust than long utility class strings
        demo_button_xpath = "//button[contains(text(), 'Solicitá una demo')]"
        
        demo_button = wait.until(EC.element_to_be_clickable((By.XPATH, demo_button_xpath)))
        
        print("Clicking 'Solicitá una demo' button...")
        demo_button.click()
        print("Button clicked successfully.")

        # Keep the session open for manual takeover
        print("\nSession is now open. You can take over the browser.")
        print("Press Ctrl+C in this terminal to stop the script. The browser will remain open.")
        
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nScript stopped by user.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
