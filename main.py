import re
from playwright.sync_api import sync_playwright
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
    "Eyebrow Microblading", "Estheticians", "Orthodontists", "Used Car dealerships", "Clothing Brand"
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
    business_list: list[Business] = field(default_factory=list)
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

def extract_coordinates_from_url(url: str) -> tuple[float, float]:
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

# Function to read the CSV file and get a list of cities and states
def get_cities_and_states_from_csv(filename):
    cities_states = []
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            cities_states.append((row['city'], row['state_id']))  # Append tuple (city, state)
    return cities_states

# Function to randomly select a city and its state
def select_random_city_and_state(cities_states):
    return random.choice(cities_states)

# Create a red-colored spinning effect function
def spinning_cursor():
    spinner = itertools.cycle(['|', '/', '-', '\\'])
    while True:
        yield f"\033[91m{next(spinner)}\033[0m"  # Red-colored spinner using ANSI escape codes

def main():
    # Display menu for business categories
    print("Select one or more business types by entering their numbers (e.g., 1 for a single type or 1-5 for a range):")
    for i, business in enumerate(business_types, start=1):
        print(f"{i}. {business}")

    # Get user input for business category
    business_choice = int(input("Enter the number of the business category you want to scrape: ")) - 1
    selected_business_type = business_types[business_choice]

    # Ask user for the number of listings to scrape
    num_listings_to_capture = int(input(f"How many {selected_business_type} listings do you want to scrape? "))

    # Ask user if they want to run in headless mode
    headless_choice = input("Do you want to run the script in headless mode? (y/n): ").strip().lower()
    headless = headless_choice == 'y'

    # Get cities and states from uscities.csv
    cities_states = get_cities_and_states_from_csv('uscities.csv')

    # Centralized filename for all cities
    centralized_filename = "Scraped_results"

    # Spinner initialization
    spinner = spinning_cursor()

    # Begin scraping process
    with sync_playwright() as p:
        # Start browser in headless mode based on user input
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        listings_scraped = 0
        business_list = BusinessList()  # Initialize BusinessList

        while listings_scraped < num_listings_to_capture and len(cities_states) > 0:
            selected_city, selected_state = select_random_city_and_state(cities_states)
            cities_states.remove((selected_city, selected_state))  # Remove to avoid revisiting

            print(f"Searching for {selected_business_type} in {selected_city}, {selected_state}.")
            search_for = f"{selected_business_type} in {selected_city}, {selected_state}"

            try:
                page.goto("https://www.google.com/maps", timeout=10000)
                page.wait_for_selector('//input[@id="searchboxinput"]', timeout=10000)
                page.locator('//input[@id="searchboxinput"]').fill(search_for)
                page.keyboard.press("Enter")
                page.wait_for_selector('//a[contains(@href, "https://www.google.com/maps/place")]', timeout=15000)
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
                        address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                        website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                        phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                        review_count_xpath = '//button[@jsaction="pane.reviewChart.moreReviews"]//span'
                        reviews_average_xpath = '//div[@jsaction="pane.reviewChart.moreReviews"]//div[@role="img"]'

                        business = Business()

                        business.name = clean_business_name(listing.get_attribute(name_attribute)) if listing.get_attribute(name_attribute) else "Unknown"
                        business.address = page.locator(address_xpath).first.inner_text() if page.locator(address_xpath).count() > 0 else "No Address"
                        business.website = page.locator(website_xpath).first.inner_text() if page.locator(website_xpath).count() > 0 else "No Website"
                        business.phone_number = page.locator(phone_number_xpath).first.inner_text() if page.locator(phone_number_xpath).count() > 0 else "No Phone"
                        business.reviews_count = int(page.locator(review_count_xpath).inner_text().split()[0].replace(',', '').strip()) if page.locator(review_count_xpath).count() > 0 else 0
                        business.reviews_average = float(page.locator(reviews_average_xpath).get_attribute('aria-label').split()[0].replace(',', '.').strip()) if page.locator(reviews_average_xpath).count() > 0 else 0.0
                        business.latitude, business.longitude = extract_coordinates_from_url(page.url)

                        business_list.add_business(business)
                        listings_scraped += 1

                        if listings_scraped % 10 == 0:
                            business_list.save_to_csv(centralized_filename, append=True)
                            business_list.business_list.clear()

                    except Exception as e:
                        print(f"\nError occurred while scraping listing: {e}")
                    
                    if listings_scraped >= num_listings_to_capture:
                        break

                page.mouse.wheel(0, 5000)  # Scroll down to load more listings
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

        business_list.save_to_csv(centralized_filename, append=True)
        browser.close()

if __name__ == "__main__":
    main()
