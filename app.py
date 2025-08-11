import streamlit as st
import requests
from datetime import datetime
import pandas as pd

# Streamlit UI
st.title("EDGAR API Data")

ticker = st.text_input("Enter a company ticker (e.g., AAPL)", value="AAPL")

# Year range slider
year_range = st.slider("Select a range of years", 2005, 2025, (2020, 2025))

if st.button("Fetch Accounts Payable Data"):
    headers = {'User-Agent': "user@address.com"}

    # Step 1: Get CIK from ticker
    ticker = ticker.upper().strip()
    try:
        mapping_resp = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
        mapping_resp.raise_for_status()
        mapping_data = mapping_resp.json()

        # Find CIK by matching ticker
        cik = None
        for item in mapping_data.values():
            if item['ticker'] == ticker:
                cik = str(item['cik_str']).zfill(10)  # pad with zeros
                break

        if not cik:
            st.error(f"CIK not found for ticker {ticker}")
        else:
            # Step 2: Fetch EDGAR company concept data
            concept_url = f'https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/AccountsPayableCurrent.json'
            filing_resp = requests.get(concept_url, headers=headers)
            filing_resp.raise_for_status()

            filing_data = filing_resp.json()

            if 'units' in filing_data and 'USD' in filing_data['units']:
                data = filing_data['units']['USD']
                df = pd.DataFrame(data)

                # Convert 'end' to datetime and filter by year range
                df['end'] = pd.to_datetime(df['end'], errors='coerce')
                df = df[df['end'].dt.year.between(year_range[0], year_range[1])]

                # Display table
                if not df.empty:
                    st.header('Company Concepts - Accounts Payable Current')
                    st.dataframe(df)
                else:
                    st.warning("No data available in the selected year range.")
            else:
                st.warning("No USD data found in the response.")

    except requests.exceptions.RequestException as e:
        st.error(f"Request error: {e}")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
