#!/usr/bin/env python3
"""
Test script for hero section image search queries.
Tests different keyword strategies and displays results in an HTML file.
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
COMPANY_SEARCH_ID = os.getenv("COMPANY_SEARCH_ID")  # Automotive websites
CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# Test car names
TEST_CARS = [
    "Mahindra Thar",
    "Hyundai Creta",
    "Tata Nexon",
    "Maruti Brezza",
]

# Different query strategies to test for hero images
HERO_QUERY_STRATEGIES = [
    # Current strategy
    "{car} official exterior",

    # Alternative strategies
    "{car} front view official",
    "{car} 2024 front quarter",
    "{car} hero shot",
    "{car} press image front",
    "{car} official photo",
    "{car} front 3/4 view",
    "{car} studio shot",
    "{car} showroom front",
    "{car} launch image",
    "{car} official wallpaper",
    "{car} front angle high resolution",
]


def search_image(query: str, num_results: int = 3) -> list:
    """
    Search for images using Google Custom Search API.
    Returns list of image results with url, title, and snippet.
    """
    params = {
        "key": GOOGLE_API_KEY,
        "cx": COMPANY_SEARCH_ID,
        "q": query,
        "searchType": "image",
        "num": num_results,
        "imgSize": "large",
    }

    try:
        response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            results = []
            for item in items:
                results.append({
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "context_link": item.get("image", {}).get("contextLink", ""),
                    "width": item.get("image", {}).get("width", 0),
                    "height": item.get("image", {}).get("height", 0),
                })
            return results
        elif response.status_code == 429:
            return [{"error": "Rate limited"}]
        else:
            return [{"error": f"HTTP {response.status_code}"}]
    except Exception as e:
        return [{"error": str(e)}]


def generate_html_report(all_results: dict) -> str:
    """Generate HTML report showing all search results."""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hero Image Search Test Results</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }}
        .car-section {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .car-name {{
            font-size: 24px;
            font-weight: 700;
            color: #dd032b;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #dd032b;
        }}
        .query-section {{
            margin-bottom: 25px;
            padding: 15px;
            background: #f9f9f9;
            border-radius: 8px;
        }}
        .query-text {{
            font-family: monospace;
            font-size: 14px;
            background: #e9ecef;
            padding: 8px 12px;
            border-radius: 4px;
            margin-bottom: 15px;
            color: #333;
        }}
        .results-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }}
        .image-card {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
        }}
        .image-card img {{
            width: 100%;
            height: 200px;
            object-fit: cover;
            display: block;
        }}
        .image-card .info {{
            padding: 10px;
            font-size: 12px;
        }}
        .image-card .title {{
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .image-card .dims {{
            color: #666;
        }}
        .image-card .source {{
            color: #0066cc;
            font-size: 11px;
            word-break: break-all;
        }}
        .error {{
            color: #dc3545;
            padding: 10px;
            background: #ffe6e6;
            border-radius: 4px;
        }}
        .no-results {{
            color: #666;
            font-style: italic;
            padding: 10px;
        }}
        .summary {{
            background: #e8f5e9;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .summary h2 {{
            color: #2e7d32;
            margin-bottom: 10px;
        }}
        .timestamp {{
            text-align: center;
            color: #666;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <h1>Hero Image Search Test Results</h1>
    <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="summary">
        <h2>Test Summary</h2>
        <p>Testing {len(TEST_CARS)} cars with {len(HERO_QUERY_STRATEGIES)} query strategies each.</p>
        <p>Search Engine: COMPANY_SEARCH_ID (automotive websites)</p>
    </div>
"""

    for car_name, queries in all_results.items():
        html += f"""
    <div class="car-section">
        <div class="car-name">{car_name}</div>
"""
        for query, results in queries.items():
            html += f"""
        <div class="query-section">
            <div class="query-text">Query: "{query}"</div>
            <div class="results-grid">
"""
            if not results:
                html += '                <div class="no-results">No results found</div>\n'
            else:
                for result in results:
                    if "error" in result:
                        html += f'                <div class="error">Error: {result["error"]}</div>\n'
                    else:
                        html += f"""                <div class="image-card">
                    <img src="{result['url']}" alt="{result['title']}" onerror="this.src='https://via.placeholder.com/300x200?text=Image+Not+Found'">
                    <div class="info">
                        <div class="title">{result['title'][:60]}...</div>
                        <div class="dims">{result['width']}x{result['height']}</div>
                        <div class="source">{result['context_link'][:50]}...</div>
                    </div>
                </div>
"""
            html += """            </div>
        </div>
"""
        html += """    </div>
"""

    html += """</body>
</html>
"""
    return html


def main():
    print("=" * 60)
    print("HERO IMAGE SEARCH TEST")
    print("=" * 60)
    print(f"Testing {len(TEST_CARS)} cars with {len(HERO_QUERY_STRATEGIES)} query strategies\n")

    all_results = {}

    for car in TEST_CARS:
        print(f"\n[{car}] Testing queries...")
        all_results[car] = {}

        for strategy in HERO_QUERY_STRATEGIES:
            query = strategy.format(car=car)
            print(f"  Searching: {query}")

            results = search_image(query, num_results=3)
            all_results[car][query] = results

            # Show quick summary
            if results and "error" not in results[0]:
                print(f"    Found {len(results)} images")
            elif results and "error" in results[0]:
                print(f"    Error: {results[0]['error']}")
            else:
                print(f"    No results")

    # Generate HTML report
    print("\n" + "=" * 60)
    print("Generating HTML report...")

    html_content = generate_html_report(all_results)

    output_file = "hero_image_test_results.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Report saved to: {output_file}")
    print(f"Open in browser: file://{os.path.abspath(output_file)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
