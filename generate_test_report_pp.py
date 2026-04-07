#!/usr/bin/env python3
"""
Quick Test Report Generator for Product Planning Agent
Converts comparison JSON to HTML report for local testing (no GCS upload).

Usage:
    python generate_test_report_pp.py input.json
    python generate_test_report_pp.py input.json output.html
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add product_planning_agent to path
sys.path.insert(0, str(Path(__file__).parent))

from product_planning_agent.reports.html_generator import create_comparison_chart_html


def generate_test_report(json_path: str, output_path: str = None):
    """
    Generate Product Planning HTML report from comparison JSON.

    Args:
        json_path: Path to the comparison JSON file
        output_path: Optional path for output HTML (defaults to pp_report_<timestamp>.html)
    """
    # Load JSON data
    print(f"Loading JSON from: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract required fields
    comparison_data = data.get('comparison_data', {})
    cars_compared = data.get('cars_compared', [])
    # Use attribute_proscons (nested dict format) for the HTML generator, not youtube_proscons (list format)
    proscons_data = data.get('attribute_proscons', {})
    # Fallback: if proscons_data is a list (wrong format), skip it
    if isinstance(proscons_data, list):
        print("WARNING: proscons_data is a list, expected dict. Skipping proscons section.")
        proscons_data = {}

    # Generate a default summary if not provided
    summary = data.get('summary', f"Comparison between {' and '.join(cars_compared)}")

    if not comparison_data:
        print("ERROR: No comparison_data found in JSON")
        sys.exit(1)

    if not cars_compared:
        print("ERROR: No cars_compared found in JSON")
        sys.exit(1)

    print(f"Generating Product Planning report for: {', '.join(cars_compared)}")
    print(f"  - Comparison data: ✓")
    print(f"  - Summary: ✓")
    print(f"  - YouTube pros/cons: {'✓' if proscons_data else '✗'}")

    # Check for variant walk data
    variant_count = 0
    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and 'variant_walk' in car_data:
            variants = car_data.get('variant_walk', {}).get('variants', {})
            variant_count += len(variants)

    if variant_count > 0:
        print(f"  - Variant walk: ✓ ({variant_count} variants found)")
    else:
        print(f"  - Variant walk: ✗")

    # Generate HTML (Product Planning requires 3 arguments)
    html_content = create_comparison_chart_html(comparison_data, summary, proscons_data)

    # Determine output path
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"pp_report_{timestamp}.html"

    # Write HTML file
    print(f"\nWriting HTML to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✓ Product Planning report generated successfully!")
    print(f"✓ Open in browser: file://{Path(output_path).absolute()}")
    print(f"\nFeatures included:")
    print(f"  - Specs comparison table")
    print(f"  - Image galleries (Exterior, Interior, Technology, Comfort, Safety)")
    print(f"  - Variant Walk (feature progression)")
    print(f"  - Price Ladder (Petrol & Diesel)")
    print(f"  - YouTube Pros & Cons Analysis")
    print(f"  - AI-Powered Summary")
    print(f"  - Citations (click 'Citations' in nav)")

    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_test_report_pp.py <input.json> [output.html]")
        print("\nExample:")
        print("  python generate_test_report_pp.py ooutput4.json")
        print("  python generate_test_report_pp.py ooutput4.json my_pp_report.html")
        print("\nThis generates a Product Planning Agent HTML report with:")
        print("  - Variant Walk & Price Ladder")
        print("  - YouTube Pros/Cons")
        print("  - Full citations")
        sys.exit(1)

    json_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(json_path).exists():
        print(f"ERROR: File not found: {json_path}")
        sys.exit(1)

    try:
        generate_test_report(json_path, output_path)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
