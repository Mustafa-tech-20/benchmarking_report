#!/usr/bin/env python3
"""
Quick Test Report Generator for Vehicle Development Agent
Converts comparison JSON to HTML report for local testing (no GCS upload).

Usage:
    python generate_test_report_vd.py input.json
    python generate_test_report_vd.py input.json output.html
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add vehicle_development_agent to path
sys.path.insert(0, str(Path(__file__).parent))

from vehicle_development_agent.reports.html_generator import create_comparison_chart_html


def generate_test_report(json_path: str, output_path: str = None):
    """
    Generate Vehicle Development HTML report from comparison JSON.

    Args:
        json_path: Path to the comparison JSON file
        output_path: Optional path for output HTML (defaults to vd_report_<timestamp>.html)
    """
    # Load JSON data
    print(f"Loading JSON from: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract required fields
    comparison_data = data.get('comparison_data', {})
    cars_compared = data.get('cars_compared', [])
    comparative_graphs = data.get('comparative_graphs', {})
    detailed_reviews = data.get('detailed_reviews', {})

    # Generate a default summary if not provided
    summary = data.get('summary', f"Comparison between {' and '.join(cars_compared)}")

    if not comparison_data:
        print("ERROR: No comparison_data found in JSON")
        sys.exit(1)

    if not cars_compared:
        print("ERROR: No cars_compared found in JSON")
        sys.exit(1)

    print(f"Generating Vehicle Development report for: {', '.join(cars_compared)}")
    print(f"  - Comparison data: ✓")
    print(f"  - Summary: ✓")
    print(f"  - Comparative graphs: {'✓' if comparative_graphs else '✗'}")
    print(f"  - Detailed reviews: {'✓' if detailed_reviews else '✗'}")

    # Check for image data
    image_count = 0
    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict):
            for key, value in car_data.items():
                if 'images' in key.lower() or 'image_sections' in key.lower():
                    if isinstance(value, (list, dict)):
                        image_count += 1

    if image_count > 0:
        print(f"  - Image sections: ✓ ({image_count} sections found)")
    else:
        print(f"  - Image sections: ✗")

    # Generate HTML (Vehicle Development requires 4 arguments)
    html_content = create_comparison_chart_html(
        comparison_data,
        summary,
        comparative_graphs,
        detailed_reviews
    )

    # Determine output path
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"vd_report_{timestamp}.html"

    # Write HTML file
    print(f"\nWriting HTML to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✓ Vehicle Development report generated successfully!")
    print(f"✓ Open in browser: file://{Path(output_path).absolute()}")
    print(f"\nFeatures included:")
    print(f"  - Specs comparison table")
    print(f"  - Features Checklist (Safety, Seats, Technology, etc.)")
    print(f"  - Image galleries (Exterior, Interior, Technology)")
    print(f"  - Comparative Graphs (Performance, Dimensions, Safety)")
    print(f"  - Detailed Reviews & Ratings")
    print(f"  - AI-Powered Summary")
    print(f"  - Citations (click 'Citations' in nav)")

    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_test_report_vd.py <input.json> [output.html]")
        print("\nExample:")
        print("  python generate_test_report_vd.py ooutput4.json")
        print("  python generate_test_report_vd.py ooutput4.json my_vd_report.html")
        print("\nThis generates a Vehicle Development Agent HTML report with:")
        print("  - Features Checklist & Specs Table")
        print("  - Comparative Graphs")
        print("  - Detailed Reviews")
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
