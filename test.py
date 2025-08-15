import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Set SEC headers (required)
HEADERS = {
    'User-Agent': "ishavarrier@address.com"
}

# Company-to-CIK and preferred Revenue tag mapping
COMPANY_INFO = {
    "Intel": {
        "cik": "0000050863",
        "revenue_tag": "SalesRevenueNet"
    },
    "Texas Instruments": {
        "cik": "0000097476",
        "revenue_tag": "RevenueFromContractWithCustomerExcludingAssessedTax"
    }
}

# Other metrics are common across companies
COMMON_TAGS = {
    "Gross Profit": "GrossProfit",
    "Net Income": "NetIncomeLoss",
    "Cash Flow": "NetCashProvidedByUsedInOperatingActivities"
}

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
                "frame": frame
            })
    df = pd.DataFrame(records)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date', ascending=False)
    return df

# Build the complete financial table
def build_financial_table(cik, revenue_tag):
    all_data = pd.DataFrame()
    
    # Include revenue tag from company-specific mapping
    full_tags = {"Revenue": revenue_tag}
    full_tags.update(COMMON_TAGS)

    for label, tag in full_tags.items():
        json_data = fetch_sec_data(cik, tag)
        if json_data:
            df = parse_data(json_data)
            if not df.empty:
                df = df.rename(columns={"val": label})
                df_subset = df[["date", "frame", label]].copy()
                
                if all_data.empty:
                    all_data = df_subset
                else:
                    all_data = pd.merge(all_data, df_subset, on=["date", "frame"], how="outer")

    if all_data.empty:
        return pd.DataFrame()

    all_data = all_data.sort_values(by="date", ascending=False)
    all_data['Quarter'] = all_data['frame']
    all_data = all_data.dropna(subset=["Revenue", "Gross Profit"])
    all_data = all_data.drop_duplicates(subset=["Quarter"], keep="first")
    all_data["Gross Margin"] = all_data["Gross Profit"] / all_data["Revenue"]
    all_data = all_data.reset_index(drop=True)
    return all_data

# Compute QoQ and YoY changes
def compute_changes(df, selected_quarter):
    metric_cols = ["Revenue", "Gross Profit", "Net Income", "Cash Flow", "Gross Margin"]
    current_row = df[df['Quarter'] == selected_quarter]
    if current_row.empty:
        raise ValueError(f"Selected quarter {selected_quarter} not found in data.")
    current = current_row[metric_cols].iloc[0]
    qoq = pd.Series("N/A", index=metric_cols)
    yoy = pd.Series("N/A", index=metric_cols)

    if selected_quarter.startswith("CY") and "Q" in selected_quarter:
        year_str = selected_quarter[2:6]
        quarter_str = selected_quarter[-1]
        try:
            year = int(year_str)
            quarter = int(quarter_str)
            prev_quarter_frame = f"CY{year}Q{quarter-1}" if quarter > 1 else f"CY{year-1}Q4"
            prev_q_row = df[df['Quarter'] == prev_quarter_frame]
            if not prev_q_row.empty:
                prev_q_vals = prev_q_row[metric_cols].iloc[0]
                for col in metric_cols:
                    if pd.notna(current[col]) and pd.notna(prev_q_vals[col]) and prev_q_vals[col] != 0:
                        qoq[col] = (current[col] - prev_q_vals[col]) / prev_q_vals[col]
            prev_year_frame = f"CY{year-1}Q{quarter}"
            prev_y_row = df[df['Quarter'] == prev_year_frame]
            if not prev_y_row.empty:
                prev_y_vals = prev_y_row[metric_cols].iloc[0]
                for col in metric_cols:
                    if pd.notna(current[col]) and pd.notna(prev_y_vals[col]) and prev_y_vals[col] != 0:
                        yoy[col] = (current[col] - prev_y_vals[col]) / prev_y_vals[col]
        except ValueError:
            pass

    return current, qoq, yoy

# ================= Streamlit App ===================

# ================= Section 1 - Current Metrics ===================


st.set_page_config(page_title="SEC Financial Dashboard", layout="wide")
st.title("📊 SEC Financial Dashboard (EDGAR)")

# Company Selector
company = st.selectbox("Choose Company", options=list(COMPANY_INFO.keys()))

selected_cik = COMPANY_INFO[company]["cik"]
selected_revenue_tag = COMPANY_INFO[company]["revenue_tag"]

# Load and cache data
@st.cache_data
def load_data(cik, revenue_tag):
    return build_financial_table(cik, revenue_tag)

df = load_data(selected_cik, selected_revenue_tag)

if df.empty:
    st.warning("No financial data available.")
else:
    available_quarters = sorted(df['Quarter'].unique().tolist(), reverse=True)
    selected_q = st.selectbox("Select Quarter", options=available_quarters)

    current, qoq, yoy = compute_changes(df.copy(), selected_q)

    combined = pd.DataFrame({
        "Current": current,
        "QoQ Change": qoq,
        "YoY Change": yoy
    })

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

    st.subheader(f"📈 Financial Summary for {company} – {selected_q}")
    st.table(formatted_combined)
# ----------- Additional Section: Graphs Over Selected Time Range -----------

st.subheader(f"📉 Financial Trends for {company}")

# Extract available years from the data
df['Year'] = df['date'].dt.year
years = sorted(df['Year'].unique())
min_year, max_year = min(years), max(years)

# Slider for year range
year_range = st.slider(
    "Select Year Range",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year)
)

# Multi-select for quarters (e.g., Q1, Q2, Q3, Q4)
available_quarters_only = sorted(df['Quarter'].str[-2:].unique())
selected_quarters = st.multiselect(
    "Select Quarters",
    options=available_quarters_only,
    default=available_quarters_only
)

# Filter data based on slider and quarter selection
filtered_df = df[
    (df['Year'] >= year_range[0]) &
    (df['Year'] <= year_range[1]) &
    (df['Quarter'].str[-2:].isin(selected_quarters))
].sort_values(by='date')

# Plotting function
# Improved plotting function with error handling
def plot_metric(df, metric, title):
    if metric in df.columns:
        chart_df = df[['date', metric]].dropna()
        if not chart_df.empty:
            chart_df = chart_df.set_index('date')
            st.subheader(f"Summary for {metric} – {selected_q}")
            st.line_chart(chart_df, use_container_width=True)
        else:
            st.info(f"No data available for {title} in the selected range.")
    else:
        st.warning(f"Metric '{metric}' not found in the dataset.")


# Render plots
plot_metric(filtered_df, "Revenue", "Revenue Over Time")
plot_metric(filtered_df, "Gross Profit", "Gross Profit Over Time")
plot_metric(filtered_df, "Net Income", "Net Income Over Time")
plot_metric(filtered_df, "Cash Flow", "Cash Flow Over Time")
plot_metric(filtered_df, "Gross Margin", "Gross Margin Over Time")
