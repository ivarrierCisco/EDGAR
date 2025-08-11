import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# Replace this with your real API key
API_KEY = 'GV3lQA95GYzn0b6TEjhveb1hTLtU8tDr'

def get_financial_data(ticker, start_year, end_year):
    url = f'https://financialmodelingprep.com/api/v3/income-statement/{ticker}?limit=120&apikey={API_KEY}'
    cash_flow_url = f'https://financialmodelingprep.com/api/v3/cash-flow-statement/{ticker}?limit=120&apikey={API_KEY}'

    income_data = requests.get(url).json()
    cash_data = requests.get(cash_flow_url).json()

    df = []
    for item in income_data:
        year = int(item['date'][:4])
        if start_year <= year <= end_year:
            revenue = item.get('revenue')
            gross_profit = item.get('grossProfit')
            net_income = item.get('netIncome')
            gross_margin = (gross_profit / revenue) if revenue else None

            cf_item = next((cf for cf in cash_data if cf['date'] == item['date']), {})
            fcf = cf_item.get('freeCashFlow')

            df.append({
                'Year': year,
                'Revenue': revenue,
                'Gross Margin': gross_margin,
                'Net Income': net_income,
                'Free Cash Flow': fcf
            })

    return pd.DataFrame(df).sort_values(by='Year')

def plot_metric(df, column, title, ylabel):
    fig, ax = plt.subplots()
    ax.plot(df['Year'], df[column], marker='o', linestyle='-')
    ax.set_title(title)
    ax.set_xlabel('Year')
    ax.set_ylabel(ylabel)
    ax.grid(True)
    st.pyplot(fig)

# Streamlit UI
st.set_page_config(layout="wide")
st.title("📊 Company Financial Metrics Viewer")

ticker = st.text_input("Enter Company Ticker (e.g., AAPL, MSFT)")
col1, col2 = st.columns(2)
with col1:
    start_year = st.number_input("Start Year", min_value=2000, max_value=2025, value=2018)
with col2:
    end_year = st.number_input("End Year", min_value=2000, max_value=2025, value=2024)

if st.button("Get Financials") and ticker:
    with st.spinner("Fetching data..."):
        try:
            df = get_financial_data(ticker.upper(), start_year, end_year)
            if df.empty:
                st.warning("No data found for the selected range.")
            else:
                st.subheader("📋 Raw Financial Data")
                st.dataframe(df.set_index("Year"))

                st.subheader("📈 Financial Trends Over Time")
                col1, col2 = st.columns(2)
                with col1:
                    plot_metric(df, 'Revenue', f"{ticker.upper()} - Revenue Over Time", "Revenue ($)")
                    plot_metric(df, 'Gross Margin', f"{ticker.upper()} - Gross Margin Over Time", "Gross Margin (Ratio)")
                with col2:
                    plot_metric(df, 'Net Income', f"{ticker.upper()} - Net Income Over Time", "Net Income ($)")
                    plot_metric(df, 'Free Cash Flow', f"{ticker.upper()} - Free Cash Flow Over Time", "Free Cash Flow ($)")

        except Exception as e:
            st.error(f"Error fetching data: {e}")
