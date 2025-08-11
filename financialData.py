import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Set SEC headers (required)
HEADERS = {
    'User-Agent': "ishavarrier@address.com"
}

# Mapping of metrics to their XBRL tags
TAGS = {
    "Revenue": "Revenues",
    "Gross Profit": "GrossProfit",
    "Net Income": "NetIncomeLoss",
    "Cash Flow": "NetCashProvidedByUsedInOperatingActivities"
}

# Input CIK for Apple as default
CIK = "0000320193"

# Function to fetch data from the SEC API
def fetch_sec_data(cik, tag):
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        st.error(f"Failed to fetch data for tag {tag}")
        return None
    return r.json()


# Parse the API data into a DataFrame - UPDATED to include frame
def parse_data(json_data):
    records = []
    for entry in json_data.get("units", {}).get("USD", []):
        # Only include entries that have a quarterly frame (CY____Q_)
        frame = entry.get("frame", "")
        if 'end' in entry and frame and "Q" in frame:
            date = entry["end"]
            val = entry["val"]
            form = entry.get("form", "")
            fy = entry.get("fy", "")
            fp = entry.get("fp", "")
            records.append({
                "date": date,
                "val": val,
                "form": form,
                "fy": fy,
                "fp": fp,
                "frame": frame  # Include frame field
            })
    df = pd.DataFrame(records)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date', ascending=False)
    return df


# Combine all data into one DataFrame - UPDATED
def build_financial_table(cik):
    all_data = pd.DataFrame()
    
    for label, tag in TAGS.items():
        json_data = fetch_sec_data(cik, tag)
        if json_data:
            df = parse_data(json_data)
            if not df.empty:
                df = df.rename(columns={"val": label})
                # Keep only the columns we need plus frame
                df_subset = df[["date", "frame", label]].copy()
                
                if all_data.empty:
                    all_data = df_subset
                else:
                    all_data = pd.merge(all_data, df_subset, on=["date", "frame"], how="outer")

    if all_data.empty:
        return pd.DataFrame()
    
    # Sort by date descending
    all_data = all_data.sort_values(by="date", ascending=False)
    
    # Create Quarter column from frame
    all_data['Quarter'] = all_data['frame']
    
    # Remove rows where we don't have both Revenue and Gross Profit
    all_data = all_data.dropna(subset=["Revenue", "Gross Profit"])
    
    # Remove duplicates based on frame/Quarter
    all_data = all_data.drop_duplicates(subset=["Quarter"], keep="first")

    # Calculate Gross Margin
    all_data["Gross Margin"] = all_data["Gross Profit"] / all_data["Revenue"]
    
    all_data = all_data.reset_index(drop=True)
    return all_data


# FIXED: QoQ and YoY change calculator using frame logic
def compute_changes(df, selected_quarter):
    # Define which columns are financial metrics
    metric_cols = ["Revenue", "Gross Profit", "Net Income", "Cash Flow", "Gross Margin"]
    
    # Find the row for the selected quarter
    current_row = df[df['Quarter'] == selected_quarter]
    if current_row.empty:
        raise ValueError(f"Selected quarter {selected_quarter} not found in data.")
    
    current = current_row[metric_cols].iloc[0]
    
    # Initialize default 'N/A' Series
    qoq = pd.Series("N/A", index=metric_cols)
    yoy = pd.Series("N/A", index=metric_cols)
    
    # Extract year and quarter from frame (e.g., "CY2018Q3" -> year=2018, quarter=3)
    if selected_quarter.startswith("CY") and "Q" in selected_quarter:
        year_str = selected_quarter[2:6]  # Extract year (positions 2-5)
        quarter_str = selected_quarter[-1]  # Extract quarter (last character)
        
        try:
            year = int(year_str)
            quarter = int(quarter_str)
            
            # Quarter-over-Quarter (previous quarter)
            if quarter > 1:
                prev_quarter_frame = f"CY{year}Q{quarter-1}"
            else:
                # If Q1, go to Q4 of previous year
                prev_quarter_frame = f"CY{year-1}Q4"
            
            prev_q_row = df[df['Quarter'] == prev_quarter_frame]
            if not prev_q_row.empty:
                prev_q_vals = prev_q_row[metric_cols].iloc[0]
                # Calculate QoQ change only for non-null values
                for col in metric_cols:
                    if pd.notna(current[col]) and pd.notna(prev_q_vals[col]) and prev_q_vals[col] != 0:
                        qoq[col] = (current[col] - prev_q_vals[col]) / prev_q_vals[col]
            
            # Year-over-Year (same quarter previous year)
            prev_year_frame = f"CY{year-1}Q{quarter}"
            prev_y_row = df[df['Quarter'] == prev_year_frame]
            if not prev_y_row.empty:
                prev_y_vals = prev_y_row[metric_cols].iloc[0]
                # Calculate YoY change only for non-null values
                for col in metric_cols:
                    if pd.notna(current[col]) and pd.notna(prev_y_vals[col]) and prev_y_vals[col] != 0:
                        yoy[col] = (current[col] - prev_y_vals[col]) / prev_y_vals[col]
                        
        except ValueError:
            # If we can't parse the year/quarter, just return N/A
            pass
    
    return current, qoq, yoy


# ================= Streamlit App ===================

st.set_page_config(page_title="SEC Financial Dashboard", layout="wide")
st.title("📊 SEC Financial Dashboard (EDGAR)")

ticker = st.text_input("Enter CIK (e.g. Apple = 0000320193)", value=CIK)

# Load and cache data
@st.cache_data
def load_data(cik):
    return build_financial_table(cik)

df = load_data(ticker)

if df.empty:
    st.warning("No financial data available.")
else:
    available_quarters = sorted(df['Quarter'].unique().tolist(), reverse=True)
    selected_q = st.selectbox("Select Quarter", options=available_quarters)

    current, qoq, yoy = compute_changes(df.copy(), selected_q)

    # Prepare a combined table
    combined = pd.DataFrame({
        "Current": current,
        "QoQ Change": qoq,
        "YoY Change": yoy
    })

    # Optional: Format percentages and currency
    def format_row(row):
        formatted = {}
        for col in combined.columns:
            val = row[col]
            if isinstance(val, float):
                if "Margin" in row.name:
                    formatted[col] = f"{val:.1%}"
                elif "Change" in col:
                    formatted[col] = f"{val:.1%}" if pd.notna(val) else "N/A"
                else:
                    formatted[col] = f"${val:,.0f}"
            else:
                formatted[col] = val
        return pd.Series(formatted)

    formatted_combined = combined.apply(format_row, axis=1)

    # Display the final table
    st.subheader(f"📊 Financial Summary for {selected_q}")
    st.table(formatted_combined)