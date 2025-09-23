import logging
import csv
import time
import os
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Main Scraper Class ---
class DisclosureUrlScraper:
    """
    A simplified web scraper for the Massachusetts Lobbyist Public Search website.

    Workflow:
    1.  Initializes a queue with URLs from a starting CSV file (summary pages).
    2.  Visits each summary.aspx page from the queue.
    3.  On each summary page, it finds all links pointing to 'CompleteDisclosure.aspx'.
    4.  It constructs the full, absolute URL for each disclosure link found.
    5.  All unique disclosure URLs are saved to a specified output text file.
    """
    def __init__(self, output_filename='urls.txt'):
        """Initializes the scraper."""
        self.output_filename = output_filename
        self.driver = None
        # Use a set to automatically handle duplicate URLs
        self.found_disclosure_urls = set()
        self.processed_urls = set()
        self.url_queue = []

    def setup_driver(self):
        """Initializes the Selenium WebDriver in headless mode."""
        logging.info("Setting up Selenium WebDriver...")
        try:
            service = ChromeService(ChromeDriverManager().install())
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--headless')
            # Use a common user-agent to avoid being blocked
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36')
            self.driver = webdriver.Chrome(service=service, options=options)
            logging.info("WebDriver initialized successfully in headless mode.")
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {e}")
            raise

    def find_and_save_disclosure_urls(self, page_source: str, base_url: str):
        """Finds links to disclosure pages and adds them to the set."""
        soup = BeautifulSoup(page_source, 'html.parser')
        # Find all anchor tags where the href contains 'CompleteDisclosure.aspx'
        links = soup.select("a[href*='CompleteDisclosure.aspx']")
        
        if not links:
            logging.info(f"No disclosure links found on {base_url}")
            return

        for link in links:
            relative_url = link.get('href')
            if relative_url:
                # Create an absolute URL from the base URL and the relative path
                absolute_url = urljoin(base_url, relative_url)
                if absolute_url not in self.found_disclosure_urls:
                    logging.info(f"Found new disclosure URL: {absolute_url}")
                    self.found_disclosure_urls.add(absolute_url)

    def save_urls_to_file(self):
        """Saves the collected URLs to the output file."""
        logging.info(f"Saving {len(self.found_disclosure_urls)} unique URLs to {self.output_filename}...")
        try:
            with open(self.output_filename, 'w', encoding='utf-8') as f:
                # Sort the URLs for a consistent output file
                for url in sorted(list(self.found_disclosure_urls)):
                    f.write(url + '\n')
            logging.info("Successfully saved URLs.")
        except IOError as e:
            logging.error(f"Failed to write to {self.output_filename}: {e}")

    def run(self, input_filename: str):
        """Executes the scraping workflow."""
        logging.info("--- Starting Disclosure URL Scraper ---")
        self.setup_driver()
        if not self.driver:
            logging.error("Driver not initialized. Aborting.")
            return

        # Seed the queue with initial URLs from the input CSV
        try:
            with open(input_filename, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    # Expecting URL in the 3rd column (index 2)
                    if len(row) >= 3 and row[2].strip().startswith('http'):
                        url = row[2].strip()
                        if 'summary.aspx' in url.lower():
                             self.url_queue.append(url)
                        else:
                            logging.warning(f"Skipping non-summary URL from input file: {url}")
            logging.info(f"Loaded {len(self.url_queue)} initial summary URLs.")
        except FileNotFoundError:
            logging.error(f"Input file not found: {input_filename}")
            if self.driver:
                self.driver.quit()
            return
        
        try:
            while self.url_queue:
                url = self.url_queue.pop(0)
                if url in self.processed_urls:
                    continue

                logging.info(f"Processing page: {url}")
                try:
                    self.driver.get(url)
                    # Wait for the body to be present, indicating page has loaded
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                    )
                    
                    # Only parse if it's a summary page
                    if 'summary.aspx' in url.lower():
                        self.find_and_save_disclosure_urls(self.driver.page_source, url)
                    
                    self.processed_urls.add(url)

                except TimeoutException:
                    logging.error(f"Timeout loading page: {url}")
                except Exception as e:
                    logging.error(f"An unexpected error occurred processing {url}: {e}", exc_info=True)
                
                # A small delay to be respectful to the server
                time.sleep(1)
        
        finally:
            self.save_urls_to_file()
            if self.driver:
                self.driver.quit()
                logging.info("WebDriver has been closed.")
        
        logging.info("--- Scraper Workflow Finished ---")


# --- Main Execution Block ---
if __name__ == '__main__':
    INPUT_URL_FILE = 'input_urls.csv'
    OUTPUT_URL_FILE = 'urls.txt'

    # Create a dummy input file if it doesn't exist to make the script runnable
    if not os.path.exists(INPUT_URL_FILE):
        logging.info(f"Creating dummy input file: {INPUT_URL_FILE}")
        with open(INPUT_URL_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Type', 'URL'])
            # Example URL from the original script
            writer.writerow(['Greater Boston Legal Services, Inc.', 'Client', 'https://www.sec.state.ma.us/lobbyistpublicsearch/Summary.aspx?sysvalue=hvS0w46oEfUey9UWwnkaGM6ECGFjfpLE+LKsKbOfEhQ='])

    # Initialize and run the scraper
    scraper = DisclosureUrlScraper(output_filename=OUTPUT_URL_FILE)
    scraper.run(input_filename=INPUT_URL_FILE)
