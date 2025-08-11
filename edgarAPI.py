import json
import requests
import csv
from datetime import datetime

# Header to simulate a request from your app or bot
headers = {'User-Agent': "ishavarrier@address.com"}


# Company CIK (e.g., Apple Inc.)
cik = "0000320193"

# Start and end date for the filter
start_date = "2025-01-01"
end_date = "2025-12-31"

# Convert string date to datetime objects for comparison
start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")

try:
    # Fetch data from the SEC API for the specific concept (Accounts Payable, Current)
    filingMetadata_response = requests.get(f'https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/NetIncomeLoss.json', headers=headers)
    filingMetadata_response.raise_for_status()  # Raise exception for bad status codes (4xx or 5xx)

    # Parse the JSON response
    filingMetadata_json = filingMetadata_response.json()

    # Ensure that 'USD' data exists in the response
    if 'units' in filingMetadata_json and 'USD' in filingMetadata_json['units']:
        data = filingMetadata_json['units']['USD']

        # Dynamically determine the fieldnames (including 'frame' if it's present)
        fieldnames = ["end", "val", "accn", "fy", "fp", "form", "filed", "start"]
        if any("frame" in entry for entry in data):
            fieldnames.append("frame")
        
        # Open CSV file for writing
        with open("revenues.csv", mode="w", newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()  # Write the header to CSV
            
            # Filter and write only the data that falls within the specified date range
            for entry in data:
                 writer.writerow(entry)  # Write the entry to the CSV

        print("Data has been written to company_concepts.csv.")

    else:
        print("No USD data found in the response.")

except requests.exceptions.RequestException as e:
    print(f"Error fetching data from SEC: {e}")
except json.JSONDecodeError:
    print("Error decoding JSON from the response.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
