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


# Parse the API data into a DataFrame
def parse_data(json_data):
    records = []
    for entry in json_data.get("units", {}).get("USD", []):
        if 'end' in entry:
            date = entry["end"]
            val = entry["val"]
            form = entry.get("form", "")
            fy = entry.get("fy", "")
            fq = entry.get("fp", "")
            records.append({
                "date": date,
                "val": val,
                "form": form,
                "fy": fy,
                "fp": fq,
            })
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by='date', ascending=False)
    return df


# Combine all data into one DataFrame
def build_financial_table(cik):
    data = {}
    for label, tag in TAGS.items():
        json_data = fetch_sec_data(cik, tag)
        if json_data:
            df = parse_data(json_data)
            df = df.rename(columns={"val": label})
            if isinstance(data, pd.DataFrame) and not data.empty:
                data = pd.merge(data, df[["date", label]], on="date", how="outer")
            else:
                data = df[["date", label]]

    if not isinstance(data, pd.DataFrame):
        return pd.DataFrame()
    data = data.sort_values(by="date", ascending=False)
    data['Quarter'] = data['date'].dt.to_period('Q')
    data = data.dropna(subset=["Revenue", "Gross Profit"])
    data = data.drop_duplicates(subset=["Quarter"], keep="first")

    data["Gross Margin"] = data["Gross Profit"] / data["Revenue"]
    data = data.reset_index(drop=True)
    return data


# QoQ and YoY change calculator
def compute_changes(df, selected_quarter):
    df = df.set_index("Quarter")

    if selected_quarter not in df.index:
        raise ValueError(f"Selected quarter {selected_quarter} not found in data.")

    # Define which columns are financial metrics
    metric_cols = ["Revenue", "Gross Profit", "Net Income", "Cash Flow", "Gross Margin"]

    current = df.loc[selected_quarter, metric_cols]

    # Initialize default 'N/A' Series
    qoq = pd.Series("N/A", index=metric_cols)
    yoy = pd.Series("N/A", index=metric_cols)

    # Quarter-over-Quarter
    prev_q = selected_quarter - 1
    if prev_q in df.index:
        prev = df.loc[prev_q, metric_cols]
        qoq = (current - prev) / prev

    # Year-over-Year
    prev_y = selected_quarter - 4
    if prev_y in df.index:
        prev_year = df.loc[prev_y, metric_cols]
        yoy = (current - prev_year) / prev_year

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
    available_quarters = df['Quarter'].unique().tolist()
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

