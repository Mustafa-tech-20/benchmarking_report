#!/usr/bin/env python3
"""
Scraper Pipeline Test Script

Tests the EXACT same scraper functions used in production for:
- Tech Specs
- Feature Specs
- Citations

Skips image extraction to focus only on spec scraping.

Usage:
    python testing/test_scraper.py "Mahindra Thar Roxx" "Jetour T2"
"""

import sys
import os
import json
import time
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the EXACT same functions used in production
from product_planning_agent.core.scraper import (
    phase0_official_site_extraction,
    phase1_per_spec_search,
    phase2_cardekho_fallback,
    fetch_engine_variants,
    CAR_SPECS,
)

# Import actual report generation functions
from product_planning_agent.reports.image_sections import (
    generate_technical_spec_section,
    generate_feature_list_section,
)
from product_planning_agent.reports.html_generator import _generate_citations_html


def run_scraper_pipeline(car_name: str) -> dict:
    """
    Run the EXACT same scraper functions used in production.
    Tests: Phase 0 + Phase 1 (AutoCar fallback) + Phase 2 (CSE for missing) + Engine Variants
    Skips: Image extraction
    """
    print(f"\n{'#'*60}")
    print(f"SCRAPING: {car_name}")
    print(f"{'#'*60}")

    start_time = time.time()

    # Phase 0: Official brand site extraction
    phase0_result = phase0_official_site_extraction(car_name)
    specs = phase0_result["specs"].copy()
    citations = phase0_result["citations"].copy()

    # Phase 1: AutoCar/CarDekho fallback (better spec coverage)
    phase1_result = phase2_cardekho_fallback(car_name, specs)

    # Merge Phase 1 results
    for spec_name, value in phase1_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase1_result["citations"].items():
        if spec_name not in citations:
            citations[spec_name] = citation

    # Phase 2: CSE grouped search (only for missing specs after fallback)
    phase2_result = phase1_per_spec_search(car_name, existing_specs=specs)

    # Merge Phase 2 results (only missing specs)
    for spec_name, value in phase2_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase2_result["citations"].items():
        if spec_name not in citations:
            citations[spec_name] = citation

    # Engine variants
    engine_variants = fetch_engine_variants(car_name)

    # Build final car_data
    car_data = {
        "car_name": car_name,
        "method": "Test: Phase0 + Phase1 (Fallback) + Phase2 (CSE) + Variants",
        "source_urls": [],
        "engine_variants": engine_variants,
    }

    # Collect source URLs
    source_urls = set()
    for citation in citations.values():
        url = citation.get("source_url", "")
        if url and url != "N/A":
            source_urls.add(url)
    car_data["source_urls"] = list(source_urls)

    # Add all specs (EXACT same logic)
    for spec_name in CAR_SPECS:
        value = specs.get(spec_name, "Not Available")
        if not value or value in ["Not found", ""]:
            value = "Not Available"

        car_data[spec_name] = value
        car_data[f"{spec_name}_citation"] = citations.get(
            spec_name,
            {"source_url": "N/A", "citation_text": ""}
        )

    # Stats
    final_count = sum(1 for s in CAR_SPECS if car_data.get(s) and car_data[s] not in ["Not Available", "Not found", ""])
    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"COMPLETE: {final_count}/{len(CAR_SPECS)} specs ({final_count/len(CAR_SPECS)*100:.1f}%) in {elapsed:.1f}s")
    print(f"{'='*60}")

    return car_data


def generate_test_html(comparison_data: dict, output_path: str):
    """Generate HTML report using actual report functions from the agents."""

    car_names = list(comparison_data.keys())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Use ACTUAL report generation functions
    print("\n[HTML Generation] Generating Technical Specifications section...")
    tech_spec_html = generate_technical_spec_section(comparison_data, page_start=1)

    print("[HTML Generation] Generating Feature List section...")
    feature_list_html = generate_feature_list_section(comparison_data, page_start=2)

    print("[HTML Generation] Generating Citations section...")
    citations_html = _generate_citations_html(comparison_data)

    # Count stats
    total_specs = len(CAR_SPECS)
    car_variants = {}
    for car_name in car_names:
        car_data = comparison_data.get(car_name, {})
        variants = car_data.get("engine_variants", [])
        if variants and len(variants) > 0:
            car_variants[car_name] = variants
        else:
            car_variants[car_name] = [{"_single": True}]
    total_variants = sum(len(v) for v in car_variants.values())

    # Raw data JSON
    raw_json = json.dumps(comparison_data, indent=2, default=str)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scraper Test Results - {timestamp}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; color: #333; }}
        .container {{ max-width: 1600px; margin: 0 auto; }}

        /* Header */
        h1 {{ color: #333; margin-bottom: 10px; }}
        h2 {{ color: #dd032b; margin: 30px 0 15px; border-bottom: 2px solid #dd032b; padding-bottom: 10px; }}
        h3 {{ color: #333; margin: 20px 0 10px; }}
        .timestamp {{ color: #666; margin-bottom: 30px; }}

        /* Stats */
        .stats {{ display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
        .stat-card {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); flex: 1; min-width: 150px; }}
        .stat-card h3 {{ color: #dd032b; font-size: 32px; margin-bottom: 5px; }}
        .stat-card p {{ color: #666; }}

        /* Section wrapper - override page styles from report functions */
        .section-wrapper {{ margin-bottom: 40px; }}
        .section-wrapper .page {{
            background: #fff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            page-break-after: auto !important;
            break-after: auto !important;
        }}

        /* Table styles */
        table {{ width: 100%; border-collapse: collapse; background: #fff; margin-bottom: 20px; }}
        th, td {{ padding: 10px 12px; text-align: left; border: 1px solid #ddd; font-size: 13px; }}
        th {{ background: #f8f9fa; color: #333; font-weight: 600; }}
        .variant-header {{ font-size: 11px; background: #f8f9fa; color: #333; border-bottom: 2px solid #dd032b; }}

        /* Category rows */
        .category-row, tr.category-row {{ background: #fff3f3 !important; }}
        .category-row td {{ font-weight: 600; color: #dd032b; }}

        /* Tech spec table header styling */
        .tech-spec-table th {{ background: #dd032b; color: #fff; }}
        .tech-spec-table .variant-header {{ background: #f8f9fa; color: #333; }}

        /* Feature list checkmarks */
        .check {{ color: #28a745; font-weight: bold; }}
        .cross {{ color: #dc3545; font-weight: bold; }}

        /* Citations styling */
        .citation-card {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .citation-car-name {{ color: #dd032b; margin-bottom: 15px; font-size: 18px; }}
        .citation-items {{ max-height: 600px; overflow-y: auto; }}
        .citation-item {{ padding: 10px; border-bottom: 1px solid #eee; }}
        .citation-field-name {{ font-weight: 600; color: #333; }}
        .citation-link {{ color: #dd032b; text-decoration: none; font-size: 12px; word-break: break-all; }}
        .citation-link:hover {{ text-decoration: underline; }}

        /* Raw JSON */
        .raw-json {{
            background: #1a1a1a;
            color: #0f0;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: monospace;
            font-size: 12px;
            max-height: 500px;
            overflow-y: auto;
        }}

        /* Override any print styles */
        @media print {{
            .page {{ page-break-after: auto !important; }}
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .stats {{ flex-direction: column; }}
            .stat-card {{ min-width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Scraper Pipeline Test Results</h1>
        <p class="timestamp">Generated: {timestamp}</p>

        <div class="stats">
            <div class="stat-card">
                <h3>{len(car_names)}</h3>
                <p>Cars Scraped</p>
            </div>
            <div class="stat-card">
                <h3>{total_specs}</h3>
                <p>Total Specs Per Car</p>
            </div>
            <div class="stat-card">
                <h3>{total_variants}</h3>
                <p>Total Engine Variants</p>
            </div>
        </div>

        <h2>Technical Specifications (Actual Report Output)</h2>
        <div class="section-wrapper">
            {tech_spec_html}
        </div>

        <h2>Feature List / Checklist (Actual Report Output)</h2>
        <div class="section-wrapper">
            {feature_list_html}
        </div>

        <h2>Citations (Actual Report Output)</h2>
        <div class="section-wrapper">
            {citations_html}
        </div>

        <h2>Raw Scraped Data (JSON)</h2>
        <pre class="raw-json">{raw_json}</pre>
    </div>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\nHTML report saved to: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python testing/test_scraper.py <car1> <car2> ...")
        print("Example: python testing/test_scraper.py 'Mahindra Thar' 'Hyundai Creta'")
        sys.exit(1)

    car_names = sys.argv[1:]
    print(f"\nTesting scraper pipeline for: {car_names}")

    comparison_data = {}
    for car_name in car_names:
        try:
            car_data = run_scraper_pipeline(car_name)
            comparison_data[car_name] = car_data
        except Exception as e:
            print(f"\nERROR scraping {car_name}: {e}")
            comparison_data[car_name] = {"error": str(e), "car_name": car_name}

    # Generate output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"testing/scraper_test_{timestamp}.html"

    generate_test_html(comparison_data, output_path)

    # Also save raw JSON
    json_path = f"testing/scraper_test_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(comparison_data, f, indent=2, default=str)
    print(f"JSON data saved to: {json_path}")


if __name__ == "__main__":
    main()
