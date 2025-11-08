import re
import signal
import sys
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from dataclasses import dataclass, asdict, field
import pandas as pd
import os
import csv
import random
import itertools
import time

# List of business categories
business_types = [
    "Real Estate companies", "Charity/Non-Profits", "Portfolio sites for Instagram artists",
    "Local Restaurant chains", "Personal Injury Law Firms", "Independent insurance sites",
    "Landscaping/Fertilizer", "Painting", "Power Washing", "Car Wash", "Axe Throwing", "Gun Ranges/Stores",
    "Currency Exchanges/Check Cashing", "Construction Materials Companies", "Gyms", "Salons with multiple locations",
    "Eyebrow Microblading", "Estheticians", "Orthodontists", "Used Car dealerships", "Clothing Brand", "Cut & Sew", "Embroidery"
]

@dataclass
class Business:
    """Holds business data"""
    name: str = None
    address: str = "No Address"
    website: str = "No Website"
    phone_number: str = "No Phone"
    reviews_count: int = 0
    reviews_average: float = 0.0
    latitude: float = None
    longitude: float = None

@dataclass
class BusinessList:
    """Holds list of Business objects and saves to both Excel and CSV."""
    business_list: list = field(default_factory=list)
    save_at: str = 'output'
    seen_businesses: set = field(default_factory=set)  # Set to track unique businesses

    def dataframe(self):
        """Transform business_list to a pandas dataframe."""
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_"
        )

    def save_to_csv(self, filename, append=True):
        """Saves pandas dataframe to a single centralized CSV file with headers."""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        file_path = f"{self.save_at}/{filename}.csv"
        mode = 'a' if append else 'w'
        if append and os.path.exists(file_path):
            self.dataframe().to_csv(file_path, mode=mode, index=False, header=False)
        else:
            self.dataframe().to_csv(file_path, mode=mode, index=False, header=True)

    def add_business(self, business):
        """Add a business to the list if it's not a duplicate."""
        unique_key = (business.name, business.address, business.phone_number)
        if unique_key not in self.seen_businesses:
            self.seen_businesses.add(unique_key)
            self.business_list.append(business)
            return True  # Business was added
        else:
            return False  # Business was a duplicate

def extract_coordinates_from_url(url: str) -> tuple:
    """Helper function to extract coordinates from URL."""
    try:
        coordinates = url.split('/@')[-1].split('/')[0]
        return float(coordinates.split(',')[0]), float(coordinates.split(',')[1])
    except (IndexError, ValueError) as e:
        print(f"Error extracting coordinates: {e}")
        return None, None

def clean_business_name(name: str) -> str:
    """Remove '· Visited link' from the business name."""
    return name.replace(" · Visited link", "").strip()

def get_cities_and_states_from_csv(filename):
    cities_states = []
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            cities_states.append((row['city'], row['state_id']))  # Append tuple (city, state)
    return cities_states

def prompt_yes_no(prompt: str, default: str = 'y') -> bool:
    """Prompt user for a yes/no answer with validation."""
    default = default.lower()
    while True:
        resp = input(f"{prompt} ").strip().lower()
        if resp == '' and default in ('y', 'n'):
            return default == 'y'
        if resp in ('y', 'yes'):
            return True
        if resp in ('n', 'no'):
            return False
        print("Please enter 'y' or 'n'.")

def parse_location_input(raw: str):
    """Parse user-entered location strings into a list of (city, state) tuples.
    Accepts semicolon-separated 'City,State' entries or 'file:path/to.csv'.
    """
    raw = raw.strip()
    if raw.lower().startswith('file:'):
        path = raw.split(':', 1)[1]
        try:
            return get_cities_and_states_from_csv(path)
        except Exception as e:
            print(f"Failed to read locations from file '{path}': {e}")
            return []

    locations = []
    for part in raw.split(';'):
        part = part.strip()
        if not part:
            continue
        if ',' in part:
            city, state = part.split(',', 1)
            locations.append((city.strip(), state.strip()))
        else:
            # allow just a city; leave state empty
            locations.append((part.strip(), ''))
    return locations

def get_positive_int(prompt_text: str, default: int = None) -> int:
    while True:
        resp = input(prompt_text).strip()
        if resp == '' and default is not None:
            return default
        try:
            val = int(resp)
            if val > 0:
                return val
            else:
                print('Please enter a positive integer.')
        except ValueError:
            print('Please enter a valid integer.')


def select_random_city_and_state(cities_states):
    return random.choice(cities_states)

def spinning_cursor():
    spinner = itertools.cycle(['|', '/', '-', '\\'])
    while True:
        yield f"\033[91m{next(spinner)}\033[0m"  # Red-colored spinner using ANSI escape codes

def main():
    # Display menu for business categories
    print("Select one or more business types by entering their numbers separated by commas or ranges (e.g., 1,3,5-7):")
    for i, business in enumerate(business_types, start=1):
        print(f"{i}. {business}")

    # Get user input for business categories (with validation)
    while True:
        business_input = input("Enter the number(s) of the business categories you want to scrape (e.g., 1,3-5): ").strip()
        if business_input:
            try:
                # validate by attempting to parse
                def _try_parse(inp):
                    selected_indices = set()
                    for part in inp.split(','):
                        part = part.strip()
                        if '-' in part:
                            start, end = part.split('-')
                            start = int(start.strip()) - 1
                            end = int(end.strip()) - 1
                            selected_indices.update(range(start, end + 1))
                        else:
                            index = int(part.strip()) - 1
                            selected_indices.add(index)
                    return sorted(selected_indices)
                _try_parse(business_input)
                break
            except Exception:
                print('Invalid selection format. Use numbers, commas and ranges like "1,3-5".')
        else:
            print('Selection cannot be empty.')

    # Function to parse the input
    def parse_business_input(business_input):
        selected_indices = set()
        for part in business_input.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                start = int(start.strip()) - 1  # Adjust for 0-based index
                end = int(end.strip()) - 1
                selected_indices.update(range(start, end + 1))
            else:
                index = int(part.strip()) - 1
                selected_indices.add(index)
        return sorted(selected_indices)

    selected_business_indices = parse_business_input(business_input)

    selected_business_types = [business_types[i] for i in selected_business_indices if 0 <= i < len(business_types)]

    if not selected_business_types:
        print("No valid business types selected.")
        return

    # Ask user if they want to run the script in headless mode
    headless = prompt_yes_no("Do you want to run the script in headless mode? (y/n):", default='y')

    # Get cities and states from uscities.csv
    cities_states_original = get_cities_and_states_from_csv('uscities.csv')

    # Allow user to choose between random cities or specify explicit locations
    use_random_locations = prompt_yes_no("Use random locations from uscities.csv? (y/n)", default='y')
    if not use_random_locations:
        raw_locs = input("Enter locations as 'City,State' separated by semicolons (e.g. Chicago,IL;Naperville,IL)\nor enter 'file:/path/to/file.csv' to load a CSV with headers 'city,state_id': ").strip()
        parsed = parse_location_input(raw_locs)
        if parsed:
            cities_states_original = parsed
        else:
            print('No valid locations parsed; falling back to random cities from uscities.csv')

    centralized_filename = "Scraped_results"

    spinner = spinning_cursor()

    # Ask user for the number of listings to scrape per business type (validated)
    num_listings_to_capture = get_positive_int(f"How many listings do you want to scrape for each business type? ", default=None)

    # Ask user how often to flush/save results to disk (every N captured listings)
    save_every_n = get_positive_int("How many captured listings before auto-saving to CSV? (default 10): ", default=10)

    # Initialize BusinessList
    business_list = BusinessList()

    # Register graceful save on Ctrl-C once business_list exists
    def _save_and_exit(signum, frame):
        print('\nReceived interrupt; saving collected results and exiting...')
        try:
            if business_list.business_list:
                business_list.save_to_csv(centralized_filename, append=True)
        except Exception as e:
            print(f'Error while saving on exit: {e}')
        sys.exit(0)

    signal.signal(signal.SIGINT, _save_and_exit)

    # Begin scraping process
    with sync_playwright() as p:
        # Start browser in headless mode based on user input
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        for selected_business_type in selected_business_types:
            print(f"\nScraping for business type: {selected_business_type}")

            # Reset listings_scraped for this business type
            listings_scraped = 0

            # Copy cities_states for this business type
            cities_states = cities_states_original.copy()

            while listings_scraped < num_listings_to_capture and len(cities_states) > 0:
                selected_city, selected_state = select_random_city_and_state(cities_states)
                cities_states.remove((selected_city, selected_state))  # Remove to avoid revisiting

                print(f"Searching for {selected_business_type} in {selected_city}, {selected_state}.")
                search_for = f"{selected_business_type} in {selected_city}, {selected_state}"

                try:
                    page.goto("https://www.google.com/maps", timeout=30000)
                    page.wait_for_selector('//input[@id="searchboxinput"]', timeout=10000)
                    page.locator('//input[@id="searchboxinput"]').fill(search_for)
                    page.keyboard.press("Enter")
                    page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]', timeout=7000)
                except PlaywrightTimeoutError as e:
                    print(f"Timeout error occurred while searching for {selected_business_type} in {selected_city}: {e}")
                    continue
                except Exception as e:
                    print(f"Error occurred while searching for {selected_business_type} in {selected_city}: {e}")
                    continue

                try:
                    current_count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                except Exception as e:
                    print(f"Error detecting results for {selected_city}, skipping: {e}")
                    continue

                if current_count == 0:
                    print(f"No results found for {selected_business_type} in {selected_city}, {selected_state}. Moving to next city.")
                    continue

                print(f"Found {current_count} listings for {selected_business_type} in {selected_city}, {selected_state}.")

                # Scroll through listings and wait for the elements to load
                MAX_SCROLL_ATTEMPTS = 10
                scroll_attempts = 0
                previously_counted = current_count

                while listings_scraped < num_listings_to_capture:
                    try:
                        listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
                    except Exception as e:
                        print(f"Error while fetching listings: {e}")
                        break

                    if not listings:
                        print(f"No more listings found. Moving to the next city.")
                        break

                    for listing in listings:
                        try:
                            if listings_scraped >= num_listings_to_capture:
                                break

                            spinner_char = next(spinner)
                            print(f"\rScraping listing: {listings_scraped + 1} of {num_listings_to_capture} {spinner_char}", end='')

                            # Define the details panel to scope our locators before clicking so we can wait on it.
                            details_panel = page.locator('div[role="main"]')
                            MAX_CLICK_RETRIES = 5
                            for retry_attempt in range(MAX_CLICK_RETRIES):
                                try:
                                    listing.click()
                                    # Wait briefly for the details panel to update after clicking.
                                    # Prefer waiting for the rating/details container which appears when a place is selected.
                                    try:
                                        # small wait to let the panel start loading
                                        page.wait_for_timeout(500)
                                        # wait for the details rating container to appear (class F7nice is observed for ratings)
                                        details_panel.locator('xpath=.//div[contains(@class, "F7nice")]').first.wait_for(timeout=5000)
                                    except PlaywrightTimeoutError:
                                        # fallback: short pause if the specific element didn't appear in time
                                        page.wait_for_timeout(2000)
                                    break
                                except Exception as e:
                                    print(f"Retrying click, attempt {retry_attempt + 1}: {e}")
                                    page.wait_for_timeout(1000)

                            name_attribute = 'aria-label'
                            address_xpath = 'xpath=//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                            website_xpath = 'xpath=//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                            phone_number_xpath = 'xpath=//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'

                            # Define the details panel to scope our locators
                            details_panel = page.locator('div[role="main"]')

                            business = Business()

                            business.name = clean_business_name(listing.get_attribute(name_attribute)) if listing.get_attribute(name_attribute) else "Unknown"
                            business.address = page.locator(address_xpath).first.inner_text() if page.locator(address_xpath).count() > 0 else "No Address"
                            business.website = page.locator(website_xpath).first.inner_text() if page.locator(website_xpath).count() > 0 else "No Website"
                            business.phone_number = page.locator(phone_number_xpath).first.inner_text() if page.locator(phone_number_xpath).count() > 0 else "No Phone"

                            # Extract reviews_average and reviews_count from the currently-open details panel.
                            # We try a robust sequence: prefer the visible aria-hidden span for rating (e.g. <span aria-hidden="true">4.7</span>),
                            # and look for a span with aria-label containing "reviews" for the count. Fall back to other nearby text if needed.
                            try:
                                # Ensure the rating container is present (may already have been waited for above)
                                rating_container = details_panel.locator('xpath=.//div[contains(@class, "F7nice")]').first
                                if rating_container.count() > 0:
                                    # Rating: look for the aria-hidden span that holds the numeric rating
                                    rating_span = rating_container.locator('xpath=.//span[@aria-hidden="true"]').first
                                    if rating_span.count() > 0:
                                        rating_text = rating_span.inner_text().strip()
                                        rating_text = rating_text.replace(',', '.')
                                        m = re.search(r'(\d+\.\d+|\d+)', rating_text)
                                        business.reviews_average = float(m.group(1)) if m else 0.0
                                    else:
                                        business.reviews_average = 0.0

                                    # Reviews count: prefer an element that has aria-label with the word "reviews"
                                    review_label = rating_container.locator('xpath=.//span[@aria-label and contains(translate(@aria-label, "REVIEWS", "reviews"), "reviews")]').first
                                    if review_label.count() > 0:
                                        label_text = review_label.get_attribute('aria-label') or review_label.inner_text() or ''
                                        m2 = re.search(r'(\d+)', label_text.replace(',', ''))
                                        business.reviews_count = int(m2.group(1)) if m2 else 0
                                    else:
                                        # fallback: look for a nearby span that contains parentheses like (62)
                                        paren_span = rating_container.locator('xpath=.//span[contains(text(), "(")]').first
                                        if paren_span.count() > 0:
                                            paren_text = paren_span.inner_text()
                                            m3 = re.search(r'(\d+)', paren_text.replace(',', ''))
                                            business.reviews_count = int(m3.group(1)) if m3 else 0
                                        else:
                                            business.reviews_count = 0
                                else:
                                    business.reviews_average = 0.0
                                    business.reviews_count = 0
                            except Exception as e:
                                # If anything goes wrong parsing, set to safe defaults for this business only
                                print(f"Warning: failed to extract reviews for a listing: {e}")
                                business.reviews_average = 0.0
                                business.reviews_count = 0

                            business.latitude, business.longitude = extract_coordinates_from_url(page.url)

                            added = business_list.add_business(business)
                            if added:
                                listings_scraped += 1

                            # Autosave every save_every_n listings
                            try:
                                if save_every_n and listings_scraped > 0 and listings_scraped % save_every_n == 0:
                                    business_list.save_to_csv(centralized_filename, append=True)
                                    business_list.business_list.clear()
                            except Exception as e:
                                print(f"Warning: autosave failed: {e}")

                        except Exception as e:
                            print(f"\nError occurred while scraping listing: {e}")
                            continue  # Continue to the next listing

                        if listings_scraped >= num_listings_to_capture:
                            break

                    page.mouse.wheel(0, 5000)
                    page.wait_for_timeout(3000)

                    new_count = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                    if new_count == previously_counted:
                        scroll_attempts += 1
                        if scroll_attempts >= MAX_SCROLL_ATTEMPTS:
                            print(f"No more listings found after {scroll_attempts} scroll attempts. Moving to next city.")
                            break
                    else:
                        scroll_attempts = 0

                    previously_counted = new_count

                    if page.locator("text=You've reached the end of the list").is_visible():
                        print(f"Reached the end of the list in {selected_city}, {selected_state}. Moving to the next city.")
                        break

            # Save any remaining businesses after finishing all business types
            if business_list.business_list:
                business_list.save_to_csv(centralized_filename, append=True)
                business_list.business_list.clear()

        browser.close()

if __name__ == "__main__":
    main()
