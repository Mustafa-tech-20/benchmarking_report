#!/usr/bin/env python3
"""
Test script for image extraction using COMPANY_SEARCH_ID (Custom Search API).
Uses the exact same queries and approach as images.py.

Usage:
    python test_image_extraction.py "Mahindra Thar"
    python test_image_extraction.py "Hyundai Creta"
"""
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from benchmarking_agent.extraction.images import extract_autocar_images


def generate_html_report(car_name: str, images: dict, output_file: str):
    """Generate HTML report showing extracted images by category."""

    total_images = sum(len(imgs) for imgs in images.values())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Extraction Test - {car_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .header {{
            background: white;
            border-radius: 20px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }}

        .header h1 {{
            font-size: 2.5em;
            color: #2d3748;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            font-size: 1.2em;
            color: #718096;
            margin-bottom: 20px;
        }}

        .stats {{
            display: flex;
            gap: 30px;
            margin-top: 20px;
        }}

        .stat {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            border-radius: 15px;
            text-align: center;
        }}

        .stat .number {{
            font-size: 2.5em;
            font-weight: bold;
            display: block;
        }}

        .stat .label {{
            font-size: 0.9em;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .category {{
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}

        .category h2 {{
            font-size: 1.8em;
            color: #2d3748;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 3px solid #667eea;
        }}

        .category .count {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            margin-left: 10px;
            font-weight: bold;
        }}

        .image-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
            margin-top: 20px;
        }}

        .image-card {{
            background: #f7fafc;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .image-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        }}

        .image-wrapper {{
            width: 100%;
            height: 250px;
            background: #e2e8f0;
            position: relative;
            overflow: hidden;
        }}

        .image-wrapper img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s ease;
        }}

        .image-card:hover .image-wrapper img {{
            transform: scale(1.05);
        }}

        .image-caption {{
            padding: 20px;
        }}

        .image-caption .title {{
            font-weight: 600;
            color: #2d3748;
            margin-bottom: 8px;
            font-size: 1.1em;
        }}

        .image-caption .url {{
            font-size: 0.85em;
            color: #718096;
            word-break: break-all;
            line-height: 1.4;
        }}

        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #a0aec0;
        }}

        .empty-state svg {{
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.3;
        }}

        .footer {{
            text-align: center;
            color: white;
            margin-top: 40px;
            font-size: 0.9em;
            opacity: 0.8;
        }}

        .method-badge {{
            display: inline-block;
            background: #48bb78;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚗 Image Extraction Test</h1>
            <div class="subtitle">{car_name}</div>
            <div class="method-badge">✨ Company Search Engine (Custom Search API)</div>

            <div class="stats">
                <div class="stat">
                    <span class="number">{total_images}</span>
                    <span class="label">Total Images</span>
                </div>
                <div class="stat">
                    <span class="number">{len([k for k, v in images.items() if v])}</span>
                    <span class="label">Categories</span>
                </div>
                <div class="stat">
                    <span class="number">{timestamp}</span>
                    <span class="label">Extracted</span>
                </div>
            </div>
        </div>
"""

    # Categories with icons
    category_icons = {
        "hero": "🎯",
        "exterior": "🚘",
        "interior": "🪑",
        "technology": "📱",
        "comfort": "✨",
        "safety": "🛡️"
    }

    # Generate sections for each category
    for category, icon in category_icons.items():
        images_list = images.get(category, [])
        count = len(images_list)

        html += f"""
        <div class="category">
            <h2>{icon} {category.title()}<span class="count">{count} images</span></h2>
"""

        if images_list:
            html += '<div class="image-grid">'
            for img_url, caption in images_list:
                # Clean caption
                clean_caption = caption.replace('"', '&quot;').replace("'", "&#39;")

                html += f"""
                <div class="image-card">
                    <div class="image-wrapper">
                        <img src="{img_url}" alt="{clean_caption}" loading="lazy"
                             onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 400 300%22%3E%3Crect fill=%22%23e2e8f0%22 width=%22400%22 height=%22300%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 fill=%22%23a0aec0%22 font-family=%22Arial%22 font-size=%2220%22%3EImage Not Available%3C/text%3E%3C/svg%3E'">
                    </div>
                    <div class="image-caption">
                        <div class="title">{clean_caption}</div>
                        <div class="url">{img_url[:80]}{'...' if len(img_url) > 80 else ''}</div>
                    </div>
                </div>
"""
            html += '</div>'
        else:
            html += """
            <div class="empty-state">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <p>No images found in this category</p>
            </div>
"""

        html += "</div>"

    html += """
        <div class="footer">
            <p>Generated by Image Extraction Test</p>
            <p>Method: COMPANY_SEARCH_ID (Custom Search API) → Same as images.py</p>
        </div>
    </div>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    return os.path.abspath(output_file)


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_image_extraction.py 'Car Name'")
        print("\nExamples:")
        print("  python test_image_extraction.py 'Mahindra Thar'")
        print("  python test_image_extraction.py 'Hyundai Creta'")
        print("  python test_image_extraction.py 'Tata Nexon'")
        sys.exit(1)

    car_name = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"TESTING IMAGE EXTRACTION: {car_name}")
    print(f"{'='*60}")
    print(f"\nMethod: COMPANY_SEARCH_ID (Custom Search API)")
    print(f"Using exact same function as images.py\n")

    # Extract images using the same function as benchmarking agent
    print("Extracting images...")
    images = extract_autocar_images(car_name)

    # Count results
    total_images = sum(len(imgs) for imgs in images.values())
    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"\nResults:")
    for category, imgs in images.items():
        print(f"  {category.title()}: {len(imgs)} images")
    print(f"\n  TOTAL: {total_images} images extracted")

    # Generate HTML report
    output_file = f"test_images_{car_name.replace(' ', '_').lower()}.html"
    output_path = generate_html_report(car_name, images, output_file)

    print(f"\n{'='*60}")
    print(f"HTML REPORT GENERATED")
    print(f"{'='*60}")
    print(f"\nFile: {output_path}")
    print(f"\nOpen in browser:")
    print(f"  file://{output_path}")
    print(f"\nOr run:")
    print(f"  open {output_file}")
    print()


if __name__ == "__main__":
    main()
