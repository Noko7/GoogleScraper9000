import csv
import re
import os
import sys
import time
import pyfiglet
from termcolor import colored
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

# List of business types
business_types = [
    "Real Estate companies", "Charity/Non-Profits", "Portfolio sites for Instagram artists",
    "Local Restaurant chains", "Personal Injury Law Firms", "Independent insurance sites",
    "Landscaping/Fertilizer", "Painting", "Power Washing", "Car Wash", "Axe Throwing", "Gun Ranges/Stores",
    "Currency Exchanges/Check Cashing", "Construction Materials Companies", "Gyms", "Salons with multiple locations",
    "Eyebrow Microblading", "Estheticians", "Orthodontists", "Used Car dealerships"
]

progress_file = "scraped_results.csv"
fieldnames = ['Business Type', 'City', 'Business Name', 'Phone Number', 'Number of Reviews', 'Website URL']

# Function to check how many listings we already have for a given business type and city
def count_existing_listings():
    progress_dict = {business: {} for business in business_types}
    total_scraped = 0
    
    if os.path.exists(progress_file):
        with open(progress_file, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                business_type = row['Business Type']
                city = row['City']
                if business_type in progress_dict:
                    if city in progress_dict[business_type]:
                        progress_dict[business_type][city] += 1
                    else:
                        progress_dict[business_type][city] = 1
                total_scraped += 1
    return progress_dict, total_scraped

# Function to find the last processed business type and city
def get_last_processed_entry():
    last_business_type = None
    last_city = None
    if os.path.exists(progress_file):
        with open(progress_file, mode='r', newline='', encoding='utf-8') as f:
            reader = list(csv.DictReader(f))
            if reader:  # If the CSV is not empty
                last_entry = reader[-1]
                last_business_type = last_entry['Business Type']
                last_city = last_entry['City']
    return last_business_type, last_city

# Create a CSV file if it doesn't exist
if not os.path.exists(progress_file):
    with open(progress_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

# Display menu to the user
print("Select one or more business types by entering their numbers (e.g., 1 for a single type or 1-5 for a range):")
for i, business in enumerate(business_types, start=1):
    print(f"{i}. {business}")

# Get user input for business types
business_choices = input("Enter your choice or range: ").split('-')
start_type = int(business_choices[0]) - 1
end_type = int(business_choices[1]) if len(business_choices) > 1 else start_type + 1
selected_business_types = business_types[start_type:end_type]

# Ask the user for the number of listings to capture
num_listings_to_capture = int(input("How many listings do you want to capture for each business type? "))

# Set up Firefox options for headless mode
options = Options()
options.headless = True  # Run Firefox in headless mode

# Set up Firefox WebDriver using webdriver-manager to auto-download the correct GeckoDriver
service = FirefoxService(GeckoDriverManager().install())
driver = webdriver.Firefox(service=service, options=options)

# Open Google Maps
driver.get("https://www.google.com/maps")
time.sleep(3)

# Load cities from the CSV file
cities = []
with open('uscities.csv', mode='r', newline='', encoding='utf-8') as file:
    csv_reader = csv.DictReader(file)
    for row in csv_reader:
        cities.append(row['city_ascii'])

# Function to scroll the listings container
def scroll_down(driver):
    try:
        listings_container = driver.find_element(By.XPATH, '//div[@role="feed"]')
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", listings_container)
    except Exception as e:
        print(f"Error during scroll: {e}")

# Function to check if the page has reached the end of the list by text content
def check_end_of_list(driver):
    try:
        end_of_list_element = driver.find_element(By.XPATH, "//*[contains(text(), \"You've reached the end of the list\")]")
        if end_of_list_element:
            return True
    except:
        return False
    return False

# Function to save progress to CSV
def save_progress(captured_listings):
    with open(progress_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for listing in captured_listings:
            writer.writerow(listing)

# Rainbow progress bar function
def update_progress_bar(current, total, business_type, business_scraped, listings_left):
    bar_length = 30  # Length of the progress bar
    progress = current / total
    block = int(round(bar_length * progress))
    
    colors = ['red', 'yellow', 'green', 'cyan', 'blue', 'magenta']
    
    # Create rainbow effect
    progress_bar = ''.join([colored('#', colors[i % len(colors)]) for i in range(block)])
    empty_bar = ' ' * (bar_length - block)
    
    progress_text = f"\rProgress: [{progress_bar}{empty_bar}] {round(progress * 100, 2)}% complete. Scraping {business_scraped}/{listings_left} {business_type} listings"
    sys.stdout.write(progress_text)
    sys.stdout.flush()

# ASCII art progress update function
def display_ascii_count(business_scraped, listings_left):
    ascii_banner = pyfiglet.figlet_format(f"{business_scraped}/{listings_left}")
    print(colored(ascii_banner, 'cyan'))

# Track total listings scraped
progress_dict, total_scraped = count_existing_listings()

# Total listings to capture for all selected business types
total_listings_to_capture = num_listings_to_capture * len(selected_business_types) * len(cities)
listings_captured = total_scraped

# Get last processed business type and city
last_business_type, last_city = get_last_processed_entry()

# Show initial progress bar on script load
update_progress_bar(listings_captured, total_listings_to_capture, "", listings_captured, total_listings_to_capture)

# If progress exists, start from the last processed point
skip_business_type = True if last_business_type else False
skip_city = True if last_city else False

for business_type in selected_business_types:
    if skip_business_type and business_type != last_business_type:
        continue
    skip_business_type = False  # Stop skipping after reaching the last processed business type

    for city in cities:
        if skip_city and city != last_city:
            continue
        skip_city = False  # Stop skipping after reaching the last processed city

        try:
            # Get the number of already scraped listings for the business type and city
            listings_scraped_in_city = progress_dict[business_type].get(city, 0)
            if listings_scraped_in_city >= num_listings_to_capture:
                continue

            listings_left = num_listings_to_capture - listings_scraped_in_city

            while listings_scraped_in_city < num_listings_to_capture:
                scroll_down(driver)
                # Logic for scraping listings and updating progress
                # ...

                listings_scraped_in_city += 1
                listings_captured += 1

                # Update the progress bar and show ASCII
                update_progress_bar(listings_captured, total_listings_to_capture, business_type, listings_captured, total_listings_to_capture)
                display_ascii_count(listings_captured, total_listings_to_capture)

        except Exception as e:
            print(f"Error processing {business_type} in {city}: {e}")

# Close the driver
driver.quit()
