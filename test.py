import requests
import json
from datetime import datetime

# Input CIK for Apple as default
CIK = "0000320193"

# Function to fetch data from the SEC API
def fetch_sec_data(cik, tag):
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
    
    # Set headers as recommended by SEC
    headers = {
        'User-Agent': 'Your Company Name your.email@company.com'  # Replace with your actual info
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def get_apple_revenue_2018q3():
    """
    Fetch Apple's revenue data and filter for 2018Q3
    """
    # Fetch revenue data using the 'Revenues' tag
    data = fetch_sec_data(CIK, 'Revenues')
    
    if not data:
        print("Failed to fetch data from SEC API")
        return None
    
    # Look for quarterly data (10-Q filings)
    quarterly_data = data.get('units', {}).get('USD', [])
    
    # Filter for 2018Q3 data using the frame field
    target_frame = "CY2018Q3"
    q3_2018_data = []
    
    for entry in quarterly_data:
        # Look for entries that match CY2018Q3 frame
        if entry.get('frame') == target_frame:
            q3_2018_data.append(entry)
    
    return q3_2018_data

def format_revenue_data(revenue_data):
    """
    Format and display the revenue data nicely
    """
    if not revenue_data:
        print("No 2018Q3 revenue data found")
        return
    
    print("Apple Revenue Data for 2018Q3:")
    print("-" * 40)
    
    for entry in revenue_data:
        revenue = entry.get('val', 0)
        filing_date = entry.get('filed', 'N/A')
        period_end = entry.get('end', 'N/A')
        
        # Format revenue in billions
        revenue_billions = revenue / 1_000_000_000 if revenue else 0
        
        print(f"Period End: {period_end}")
        print(f"Revenue: ${revenue:,} ({revenue_billions:.2f} billion)")
        print(f"Filed: {filing_date}")
        print(f"Form: {entry.get('form', 'N/A')}")
        print(f"Frame: {entry.get('frame', 'N/A')}")
        print("-" * 40)

# Main execution
if __name__ == "__main__":
    print("Fetching Apple's 2018Q3 revenue data from SEC API...")
    
    # Get the revenue data for 2018Q3
    revenue_data = get_apple_revenue_2018q3()
    
    # Format and display the results
    format_revenue_data(revenue_data)
    
    # Also try to get annual data for context
    print("\nAlso checking for annual revenue data around 2018...")
    data = fetch_sec_data(CIK, 'Revenues')
    
    if data:
        annual_data = data.get('units', {}).get('USD', [])
        for entry in annual_data:
            if (entry.get('end') == "2018-09-29" and  # Apple's fiscal year end
                entry.get('form') == '10-K'):
                revenue = entry.get('val', 0)
                revenue_billions = revenue / 1_000_000_000
                print(f"Annual Revenue 2018: ${revenue:,} ({revenue_billions:.2f} billion)")
                break