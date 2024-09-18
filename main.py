import re
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

    # Get user input for business categories
    business_input = input("Enter the number(s) of the business categories you want to scrape (e.g., 1,3-5): ")

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

    # Ask user if they want to run in headless mode
    headless_choice = input("Do you want to run the script in headless mode? (y/n): ").strip().lower()
    headless = headless_choice == 'y'

    # Get cities and states from uscities.csv
    cities_states_original = get_cities_and_states_from_csv('uscities.csv')

    centralized_filename = "Scraped_results"

    spinner = spinning_cursor()

    # Ask user for the number of listings to scrape per business type
    num_listings_to_capture = int(input(f"How many listings do you want to scrape for each business type? "))

    # Initialize BusinessList
    business_list = BusinessList()

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

                            MAX_CLICK_RETRIES = 5
                            for retry_attempt in range(MAX_CLICK_RETRIES):
                                try:
                                    listing.click()
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

                            # Extract reviews_average
                            reviews_average_element = details_panel.locator('xpath=.//span[@role="img" and @aria-label and contains(@aria-label, "stars")]').first
                            if reviews_average_element.count() > 0:
                                reviews_average_text = reviews_average_element.get_attribute('aria-label')
                                if reviews_average_text:
                                    match = re.search(r'(\d+\.\d+|\d+)', reviews_average_text.replace(',', '.'))
                                    if match:
                                        business.reviews_average = float(match.group(1))
                                    else:
                                        business.reviews_average = 0.0
                                else:
                                    business.reviews_average = 0.0
                            else:
                                business.reviews_average = 0.0

                            # Extract reviews_count
                            # Updated XPath and extraction logic
                            reviews_count_element = details_panel.locator('xpath=.//button[./span[contains(text(), "reviews")]]/span').first
                            if reviews_count_element.count() > 0:
                                reviews_count_text = reviews_count_element.inner_text()
                                if reviews_count_text:
                                    match = re.search(r'(\d+)', reviews_count_text.replace(',', ''))
                                    if match:
                                        business.reviews_count = int(match.group(1))
                                    else:
                                        business.reviews_count = 0
                                else:
                                    business.reviews_count = 0
                            else:
                                business.reviews_count = 0

                            business.latitude, business.longitude = extract_coordinates_from_url(page.url)

                            added = business_list.add_business(business)
                            if added:
                                listings_scraped += 1

                            if listings_scraped % 10 == 0:
                                business_list.save_to_csv(centralized_filename, append=True)
                                business_list.business_list.clear()

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
