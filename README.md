# Web Scrape Poland - Selenium Manual Takeover

This project provides a Python script using Selenium that automates initial browser interactions and then maintains the session so a human can easily take over.

## Prerequisites

- **Python 3.x**: Ensure Python is installed on your system.
- **Google Chrome**: This script is configured to use the Chrome browser.

## Step-by-Step Setup

### 1. Clone or Navigate to the Directory
If you haven't already, navigate to the project root:
```bash
cd /your-path/webscrape_poland
```

### 2. Create a Virtual Environment (Recommended)
Isolate your dependencies by creating a virtual environment:
```bash
python3 -m venv venv
```

### 3. Activate the Virtual Environment
- **macOS/Linux**:
  ```bash
  source venv/bin/activate
  ```
- **Windows**:
  ```bash
  venv\Scripts\activate
  ```

### 4. Install Dependencies
Install the required libraries (Selenium and WebDriver Manager):
```bash
pip install -r requirements.txt
```

### 5. Run the Script
Execute the automation script:
```bash
python scraper.py
```

## How it Works

1. **Automation**: The script launches a Chrome instance and navigates to the target URL (default: Google).
2. **Action**: It attempts to click specific buttons (e.g., cookie consent "Reject all").
3. **Manual Takeover**:
   - The script uses the `detach` option, which keeps the browser window open even if the Python process finishes.
   - The script enters an infinite loop in the terminal to keep the session "live" from the script's perspective.
   - You can now interact with the browser manually.
4. **Closing**: To stop the script, press `Ctrl+C` in your terminal. Because of the `detach` setting, the browser window will remain open for you to continue your work manually.

## Customization
To target a different website or specific buttons, modify the `url` and `find_element` logic in `scraper.py`.
