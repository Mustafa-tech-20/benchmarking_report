#!/usr/bin/env python3
"""
Quick Test Report Generator
Converts comparison JSON to HTML report for local testing (no GCS upload).

Usage:
    python generate_test_report.py input.json
    python generate_test_report.py input.json output.html
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add benchmarking_agent to path
sys.path.insert(0, str(Path(__file__).parent))

from benchmarking_agent.reports.html_generator import create_comparison_chart_html


def generate_test_report(json_path: str, output_path: str = None):
    """
    Generate HTML report from comparison JSON.

    Args:
        json_path: Path to the comparison JSON file
        output_path: Optional path for output HTML (defaults to report_<timestamp>.html)
    """
    # Load JSON data
    print(f"Loading JSON from: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract required fields
    comparison_data = data.get('comparison_data', {})
    cars_compared = data.get('cars_compared', [])

    # Generate a default summary if not provided
    summary = data.get('summary', f"Comparison between {' and '.join(cars_compared)}")

    if not comparison_data:
        print("ERROR: No comparison_data found in JSON")
        sys.exit(1)

    if not cars_compared:
        print("ERROR: No cars_compared found in JSON")
        sys.exit(1)

    print(f"Generating report for: {', '.join(cars_compared)}")

    # Generate HTML
    html_content = create_comparison_chart_html(comparison_data, summary)

    # Determine output path
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"report_{timestamp}.html"

    # Write HTML file
    print(f"Writing HTML to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✓ Report generated successfully!")
    print(f"✓ Open in browser: file://{Path(output_path).absolute()}")

    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_test_report.py <input.json> [output.html]")
        print("\nExample:")
        print("  python generate_test_report.py output.json")
        print("  python generate_test_report.py output.json my_report.html")
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
