import requests
import json
from typing import Dict, Optional, List

class SECDataFetcher:
    def __init__(self):
        self.headers = {
            'User-Agent': "ishavarrier@address.com"
        }
        
        # Revenue tag mappings - can be extended as needed
        self.company_revenue_preferences = {
            "Intel": [ "RevenueFromContractWithCustomerExcludingAssessedTax"],
            "Texas Instruments": ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        }

        # --- Global fallback revenue tag candidates, in order of preference ---
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
            "Total Assets": "Assets",
            "Total Liabilities": "Liabilities",
            "Shareholders Equity": "StockholdersEquity"
        }
        
        # Cache for CIK lookups to avoid repeated API calls
        self.cik_cache = {}
    
    def get_company_cik(self, company_name: str) -> Optional[str]:
        """
        Fetch CIK for a given company name using SEC's company tickers API
        """
        if company_name in self.cik_cache:
            return self.cik_cache[company_name]
        
        try:
            # SEC provides a company tickers JSON file
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                companies = response.json()
                
                # Search for company (case-insensitive partial match)
                for entry in companies.values():
                    if company_name.lower() in entry['title'].lower():
                        cik = str(entry['cik_str']).zfill(10)  # Pad with zeros
                        self.cik_cache[company_name] = cik
                        return cik
                        
        except Exception as e:
            print(f"Error fetching CIK for {company_name}: {e}")
        
        return None
    
    def get_revenue_tag_for_company(self, company_name: str) -> str:
        """
        Get the appropriate revenue tag for a company based on mappings
        Falls back to most common revenue tag if not found
        """
        for tag, companies in self.company_revenue_preferences.items():
            if company_name in companies:
                return tag
        
        # Default fallback - most common revenue tag
        return "SalesRevenueNet"
    
    def fetch_sec_data(self, cik: str, tag: str) -> Optional[Dict]:
        """
        Fetch data from SEC API for given CIK and tag
        """
        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch data for tag {tag}. Status: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching SEC data: {e}")
            return None
    
    def get_company_data(self, company_name: str, metrics: List[str] = None) -> Dict:
        """
        Main method to get financial data for any company
        
        Args:
            company_name: Name of the company
            metrics: List of metrics to fetch. If None, fetches common metrics
            
        Returns:
            Dictionary with fetched data for each metric
        """
        if metrics is None:
            metrics = ["Revenue"] + list(self.common_tags.keys())
        
        # Get CIK for the company
        cik = self.get_company_cik(company_name)
        if not cik:
            return {"error": f"Could not find CIK for company: {company_name}"}
        
        results = {"company": company_name, "cik": cik, "data": {}}
        
        for metric in metrics:
            if metric == "Revenue":
                # Handle revenue with company-specific tag
                tag = self.get_revenue_tag_for_company(company_name)
            elif metric in self.common_tags:
                # Handle common metrics
                tag = self.common_tags[metric]
            else:
                # Skip unknown metrics
                results["data"][metric] = {"error": f"Unknown metric: {metric}"}
                continue
            
            # Fetch the data
            data = self.fetch_sec_data(cik, tag)
            results["data"][metric] = {
                "tag": tag,
                "data": data
            }
        
        return results
    
    def add_revenue_mapping(self, revenue_tag: str, companies: List[str]):
        """
        Add new revenue tag mapping for companies
        """
        if revenue_tag not in self.company_revenue_preferences:
            self.company_revenue_preferences[revenue_tag] = []
        
        self.company_revenue_preferences[revenue_tag].extend(companies)
    
    def search_companies(self, search_term: str) -> List[Dict]:
        """
        Search for companies matching the search term
        """
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                companies = response.json()
                matches = []
                
                for entry in companies.values():
                    if search_term.lower() in entry['title'].lower():
                        matches.append({
                            "name": entry['title'],
                            "ticker": entry['ticker'],
                            "cik": str(entry['cik_str']).zfill(10)
                        })
                
                return matches[:10]  # Return top 10 matches
                
        except Exception as e:
            print(f"Error searching companies: {e}")
        
        return []

# Usage example
if __name__ == "__main__":
    fetcher = SECDataFetcher()
    
    # Example 1: Get data for a known company
    intel_data = fetcher.get_company_data("Intel", ["Revenue", "Net Income", "Gross Profit"])
    print("Intel Data:", json.dumps(intel_data, indent=2))
    
    # Example 2: Search for companies
    # matches = fetcher.search_companies("Tesla")
    # print("Tesla Search Results:", matches)
    
    # # Example 3: Add new revenue mapping
    # fetcher.add_revenue_mapping("RevenueFromContractWithCustomerExcludingAssessedTax", ["NVIDIA"])
    
    # # Example 4: Get data for newly mapped company
    # nvidia_data = fetcher.get_company_data("NVIDIA", ["Revenue", "Net Income"])
    # print("NVIDIA Data:", json.dumps(nvidia_data, indent=2))