#!/usr/bin/env python3
"""
Image Search Query Tester - HTML Visual Output
Test different queries and see results visually in HTML.

Usage:
    python test_image_search.py
    # Opens HTML file in browser automatically
"""
import asyncio
import sys
import json
import webbrowser
from datetime import datetime
from typing import List, Dict, Tuple
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

# Add project to path
sys.path.insert(0, '/Users/mustafa.mohammed/Documents/Mahindra-CloudRun')

from benchmarking_agent.config import GOOGLE_API_KEY, COMPANY_SEARCH_ID, CUSTOM_SEARCH_URL
from benchmarking_agent.extraction.async_images import (
    calculate_relevance_score,
    select_best_image
)


# ============================================================================
# TEST QUERIES - Customize these!
# ============================================================================

# Test different query formats to see which works best
BATCH_TEST_QUERIES = [
    # Format 1: Simple feature
    ("Toyota Camry", "headlights"),
    ("Toyota Camry", "dashboard"),
    ("Toyota Camry", "interior seats"),

    # Format 2: More specific
    ("Toyota Camry", "LED headlights front"),
    ("Toyota Camry", "dashboard instrument cluster"),
    ("Toyota Camry", "leather seats interior"),

    # Format 3: With descriptors
    ("Toyota Camry", "premium LED headlights"),
    ("Toyota Camry", "digital dashboard display"),
    ("Toyota Camry", "ventilated front seats"),

    # Test other features
    ("Honda Civic", "sunroof panoramic"),
    ("BMW 3 Series", "alloy wheels"),
    ("Tesla Model 3", "touchscreen infotainment"),
]


# ============================================================================
# HTML GENERATOR
# ============================================================================

def generate_html_report(all_results: List[Dict]) -> str:
    """Generate HTML report with visual image comparison."""

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Image Search Test Results</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header p {{ font-size: 1.1em; opacity: 0.9; }}
        .query-section {{
            margin: 30px;
            padding: 30px;
            background: #f8f9fa;
            border-radius: 12px;
            border-left: 5px solid #667eea;
        }}
        .query-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #dee2e6;
        }}
        .query-title {{
            font-size: 1.5em;
            font-weight: 600;
            color: #2c3e50;
        }}
        .query-meta {{
            display: flex;
            gap: 15px;
            font-size: 0.9em;
            color: #6c757d;
        }}
        .results-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .result-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            position: relative;
        }}
        .result-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
        }}
        .result-card.selected {{
            border: 3px solid #28a745;
            box-shadow: 0 5px 25px rgba(40, 167, 69, 0.4);
        }}
        .selected-badge {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: #28a745;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 600;
            z-index: 10;
        }}
        .result-rank {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: #667eea;
            color: white;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            z-index: 10;
        }}
        .image-container {{
            width: 100%;
            height: 200px;
            overflow: hidden;
            border-radius: 8px;
            background: #f0f0f0;
            margin-bottom: 12px;
        }}
        .image-container img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .score-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
        .score-high {{ background: #d4edda; color: #155724; }}
        .score-medium {{ background: #fff3cd; color: #856404; }}
        .score-low {{ background: #f8d7da; color: #721c24; }}
        .result-title {{
            font-weight: 600;
            margin-bottom: 8px;
            color: #2c3e50;
            font-size: 0.95em;
            line-height: 1.4;
            max-height: 2.8em;
            overflow: hidden;
        }}
        .result-snippet {{
            font-size: 0.85em;
            color: #6c757d;
            line-height: 1.5;
            max-height: 4.5em;
            overflow: hidden;
        }}
        .summary {{
            margin: 30px;
            padding: 30px;
            background: #e8f5e9;
            border-radius: 12px;
            border-left: 5px solid #4caf50;
        }}
        .summary h2 {{
            color: #2e7d32;
            margin-bottom: 20px;
        }}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }}
        .summary-table th {{
            background: #4caf50;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        .summary-table td {{
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .summary-table tr:hover {{
            background: #f5f5f5;
        }}
        .no-results {{
            padding: 40px;
            text-align: center;
            color: #6c757d;
            font-size: 1.2em;
        }}
        .timestamp {{
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Image Search Test Results</h1>
            <p>Visual comparison of image search relevance and selection</p>
        </div>
"""

    # Add each query result
    for result in all_results:
        if result["status"] != "success":
            html += f"""
        <div class="query-section">
            <div class="query-header">
                <div class="query-title">❌ {result['query']}</div>
            </div>
            <div class="no-results">
                {result.get('error', 'No results found')}
            </div>
        </div>
"""
            continue

        # Get selected image index
        selected_rank = result.get('selected_rank', 0)

        html += f"""
        <div class="query-section">
            <div class="query-header">
                <div class="query-title">{result['query']}</div>
                <div class="query-meta">
                    <span>📊 {result['total_results']} results</span>
                    <span>⭐ Best: {result['best_score']:.2f}</span>
                    <span>✅ Selected: #{selected_rank}</span>
                </div>
            </div>
            <div class="results-grid">
"""

        # Add each image result
        for img_result in result.get('results', []):
            rank = img_result['rank']
            score = img_result['score']
            title = img_result['title'] or 'No title'
            snippet = img_result['snippet'] or 'No description'
            img_url = img_result['url']

            is_selected = rank == selected_rank

            # Determine score badge
            if score >= 0.5:
                score_class = "score-high"
                score_emoji = "🟢"
            elif score >= 0.3:
                score_class = "score-medium"
                score_emoji = "🟡"
            else:
                score_class = "score-low"
                score_emoji = "🔴"

            selected_class = "selected" if is_selected else ""
            selected_badge = '<div class="selected-badge">✅ SELECTED</div>' if is_selected else ''

            html += f"""
                <div class="result-card {selected_class}">
                    <div class="result-rank">#{rank}</div>
                    {selected_badge}
                    <div class="image-container">
                        <img src="{img_url}" alt="{title}" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22200%22%3E%3Crect width=%22300%22 height=%22200%22 fill=%22%23ddd%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23999%22%3EImage Not Available%3C/text%3E%3C/svg%3E'">
                    </div>
                    <div class="score-badge {score_class}">
                        {score_emoji} Score: {score:.2f}
                    </div>
                    <div class="result-title">{title[:100]}</div>
                    <div class="result-snippet">{snippet[:150]}</div>
                </div>
"""

        html += """
            </div>
        </div>
"""

    # Add summary table
    successful = [r for r in all_results if r["status"] == "success"]
    successful.sort(key=lambda x: x["best_score"], reverse=True)

    if successful:
        html += """
        <div class="summary">
            <h2>📊 Summary & Best Practices</h2>
            <table class="summary-table">
                <thead>
                    <tr>
                        <th>Query</th>
                        <th>Results</th>
                        <th>Best Score</th>
                        <th>Selected</th>
                        <th>Quality</th>
                    </tr>
                </thead>
                <tbody>
"""

        for r in successful:
            quality = "🟢 Excellent" if r['best_score'] >= 0.7 else "🟡 Good" if r['best_score'] >= 0.5 else "🟠 Fair" if r['best_score'] >= 0.3 else "🔴 Poor"
            html += f"""
                    <tr>
                        <td>{r['query']}</td>
                        <td>{r['total_results']}</td>
                        <td>{r['best_score']:.2f}</td>
                        <td>#{r['selected_rank']}</td>
                        <td>{quality}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
        </div>
"""

    # Footer
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html += f"""
        <div class="timestamp">
            Generated: {timestamp}
        </div>
    </div>
</body>
</html>
"""

    return html


# ============================================================================
# IMAGE SEARCH TESTER
# ============================================================================

async def test_image_search(
    car_name: str,
    feature_query: str,
    num_results: int = 10
) -> Dict:
    """
    Test image search and show detailed results.

    Args:
        car_name: Car name
        feature_query: Feature to search for
        num_results: Number of results to fetch

    Returns:
        Dict with search results and analysis
    """
    query = f"{car_name} {feature_query}"

    print(f"\n{'='*80}")
    print(f"🔍 Testing Query: '{query}'")
    print(f"{'='*80}")

    async with aiohttp.ClientSession() as session:
        try:
            params = {
                "key": GOOGLE_API_KEY,
                "cx": COMPANY_SEARCH_ID,
                "q": query,
                "searchType": "image",
                "num": num_results,
                "imgSize": "medium",
                "safe": "active",
                "imgType": "photo",
            }

            async with session.get(CUSTOM_SEARCH_URL, params=params) as response:
                if response.status != 200:
                    print(f"❌ Error: HTTP {response.status}")
                    print("eror response",response.text)
                    return {
                        "query": query,
                        "status": "error",
                        "error": f"HTTP {response.status}"
                    }

                data = await response.json()
                items = data.get("items", [])

                if not items:
                    print(f"❌ No results found")
                    return {
                        "query": query,
                        "status": "no_results",
                        "results": []
                    }

                # Analyze each result
                results = []
                for i, item in enumerate(items, 1):
                    img_url = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")

                    # Calculate relevance score
                    score = calculate_relevance_score(item, feature_query)

                    results.append({
                        "rank": i,
                        "url": img_url,
                        "title": title,
                        "snippet": snippet,
                        "score": score
                    })

                # Select best image
                best_result = select_best_image(items, feature_query)
                if best_result:
                    best_url, best_score = best_result
                    best_idx = next((i for i, r in enumerate(results) if r["url"] == best_url), -1)

                return {
                    "query": query,
                    "car_name": car_name,
                    "feature_query": feature_query,
                    "status": "success",
                    "total_results": len(results),
                    "best_score": best_score if best_result else 0.0,
                    "selected_rank": best_idx + 1 if best_result else None,
                    "results": results
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            return {
                "query": query,
                "status": "exception",
                "error": str(e)
            }


# ============================================================================
# BATCH TEST MODE
# ============================================================================

async def batch_test():
    """Test multiple queries and generate HTML report."""
    print(f"\n🔍 Testing {len(BATCH_TEST_QUERIES)} image search queries...")
    print(f"⏳ Please wait...")

    all_results = []

    for i, (car_name, feature_query) in enumerate(BATCH_TEST_QUERIES, 1):
        print(f"  [{i}/{len(BATCH_TEST_QUERIES)}] {car_name} - {feature_query}")
        result = await test_image_search(car_name, feature_query, num_results=5)
        all_results.append(result)
        await asyncio.sleep(0.5)  # Small delay between requests

    # Generate HTML report
    print(f"\n📝 Generating HTML report...")
    html_content = generate_html_report(all_results)

    # Save HTML file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_filename = f"image_search_results_{timestamp}.html"

    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ Report generated: {html_filename}")
    print(f"🌐 Opening in browser...")

    # Open in browser
    webbrowser.open(f"file://{Path(html_filename).absolute()}")

    return html_filename


# ============================================================================
# INTERACTIVE MODE
# ============================================================================

async def interactive_test():
    """Interactive mode to test custom queries."""
    print(f"\n{'#'*80}")
    print(f"# INTERACTIVE IMAGE SEARCH TESTER")
    print(f"{'#'*80}\n")
    print("Test custom queries and see visual results in HTML")
    print("Type 'done' when finished\n")

    custom_queries = []

    while True:
        try:
            car_name = input("\n🚗 Car name (or 'done' to finish): ").strip()
            if car_name.lower() in ['quit', 'exit', 'q', 'done']:
                break

            feature_query = input("🔍 Feature query: ").strip()
            if feature_query.lower() in ['quit', 'exit', 'q', 'done']:
                break

            if not car_name or not feature_query:
                print("❌ Please provide both car name and feature query")
                continue

            custom_queries.append((car_name, feature_query))
            print(f"✅ Added: {car_name} - {feature_query}")

        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            break

    if custom_queries:
        print(f"\n🔍 Testing {len(custom_queries)} custom queries...")
        all_results = []

        for car_name, feature_query in custom_queries:
            result = await test_image_search(car_name, feature_query, num_results=5)
            all_results.append(result)
            await asyncio.sleep(0.5)

        # Generate HTML report
        print(f"\n📝 Generating HTML report...")
        html_content = generate_html_report(all_results)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_filename = f"custom_image_search_{timestamp}.html"

        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"\n✅ Report generated: {html_filename}")
        print(f"🌐 Opening in browser...")

        webbrowser.open(f"file://{Path(html_filename).absolute()}")

    else:
        print("\n❌ No queries to test")


# ============================================================================
# MAIN
# ============================================================================

async def single_query_test(car_name: str, feature_query: str, num_results: int = 10):
    """Test a single query and generate HTML report."""
    print(f"\n🔍 Testing: {car_name} - {feature_query}")
    print(f"⏳ Searching for {num_results} images...")

    result = await test_image_search(car_name, feature_query, num_results)

    # Generate HTML report
    print(f"\n📝 Generating HTML report...")
    html_content = generate_html_report([result])

    # Save HTML file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_filename = f"image_search_{car_name.replace(' ', '_')}_{feature_query.replace(' ', '_')}_{timestamp}.html"

    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ Report generated: {html_filename}")
    print(f"🌐 Opening in browser...")

    # Open in browser
    webbrowser.open(f"file://{Path(html_filename).absolute()}")

    return html_filename


def main():
    """Main entry point."""
    load_dotenv()

    # Check if API keys are set
    if not GOOGLE_API_KEY or not COMPANY_SEARCH_ID:
        print("❌ Error: Missing API keys!")
        print("   Set GOOGLE_API_KEY and COMPANY_SEARCH_ID in .env file")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"🔍 IMAGE SEARCH QUERY TESTER")
    print(f"{'='*80}")
    print(f"\nThis tool helps you find the best queries for each car feature image.")
    print(f"Results will open in your browser as a visual HTML report.\n")

    # Parse arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--custom":
            # Interactive mode
            asyncio.run(interactive_test())

        elif sys.argv[1] == "--query":
            # Single query mode
            if len(sys.argv) < 4:
                print("❌ Usage: python test_image_search.py --query \"Car Name\" \"feature query\" [num_results]")
                print("   Example: python test_image_search.py --query \"Toyota Camry\" \"headlights\" 10")
                sys.exit(1)

            car_name = sys.argv[2]
            feature_query = sys.argv[3]
            num_results = int(sys.argv[4]) if len(sys.argv) > 4 else 10

            asyncio.run(single_query_test(car_name, feature_query, num_results))

        elif sys.argv[1] in ["-h", "--help"]:
            print("""
Usage:
    # Default: Run batch test with predefined queries
    python test_image_search.py

    # Single query test
    python test_image_search.py --query "Toyota Camry" "headlights" [num_results]

    # Custom interactive mode
    python test_image_search.py --custom

Examples:
    python test_image_search.py --query "Honda Civic" "dashboard"
    python test_image_search.py --query "BMW 3 Series" "LED headlights" 15
    python test_image_search.py --custom
""")
        else:
            print("❌ Invalid argument. Use --help for usage info")
    else:
        # Batch test by default
        print(f"Running default batch test with {len(BATCH_TEST_QUERIES)} queries...")
        print(f"(Use --query for single test, --custom for interactive, --help for info)\n")
        asyncio.run(batch_test())


if __name__ == "__main__":
    main()
