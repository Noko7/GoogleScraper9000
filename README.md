# Google Maps Business Scraper

This script automates the extraction of business information from Google Maps using Playwright. It allows users to select business categories and scrape details such as business name, address, website, phone number, reviews count, reviews average, latitude, and longitude.


## Features

- **Multiple Business Categories**: Choose from a predefined list of business types or add your own.
- **Random City Selection**: Randomly selects cities and states from a provided CSV file (`uscities.csv`).
- **Data Extraction**: Captures business details including reviews count and average rating.
- **Data Storage**: Saves scraped data to a centralized CSV file with options to append or overwrite.
- **Duplicate Handling**: Ensures no duplicate businesses are saved.

## Prerequisites

- **Python 3.7 or higher**
- **Playwright**: For browser automation.
- **Pandas**: For data manipulation.
- **An included CSV file named `uscities.csv`**: Should contain at least `city` and `state_id` columns.

## Installation

1. Downlaod or clone the script
   ```
   git clone https://github.com/Noko7/GoogleScraper9000
   ```
Ensure you have the uscities.csv file in your project directory.

2. **Create a Virtual Environment (Optional but Recommended)**

   ```
   python -m venv venv
   source venv/bin/activate
   # On Windows use 'venv\Scripts\activate
3. **Install Dependencies**

Install the required packages using pip:

```
pip install -r requirements.txt
playwright install
```

## Usage

#Selecting Business Catagories (Feel free to add your own)
When you run the script, it will display a menu of business catagories:
```
Select one or more business types by entering their numbers separated by commas or ranges (e.g., 1,3,5-7):
1. Real Estate companies
2. Charity/Non-Profits
3. (ect)...
```

## Running the Script

1. Run the script
```
python scraper.py
```
2. Follow the prompts
- **Select Business Types:** Use the instructions above to select catagories
- **Choose the number of listings you want to capture**
- **Start Scraping**
- Check the output folder for the data
