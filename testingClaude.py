import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, Optional, List
import json

# ================= SEC Data Fetcher Class ===================

class SECDataFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': "ishavarrier@address.com"
        }
        
        # Revenue tag mappings - can be extended as needed
        self.company_revenue_preferences = {
            "Intel": ["RevenueFromContractWithCustomerExcludingAssessedTax"],
            "Texas Instruments": ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
            "Apple": ["SalesRevenueNet"],
            "Microsoft": ["SalesRevenueNet"],
            "Google": ["Revenues"],
            "Alphabet": ["Revenues"],
            "Amazon": ["SalesRevenueNet"],
            "Tesla": ["SalesRevenueNet"],
            "NVIDIA": ["RevenueFromContractWithCustomerExcludingAssessedTax"],
        }

        # Global fallback revenue tag candidates, in order of preference
        self.default_revenue_tags = [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet", 
            "Revenues",
            "SalesRevenueGoodsNet",
            "SalesRevenueServicesNet",
        ]
                
        # Common tags that work across most companies
        self.common_tags = {
            "Gross Profit": "GrossProfit",
            "Net Income": "NetIncomeLoss", 
            "Cash Flow": "NetCashProvidedByUsedInOperatingActivities",
        }
        
        # Cache for CIK lookups and company searches
        self.cik_cache = {}
        self.company_list_cache = None
    
    def get_company_list(self) -> List[Dict]:
        """Get full list of companies from SEC"""
        if self.company_list_cache is not None:
            return self.company_list_cache
            
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                companies_data = response.json()
                companies = []
                
                for entry in companies_data.values():
                    companies.append({
                        "name": entry['title'],
                        "ticker": entry['ticker'],
                        "cik": str(entry['cik_str']).zfill(10)
                    })
                
                # Sort by company name
                companies.sort(key=lambda x: x['name'])
                self.company_list_cache = companies
                return companies
                
        except Exception as e:
            st.error(f"Error loading company list: {e}")
        
        return []
    
    def get_company_cik(self, company_name: str) -> Optional[str]:
        """Get CIK for a company name"""
        print(self.cik_cache)
        if company_name in self.cik_cache:
            return self.cik_cache[company_name]
        
        companies = self.get_company_list()
        for company in companies:
            if company['name'] == company_name:
                cik = company['cik']
                self.cik_cache[company_name] = cik
                return cik
        
        return None
    
    def get_revenue_tag_for_company(self, company_name: str, cik: str) -> str:
        """
        Get the appropriate revenue tag for a company.
        First checks preferences, then tries fallback tags by testing them.
        """
        # Check if company has specific preference
        if company_name in self.company_revenue_preferences:
            for tag in self.company_revenue_preferences[company_name]:
                # Test if this tag works for the company
                if self.test_tag_availability(cik, tag):
                    return tag
        
        # Try default tags in order of preference
        for tag in self.default_revenue_tags:
            if self.test_tag_availability(cik, tag):
                return tag
        
        # Final fallback
        return "SalesRevenueNet"
    
    def test_tag_availability(self, cik: str, tag: str) -> bool:
        """Test if a tag is available for a company"""
        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
        try:
            response = requests.get(url, headers=self.headers)
            return response.status_code == 200
        except:
            return False
    
    def fetch_sec_data(self, cik: str, tag: str) -> Optional[Dict]:
        """Fetch data from SEC API for given CIK and tag"""
        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            st.error(f"Error fetching SEC data: {e}")
            return None

# ================= Helper Functions ===================

# Initialize the fetcher
@st.cache_resource
def get_sec_fetcher():
    return SECDataFetcher()

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
def build_financial_table(cik, revenue_tag, fetcher):
    all_data = pd.DataFrame()
    
    # Include revenue tag from company-specific mapping
    full_tags = {"Revenue": revenue_tag}
    full_tags.update(fetcher.common_tags)

    for label, tag in full_tags.items():
        json_data = fetcher.fetch_sec_data(cik, tag)
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
    all_data = all_data.dropna(subset=["Revenue"])
    
    # Only calculate gross margin if gross profit exists
    if "Gross Profit" in all_data.columns:
        all_data = all_data.dropna(subset=["Gross Profit"])
        all_data["Gross Margin"] = all_data["Gross Profit"] / all_data["Revenue"]
    
    all_data = all_data.drop_duplicates(subset=["Quarter"], keep="first")
    all_data = all_data.reset_index(drop=True)
    return all_data

# Compute QoQ and YoY changes
def compute_changes(df, selected_quarter):
    metric_cols = [col for col in ["Revenue", "Gross Profit", "Net Income", "Cash Flow", "Gross Margin"] if col in df.columns]
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

st.set_page_config(page_title="SEC Financial Dashboard", layout="wide")
st.title("📊 SEC Financial Dashboard (EDGAR)")

# Initialize fetcher
fetcher = get_sec_fetcher()

# ================= Company Selection ===================
st.subheader("🏢 Company Selection")
tab1, tab2 = st.tabs(["Quick Select", "Search All Companies"])

def picked_quick():
    # When quick is picked, clear full_search so tab1 wins
    st.session_state["full_search"] = ""

def picked_full():
    # When full search is picked, clear quick so tab2 wins
    st.session_state["quick_select"] = None

with tab1:
    default_companies = ["Intel", "Texas Instruments", "Apple Inc.", "Hon Hai Precision Ind. Co., Ltd.", "Marvell Technology, Inc.", "Tesla", "Amazon", "Google"]
    st.selectbox(
        "Choose from popular companies:",
        options=default_companies,
        key="quick_select",
        on_change=picked_quick
    )

with tab2:
    with st.spinner("Loading company database..."):
        all_companies = fetcher.get_company_list()

    if not all_companies:
        st.error("Unable to load company database. Please try again later.")
        st.stop()

    company_names = [comp["name"] for comp in all_companies]
    st.selectbox(
        "Search and select any public company:",
        options=[""] + company_names,  # allow empty so quick can win
        key="full_search",
        help="Type to search through all SEC-registered companies",
        on_change=picked_full
    )

# Single source of truth
company = st.session_state.get("full_search") or st.session_state.get("quick_select")
if not company:
    st.info("Select a company to begin.")
    st.stop()


# ================= Data Processing ===================

# Get company info
selected_cik = fetcher.get_company_cik(company)
if not selected_cik:
    st.error(f"Could not find CIK for {company}. Please try another company.")
    st.stop()

# Get appropriate revenue tag
selected_revenue_tag = fetcher.get_revenue_tag_for_company(company, selected_cik)

st.info(f"**Selected Company:** {company} | **CIK:** {selected_cik} | **Revenue Tag:** {selected_revenue_tag}")

# Load and cache data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data(cik, revenue_tag, company_name):
    return build_financial_table(cik, revenue_tag, fetcher)

with st.spinner(f"Loading financial data for {company}..."):
    df = load_data(selected_cik, selected_revenue_tag, company)

if df.empty:
    st.warning(f"No financial data available for {company}. This could be because:")
    st.write("- The company doesn't file standard XBRL reports")
    st.write("- The revenue tag mapping needs adjustment") 
    st.write("- The company is newly public with limited data")
    st.stop()

# ================= Section 1 - Current Metrics ===================

available_quarters = sorted(df['Quarter'].unique().tolist(), reverse=True)
selected_q = st.selectbox("Select Quarter", options=available_quarters)

try:
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

except Exception as e:
    st.error(f"Error computing financial changes: {e}")

# ================= Section 2 - Historical Charts ===================

st.subheader(f"📉 Financial Trends for {company}")

# Extract available years from the data
df['Year'] = df['date'].dt.year
years = sorted(df['Year'].unique())
if len(years) > 0:
    min_year, max_year = min(years), max(years)

    # Slider for year range
    year_range = st.slider(
        "Select Year Range",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year)
    )

    # Multi-select for quarters
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
    def plot_metric(df, metric, title):
        if metric in df.columns:
            chart_df = df[['date', metric]].dropna()
            if not chart_df.empty:
                chart_df = chart_df.set_index('date')
                st.subheader(f"{title}")
                st.line_chart(chart_df, use_container_width=True)
            else:
                st.info(f"No data available for {title} in the selected range.")
        else:
            st.warning(f"Metric '{metric}' not found in the dataset for {company}.")

    # Create columns for better layout
    col1, col2 = st.columns(2)
    
    with col1:
        plot_metric(filtered_df, "Revenue", "Revenue Over Time")
        plot_metric(filtered_df, "Net Income", "Net Income Over Time")
        if "Gross Margin" in filtered_df.columns:
            plot_metric(filtered_df, "Gross Margin", "Gross Margin Over Time")
    
    with col2:
        if "Gross Profit" in filtered_df.columns:
            plot_metric(filtered_df, "Gross Profit", "Gross Profit Over Time")
        plot_metric(filtered_df, "Cash Flow", "Cash Flow Over Time")

else:
    st.warning("No historical data available for charting.")

st.subheader(f"📈 Financial Summary for {company} – {selected_q}")

# Make the table editable (start from your formatted table)
editable_init = formatted_combined.copy()
editable_init.index.name = "Metric"
editable_init = editable_init.reset_index()

# Toggle: per-row Notes column
include_row_notes = st.checkbox("Add a per-row Notes column", value=False, key="fin_row_notes_toggle")
if include_row_notes and "Notes" not in editable_init.columns:
    editable_init["Notes"] = ""

# Editor
col_cfg = {
    "Metric": st.column_config.TextColumn(required=True, width="large"),
    "Current": st.column_config.TextColumn(help="Edit freely (e.g. $3,591,000,000)"),
    "QoQ Change": st.column_config.TextColumn(help="e.g. +5%, -1%, N/A"),
    "YoY Change": st.column_config.TextColumn(help="e.g. +5%, -1%, N/A"),
}
if include_row_notes:
    col_cfg["Notes"] = st.column_config.TextColumn(
        help="Multi-line supported (Shift+Enter). Use • or - for bullets.",
        width="large"
    )

editable_df = st.data_editor(
    editable_init,
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic",
    column_config=col_cfg,
    key="editable_fin_summary"
)

# Optional section-level Notes (unchanged)
include_notes = st.checkbox("Include a section-level Notes box", value=False, key="fin_notes_toggle")
notes_text = st.text_area("Notes", placeholder="Add context or takeaways…", height=140, key="fin_notes_text") if include_notes else ""

# ---------------- Exports (reflect current edits) ----------------
ts = datetime.now().strftime("%Y-%m-%d %H:%M")
title = f"{company} — Financial Summary ({selected_q})"

# CSV
csv_bytes = editable_df.to_csv(index=False).encode("utf-8")

# Excel (Sheet1: Summary, Sheet2: Notes if used)
xlsx_buf = io.BytesIO()
with pd.ExcelWriter(xlsx_buf, engine="xlsxwriter") as writer:
    editable_df.to_excel(writer, index=False, sheet_name="Summary")
    if include_notes:
        pd.DataFrame({"Notes": [notes_text]}).to_excel(writer, index=False, sheet_name="Notes")
xlsx_buf.seek(0)

# HTML (self-contained; dynamically includes Notes column if present)
def _html_table(df: pd.DataFrame, title: str, notes_text: str) -> bytes:
    cols = list(df.columns)
    css = """
    <style>
      body { font-family:-apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding:24px; }
      h1 { font-size:22px; margin:0 0 8px 0; }
      .meta { color:#666; margin-bottom:16px; }
      table { border-collapse:collapse; width:100%; }
      th, td { border:1px solid #ddd; padding:10px; }
      th { background:#f7f7f7; text-align:left; }
      td { text-align:right; }
      td:first-child, th:first-child { text-align:left; }
      .notes { margin-top:18px; border:1px solid #ddd; padding:12px; border-radius:8px; white-space:pre-wrap; }
      ul { margin:0; padding-left:18px; }
    </style>
    """
    # Convert Notable/Notes text with bullet markers to <ul>
    def bullets_html(text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        # If any line begins with "-" or "•", render as list; else just pre-wrap text
        if any(l.startswith(("•","-")) for l in lines):
            items = "".join(f"<li>{pd.io.common.escape_html(l.lstrip('•- ').strip())}</li>" for l in lines)
            return f"<ul>{items}</ul>"
        return pd.io.common.escape_html("\n".join(lines)).replace("\n","<br>")

    # Render header
    thead = "<tr>" + "".join(f"<th>{pd.io.common.escape_html(c)}</th>" for c in cols) + "</tr>"
    # Render rows
    body_rows = []
    for _, r in df.iterrows():
        tds = []
        for c in cols:
            val = r[c]
            # Left-align text columns (Metric + Notes if present)
            left_align = (c == "Metric") or (c == "Notes")
            if c in ("Notes", "Notable"):
                cell = bullets_html(str(val)) if isinstance(val, str) else ""
            else:
                cell = pd.io.common.escape_html("" if pd.isna(val) else str(val))
            tds.append(f"<td style='text-align:{'left' if left_align else 'right'}'>{cell}</td>")
        body_rows.append("<tr>" + "".join(tds) + "</tr>")
    notes_block = f"<div class='notes'><strong>Notes</strong><br>{pd.io.common.escape_html(notes_text)}</div>" if notes_text.strip() else ""
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>{css}</head>
    <body>
      <h1>{title}</h1>
      <div class="meta">Generated: {ts}</div>
      <table><thead>{thead}</thead><tbody>{''.join(body_rows)}</tbody></table>
      {notes_block}
    </body></html>"""
    return html.encode("utf-8")

html_bytes = _html_table(editable_df, title, notes_text if include_notes else "")

# Plaintext (email-friendly) — dynamically includes Notes column
def _to_plaintext(df: pd.DataFrame, title: str, notes_text: str) -> str:
    cols = list(df.columns)
    widths = [max(len(str(c)), *(len(str(v)) for v in df[c].fillna("").astype(str))) for c in cols]
    def fmt_row(row): return " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(cols))
    header = fmt_row(pd.Series({c: c for c in cols}))
    sep = "-+-".join("-"*w for w in widths)
    body = "\n".join(fmt_row(r) for _, r in df.iterrows())
    extra = f"\n\nNotes:\n{notes_text}" if notes_text.strip() else ""
    return f"{title}\nGenerated: {ts}\n\n{header}\n{sep}\n{body}{extra}\n"

plaintext = _to_plaintext(editable_df, title, notes_text if include_notes else "")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.download_button("⬇️ Download CSV", data=csv_bytes,
                       file_name=f"{company.replace(' ','_')}_financial_summary.csv",
                       mime="text/csv")
with c2:
    st.download_button("⬇️ Download Excel", data=xlsx_buf,
                       file_name=f"{company.replace(' ','_')}_financial_summary.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with c3:
    st.download_button("⬇️ Download HTML", data=html_bytes,
                       file_name=f"{company.replace(' ','_')}_financial_summary.html",
                       mime="text/html")
with c4:
    st_html(
        f"""
        <button onclick="navigator.clipboard.writeText(decodeURIComponent('{requests.utils.quote(plaintext)}'));">
            📋 Copy table
        </button>
        """,
        height=40
    )

with st.expander("Preview plaintext (for email copy)"):
    st.code(plaintext)
# ---------- end ----------