import json
import time
from typing import Dict, Any

from vertexai.generative_models import GenerativeModel

from benchmarking_agent.utils.helpers import generate_sales_data_urls


def extract_sales_data_from_url(url: str, car_name: str) -> Dict[str, Any]:
    """
    Use Gemini to extract ONLY sales data from a URL.
    """
    try:
        model = GenerativeModel("gemini-2.5-flash")

        prompt = f"""
        You are visiting this webpage: {url}

        Your task: Extract SALES DATA for "{car_name}" from this webpage.

        CRITICAL INSTRUCTIONS:
        1. Look for sales figures, units sold, market performance
        2. Search for monthly sales, yearly sales, market share data
        3. Look in news articles, sales reports, market analysis sections
        4. Extract actual numbers and percentages
        5. Only use "Not Available" if you absolutely cannot find the information

        Extract these SALES fields:
        {{
            "car_name": "{car_name}",
            "monthly_sales": "Average monthly sales units (e.g., 5,000 units/month, 5K units)",
            "monthly_sales_citation": "Exact text: 'Monthly sales average 5,000 units' - Found in: Sales Report section"
        }}

        SEARCH PATTERNS TO LOOK FOR:
        - Sales figures: "units sold", "monthly sales", "yearly sales", "annual sales"
        - Numbers: "5,000 units", "60K sales", "5000 units/month"
        - Market: "market share", "segment share", "% of market"
        - Trends: "YoY", "year-over-year", "growth", "decline", "increase", "decrease"
        - Time periods: "in 2026", "last month", "Q1 2025", "FY2026"

        CITATION FORMAT:
        For each field's citation, provide:
        1. The EXACT text snippet from the webpage (in quotes)
        2. The location/section where you found it

        Return ONLY the JSON object with actual extracted sales values, no additional text.
        If you cannot find specific sales information, use "Not Available" for both value and citation.
        """

        response = model.generate_content([prompt])

        # Parse response
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        sales_data = json.loads(response_text.strip())
        return sales_data

    except json.JSONDecodeError as e:
        print(f"   JSON parsing error for sales data: {e}")
        return {"car_name": car_name, "error": "Failed to parse sales data"}
    except Exception as e:
        print(f"    Sales data extraction failed: {e}")
        return {"car_name": car_name, "error": f"Failed to extract sales data: {str(e)}"}


def scrape_sales_data(car_name: str) -> Dict[str, Any]:
    """
    Scrape sales data for a car from multiple sources.
    Uses a separate Gemini call focused only on sales metrics.
    """
    print(f"\n{'='*60}")
    print(f"Scraping SALES DATA for: {car_name}")
    print(f"{'='*60}")

    urls = generate_sales_data_urls(car_name)

    sales_fields = ["monthly_sales"]
    aggregated_sales = {
        "car_name": car_name,
        "sales_source_urls": []
    }

    missing_fields = sales_fields.copy()

    for idx, url in enumerate(urls):
        if not missing_fields:
            print(f"\n All sales fields populated! Stopping early.")
            break

        print(f"\n[Sales URL {idx+1}/{len(urls)}] Analyzing: {url}")
        print(f"   Missing fields: {', '.join(missing_fields)}")

        sales_data = extract_sales_data_from_url(url, car_name)

        if "error" not in sales_data:
            newly_found = []
            for field in missing_fields[:]:
                value = sales_data.get(field)
                if value and value not in ["Not Available", "N/A", None, ""] and str(value).strip():
                    aggregated_sales[field] = value
                    citation_key = f"{field}_citation"
                    if citation_key in sales_data and sales_data[citation_key]:
                        aggregated_sales[citation_key] = {
                            "source_url": url,
                            "citation_text": sales_data[citation_key]
                        }
                    missing_fields.remove(field)
                    newly_found.append(field)

            if newly_found:
                aggregated_sales["sales_source_urls"].append(url)
                print(f"    Found {len(newly_found)} sales metrics: {', '.join(newly_found)}")
        else:
            print(f"    No sales data found")

        time.sleep(2)  # Rate limiting

    # Fill missing fields
    for field in missing_fields:
        aggregated_sales[field] = "Not Available"
        aggregated_sales[f"{field}_citation"] = {
            "source_url": "N/A",
            "citation_text": "Sales data not available from any source"
        }

    populated = len(sales_fields) - len(missing_fields)
    print(f"\n Sales data complete: {populated}/{len(sales_fields)} fields populated")

    return aggregated_sales
