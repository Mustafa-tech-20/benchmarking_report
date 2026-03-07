"""
Technical Specifications HTML Report Generator
Generates professional technical specification reports similar to Mahindra launch reports
Includes: Technical Specs, Variant Walk, Price Ladder, Dimensions
"""

from typing import Dict, List, Any, Optional


def create_technical_specs_html(comparison_data: Dict[str, Any]) -> str:
    """
    Create a technical specifications report with tables and charts.

    Args:
        comparison_data: Dictionary with car comparison data including specs

    Returns:
        HTML string with technical specifications report
    """

    car_names = list(comparison_data.keys())

    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Technical Specifications Report</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
        }

        .header {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            letter-spacing: 3px;
        }

        .section {
            padding: 40px;
            margin-bottom: 20px;
        }

        .section-title {
            font-size: 2em;
            color: #1e3a8a;
            margin-bottom: 30px;
            text-align: center;
            letter-spacing: 2px;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 15px;
        }

        /* Technical Specifications Table */
        .tech-table {
            width: 100%;
            border-collapse: collapse;
            margin: 30px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .tech-table th {
            background: #1e3a8a;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            border: 1px solid #ddd;
        }

        .tech-table td {
            padding: 12px 15px;
            border: 1px solid #ddd;
            background: white;
        }

        .tech-table tr:nth-child(even) td {
            background: #f8f9fa;
        }

        .tech-table .category-header {
            background: #3b82f6;
            color: white;
            font-weight: 600;
            text-align: center;
            padding: 12px;
        }

        .spec-name {
            font-weight: 600;
            color: #333;
            width: 200px;
        }

        /* Comparison Grid */
        .comparison-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }

        .car-card {
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 5px solid #3b82f6;
        }

        .car-card h3 {
            color: #1e3a8a;
            font-size: 1.5em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e5e7eb;
        }

        .spec-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #f3f4f6;
        }

        .spec-item:last-child {
            border-bottom: none;
        }

        .spec-label {
            color: #6b7280;
            font-weight: 500;
        }

        .spec-value {
            color: #111827;
            font-weight: 600;
        }

        /* Price Ladder */
        .price-section {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 10px;
            margin: 30px 0;
        }

        .price-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .price-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
            border-top: 4px solid #3b82f6;
        }

        .price-card .car-name {
            font-size: 1.2em;
            color: #1e3a8a;
            font-weight: 600;
            margin-bottom: 10px;
        }

        .price-card .price {
            font-size: 1.8em;
            color: #10b981;
            font-weight: 700;
        }

        /* Performance Metrics */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }

        .metric-box {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .metric-box .label {
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 8px;
        }

        .metric-box .value {
            font-size: 1.8em;
            font-weight: 700;
        }

        /* Variant Walk Table */
        .variant-table {
            width: 100%;
            border-collapse: collapse;
            margin: 30px 0;
            font-size: 0.9em;
        }

        .variant-table th {
            background: #1e3a8a;
            color: white;
            padding: 12px;
            text-align: center;
            border: 1px solid #ddd;
        }

        .variant-table td {
            padding: 10px;
            border: 1px solid #ddd;
            text-align: center;
        }

        .variant-table .feature-name {
            text-align: left;
            font-weight: 500;
            background: #f8f9fa;
        }

        .variant-table .available {
            color: #10b981;
            font-weight: 700;
        }

        .variant-table .not-available {
            color: #ef4444;
        }

        /* Footer */
        .footer {
            background: #1e3a8a;
            color: white;
            padding: 30px;
            text-align: center;
            margin-top: 40px;
        }

        .note-box {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }

        @media print {
            body {
                background: white;
                padding: 0;
            }

            .section {
                page-break-after: always;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TECHNICAL SPECIFICATIONS</h1>
            <p>Comprehensive Comparison Report</p>
        </div>
"""

    # Generate comparison data for all cars
    html += """
        <div class="section">
            <h2 class="section-title">Vehicle Specifications Overview</h2>
            <div class="comparison-grid">
"""

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            html += f"""
            <div class="car-card">
                <h3>{car_name}</h3>
"""
            # Key specs
            key_specs = [
                ("Price Range", "price_range"),
                ("Engine", "performance"),
                ("Torque", "torque"),
                ("Transmission", "transmission"),
                ("Mileage", "mileage"),
                ("Seating", "seating_capacity"),
                ("Safety Rating", "user_rating")
            ]

            for label, key in key_specs:
                value = car_data.get(key, "N/A")
                if value and value not in ["Not Available", "Not found", "N/A"]:
                    html += f"""
                <div class="spec-item">
                    <span class="spec-label">{label}</span>
                    <span class="spec-value">{value}</span>
                </div>
"""

            html += """
            </div>
"""

    html += """
            </div>
        </div>
"""

    # Technical Specifications Table
    html += """
        <div class="section">
            <h2 class="section-title">Detailed Technical Specifications</h2>
            <table class="tech-table">
                <thead>
                    <tr>
                        <th>Specification</th>
"""

    for car_name in car_names:
        html += f"                        <th>{car_name}</th>\n"

    html += """
                    </tr>
                </thead>
                <tbody>
"""

    # Specification categories
    spec_categories = {
        "Engine & Performance": [
            ("Power", "performance"),
            ("Torque", "torque"),
            ("Transmission", "transmission"),
            ("Acceleration", "acceleration")
        ],
        "Efficiency": [
            ("Mileage", "mileage"),
            ("Fuel Type", "price_range")  # Approximate
        ],
        "Comfort & Features": [
            ("Seating Capacity", "seating_capacity"),
            ("Climate Control", "climate_control"),
            ("Infotainment", "infotainment_screen"),
            ("Sunroof", "sunroof"),
            ("Boot Space", "boot_space")
        ],
        "Safety": [
            ("Safety Rating", "user_rating"),
            ("Safety Features", "vehicle_safety_features"),
            ("Braking", "braking")
        ],
        "Dynamics": [
            ("Steering", "steering"),
            ("Ride Quality", "ride_quality"),
            ("NVH Levels", "nvh")
        ]
    }

    for category, specs in spec_categories.items():
        html += f"""
                    <tr>
                        <td colspan="{len(car_names) + 1}" class="category-header">{category}</td>
                    </tr>
"""

        for spec_name, spec_key in specs:
            html += f"""
                    <tr>
                        <td class="spec-name">{spec_name}</td>
"""

            for car_name in car_names:
                car_data = comparison_data.get(car_name, {})
                value = car_data.get(spec_key, "N/A")
                if value in ["Not Available", "Not found", ""]:
                    value = "N/A"

                html += f"                        <td>{value}</td>\n"

            html += "                    </tr>\n"

    html += """
                </tbody>
            </table>
        </div>
"""

    # Price Comparison
    html += """
        <div class="section">
            <h2 class="section-title">Price Comparison</h2>
            <div class="price-section">
                <div class="price-grid">
"""

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            price = car_data.get("price_range", "N/A")

            html += f"""
                    <div class="price-card">
                        <div class="car-name">{car_name}</div>
                        <div class="price">{price}</div>
                    </div>
"""

    html += """
                </div>
            </div>
        </div>
"""

    # Performance Metrics Section
    html += """
        <div class="section">
            <h2 class="section-title">Performance Metrics</h2>
"""

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            html += f"""
            <h3 style="color: #1e3a8a; margin: 30px 0 20px 0;">{car_name}</h3>
            <div class="metrics-grid">
"""

            metrics = [
                ("Power", car_data.get("performance", "N/A")),
                ("Torque", car_data.get("torque", "N/A")),
                ("Mileage", car_data.get("mileage", "N/A")),
                ("0-100", car_data.get("acceleration", "N/A"))
            ]

            for label, value in metrics:
                if value not in ["Not Available", "Not found", "N/A", ""]:
                    html += f"""
                <div class="metric-box">
                    <div class="label">{label}</div>
                    <div class="value">{value}</div>
                </div>
"""

            html += """
            </div>
"""

    html += """
        </div>
"""

    # Note box
    html += """
        <div class="section">
            <div class="note-box">
                <strong>Note:</strong> All specifications are indicative and may vary based on variant,
                region, and model year. Please verify with official sources before making purchase decisions.
            </div>
        </div>

        <div class="footer">
            <p>Technical Specifications Report</p>
            <p style="margin-top: 10px; font-size: 0.9em;">
                Generated for Product Planning Analysis
            </p>
        </div>
    </div>
</body>
</html>
"""

    return html


def save_technical_specs_html(comparison_data: Dict[str, Any], filename: str = "technical_specs_report.html") -> str:
    """
    Create and save technical specifications HTML report.

    Args:
        comparison_data: Dictionary with car comparison data
        filename: Output filename

    Returns:
        Path to saved HTML file
    """
    html_content = create_technical_specs_html(comparison_data)

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return filename
