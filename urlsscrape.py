import os
import time
import json
import logging
import re
import threading
import random
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
# REMOVED: from webdriver_manager.chrome import ChromeDriverManager
from tqdm import tqdm

# --- Configuration ---
MAX_WORKERS = 100
RETRY_PAUSE_SECONDS = 10
MIN_FILE_SIZE_BYTES = 1024  # 1 KB
STATE_FILE = 'state.json'
URL_FILE = 'formatted_urls.txt'
OUTPUT_DIR = 'html_output'
LOG_FILE = 'scraper.log'

# --- Thread-safe State Manager ---
class StateManager:
    def __init__(self, filepath):
        self.filepath = filepath
        self.lock = threading.Lock()
        self.state = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                return json.load(f)
        return {}

    def initialize_urls(self, urls):
        with self.lock:
            updated = False
            for url in urls:
                if url not in self.state:
                    self.state[url] = 'pending'
                    updated = True
            if updated:
                self._save()

    def _save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.state, f, indent=4)

    def update_status(self, url, status, message=""):
        with self.lock:
            logging.info(f"Updating status for {url} to '{status}'")
            self.state[url] = status
            self._save()

    def get_urls_to_process(self):
        return [url for url, status in self.state.items() if status != 'completed']

# --- Main Scraper Function (for each worker) ---
def scrape_url(url, state_manager):
    """Scrapes a single URL, handles retries, and updates state."""
    thread_id = threading.get_ident()
    logging.info(f"[Thread-{thread_id}] Starting scrape for: {url}")

    # ** STEP 1: DEFINE THE PATH TO YOUR DRIVER **
    # Replace this placeholder with the actual path you found on your system.
    CHROME_DRIVER_PATH = "/home/jon/.wdm/drivers/chromedriver/linux64/140.0.7339.185/chromedriver-linux64/chromedriver"

    chrome_options = Options()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    chrome_options.add_argument(f'user-agent={user_agent}')
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-dev-shm-usage")
    prefs = {"profile.managed_default_content_settings": {"images": 2, "javascript": 2, "stylesheets": 2}}
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = None
    try:
        # ** STEP 2: USE THE DIRECT PATH **
        # This completely bypasses webdriver-manager and stops all related logs.
        if not os.path.exists(CHROME_DRIVER_PATH):
            logging.error(f"ChromeDriver not found at path: {CHROME_DRIVER_PATH}")
            logging.error("Please update the CHROME_DRIVER_PATH variable in the script.")
            state_manager.update_status(url, 'failed_driver_not_found')
            return url, 'failed'
            
        service = Service(CHROME_DRIVER_PATH)
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        for attempt in range(2): # 0 = first try, 1 = retry
            if attempt == 1:
                logging.warning(f"[Thread-{thread_id}] Pausing for {RETRY_PAUSE_SECONDS}s before retrying {url}")
                time.sleep(RETRY_PAUSE_SECONDS)
        
            driver.get(url)
            html_content = driver.page_source

            filename = re.sub(r'^https?:\/\/', '', url)
            filename = re.sub(r'[\/:*?"<>|]', '_', filename) + ".html"
            save_path = os.path.join(OUTPUT_DIR, filename)

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            file_size = os.path.getsize(save_path)
            if file_size < MIN_FILE_SIZE_BYTES:
                if attempt == 0:
                    logging.warning(f"[Thread-{thread_id}] File for {url} is too small ({file_size} bytes). Queuing for retry.")
                    continue
                else:
                    logging.error(f"[Thread-{thread_id}] File for {url} is still too small ({file_size} bytes) after retry. Marking as failed.")
                    state_manager.update_status(url, 'failed_small_file')
                    return url, 'failed'
            
            state_manager.update_status(url, 'completed')
            logging.info(f"[Thread-{thread_id}] Successfully saved {url} ({file_size} bytes)")
            return url, 'completed'

    except Exception as e:
        logging.error(f"[Thread-{thread_id}] Unhandled exception for {url}: {e}", exc_info=True)
        state_manager.update_status(url, 'failed_exception')
        return url, 'failed'
    finally:
        if driver:
            driver.quit()

# --- Main Execution Block ---
def main():
    start_time = time.time()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, mode='w'),
            logging.StreamHandler()
        ]
    )

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    try:
        with open(URL_FILE, 'r') as f:
            initial_urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"'{URL_FILE}' not found. Please create it with one URL per line.")
        return

    state_manager = StateManager(STATE_FILE)
    state_manager.initialize_urls(initial_urls)
    
    urls_to_process = state_manager.get_urls_to_process()

    if not urls_to_process:
        logging.info("All URLs are already marked as completed. Nothing to do.")
    else:
        logging.info(f"Starting scrape for {len(urls_to_process)} URLs with {MAX_WORKERS} workers.")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            task_lambda = lambda url: scrape_url(url, state_manager)
            
            results = list(tqdm(executor.map(task_lambda, urls_to_process), total=len(urls_to_process), desc="Scraping URLs"))

    end_time = time.time()
    logging.info(f"\n--- Scraping Finished ---")
    logging.info(f"Total execution time: {end_time - start_time:.2f} seconds.")
    
    final_state = state_manager._load()
    completed_count = sum(1 for status in final_state.values() if status == 'completed')
    failed_count = len(final_state) - completed_count
    logging.info(f"Summary: {completed_count} completed, {failed_count} failed/pending.")


if __name__ == "__main__":
    main()
