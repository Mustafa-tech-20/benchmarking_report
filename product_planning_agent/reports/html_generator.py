
from typing import Dict, Any, Optional

import json
import re

from product_planning_agent.reports.image_sections import (
    generate_hero_section,
    generate_image_gallery_section,
    generate_technical_spec_section,
    generate_feature_list_section,
    generate_lifecycle_section,
    generate_vehicle_highlights_section,
    generate_venn_diagram_section,
    get_image_section_styles
)


# ============================================================================
# ROBUST DATA EXTRACTION HELPERS
# ============================================================================

def extract_price(price_str: str) -> float:
    """
    Extract price value in Lakhs from various formats.

    Handles:
    - "₹11.35 Lakh onwards"
    - "Rs 12.5 - 18.9 Lakh"
    - "₹10.79 lakh to ₹20.05 lakh"
    - "11.35"
    - "Rs. 12,50,000"
    """
    if not price_str or price_str in ["Not Available", "Not found", "N/A"]:
        return 0.0

    try:
        # Clean the string
        s = str(price_str).lower()

        # Handle crore to lakh conversion
        if 'crore' in s:
            crore_match = re.search(r'(\d+\.?\d*)\s*crore', s)
            if crore_match:
                return float(crore_match.group(1)) * 100

        # Remove currency symbols and common words
        s = re.sub(r'[₹$]', '', s)
        s = re.sub(r'\b(rs\.?|rupees?|inr|lakh|lakhs?|onwards|starting|from|ex-showroom|approx\.?)\b', '', s, flags=re.IGNORECASE)
        s = s.replace(',', '')

        # Find all numbers (including decimals)
        numbers = re.findall(r'\d+\.?\d*', s)

        if not numbers:
            return 0.0

        # Convert to floats and filter valid prices
        values = [float(n) for n in numbers if n]
        values = [v for v in values if 1 <= v <= 500]  # Valid price range in lakhs

        if not values:
            return 0.0

        # Return average if range, else first value
        if len(values) >= 2:
            return sum(values[:2]) / 2
        return values[0]

    except Exception:
        return 0.0


def extract_mileage(mileage_str: str) -> float:
    """
    Extract mileage value in kmpl from various formats.

    Handles:
    - "15.2 kmpl"
    - "14.5 - 18.2 kmpl"
    - "16 km/l"
    - "15.2"
    """
    if not mileage_str or mileage_str in ["Not Available", "Not found", "N/A"]:
        return 0.0

    try:
        s = str(mileage_str).lower()

        # Skip EV range values
        if any(x in s for x in ['km/charge', 'kwh', 'range', 'charge', 'electric']):
            return 0.0

        # Remove units
        s = re.sub(r'\b(kmpl|km/l|kpl|mileage)\b', '', s, flags=re.IGNORECASE)

        # Find all numbers
        numbers = re.findall(r'\d+\.?\d*', s)

        if not numbers:
            return 0.0

        values = [float(n) for n in numbers if n]
        # Filter valid mileage values (typically 5-50 kmpl)
        values = [v for v in values if 5 <= v <= 50]

        if not values:
            return 0.0

        if len(values) >= 2:
            return sum(values[:2]) / 2
        return values[0]

    except Exception:
        return 0.0


def extract_rating(rating_str: str) -> float:
    """
    Extract rating value (0-5 scale) from various formats.

    Handles:
    - "4.5/5"
    - "4.2 out of 5"
    - "4.3 stars"
    - "4.5"
    """
    if not rating_str or rating_str in ["Not Available", "Not found", "N/A"]:
        return 0.0

    try:
        s = str(rating_str).lower()

        # Try to find X/5 or X out of 5 pattern
        match = re.search(r'(\d+\.?\d*)\s*(?:/|out\s*of)\s*5', s)
        if match:
            val = float(match.group(1))
            return val if 0 <= val <= 5 else 0.0

        # Try to find X/10 pattern and convert
        match = re.search(r'(\d+\.?\d*)\s*/\s*10', s)
        if match:
            val = float(match.group(1)) / 2
            return val if 0 <= val <= 5 else 0.0

        # Find first number that looks like a rating
        numbers = re.findall(r'\d+\.?\d*', s)
        for n in numbers:
            val = float(n)
            if 0 <= val <= 5:
                return val

        return 0.0

    except Exception:
        return 0.0


def extract_seating(seating_str: str) -> int:
    """
    Extract seating capacity from various formats.

    Handles:
    - "5 Seater"
    - "5/7 Seater"
    - "5"
    - "7-seater"
    """
    if not seating_str or seating_str in ["Not Available", "Not found", "N/A"]:
        return 0

    try:
        s = str(seating_str).lower()

        # Find all numbers
        numbers = re.findall(r'\d+', s)

        if not numbers:
            return 0

        # Take the first reasonable seating value (2-9)
        for n in numbers:
            val = int(n)
            if 2 <= val <= 9:
                return val

        return 0

    except Exception:
        return 0


def extract_sales(sales_str: str) -> int:
    """
    Extract monthly sales volume from various formats.

    Handles:
    - "18,522 units"
    - "3853 units (January 2026)"
    - "approximately 15000"
    - "10,000 - 15,000 units"
    """
    if not sales_str or sales_str in ["Not Available", "Not found", "N/A"]:
        return 0

    try:
        s = str(sales_str).lower()

        # Remove common words
        s = re.sub(r'\b(units?|approximately|approx\.?|around|about|between|monthly|sales)\b', '', s, flags=re.IGNORECASE)
        s = s.replace(',', '')

        # Find all numbers
        numbers = re.findall(r'\d+', s)

        if not numbers:
            return 0

        values = [int(n) for n in numbers]
        # Filter valid sales values (typically 100 - 50000)
        values = [v for v in values if 100 <= v <= 100000]

        if not values:
            return 0

        # Return first value (usually the main figure)
        return values[0]

    except Exception:
        return 0


# ============================================================================
# CITATIONS HTML GENERATION
# ============================================================================

def _generate_citations_html(comparison_data: Dict[str, Any]) -> str:
    """Generate HTML for citations section."""
    citations_html = ""
    
    for car_name, car_data in comparison_data.items():
        if "error" in car_data:
            continue
            
        citations_html += f"""
        <div class="citation-card animate-on-scroll">
            <h3 class="citation-car-name">{car_data.get('car_name', car_name).upper()}</h3>
            <div class="citation-items">
        """
        
        # Get all citation fields
        citation_fields = [
            # Original 19 specs
            ("price_range", "Price Range"),
            ("mileage", "Mileage"),
            ("user_rating", "User Rating"),
            ("seating_capacity", "Seating Capacity"),
            ("braking", "Braking"),
            ("steering", "Steering"),
            ("climate_control", "Climate Control"),
            ("battery", "Battery"),
            ("transmission", "Transmission"),
            ("brakes", "Brakes"),
            ("wheels", "Wheels"),
            ("performance", "Performance"),
            ("body", "Body Type"),
            ("vehicle_safety_features", "Vehicle Safety Features"),
            ("lighting", "Lighting"),
            ("audio_system", "Audio System"),
            ("off_road", "Off-Road"),
            ("interior", "Interior"),
            ("seat", "Seat"),
            ("monthly_sales", "Monthly Sales"),
            
            # NEW: 72 Additional specs
            ("ride", "Ride"),
            ("performance_feel", "Performance Feel"),
            ("driveability", "Driveability"),
            ("manual_transmission_performance", "Manual Transmission Performance"),
            ("pedal_operation", "Pedal Operation"),
            ("automatic_transmission_performance", "Automatic Transmission Performance"),
            ("powertrain_nvh", "Powertrain NVH"),
            ("wind_nvh", "Wind NVH"),
            ("road_nvh", "Road NVH"),
            ("visibility", "Visibility"),
            ("seats_restraint", "Seats Restraint"),
            ("impact", "Impact"),
            ("seat_cushion", "Seat Cushion"),
            ("turning_radius", "Turning Radius"),
            ("epb", "Electronic Parking Brake"),
            ("brake_performance", "Brake Performance"),
            ("stiff_on_pot_holes", "Stiff on Pot Holes"),
            ("bumps", "Bumps"),
            ("jerks", "Jerks"),
            ("pulsation", "Pulsation"),
            ("stability", "Stability"),
            ("shakes", "Shakes"),
            ("shudder", "Shudder"),
            ("shocks", "Shocks"),
            ("grabby", "Grabby"),
            ("spongy", "Spongy"),
            ("telescopic_steering", "Telescopic Steering"),
            ("torque", "Torque"),
            ("nvh", "NVH"),
            ("wind_noise", "Wind Noise"),
            ("tire_noise", "Tire Noise"),
            ("crawl", "Crawl"),
            ("gear_shift", "Gear Shift"),
            ("pedal_travel", "Pedal Travel"),
            ("gear_selection", "Gear Selection"),
            ("turbo_noise", "Turbo Noise"),
            ("resolution", "Resolution"),
            ("touch_response", "Touch Response"),
            ("button", "Button"),
            ("apple_carplay", "Apple CarPlay"),
            ("digital_display", "Digital Display"),
            ("blower_noise", "Blower Noise"),
            ("soft_trims", "Soft Trims"),
            ("armrest", "Armrest"),
            ("sunroof", "Sunroof"),
            ("irvm", "IRVM"),
            ("orvm", "ORVM"),
            ("window", "Window"),
            ("alloy_wheel", "Alloy Wheel"),
            ("tail_lamp", "Tail Lamp"),
            ("boot_space", "Boot Space"),
            ("led", "LED"),
            ("drl", "DRL"),
            ("ride_quality", "Ride Quality"),
            ("infotainment_screen", "Infotainment Screen"),
            ("chasis", "Chassis"),
            ("straight_ahead_stability", "Straight Ahead Stability"),
            ("wheelbase", "Wheelbase"),
            ("egress", "Egress"),
            ("ingress", "Ingress"),
            ("corner_stability", "Corner Stability"),
            ("parking", "Parking"),
            ("manoeuvring", "Manoeuvring"),
            ("city_performance", "City Performance"),
            ("highway_performance", "Highway Performance"),
            ("wiper_control", "Wiper Control"),
            ("sensitivity", "Sensitivity"),
            ("rattle", "Rattle"),
            ("headrest", "Headrest"),
            ("acceleration", "Acceleration"),
            ("response", "Response"),
            ("door_effort", "Door Effort"),
        ]
        
        for field, field_display in citation_fields:
            citation_key = f"{field}_citation"
            if citation_key in car_data and car_data[citation_key]:
                citation = car_data[citation_key]
                
                if isinstance(citation, dict):
                    source_url = citation.get('source_url', 'Unknown')
                    citation_text = citation.get('citation_text', 'No citation available')
                else:
                    source_url = car_data.get('source_urls', ['Unknown'])[0] if 'source_urls' in car_data else 'Unknown'
                    citation_text = citation
                
                # Update display for RAG sources
                if "RAG Corpus" in str(source_url):
                    source_url = "RAG Engine"
                    citation_text = f"Retrieved from RAG Engine: {citation_text}"
                
                citations_html += f"""
                <div class="citation-item">
                    <div class="citation-field-name">{field_display}</div>
                    <div class="citation-text">&nbsp;</div>
                    <a href="{source_url}" target="_blank" class="citation-link">
                        {source_url}
                    </a>
                </div>
                """
        
        citations_html += """
            </div>
        </div>
        """
    
    return citations_html




def generate_checklist_table(comparison_data: Dict[str, Any]) -> str:
    """
    Generate checklist comparison table with ✓, ✗, numbers, and short text values.

    Args:
        comparison_data: Dictionary containing car comparison data

    Returns:
        HTML string for the checklist table
    """
    # Transform all cars to checklist format
    checklists = {}
    car_names = []

    for car_name, car_data in comparison_data.items():
        if "error" not in car_data:
            checklist = transform_to_checklist(car_data)
            checklists[car_name] = checklist
            car_names.append(car_name)

    if not car_names:
        return "<p>No data available for checklist comparison.</p>"

    # Generate table HTML
    html = """
    <div class="checklist-table-container">
        <div class="table-responsive">
            <table class="checklist-table">
                <thead>
                    <tr>
                        <th class="category-col">Category</th>
                        <th class="feature-col">Feature</th>
"""

    # Add car name columns
    for car_name in car_names:
        html += f'                        <th class="car-col">{car_name}</th>\n'

    html += """
                    </tr>
                </thead>
                <tbody>
"""

    # Safety & Airbags Section
    html += """
                    <tr class="category-header">
                        <td colspan="{}" class="category-name">Safety & Airbags</td>
                    </tr>
""".format(len(car_names) + 2)

    safety_features = [
        ("Number of Airbags", "safety", "airbag_total"),
        ("Knee Airbag", "safety", "airbag_knee"),
        ("Curtain Airbag", "safety", "airbag_curtain"),
        ("Side Airbag", "safety", "airbag_side"),
        ("ABS (Anti-lock Braking)", "safety", "abs"),
        ("DSC / ESP", "safety", "dsc"),
        ("ADAS", "safety", "adas"),
        ("NCAP Rating", "safety", "ncap_rating"),
        ("Hill Hold / Hill Descent", "safety", "hill_hold"),
        ("TPMS (Tyre Pressure Monitor)", "safety", "tpms"),
        ("ISOFIX Child Seat Anchors", "safety", "isofix"),
    ]

    for idx, (feature_name, category, key) in enumerate(safety_features):
        html += f'                    <tr>\n'
        if idx == 0:
            html += f'                        <td class="category-cell" rowspan="{len(safety_features)}">Safety</td>\n'
        html += f'                        <td class="feature-cell">{feature_name}</td>\n'
        for car_name in car_names:
            value = checklists[car_name][category][key]
            html += f'                        <td class="value-cell">{format_checklist_value(value)}</td>\n'
        html += f'                    </tr>\n'

    # Seats & Comfort Section
    html += """
                    <tr class="category-header">
                        <td colspan="{}" class="category-name">Seats & Comfort</td>
                    </tr>
""".format(len(car_names) + 2)

    seat_features = [
        ("Seat Material", "seats", "material"),
        ("Backrest Split Ratio", "seats", "backrest_split"),
        ("Lumbar Support", "seats", "lumbar_support"),
        ("Driver Seat Height Adjust", "seats", "seat_height_adjust"),
        ("Ventilated Seats - Driver", "seats", "ventilation_driver"),
        ("Ventilated Seats - Co-Driver", "seats", "ventilation_codriver"),
        ("Rear Seat Folding", "seats", "rear_fold"),
        ("Rear Center Armrest", "seats", "rear_armrest"),
    ]

    for idx, (feature_name, category, key) in enumerate(seat_features):
        html += f'                    <tr>\n'
        if idx == 0:
            html += f'                        <td class="category-cell" rowspan="{len(seat_features)}">Seats</td>\n'
        html += f'                        <td class="feature-cell">{feature_name}</td>\n'
        for car_name in car_names:
            value = checklists[car_name][category][key]
            html += f'                        <td class="value-cell">{format_checklist_value(value)}</td>\n'
        html += f'                    </tr>\n'

    # Seatbelt Section
    html += """
                    <tr class="category-header">
                        <td colspan="{}" class="category-name">Seatbelt Features</td>
                    </tr>
""".format(len(car_names) + 2)

    seatbelt_features = [
        ("Pretensioner", "seatbelts", "pretensioner"),
        ("Load Limiter", "seatbelts", "load_limiter"),
        ("Height Adjuster", "seatbelts", "height_adjuster"),
    ]

    for idx, (feature_name, category, key) in enumerate(seatbelt_features):
        html += f'                    <tr>\n'
        if idx == 0:
            html += f'                        <td class="category-cell" rowspan="{len(seatbelt_features)}">Seatbelt</td>\n'
        html += f'                        <td class="feature-cell">{feature_name}</td>\n'
        for car_name in car_names:
            value = checklists[car_name][category][key]
            html += f'                        <td class="value-cell">{format_checklist_value(value)}</td>\n'
        html += f'                    </tr>\n'

    # Technology Section
    html += """
                    <tr class="category-header">
                        <td colspan="{}" class="category-name">Technology</td>
                    </tr>
""".format(len(car_names) + 2)

    tech_features = [
        ("Touchscreen Size", "technology", "infotainment_size"),
        ("Digital Instrument Cluster", "technology", "digital_display"),
        ("Apple CarPlay / Android Auto", "technology", "apple_carplay"),
        ("Audio System", "technology", "audio_system"),
        ("Cruise Control", "technology", "cruise_control"),
        ("Parking Camera", "technology", "parking_camera"),
        ("Parking Sensors", "technology", "parking_sensors"),
        ("Push Button Start", "technology", "push_button_start"),
    ]

    for idx, (feature_name, category, key) in enumerate(tech_features):
        html += f'                    <tr>\n'
        if idx == 0:
            html += f'                        <td class="category-cell" rowspan="{len(tech_features)}">Technology</td>\n'
        html += f'                        <td class="feature-cell">{feature_name}</td>\n'
        for car_name in car_names:
            value = checklists[car_name][category][key]
            html += f'                        <td class="value-cell">{format_checklist_value(value)}</td>\n'
        html += f'                    </tr>\n'

    # Comfort Features Section
    html += """
                    <tr class="category-header">
                        <td colspan="{}" class="category-name">Comfort Features</td>
                    </tr>
""".format(len(car_names) + 2)

    comfort_features = [
        ("Sunroof / Panoramic Sunroof", "comfort", "sunroof"),
        ("Climate Control", "comfort", "climate_control"),
        ("Armrest", "comfort", "armrest"),
        ("Adjustable Headrest", "comfort", "headrest"),
        ("Power Windows", "comfort", "power_windows"),
        ("Auto-Dimming IRVM", "comfort", "auto_irvm"),
        ("Power Adjustable ORVM", "comfort", "power_orvm"),
        ("Electronic Parking Brake", "comfort", "epb"),
    ]

    for idx, (feature_name, category, key) in enumerate(comfort_features):
        html += f'                    <tr>\n'
        if idx == 0:
            html += f'                        <td class="category-cell" rowspan="{len(comfort_features)}">Comfort</td>\n'
        html += f'                        <td class="feature-cell">{feature_name}</td>\n'
        for car_name in car_names:
            value = checklists[car_name][category][key]
            html += f'                        <td class="value-cell">{format_checklist_value(value)}</td>\n'
        html += f'                    </tr>\n'

    # Exterior Features Section
    html += """
                    <tr class="category-header">
                        <td colspan="{}" class="category-name">Exterior Features</td>
                    </tr>
""".format(len(car_names) + 2)

    exterior_features = [
        ("LED Headlights", "exterior", "led_headlights"),
        ("LED DRLs", "exterior", "led_drls"),
        ("LED Tail Lamps", "exterior", "led_tail_lamps"),
        ("Alloy Wheels", "exterior", "alloy_wheels"),
        ("Wheel Size", "exterior", "wheel_size"),
        ("Tyre Size", "exterior", "tyre_size"),
    ]

    for idx, (feature_name, category, key) in enumerate(exterior_features):
        html += f'                    <tr>\n'
        if idx == 0:
            html += f'                        <td class="category-cell" rowspan="{len(exterior_features)}">Exterior</td>\n'
        html += f'                        <td class="feature-cell">{feature_name}</td>\n'
        for car_name in car_names:
            value = checklists[car_name][category][key]
            html += f'                        <td class="value-cell">{format_checklist_value(value)}</td>\n'
        html += f'                    </tr>\n'

    # Dimensions & Specs Section
    html += """
                    <tr class="category-header">
                        <td colspan="{}" class="category-name">Dimensions & Specs</td>
                    </tr>
""".format(len(car_names) + 2)

    dimension_features = [
        ("Wheelbase", "dimensions", "wheelbase"),
        ("Ground Clearance", "dimensions", "ground_clearance"),
        ("Turning Radius", "dimensions", "turning_radius"),
        ("Boot Space", "dimensions", "boot_space"),
        ("Fuel Type", "dimensions", "fuel_type"),
        ("Engine Displacement", "dimensions", "engine_displacement"),
    ]

    for idx, (feature_name, category, key) in enumerate(dimension_features):
        html += f'                    <tr>\n'
        if idx == 0:
            html += f'                        <td class="category-cell" rowspan="{len(dimension_features)}">Dimensions</td>\n'
        html += f'                        <td class="feature-cell">{feature_name}</td>\n'
        for car_name in car_names:
            value = checklists[car_name][category][key]
            html += f'                        <td class="value-cell">{format_checklist_value(value)}</td>\n'
        html += f'                    </tr>\n'

    html += """
                </tbody>
            </table>
        </div>
    </div>
"""

    return html


def generate_variant_walk_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate variant walk section showing features across different variants.

    Args:
        comparison_data: Dictionary with car comparison data

    Returns:
        HTML string for variant walk section
    """
    if not comparison_data:
        return "<p>No variant data available.</p>"

    html = """
    <style>
        .variant-walk-container {
            overflow-x: auto;
            margin: 30px 0;
        }

        .variant-walk-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 800px;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .variant-walk-table th {
            background: #000;
            color: white;
            padding: 20px 15px;
            text-align: center;
            font-size: 1.3em;
            font-weight: 700;
            border: 1px solid #fff;
        }

        .variant-walk-table td {
            padding: 15px;
            border: 1px solid #e0e0e0;
            vertical-align: top;
            font-size: 0.9em;
            line-height: 1.8;
        }

        .variant-features {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .variant-features li {
            padding: 5px 0 5px 20px;
            position: relative;
        }

        .variant-features li:before {
            content: "•";
            position: absolute;
            left: 5px;
            font-weight: bold;
        }

        .feature-added {
            color: #10b981;
            font-weight: 500;
        }

        .feature-added:before {
            content: "+ ";
            color: #10b981;
            font-weight: bold;
        }

        .feature-deleted {
            color: #dd032b;
            font-weight: 500;
        }

        .feature-deleted:before {
            content: "- ";
            color: #dd032b;
            font-weight: bold;
        }

        .feature-standard:before {
            color: #000;
        }

        .variant-section-title {
            font-weight: 700;
            color: #000;
            margin-top: 10px;
            margin-bottom: 5px;
        }

        .variant-sub-section {
            font-size: 0.85em;
            color: #6b7280;
            font-style: italic;
            margin-top: 15px;
            margin-bottom: 5px;
        }
    </style>

    <div class="variant-walk-container">
"""

    # For each car, generate its variant walk
    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            # Get variant walk data with safety check for None
            variant_walk = car_data.get('variant_walk') or {}
            variants = (variant_walk.get('variants') or {}) if isinstance(variant_walk, dict) else {}

            if not variants:
                # Fallback to generic variant display if no data
                html += f"""
        <h3 style="color: #1a1f71; margin: 30px 0 20px 0;">{car_name} - Variant Walk</h3>
        <p style="color: #6b7280; font-style: italic;">No variant data available for this car.</p>
"""
                continue

            # Get variant names for header
            variant_names = [v.get('name', k) for k, v in variants.items()]

            html += f"""
        <h3 style="color: #1a1f71; margin: 30px 0 20px 0;">{car_name} - Variant Walk</h3>
        <table class="variant-walk-table">
            <thead>
                <tr>
"""

            # Generate header with actual variant names
            for variant_name in variant_names:
                html += f'                    <th>{variant_name}</th>\n'

            html += """
                </tr>
            </thead>
            <tbody>
                <tr>
"""

            # Generate columns for each variant
            is_first_variant = True
            for variant_key, variant_data in variants.items():
                variant_data = variant_data or {}
                variant_name = variant_data.get('name', variant_key)
                features = variant_data.get('features') or []
                features_added = variant_data.get('features_added') or []
                features_deleted = variant_data.get('features_deleted') or []

                html += """
                    <td>
"""

                # Show section title
                if is_first_variant:
                    html += """
                        <div class="variant-section-title">Standard Features:</div>
"""
                    is_first_variant = False
                else:
                    prev_variant = list(variants.keys())[list(variants.keys()).index(variant_key) - 1]
                    prev_name = variants[prev_variant].get('name', prev_variant)
                    html += f"""
                        <div class="variant-section-title">In addition to {prev_name}:</div>
"""

                # Show features added (or all features for base variant)
                if features_added:
                    html += """
                        <ul class="variant-features">
"""
                    for feature in features_added:
                        html += f'                            <li class="feature-added">{feature}</li>\n'
                    html += """
                        </ul>
"""
                elif features:
                    html += """
                        <ul class="variant-features">
"""
                    for feature in features[:10]:  # Limit to first 10 for base variant
                        html += f'                            <li class="feature-standard">{feature}</li>\n'
                    html += """
                        </ul>
"""

                # Show features deleted if any
                if features_deleted:
                    html += """
                        <div class="variant-sub-section">Features deleted:</div>
                        <ul class="variant-features">
"""
                    for feature in features_deleted:
                        html += f'                            <li class="feature-deleted">{feature}</li>\n'
                    html += """
                        </ul>
"""

                html += """
                    </td>
"""

            html += """
                </tr>
            </tbody>
        </table>
"""

    html += """
    </div>
    <div style="margin-top: 20px; padding: 15px; background: #f9fafb; border-radius: 6px; font-size: 0.9em; border-left: 4px solid #dd032b;">
        <strong>Note:</strong> Variant walk shows progressive feature additions across trim levels.
        <span style="color: #10b981;">Green text</span> indicates new features added,
        <span style="color: #dd032b;">red text</span> indicates features removed.
    </div>
"""

    return html


def generate_old_vs_new_price_ladder(car_name: str, old_gen_data: Dict[str, Any],
                                      new_gen_data: Dict[str, Any]) -> str:
    """
    Generate Old vs New generation price ladder.
    Layout: price axis (left) | old variants on vertical line | callout boxes (center) | new variants on vertical line
    Uses absolute positioning for dots exactly on the vertical line at 50% of each column.
    Color scheme: white background, red accents (#dd032b), black text.
    """
    import re

    if not old_gen_data.get('has_old_generation'):
        return ""

    html = ""
    variant_mapping = old_gen_data.get('variant_mapping', {})
    old_variants = old_gen_data.get('old_variants', {})
    new_price_ladder = new_gen_data.get('price_ladder', {})

    fuel_trans_combos = [
        ('petrol_mt', 'Petrol', 'MT', 'petrol'),
        ('petrol_at', 'Petrol', 'AT', 'petrol'),
        ('diesel_mt', 'Diesel', 'MT', 'diesel'),
        ('diesel_at', 'Diesel', 'AT', 'diesel')
    ]

    for combo_key, fuel_label, trans_label, fuel_key in fuel_trans_combos:
        old_vars = old_variants.get(combo_key, [])
        mappings = variant_mapping.get(combo_key, [])
        if not old_vars or not mappings:
            continue
        new_prices = new_price_ladder.get(fuel_key, {}).get(trans_label, {})
        if not new_prices:
            continue

        # Collect all prices to build axis scale
        all_price_vals = []
        for ov in old_vars:
            m = re.search(r'(\d+\.?\d*)', str(ov.get('price', '')))
            if m:
                all_price_vals.append(float(m.group(1)))
        for p in new_prices.values():
            m = re.search(r'(\d+\.?\d*)', str(p))
            if m:
                all_price_vals.append(float(m.group(1)))

        if not all_price_vals:
            continue

        min_p = min(all_price_vals)
        max_p = max(all_price_vals)
        # Round axis to nice lakhs values with padding
        axis_min_lakh = int(min_p)
        axis_max_lakh = int(max_p) + 1

        # Build axis tick marks (every 1-2 lakhs depending on range)
        price_range = axis_max_lakh - axis_min_lakh
        tick_step = 1 if price_range <= 10 else 2
        axis_ticks = list(range(axis_min_lakh, axis_max_lakh + 1, tick_step))

        # Sort old variants by price (ascending)
        old_sorted = sorted(old_vars, key=lambda v: float(re.search(r'(\d+\.?\d*)', str(v.get('price', '0'))).group(1)) if re.search(r'(\d+\.?\d*)', str(v.get('price', '0'))) else 0)

        # Sort new variants by price
        new_sorted = sorted(new_prices.items(), key=lambda x: float(re.search(r'(\d+\.?\d*)', str(x[1])).group(1)) if re.search(r'(\d+\.?\d*)', str(x[1])) else 0)

        # Calculate pixel position based on price
        # Container is 600px, usable area is from 30px (top) to 530px (600-70 bottom padding) = 500px usable
        CHART_TOP = 30
        CHART_USABLE = 500
        def price_to_px(price_val):
            """Convert price to pixel position from top (higher price = closer to top)."""
            if axis_max_lakh == axis_min_lakh:
                return CHART_TOP + CHART_USABLE // 2
            pct = (price_val - axis_min_lakh) / (axis_max_lakh - axis_min_lakh)
            return CHART_TOP + int((1 - pct) * CHART_USABLE)

        # --- Build HTML ---
        html += f"""
        <div class="gen-comparison-page" style="page-break-after: always; margin-bottom: 60px; background: white;">
            <h2 style="text-align: center; font-size: 1.8em; margin-bottom: 10px; color: #000;">
                New Vs Old {car_name} Price points [{fuel_label} {trans_label}]
            </h2>
            <div style="text-align: center; margin-bottom: 20px;">
                <p style="font-size: 1.05em; color: #374151;">
                    &bull; {car_name} still maintains its competitive pricing.<br>
                    &bull; Price increase done are justified by its feature additions
                </p>
            </div>
            <div style="display: flex; gap: 0; height: 600px; position: relative;">

                <!-- PRICE AXIS -->
                <div style="flex: 0 0 70px; position: relative;">
                    <!-- axis line -->
                    <div style="position: absolute; left: 12px; top: 30px; bottom: 70px; width: 2px; background: #374151;"></div>
                    <!-- top arrow -->
                    <div style="position: absolute; left: 8px; top: 22px; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 8px solid #374151;"></div>
                    <!-- bottom arrow -->
                    <div style="position: absolute; left: 8px; bottom: 62px; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 8px solid #374151;"></div>
"""
        # Axis tick labels
        for tick in axis_ticks:
            tick_px = price_to_px(tick)
            html += f"""
                    <div style="position: absolute; left: 20px; top: {tick_px}px; transform: translateY(-50%); font-size: 0.75em; color: #374151; font-weight: 600; white-space: nowrap;">
                        {tick} L
                    </div>
"""
        html += f"""
                    <div style="position: absolute; bottom: 5px; left: 0; width: 70px; text-align: left;">
                        <div style="font-weight: 700; font-size: 0.8em; color: #000;">{fuel_label} {trans_label}</div>
                        <div style="font-size: 0.6em; color: #6b7280;">Ex-Showroom</div>
                    </div>
                </div>

                <!-- OLD GENERATION COLUMN -->
                <div style="flex: 1; position: relative;">
                    <!-- vertical red line at center of this column -->
                    <div style="position: absolute; left: 50%; top: 30px; bottom: 70px; width: 3px; background: #dd032b; transform: translateX(-50%); z-index: 1;"></div>
"""
        # Position each old variant: dot at center, label to the left
        for ov in old_sorted:
            vname = ov.get('variant', '')
            price_str = ov.get('price', '')
            pm = re.search(r'(\d+\.?\d*)', str(price_str))
            if pm:
                price_val = float(pm.group(1))
                pd = pm.group(1)
                top_px = price_to_px(price_val)
                # Dot positioned absolutely at 50% of column
                html += f"""
                    <!-- Dot at center -->
                    <div style="position: absolute; left: 50%; top: {top_px}px; transform: translate(-50%, -50%); width: 14px; height: 14px; border-radius: 50%; background: #374151; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.3); z-index: 2;"></div>
                    <!-- Label to the left of dot -->
                    <div style="position: absolute; right: 52%; top: {top_px}px; transform: translateY(-50%); padding-right: 12px; font-size: 0.78em; color: #000; white-space: nowrap; text-align: right; z-index: 2;">
                        <span style="font-weight: 700;">{pd}</span>, {vname}
                    </div>
"""
        html += f"""
                    <!-- Bottom label -->
                    <div style="position: absolute; bottom: 5px; left: 0; right: 0; text-align: center;">
                        <div style="font-size: 1em; font-weight: 700; color: #000; margin-bottom: 5px;">{fuel_label[0]} {trans_label}</div>
                        <div style="display: inline-block; padding: 6px 20px; background: #1f2937; color: white; border-radius: 6px; font-weight: 700; font-size: 0.85em;">Old {car_name.split()[0]}</div>
                    </div>
                </div>

                <!-- CALLOUT BOXES (CENTER) -->
                <div style="flex: 0 0 180px; display: flex; flex-direction: column; justify-content: center; gap: 15px; padding: 30px 5px; overflow: hidden;">
"""
        # Helper: fuzzy-match new variant name from mapping against price_ladder keys
        def _find_new_price(new_var_name, new_prices_dict):
            """Try exact match first, then substring/prefix match."""
            if new_var_name in new_prices_dict:
                return new_prices_dict[new_var_name]
            nv_lower = new_var_name.lower().strip()
            for key, val in new_prices_dict.items():
                if nv_lower.startswith(key.lower().strip()):
                    return val
                if key.lower().strip().startswith(nv_lower):
                    return val
            nv_first = nv_lower.split()[0] if nv_lower else ''
            for key, val in new_prices_dict.items():
                if key.lower().strip().split()[0] == nv_first:
                    return val
            return '0'

        callout_count = 0
        for mapping in mappings:
            features = mapping.get('features_added', [])
            if len(features) >= 2 and callout_count < 3:
                old_var_name = mapping.get('old_variant', '')
                new_var_name = mapping.get('new_variant', '')
                old_price = next((v['price'] for v in old_vars if v['variant'] == old_var_name), '0')
                new_price_val = _find_new_price(new_var_name, new_prices)
                old_val = float(re.search(r'(\d+\.?\d*)', str(old_price)).group(1)) if re.search(r'(\d+\.?\d*)', str(old_price)) else 0
                new_val = float(re.search(r'(\d+\.?\d*)', str(new_price_val)).group(1)) if re.search(r'(\d+\.?\d*)', str(new_price_val)) else 0
                price_diff = new_val - old_val
                if abs(price_diff) > 0:
                    arrow = "&uarr;" if price_diff > 0 else "&darr;"
                    diff_color = "#dd032b" if price_diff > 0 else "#059669"
                    html += f"""
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 170px;">
                        <div style="text-align: center; font-weight: 700; color: #000; margin-bottom: 4px; border-bottom: 1px solid #e5e7eb; padding-bottom: 3px; font-size: 0.65em;">
                            Price charged Vs Features added
                        </div>
                        <div style="text-align: center; font-size: 0.9em; font-weight: 800; color: {diff_color}; margin-bottom: 4px;">
                            {arrow} Rs.{abs(price_diff):.2f}L
                        </div>
                        <div style="font-size: 0.6em; color: #000; line-height: 1.3; max-height: 80px; overflow: hidden;">
"""
                    for feature in features[:5]:
                        html += f"                            + {feature}<br>\n"
                    html += """
                        </div>
                    </div>
"""
                    callout_count += 1

        if callout_count == 0:
            html += """<div style="text-align: center; color: #9ca3af; font-size: 0.75em;">No significant<br>feature changes</div>"""

        html += """
                </div>

                <!-- NEW GENERATION COLUMN -->
                <div style="flex: 1; position: relative;">
                    <!-- vertical red line at center of this column -->
                    <div style="position: absolute; left: 50%; top: 30px; bottom: 70px; width: 3px; background: #dd032b; transform: translateX(-50%); z-index: 1;"></div>
"""
        # Position each new variant: dot at center, label to the right
        for vname, price in new_sorted:
            pm = re.search(r'(\d+\.?\d*)', str(price))
            if pm:
                price_val = float(pm.group(1))
                pd = pm.group(1)
                top_px = price_to_px(price_val)
                html += f"""
                    <!-- Dot at center -->
                    <div style="position: absolute; left: 50%; top: {top_px}px; transform: translate(-50%, -50%); width: 14px; height: 14px; border-radius: 50%; background: #374151; border: 2px solid white; box-shadow: 0 1px 3px rgba(0,0,0,0.3); z-index: 2;"></div>
                    <!-- Label to the right of dot -->
                    <div style="position: absolute; left: 52%; top: {top_px}px; transform: translateY(-50%); padding-left: 12px; font-size: 0.78em; color: #000; white-space: nowrap; z-index: 2;">
                        <span style="font-weight: 700;">{pd}</span>, {vname}
                    </div>
"""
        html += f"""
                    <!-- Bottom label -->
                    <div style="position: absolute; bottom: 5px; left: 0; right: 0; text-align: center;">
                        <div style="font-size: 1em; font-weight: 700; color: #000; margin-bottom: 5px;">{fuel_label[0]} {trans_label}</div>
                        <div style="display: inline-block; padding: 6px 20px; background: #1f2937; color: white; border-radius: 6px; font-weight: 700; font-size: 0.85em;">New {car_name.split()[0]}</div>
                    </div>
                </div>

            </div>

            <div style="margin-top: 15px; padding: 10px; background: #f3f4f6; border-left: 4px solid #374151; font-size: 0.85em; color: #000;">
                <strong>Note:</strong> Below variants are as per reveal done during launch event on {old_gen_data.get('old_generation', {}).get('launch_year', '2024')}.
                More sub-variants [ with/without sunroof, CAMO edition etc] may get released in future.
            </div>
        </div>
"""

    return html


def generate_price_ladder_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate price ladder section showing petrol and diesel prices across variants.
    Now supports both old vs new comparison AND traditional variant ladder.

    Args:
        comparison_data: Dictionary with car comparison data including variant_walk

    Returns:
        HTML string for price ladder sections
    """
    if not comparison_data:
        return "<p>No pricing data available.</p>"

    def extract_price_value(price_str: str) -> float:
        """Extract numeric value from price string for sorting."""
        if not price_str or price_str == "Not Available":
            return 0.0
        # Remove currency symbols, 'lakh', and extract first number
        import re
        price_str = price_str.replace('₹', '').replace('lakh', '').strip()
        # Extract first number (handles cases like "14.83 (1.5 MPI IVT)")
        match = re.search(r'(\d+\.?\d*)', price_str)
        if match:
            return float(match.group(1))
        return 0.0

    html = """
    <style>
        .gen-comparison-page {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .price-ladder-container {
            margin: 30px 0;
        }

        .price-ladder-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 40px;
            margin-bottom: 30px;
        }

        .price-ladder-card {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: 30px;
            border: 1px solid #e5e7eb;
        }

        .price-ladder-title {
            font-size: 1.5em;
            font-weight: 700;
            color: #000;
            margin-bottom: 25px;
            text-align: center;
            padding-bottom: 15px;
            letter-spacing: 1px;
        }

        .ladder-chart-container {
            display: flex;
            justify-content: space-around;
            align-items: flex-end;
            min-height: 500px;
            padding: 30px 20px;
            position: relative;
            background: white;
        }

        .ladder-column {
            display: flex;
            flex-direction: column-reverse;
            align-items: center;
            position: relative;
            flex: 1;
            max-width: 200px;
        }

        .ladder-column-title {
            position: absolute;
            top: -30px;
            font-weight: 600;
            font-size: 1em;
            color: #374151;
            text-align: center;
        }

        .ladder-line {
            width: 2px;
            background: #d1d5db;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .ladder-point {
            position: relative;
            display: flex;
            align-items: center;
            margin: 8px 0;
        }

        .ladder-dot {
            width: 10px;
            height: 10px;
            background: #6b7280;
            border-radius: 50%;
            position: relative;
            z-index: 2;
        }

        .ladder-label {
            position: absolute;
            left: 15px;
            white-space: nowrap;
            font-size: 0.75em;
            color: #1f2937;
            font-weight: 500;
        }

        .ladder-label .variant-name {
            font-weight: 600;
            color: #000;
        }

        .ladder-label .price {
            color: #dd032b;
            font-weight: 700;
        }

        .transmission-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            justify-content: center;
        }

        .transmission-tab {
            padding: 10px 25px;
            background: #f3f4f6;
            border: 2px solid #e5e7eb;
            border-radius: 6px;
            font-weight: 600;
            color: #6b7280;
            cursor: pointer;
            transition: all 0.3s;
        }

        .transmission-tab.active {
            background: white;
            border-color: #dd032b;
            color: #dd032b;
        }

        .fuel-badge {
            display: inline-block;
            padding: 6px 16px;
            border-radius: 4px;
            font-size: 0.9em;
            font-weight: 700;
            margin-bottom: 20px;
            letter-spacing: 0.5px;
        }

        .fuel-badge.petrol {
            background: #f3f4f6;
            color: #1f2937;
            border: 2px solid #d1d5db;
        }

        .fuel-badge.diesel {
            background: #f3f4f6;
            color: #1f2937;
            border: 2px solid #d1d5db;
        }

        @media print {
            .gen-comparison-page {
                page-break-after: always;
            }
        }
    </style>

    <div class="price-ladder-container">
"""

    # For each car, generate its price ladders
    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            variant_walk = car_data.get('variant_walk') or {}
            price_ladder = variant_walk.get('price_ladder', {})

            # Check if generation comparison data is available
            old_gen_data = car_data.get('generation_comparison') or {}

            # If old vs new comparison data exists, use the new format
            if old_gen_data.get('has_old_generation'):
                html += generate_old_vs_new_price_ladder(car_name, old_gen_data, variant_walk)
                continue

            # Otherwise, use traditional price ladder format
            if not price_ladder:
                continue

            html += f"""
        <h3 style="color: #000000; margin: 30px 0 20px 0;">{car_name} - Price Ladder</h3>
        <div class="price-ladder-grid">
"""

            # Petrol Price Ladder
            petrol_data = price_ladder.get('petrol') or {}
            if petrol_data:
                html += """
            <div class="price-ladder-card">
                <div style="text-align: center;">
                    <span class="fuel-badge petrol">PETROL</span>
                </div>
                <div class="price-ladder-title">PRICE LADDER PETROL MT & AT</div>
                <div class="ladder-chart-container">
"""

                # MT Column
                mt_variants = petrol_data.get('MT') or {}
                if mt_variants:
                    # Sort by price (extract numeric value)
                    sorted_mt = sorted(mt_variants.items(),
                                      key=lambda x: extract_price_value(x[1]))

                    html += """
                    <div class="ladder-column">
                        <div class="ladder-column-title">MT</div>
                        <div class="ladder-line" style="height: 400px;">
"""
                    for variant_name, price in sorted_mt:
                        if price and price != "Not Available":
                            clean_price = price.replace('₹', '').strip()
                            html += f"""
                            <div class="ladder-point">
                                <div class="ladder-dot"></div>
                                <div class="ladder-label">
                                    <span class="variant-name">{variant_name}</span>, <span class="price">{clean_price}</span>
                                </div>
                            </div>
"""
                    html += """
                        </div>
                    </div>
"""

                # AT Column
                at_variants = petrol_data.get('AT') or {}
                if at_variants:
                    sorted_at = sorted(at_variants.items(),
                                      key=lambda x: extract_price_value(x[1]))

                    html += """
                    <div class="ladder-column">
                        <div class="ladder-column-title">AT</div>
                        <div class="ladder-line" style="height: 400px;">
"""
                    for variant_name, price in sorted_at:
                        if price and price != "Not Available":
                            clean_price = price.replace('₹', '').strip()
                            html += f"""
                            <div class="ladder-point">
                                <div class="ladder-dot"></div>
                                <div class="ladder-label">
                                    <span class="variant-name">{variant_name}</span>, <span class="price">{clean_price}</span>
                                </div>
                            </div>
"""
                    html += """
                        </div>
                    </div>
"""

                html += """
                </div>
            </div>
"""

            # Diesel Price Ladder
            diesel_data = price_ladder.get('diesel') or {}

            # Check if there's any valid price data in diesel before creating the section
            has_valid_diesel_data = False
            if diesel_data:
                mt_variants = diesel_data.get('MT') or {}
                at_variants = diesel_data.get('AT') or {}

                # Check if MT has valid prices
                for _, price in mt_variants.items():
                    if price and price != "Not Available":
                        has_valid_diesel_data = True
                        break

                # Check if AT has valid prices if MT didn't have any
                if not has_valid_diesel_data:
                    for _, price in at_variants.items():
                        if price and price != "Not Available":
                            has_valid_diesel_data = True
                            break

            if has_valid_diesel_data:
                html += """
            <div class="price-ladder-card">
                <div style="text-align: center;">
                    <span class="fuel-badge diesel">DIESEL</span>
                </div>
                <div class="price-ladder-title">PRICE LADDER DIESEL MT & AT</div>
                <div class="ladder-chart-container">
"""

                # MT Column
                mt_variants = diesel_data.get('MT') or {}
                if mt_variants:
                    sorted_mt = sorted(mt_variants.items(),
                                      key=lambda x: extract_price_value(x[1]))

                    html += """
                    <div class="ladder-column">
                        <div class="ladder-column-title">MT</div>
                        <div class="ladder-line" style="height: 400px;">
"""
                    for variant_name, price in sorted_mt:
                        if price and price != "Not Available":
                            clean_price = price.replace('₹', '').strip()
                            html += f"""
                            <div class="ladder-point">
                                <div class="ladder-dot"></div>
                                <div class="ladder-label">
                                    <span class="variant-name">{variant_name}</span>, <span class="price">{clean_price}</span>
                                </div>
                            </div>
"""
                    html += """
                        </div>
                    </div>
"""

                # AT Column
                at_variants = diesel_data.get('AT') or {}
                if at_variants:
                    sorted_at = sorted(at_variants.items(),
                                      key=lambda x: extract_price_value(x[1]))

                    html += """
                    <div class="ladder-column">
                        <div class="ladder-column-title">AT</div>
                        <div class="ladder-line" style="height: 400px;">
"""
                    for variant_name, price in sorted_at:
                        if price and price != "Not Available":
                            clean_price = price.replace('₹', '').strip()
                            html += f"""
                            <div class="ladder-point">
                                <div class="ladder-dot"></div>
                                <div class="ladder-label">
                                    <span class="variant-name">{variant_name}</span>, <span class="price">{clean_price}</span>
                                </div>
                            </div>
"""
                    html += """
                        </div>
                    </div>
"""

                html += """
                </div>
            </div>
"""

            html += """
        </div>
"""

    html += """
    </div>
    <div style="margin-top: 20px; padding: 15px; background: #f9fafb; border-radius: 6px; font-size: 0.9em; border-left: 4px solid #dd032b;">
        <strong>Note:</strong> Prices shown are ex-showroom and may vary by location. Price ladder shows progressive pricing across trim levels.
    </div>
"""

    return html


def generate_attribute_proscons_section(attribute_proscons_data: Dict[str, Dict[str, Any]]) -> str:
    """
    Generate HTML section for attribute-based pros/cons analysis.

    Args:
        attribute_proscons_data: Dictionary mapping car names to their attribute pros/cons
                                Format: {car_name: {category: {attribute: {pros: [], cons: []}}}}

    Returns:
        HTML string for the attribute pros/cons section
    """
    if not attribute_proscons_data:
        return "<p>No attribute analysis data available.</p>"

    car_names = list(attribute_proscons_data.keys())
    num_cars = len(car_names)

    # Category order and icons
    category_icons = {
        "Comfort": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v3"/><path d="M2 11v5a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v2H6v-2a2 2 0 0 0-4 0z"/><path d="M4 18v2"/><path d="M20 18v2"/></svg>',
        "Dynamics": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
        "Performance": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>',
        "Safety": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        "Space & Versatility": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>',
        "NVH": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
        "All Terrain Capability": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 17H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-1"/><polygon points="12 15 17 21 7 21 12 15"/></svg>',
        "Features": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>'
    }

    # Define attribute categories
    attribute_categories = {
        "Comfort": ["Ride", "Climate Control", "Seats"],
        "Dynamics": ["Customer Handling", "Steering"],
        "Performance": ["Performance Feel", "Driveability", "Manual Transmission Operation", "Clutch Operation", "Automatic Transmission Operation"],
        "Safety": ["Braking", "Restraints"],
        "Space & Versatility": ["Visibility", "Package", "Usability", "Functional Hardware"],
        "NVH": ["PT-NVH", "Road NVH", "Wind NVH", "Electro Mech NVH"],
        "All Terrain Capability": ["4X4 Operation"],
        "Features": ["Infotainment System", "Night Operation"]
    }

    # Generate YouTube source links for each car + channel combination
    channels = ["Autocar India", "Overdrive"]
    source_links_html = '<div class="youtube-sources"><strong>Sources:</strong> '
    links = []
    for car_name in car_names:
        for channel in channels:
            search_query = (car_name + ' ' + channel + ' review').replace(' ', '+')
            youtube_url = f"https://www.youtube.com/results?search_query={search_query}"
            links.append(f'<a href="{youtube_url}" target="_blank" rel="noopener noreferrer" class="youtube-source-link">{car_name} - {channel}</a>')
    source_links_html += ' | '.join(links)
    source_links_html += '</div>'

    html = f"""
    <div class="attribute-proscons-container">
        {source_links_html}
    """

    for category, attributes in attribute_categories.items():
        icon = category_icons.get(category, '')
        html += f"""
        <div class="attr-category-section">
            <div class="attr-category-header" onclick="this.parentElement.classList.toggle('collapsed')">
                <div class="attr-category-icon">{icon}</div>
                <h3>{category}</h3>
                <span class="attr-toggle-icon"></span>
            </div>
            <div class="attr-category-content">
                <table class="attr-proscons-table">
                    <thead>
                        <tr>
                            <th class="attr-name-col">Attribute</th>
        """

        # Add car name headers with Pros/Cons sub-headers
        for car_name in car_names:
            html += f"""
                            <th class="car-col" colspan="2">{car_name}</th>
            """

        html += """
                        </tr>
                        <tr class="sub-header-row">
                            <th></th>
        """

        for _ in car_names:
            html += """
                            <th class="pros-subheader">Pros</th>
                            <th class="cons-subheader">Cons</th>
            """

        html += """
                        </tr>
                    </thead>
                    <tbody>
        """

        for attr in attributes:
            html += f"""
                        <tr>
                            <td class="attr-name-cell"><strong>{attr}</strong></td>
            """

            for car_name in car_names:
                car_data = attribute_proscons_data.get(car_name, {})
                cat_data = car_data.get(category, {})
                attr_data = cat_data.get(attr, {"pros": [], "cons": []})

                pros = attr_data.get("pros", [])
                cons = attr_data.get("cons", [])

                # Format pros
                pros_html = "<ul class='attr-list pros-list'>"
                for pro in pros[:3]:  # Limit to 3
                    if pro and pro not in ["N/A", "N/A - not available", "Data not available", "Not covered in reviews"]:
                        pros_html += f"<li>{pro}</li>"
                    elif pro:
                        pros_html += f"<li class='na-item'>{pro}</li>"
                pros_html += "</ul>" if pros else "<span class='no-data'>-</span>"

                # Format cons
                cons_html = "<ul class='attr-list cons-list'>"
                for con in cons[:3]:  # Limit to 3
                    if con and con not in ["N/A", "N/A - not available", "Data not available", "Not covered in reviews"]:
                        cons_html += f"<li>{con}</li>"
                    elif con:
                        cons_html += f"<li class='na-item'>{con}</li>"
                cons_html += "</ul>" if cons else "<span class='no-data'>-</span>"

                html += f"""
                            <td class="pros-cell">{pros_html}</td>
                            <td class="cons-cell">{cons_html}</td>
                """

            html += """
                        </tr>
            """

        html += """
                    </tbody>
                </table>
            </div>
        </div>
        """

    html += """
    </div>

    <style>
        .attribute-proscons-container {
            margin: 20px 0;
        }
        .youtube-sources {
            padding: 12px 16px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 13px;
            color: #495057;
            border-left: 4px solid #cc0000;
        }
        .youtube-source-link {
            color: #cc0000;
            text-decoration: none;
            font-weight: 500;
        }
        .youtube-source-link:hover {
            text-decoration: underline;
        }
        .attr-category-section {
            margin-bottom: 15px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
            background: white;
        }
        .attr-category-section.collapsed .attr-category-content {
            display: none;
        }
        .attr-category-section.collapsed .attr-toggle-icon::before {
            content: '+';
        }
        .attr-category-header {
            display: flex;
            align-items: center;
            padding: 15px 20px;
            background: #1c2a39;
            color: white;
            cursor: pointer;
            user-select: none;
            border-left: 4px solid #cc0000;
        }
        .attr-category-header:hover {
            background: #2a3a4a;
        }
        .attr-category-icon {
            width: 24px;
            height: 24px;
            margin-right: 12px;
        }
        .attr-category-icon svg {
            width: 100%;
            height: 100%;
        }
        .attr-category-header h3 {
            margin: 0;
            flex: 1;
            font-size: 1.1em;
        }
        .attr-toggle-icon {
            font-size: 1.5em;
            font-weight: bold;
            transition: transform 0.3s;
        }
        .attr-toggle-icon::before {
            content: '-';
        }
        .attr-category-content {
            padding: 15px;
            overflow-x: auto;
        }
        .attr-proscons-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .attr-proscons-table thead tr:first-child th {
            background: #f8f9fa;
            padding: 12px 8px;
            text-align: center;
            border-bottom: 2px solid #cc0000;
            font-weight: 600;
            color: #1c2a39;
        }
        .attr-proscons-table .sub-header-row th {
            background: #f1f3f4;
            padding: 8px;
            font-size: 0.85em;
            font-weight: 500;
        }
        .attr-proscons-table .pros-subheader {
            color: #27ae60;
            border-right: 1px solid #dee2e6;
        }
        .attr-proscons-table .cons-subheader {
            color: #e74c3c;
        }
        .attr-proscons-table .attr-name-col {
            width: 150px;
            min-width: 150px;
        }
        .attr-proscons-table .car-col {
            text-align: center;
            border-left: 2px solid #dee2e6;
        }
        .attr-proscons-table tbody tr {
            border-bottom: 1px solid #e9ecef;
        }
        .attr-proscons-table tbody tr:hover {
            background: #f8f9fa;
        }
        .attr-proscons-table td {
            padding: 10px 8px;
            vertical-align: top;
        }
        .attr-name-cell {
            background: #fafafa;
            border-right: 1px solid #dee2e6;
        }
        .pros-cell {
            background: rgba(39, 174, 96, 0.05);
            border-right: 1px solid #e9ecef;
        }
        .cons-cell {
            background: rgba(231, 76, 60, 0.05);
            border-right: 2px solid #dee2e6;
        }
        .attr-list {
            margin: 0;
            padding-left: 16px;
            list-style: none;
        }
        .attr-list li {
            margin-bottom: 4px;
            position: relative;
            padding-left: 8px;
        }
        .pros-list li::before {
            content: '+';
            position: absolute;
            left: -8px;
            color: #27ae60;
            font-weight: bold;
        }
        .cons-list li::before {
            content: '-';
            position: absolute;
            left: -8px;
            color: #e74c3c;
            font-weight: bold;
        }
        .attr-list .na-item {
            color: #999;
            font-style: italic;
        }
        .attr-list .na-item::before {
            content: '';
        }
        .no-data {
            color: #ccc;
            text-align: center;
            display: block;
        }
        @media print {
            .attr-category-section {
                page-break-inside: avoid;
            }
            .attr-category-header {
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
        }
    </style>
    """

    return html


def generate_proscons_table(proscons_data: Dict[str, Any]) -> str:
    """
    Generate pros/cons comparison table from YouTube reviews.

    Args:
        proscons_data: Dictionary containing pros/cons data for each car
                      Format: {car_name: [
                          {positives: [...], negatives: [...], publication: str, link: str},
                          ...
                      ]}

    Returns:
        HTML string for the pros/cons table
    """
    if not proscons_data:
        return "<p>No pros/cons data available.</p>"

    car_names = list(proscons_data.keys())

    # Generate table HTML
    html = """
    <div class="proscons-table-container">
        <div class="table-responsive">
            <table class="proscons-table">
                <thead>
                    <tr>
                        <th class="serial-col">Sr No</th>
                        <th class="car-col">Car</th>
                        <th class="publication-col">Publication</th>
                        <th class="link-col">Link</th>
                        <th class="positives-col">Positives</th>
                        <th class="negatives-col">Negatives</th>
                    </tr>
                </thead>
                <tbody>
"""

    # Generate rows for each car and each review
    row_num = 1
    for car_name in car_names:
        reviews = proscons_data[car_name]

        # Handle both list and dict formats for backward compatibility
        if not isinstance(reviews, list):
            reviews = [reviews]

        for review in reviews:
            publication = review.get("publication", "N/A")
            link = review.get("link", "#")
            positives = review.get("positives", [])
            negatives = review.get("negatives", [])

            # Format positives as bullet points
            positives_html = "<ul class='proscons-list'>"
            for positive in positives:
                positives_html += f"<li>{positive}</li>"
            positives_html += "</ul>"

            # Format negatives as bullet points
            negatives_html = "<ul class='proscons-list'>"
            for negative in negatives:
                negatives_html += f"<li>{negative}</li>"
            negatives_html += "</ul>"

            # Create row
            html += f"""
                    <tr>
                        <td class="serial-cell">{row_num}</td>
                        <td class="car-cell"><strong>{car_name}</strong></td>
                        <td class="publication-cell">{publication}</td>
                        <td class="link-cell">
                            <a href="{link}" target="_blank" rel="noopener noreferrer" class="youtube-citation-box">
                                {publication}
                            </a>
                        </td>
                        <td class="positives-cell">{positives_html}</td>
                        <td class="negatives-cell">{negatives_html}</td>
                    </tr>
"""
            row_num += 1

    html += """
                </tbody>
            </table>
        </div>
    </div>
"""

    return html


def create_comparison_chart_html(comparison_data: Dict[str, Any], summary: str, proscons_data: Optional[Dict[str, Dict[str, Any]]] = None, summary_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Create interactive HTML report with enhanced design featuring grouped specifications.
    Specifications are grouped into collapsible accordions for better readability.
    Optimized for PDF printing with proper page breaks and layout.
    
    Features:
    - Grouped specification table with accordion functionality
    - Sticky header with smooth-scrolling navigation
    - Professional section headers with icons
    - Alternating color charts (dark blue and Mahindra red)
    - Scroll animations for all components
    - PDF-optimized printing (2 charts per page, landscape table)
    
    Args:
        comparison_data: Dictionary containing car comparison data
        summary: Text summary of the comparison
        
    Returns:
        Complete HTML string ready to be saved as a file
    """
    
    # Helper function for summary formatting
    def format_summary(summary_text: str) -> str:
        """Format summary with bold text preserved and clean bullet points"""
        processed_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', summary_text)
        processed_text = processed_text.replace('\n', '<br>').replace('*','•')
        return processed_text

    # Data Extraction using robust helper functions
    cars, prices, mileages, ratings, seating, sales_volumes = [], [], [], [], [], []

    for car_name, car_data in comparison_data.items():
        if "error" not in car_data or car_data.get("price_range") != "Not Available":
            cars.append(car_data.get("car_name", car_name))

            # Extract price using robust helper
            prices.append(extract_price(car_data.get("price_range", "")))

            # Extract mileage using robust helper
            mileages.append(extract_mileage(car_data.get("mileage", "")))

            # Extract rating using robust helper
            ratings.append(extract_rating(car_data.get("user_rating", "")))

            # Extract seating using robust helper
            seating.append(extract_seating(car_data.get("seating_capacity", "")))

            # Extract sales using robust helper
            sales_volumes.append(extract_sales(car_data.get("monthly_sales", "")))

    # Generate attribute pros/cons section (if provided)
    if proscons_data:
        proscons_html = generate_attribute_proscons_section(proscons_data)
    else:
        proscons_html = "<p>Attribute pros/cons analysis not available.</p>"

    # Format AI-powered summary
    formatted_summary = format_summary(summary)

    citations_html = _generate_citations_html(comparison_data)
    

    def count_words(text: str) -> int:
        return len(str(text).split())
    
    WORD_THRESHOLD = 12

    # Build table with grouped accordion structure
    features_table = "<table><thead><tr><th>Specification</th>"
    for car_name in cars:
        features_table += f"<th>{car_name.upper()}</th>"
    features_table += "</tr></thead><tbody id=\"specifications-tbody\">"

    spec_groups = {
    "Key Specifications": {
        "": [  # Empty string means no accordion, direct rows
            ("Price Range", "price_range"),
            ("Monthly Sales", "monthly_sales"),
            ("Mileage", "mileage"),
            ("User Rating", "user_rating"),
            ("Seating Capacity", "seating_capacity"),
        ]
    },
    "Specifications": {
        "Engine & Transmission": [
            ("Performance", "performance"),
            ("Acceleration", "acceleration"),
            ("Torque", "torque"),
            ("Driveability", "driveability"),
            ("Response", "response"),
            ("Transmission", "transmission"),
            ("Manual Transmission Performance", "manual_transmission_performance"),
            ("Automatic Transmission Performance", "automatic_transmission_performance"),
            ("Gear Shift", "gear_shift"),
            ("Gear Selection", "gear_selection"),
            ("Pedal Operation", "pedal_operation"),
            ("Pedal Travel", "pedal_travel"),
            ("Turbo Noise", "turbo_noise"),
            ("Powertrain NVH", "powertrain_nvh"),
            ("Crawl", "crawl"),
            ("Performance Feel", "performance_feel"),
            ("City Performance", "city_performance"),
            ("Highway Performance", "highway_performance"),
        ],
        "Dimensions & Weight": [
            ("Turning Radius", "turning_radius"),
            ("Body Type", "body"),
            ("Wheelbase", "wheelbase"),
            ("Chassis", "chasis"),
        ],
        "Capacity & Space": [
            ("Boot Space", "boot_space"),
            ("Egress", "egress"),
            ("Ingress", "ingress"),
        ],
        "Suspensions, Brakes, Steering & Tyres": [
            ("Ride", "ride"),
            ("Ride Quality", "ride_quality"),
            ("Stiff on Pot Holes", "stiff_on_pot_holes"),
            ("Bumps", "bumps"),
            ("Jerks", "jerks"),
            ("Shocks", "shocks"),
            ("Stability", "stability"),
            ("Straight Ahead Stability", "straight_ahead_stability"),
            ("Corner Stability", "corner_stability"),
            ("Shakes", "shakes"),
            ("Shudder", "shudder"),
            ("Pulsation", "pulsation"),
            ("Braking", "braking"),
            ("Brake Performance", "brake_performance"),
            ("Brakes", "brakes"),
            ("Electronic Parking Brake", "epb"),
            ("Grabby", "grabby"),
            ("Spongy", "spongy"),
            ("Steering", "steering"),
            ("Telescopic Steering", "telescopic_steering"),
            ("Sensitivity", "sensitivity"),
            ("Wheels", "wheels"),
            ("Alloy Wheel", "alloy_wheel"),
        ],
        "NVH (Noise, Vibration, Harshness)": [
            ("NVH", "nvh"),
            ("Wind NVH", "wind_nvh"),
            ("Road NVH", "road_nvh"),
            ("Wind Noise", "wind_noise"),
            ("Tire Noise", "tire_noise"),
            ("Blower Noise", "blower_noise"),
            ("Rattle", "rattle"),
        ],
        "Parking & Manoeuvring": [
            ("Parking", "parking"),
            ("Manoeuvring", "manoeuvring"),
        ],
        "Electric Motor & Battery": [
            ("Battery", "battery"),
        ],
    },
    "Features": {
        "Exterior": [
            ("Sunroof", "sunroof"),
            ("Lighting", "lighting"),
            ("LED", "led"),
            ("DRL", "drl"),
            ("Tail Lamp", "tail_lamp"),
            ("ORVM", "orvm"),
            ("Window", "window"),
            ("Door Effort", "door_effort"),
        ],
        "Safety & Impact": [
            ("Vehicle Safety Features", "vehicle_safety_features"),
            ("Impact", "impact"),
            ("Seats Restraint", "seats_restraint"),
            ("Seat Cushion", "seat_cushion"),
            ("Headrest", "headrest"),
        ],
        "Comfort & Convenience": [
            ("Interior", "interior"),
            ("Seat", "seat"),
            ("Soft Trims", "soft_trims"),
            ("Armrest", "armrest"),
            ("IRVM", "irvm"),
            ("Climate Control", "climate_control"),
        ],
        "Infotainment & Connectivity": [
            ("Infotainment Screen", "infotainment_screen"),
            ("Resolution", "resolution"),
            ("Touch Response", "touch_response"),
            ("Audio System", "audio_system"),
            ("Button", "button"),
            ("Apple CarPlay", "apple_carplay"),
            ("Digital Display", "digital_display"),
        ],
        "Visibility & Controls": [
            ("Visibility", "visibility"),
            ("Wiper Control", "wiper_control"),
        ],
        "Off-Road": [
            ("Off-Road", "off_road"),
        ],
    }
}

    # REPLACEMENT FOR THE TABLE GENERATION LOOP
    for main_group_title, sub_groups in spec_groups.items():
    # Add a non-collapsible main heading for the entire section
        features_table += f"""
        <tr class="main-group-header">
            <td>{main_group_title}</td>
        """

        # Add empty cells for car columns
        for _ in cars:
            features_table += "<td></td>"

        features_table += "</tr>\n"
        
        for group_name, specifications in sub_groups.items():
            # Check if any car has a value for any spec in this sub-group
            group_has_data = any(
                comparison_data[car_name].get(key) not in [None, 'N/A', '']
                for _, key in specifications
                for car_name in cars
            )
            if not group_has_data:
                continue  # Skip rendering empty accordion groups

            # Special handling for Key Specifications (no accordion)
            if main_group_title == "Key Specifications":
                # Render specs directly without accordion header
                for label, key in specifications:
                    features_table += f"<tr class='spec-row'><td>{label}</td>"

                    for car_name, car_data in comparison_data.items():
                        
                        if "error" not in car_data or car_data.get("price_range") != "Not Available":
                            value = car_data.get(key, 'N/A')
                            display_value = ", ".join(value) if isinstance(value, list) else str(value or 'N/A')
                            word_count = count_words(display_value)
                            
                            features_table += "<td>"
                            
                            if word_count > WORD_THRESHOLD:
                                features_table += f'<div class="expandable-content">{display_value}</div>'
                                features_table += '<button onclick="toggleExpand(this)" class="read-more-btn">Read more</button>'
                            
                            else:
                                features_table += display_value
                            features_table += "</td>"
                    features_table += "</tr>"
            
            else:
                # Regular accordion rendering for other groups
                features_table += f"""
                    <tr class="accordion-header" onclick="toggleAccordion(this)">
                    <td class="accordion-title-cell">
                        {group_name}
                    </td>
                """

                # Add empty cells for car columns (except the last one)
                for i in range(len(cars)):

                    if i == len(cars) - 1:
                        # Last column gets the arrow icon
                        features_table += """
                    <td class='accordion-empty-cell accordion-icon-cell'>
                        <span class="accordion-icon"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z"/></svg></span>
                    </td>
                """
                    
                    else:
                        features_table += "<td class='accordion-empty-cell'></td>\n"

                features_table += "</tr>\n"
                
                for label, key in specifications:
                    features_table += f"<tr class='spec-row hidden-spec'><td>{label}</td>"
                    
                    for car_name, car_data in comparison_data.items():
                        
                        if "error" not in car_data or car_data.get("price_range") != "Not Available":
                            value = car_data.get(key, 'N/A')
                            display_value = ", ".join(value) if isinstance(value, list) else str(value or 'N/A')
                            word_count = count_words(display_value)
                            
                            features_table += "<td>"
                            if word_count > WORD_THRESHOLD:
                                features_table += f'<div class="expandable-content">{display_value}</div>'
                                features_table += '<button onclick="toggleExpand(this)" class="read-more-btn">Read more</button>'
                            else:
                                features_table += display_value
                            features_table += "</td>"
                    features_table += "</tr>"

    features_table += "</tbody></table>"

    #HTML template 
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>Car Comparison Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{ font-family: 'Poppins', sans-serif; background: #f8f9fa; color: #212529; }}
        .container {{ max-width: 100%; margin: 0 auto; background: white; overflow: hidden; }}
        .site-header {{ display: flex; justify-content: space-between; align-items: center; padding: 16px 40px; background: #fff; border-bottom: 1px solid #e9ecef; width: 100%; position: sticky; top: 0; z-index: 1000; }}
        .logo {{ height: 22px; width: auto; }}
        .header-actions {{ display: flex; align-items: center; gap: 20px; }}
        .main-nav {{ display: flex; gap: 4px; align-items: center; }}
        .main-nav > a, .main-nav > .nav-dropdown > .nav-dropdown-toggle {{
            text-decoration: none; color: #212529; font-size: 13px; font-weight: 500;
            transition: color 0.2s; padding: 6px 10px; border-radius: 6px; white-space: nowrap;
        }}
        .main-nav > a:hover, .main-nav > .nav-dropdown > .nav-dropdown-toggle:hover {{ color: #dd032b; background: #f5f5f5; }}
        .main-nav > a.nav-active {{ color: #dd032b; font-weight: 600; }}
        .nav-dropdown {{ position: relative; }}
        .nav-dropdown-toggle {{ cursor: pointer; display: flex; align-items: center; gap: 4px; background: none; border: none; font-family: inherit; }}
        .nav-dropdown-toggle::after {{ content: "▾"; font-size: 10px; opacity: 0.6; }}
        .nav-dropdown-menu {{
            display: none; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
            background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.12); padding: 6px 0; min-width: 160px; z-index: 999;
            padding-top: 12px; margin-top: -6px;
        }}
        .nav-dropdown-menu a {{
            display: block; padding: 8px 16px; font-size: 13px; color: #374151;
            text-decoration: none; font-weight: 500; white-space: nowrap; transition: background 0.15s;
        }}
        .nav-dropdown-menu a:hover {{ background: #fef2f2; color: #dd032b; }}
        .nav-sep {{ width: 1px; height: 18px; background: #e5e7eb; margin: 0 2px; }}
        .main-group-header td {{
            font-size: 22px;
            font-weight: 700;
            color: #1c2a39;
            padding-top: 40px !important;
            padding-bottom: 10px !important;
            border-bottom: none !important;
            background: #fff;
            text-align: left;
        }}

        .main-group-header td:not(:first-child) {{
            background: #fff;
        }}
        #comparison-section, #variant-walk-section, #price-ladder-section, #summary-section {{ scroll-margin-top: 90px; }}
        .print-btn {{ background: transparent; color: #333; padding: 8px 12px; border: 1px solid #ced4da; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s ease; display: flex; align-items: center; gap: 8px; }}
        .print-btn:hover {{ color: #dd032b; border-color: #dd032b; background-color: #fff5f7; }}
        .content {{ padding: 50px 60px; }}
        .section-header {{ display: flex; align-items: center; gap: 15px; margin-bottom: 25px; }}
        .section-header .icon-wrapper {{ flex-shrink: 0; width: 50px; height: 50px; border-radius: 50%; background-color: white; border: 1px solid #fccad4; display: flex; align-items: center; justify-content: center; }}
        .section-header .icon-wrapper svg {{ width: 24px; height: 24px; stroke: #dd032b; stroke-width: 2; }}
        .section-header h2 {{ font-size: 24px; font-weight: 600; color: #1c2a39; }}
        .summary, .chart-container {{ background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #e9ecef; }}
        .summary p {{ line-height: 1.8; font-size: 14px; color: #495057; }}
        .summary strong {{ font-weight: 600; color: #212529; }}
        .charts-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 25px; margin-bottom: 40px; }}
        .chart-container h3 {{ color: #212529; margin-bottom: 20px; text-align: center; font-size: 16px; font-weight: 600; }}
        .chart-container:nth-child(2) {{ page-break-after: always; }}
        .chart-container {{ page-break-inside: avoid; }}
        .chart-container canvas {{
            max-width: 100% !important;
            height: auto !important;
            display: block;
        }}

        .charts-grid {{
            width: 100%;
            overflow: hidden;
        }}

        .chart-container {{
            width: 100%;
            overflow: hidden;
            position: relative;
        }}
        
        /* Sales Chart Container Fix - commented out
        .chart-container:has(#salesChart) {{
            position: relative;
            height: 450px;
        }}

        .chart-container:has(#salesChart) canvas {{
            position: absolute;
            left: 0;
            top: 0;
            width: 100% !important;
            height: 100% !important;
        }}
        */
        
        .table-container {{ overflow-x: auto; margin-top: 24px; border-radius: 12px; background: white; border: 1px solid #e9ecef; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); position: relative; }}
        .table-filter-wrapper {{ padding: 20px 20px 0 20px; background: #f8f9fa; border-bottom: 1px solid #e9ecef; position: sticky; top: 0; left: 0; z-index: 10; width: 100%; }}
        .filter-input-group {{ position: relative; display: flex; align-items: center; margin-bottom: 12px; }}
        .filter-icon {{ position: absolute; left: 16px; width: 18px; height: 18px; stroke: #6c757d; pointer-events: none; }}
        .filter-input {{ width: 100%; padding: 12px 45px 12px 45px; border: 2px solid #e9ecef; border-radius: 8px; font-size: 14px; font-family: 'Poppins', sans-serif; transition: all 0.2s ease; background: white; }}
        .filter-input:focus {{ outline: none; border-color: #e9ecef; box-shadow: 0 0 0 3px rgba(221, 3, 43, 0.1); }}
        .filter-clear-btn {{ position: absolute; right: 12px; width: 28px; height: 28px; border: none; background: #e9ecef; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s ease; padding: 0; }}
        .filter-clear-btn:hover {{ background: #dd032b; }}
        .filter-clear-btn:hover svg {{ stroke: white; }}
        .filter-clear-btn svg {{ width: 14px; height: 14px; stroke: #6c757d; transition: stroke 0.2s ease; }}
        .filter-results-info {{ font-size: 13px; color: #6c757d; padding: 0 4px 12px 4px; font-weight: 500; }}
        .filter-results-info.no-results {{ color: #dd032b; }}
        table {{ font-size: 13px; width: 100%; border-collapse: collapse; color: #212529; }}
        table th, table td {{ padding: 16px 14px; border-bottom: 1px solid #e9ecef; }}
        table th {{ background: #ffffff !important; color: #212529 !important; text-align: center; font-weight: 600; border-bottom: 2px solid #dee2e6; }}
        table th:first-child {{ text-align: left; }}
        tbody td {{ text-align: center; vertical-align: middle; }}
        tbody td:first-child {{ font-weight: 600; text-align: left; vertical-align: top; }}
        .read-more-btn {{ background: none; border: none; color: black; text-decoration: underline; cursor: pointer; padding: 4px 0; font-size: 12px; font-weight: 600; }}
        .expandable-content {{ display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; transition: -webkit-line-clamp 0.3s ease; }}
        .expandable-content.expanded {{ -webkit-line-clamp: 50; }}
        .accordion-header {{ background: #f8f9fa; cursor: pointer; transition: background 0.2s ease; user-select: none; }}
        .accordion-header:hover {{ background: #e9ecef; }}
        .accordion-header td {{ padding: 12px 14px !important; font-weight: 700; color: #1c2a39; border-bottom: 2px solid #dee2e6 !important; }}
        .accordion-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 24px; 
            font-weight: 300; 
            line-height: 1; 
            transition: transform 0.3s ease; 
        }}
        .accordion-header.active .accordion-icon {{ transform: rotate(180deg); }}
        .accordion-icon-cell {{
            text-align: right !important;
            vertical-align: middle !important;
        }}
        .hidden-spec {{ display: none; }}
        .spec-row td {{ background: #fff; }}
        .animate-on-scroll {{ opacity: 0; transform: translateY(30px); transition: opacity 0.6s ease-out, transform 0.6s ease-out; }}
        .animate-on-scroll.is-visible {{ opacity: 1; transform: translateY(0); }}
        /* #salesChart {{ min-height: 400px !important; }} */
        /* .chart-container:has(#salesChart) {{ grid-column: 1 / -1; page-break-before: always; }} */
        .footer {{ background: #dd032b; padding: 20px 60px; display: flex; align-items: center; justify-content: center; gap: 12px; border-top: none; }}
        .footer .logo {{ height: 24px; width: auto; }}
        .footer span {{ color: white; font-size: 13px; font-weight: 400; }}
        /* Consolidated Review Table Styles */
        .review-table-container {{
            background: white;
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
            border: 1px solid #e9ecef;
            overflow-x: auto;
            margin-top: 30px;
        }}

        .review-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            table-layout: fixed;
        }}

        .review-table th {{
            background: #2E3B4E !important;
            color: white !important;
            padding: 16px 14px;
            text-align: center;
            font-weight: 600;
            border: 1px solid #dee2e6;
            font-size: 14px;
        }}

        .review-table th:first-child {{
            background: #dd032b !important;
            text-align: left;
        }}

        .review-table td {{
            padding: 16px 14px;
            border: 1px solid #dee2e6;
            vertical-align: top;
            text-align: left;
            line-height: 1.8;
        }}

        .review-table td:first-child {{
            font-weight: 700;
            background: #f8f9fa;
            color: #1c2a39;
            font-size: 13px;
        }}

        .review-table .review-negative {{
            color: #000000;
            font-weight: 600;
        }}
        .review-table .review-category {{
            font-weight: 700;
            color: #212529;
        }}
        .review-table .expandable-content {{
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 3;
            overflow: hidden;
            transition: -webkit-line-clamp 0.3s ease;
            text-overflow: ellipsis; /* Ensure ellipsis is shown */
        }}
        .review-table .expandable-content.expanded {{
            -webkit-line-clamp: 50;
        }}

        .review-table .read-more-btn {{
            background: none;
            border: none;
            color: black;
            text-decoration: underline;
            cursor: pointer;
            padding: 4px 0;
            font-size: 12px;
            font-weight: 600;
            margin-top: 4px;
        }}

        .review-table .read-more-btn:hover {{
            color: #dd032b;
        }}

                
                /* Citations Section Styles */
                .citations-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
                    gap: 25px;
                }}
                
                .citation-card {{
                    background: white;
                    padding: 25px;
                    border-radius: 12px;
                    border: 1px solid #e9ecef;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
                }}
                
                .citation-car-name {{
                    font-size: 20px;
                    font-weight: 700;
                    color: #212529;
                    margin-bottom: 20px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #212529;
                }}
                
                .citation-items {{
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                    max-height: 600px;
                    overflow-y: auto;
                }}
                
                .citation-item {{
                    padding: 12px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    border-left: 3px solid #dd032b;
                }}
                
                .citation-field-name {{
                    font-size: 12px;
                    font-weight: 600;
                    color: #6c757d;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 6px;
                }}
                
                .citation-link {{
                    font-size: 12px;
                    color: #212529;
                    text-decoration: none;
                    font-weight: 600;
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    transition: color 0.2s ease;
                }}
                
                .citation-link:hover {{
                    color: #dd032b;
                    text-decoration: underline;
                }}
                
            
            @media print {{
            #citations-section, #citations-toggle, .site-header, .print-btn, .main-nav, .table-filter-wrapper, .read-more-btn {{ display: none !important; }}
            
            @page {{ 
                size: A4 landscape; 
                margin: 10mm; 
            }}
            
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}
            
            /* BASE FONT RESET */
            html {{
                font-size: 10px !important;
            }}
            
            body {{
                font-size: 10px !important;
                line-height: 1.4 !important;
                font-family: 'Poppins', Arial, sans-serif !important;
            }}
            
            .animate-on-scroll {{ opacity: 1 !important; transform: none !important; }}
            .filtered-row {{ display: table-row !important; }}
            .expandable-content {{ display: block !important; -webkit-line-clamp: unset !important; overflow: visible !important; }}
            
            .container {{ max-width: 100%; background: white; box-shadow: none; }}
            .content {{ padding: 15px 8px; page-break-inside: avoid; }}
            
            .section-header {{ margin-bottom: 12px; page-break-after: avoid; }}
            .section-header h2 {{ font-size: 16px !important; line-height: 1.3 !important; }}
            .section-header .icon-wrapper {{ display: none; }}
            
            /* OPTIMIZED TABLE STYLES */
            .table-container {{ 
                overflow: visible !important; 
                border-radius: 0; 
                box-shadow: none; 
                page-break-inside: auto; 
                margin-top: 8px; 
                width: 100%;
            }}
            
            table {{ 
                font-size: 10px !important; 
                line-height: 1.4 !important;
                width: 100% !important; 
                page-break-inside: auto; 
                border-collapse: collapse !important;
                table-layout: fixed !important;
            }}
            
            table th, table td {{ 
                padding: 8px 6px !important; 
                border: 1px solid #333 !important; 
                font-size: 10px !important;
                line-height: 1.4 !important;
                word-wrap: break-word !important;
                overflow-wrap: break-word !important;
                word-break: break-word !important;
                vertical-align: top !important;
                hyphens: auto !important;
                -webkit-hyphens: auto !important;
                -ms-hyphens: auto !important;
            }}
            
            table th {{ 
                background: #e9ecef !important; 
                color: #000 !important; 
                font-size: 11px !important; 
                font-weight: 700 !important;
                text-align: center !important;
                line-height: 1.3 !important;
                padding: 10px 6px !important;
            }}
            
            table th:first-child {{ 
                background: #6c757d !important; 
                color: white !important;
                text-align: left !important;
                width: 180px !important;
                min-width: 180px !important;
                max-width: 180px !important;
                font-size: 11px !important;
            }}
            
            table tr {{ 
                page-break-inside: avoid !important;
            }}
            
            tbody td {{ 
                font-size: 10px !important;
                line-height: 1.4 !important;
                padding: 8px 6px !important;
            }}
            
            tbody td:first-child {{ 
                font-weight: 700; 
                font-size: 10px !important;
                background: #f8f9fa !important;
                text-align: left !important;
                width: 180px !important;
                min-width: 180px !important;
                max-width: 180px !important;
                line-height: 1.3 !important;
            }}
            
            tbody td:not(:first-child) {{
                text-align: center !important;
                font-size: 10px !important;
                font-weight: 400 !important;
            }}
            
            /* Long text handling */
            tbody td {{
                white-space: normal !important;
                overflow: visible !important;
            }}
            
            /* Hide empty cells/rows */
            tbody tr:has(td:nth-child(2):empty):has(td:nth-child(3):empty):not(.spec-row) {{
                display: none !important;
            }}
            
            /* Accordion Headers */
            .accordion-header {{ 
                display: table-row !important; 
                background: #dee2e6 !important; 
                page-break-after: avoid !important;
            }}
            
            .accordion-header td {{ 
                font-size: 11px !important; 
                font-weight: 700 !important;
                padding: 10px 6px !important;
                border: 1px solid #333 !important;
                line-height: 1.3 !important;
            }}
            
            .accordion-header td:not(:first-child):empty {{
                display: none !important;
            }}
            
            .accordion-icon {{ display: none !important; }}
            
            .accordion-title-cell {{
                padding: 10px 6px !important;
                font-weight: 700;
                font-size: 11px !important;
                color: #000 !important;
                border: 1px solid #333 !important;
                background: #dee2e6 !important;
                text-align: left !important;
                line-height: 1.3 !important;
            }}

            .accordion-empty-cell {{
                background: #dee2e6 !important;
                border: 1px solid #333 !important;
                padding: 10px 6px !important;
            }}

            /* Main Group Headers */
            .main-group-header td {{
                font-size: 12px !important;
                font-weight: 700 !important;
                line-height: 1.3 !important;
                color: #000 !important;
                padding: 12px 6px !important;
                background: #f8f9fa !important;
                border: 1px solid #333 !important;
                text-align: left !important;
            }}

            .spec-row td {{
                background: #fff !important;
            }}
            
            .hidden-spec {{ display: table-row !important; }}
            
            /* Review Table */
            .review-table-container {{
                page-break-inside: avoid !important;
                padding: 12px !important;
                margin-top: 15px;
                box-shadow: none !important;
                border-radius: 0;
                overflow: visible !important;
            }}
            
            .review-table {{
                font-size: 10px !important;
                line-height: 1.4 !important;
                page-break-inside: avoid !important;
                table-layout: fixed !important;
                width: 100% !important;
                border-collapse: collapse !important;
            }}

            .review-table th, .review-table td {{
                padding: 8px 6px !important;
                font-size: 10px !important;
                line-height: 1.4 !important;
                border: 1px solid #333 !important;
                word-wrap: break-word !important;
                overflow-wrap: break-word !important;
                word-break: break-word !important;
                vertical-align: top !important;
                hyphens: auto !important;
                -webkit-hyphens: auto !important;
                -ms-hyphens: auto !important;
                white-space: normal !important;
                overflow: visible !important;
            }}

            .review-table th {{
                background: #e9ecef !important;
                color: #000 !important;
                font-size: 11px !important;
                font-weight: 700 !important;
                text-align: center !important;
                line-height: 1.3 !important;
                padding: 10px 6px !important;
            }}
            
            .review-table th:first-child {{
                background: #adb5bd !important;
                color: #000 !important;
                text-align: left !important;
                width: 180px !important;
                min-width: 180px !important;
                max-width: 180px !important;
                font-size: 11px !important;
            }}
            
            .review-table td:first-child {{
                font-size: 11px !important;
                background: #f8f9fa !important;
                width: 180px !important;
                min-width: 180px !important;
                max-width: 180px !important;
                font-weight: 700 !important;
                text-align: left !important;
                line-height: 1.3 !important;
            }}
            
            .review-table td:not(:first-child) {{
                text-align: left !important;
                font-size: 10px !important;
                font-weight: 400 !important;
                line-height: 1.4 !important;
            }}
            
            .review-table tr {{
                page-break-inside: avoid !important;
            }}
            
            .review-table .review-category {{
                font-weight: 700 !important;
                color: #000 !important;
            }}
            
            /* Hide Read More buttons in print */
            .review-table .read-more-btn {{
                display: none !important;
            }}
            
            /* Expand all content in print */
            .review-table .expandable-content {{
                display: block !important;
                -webkit-line-clamp: unset !important;
                overflow: visible !important;
            }}
            
            .review-table .expandable-content.expanded {{
                -webkit-line-clamp: unset !important;
            }}
            
            /* Charts */
            .charts-grid {{ 
                display: grid !important; 
                grid-template-columns: repeat(2, 1fr) !important; 
                gap: 12px !important; 
                margin-bottom: 0 !important; 
                page-break-inside: avoid; 
            }}
            
            .chart-container {{ 
                padding: 12px !important; 
                border: 1px solid #333 !important; 
                border-radius: 6px; 
                box-shadow: none !important; 
                page-break-inside: avoid !important; 
                break-inside: avoid !important; 
                margin-bottom: 8px; 
            }}
            
            .chart-container h3 {{ 
                font-size: 13px !important; 
                line-height: 1.3 !important;
                margin-bottom: 8px !important; 
            }}
            
            .chart-container:nth-child(2) {{ 
                page-break-after: always !important; 
                break-after: page !important; 
            }}
            
            canvas {{ 
                max-width: 100% !important; 
                height: auto !important; 
            }}
            
            /* Summary */
            .summary {{ 
                padding: 12px !important; 
                border: 1px solid #333 !important; 
                border-radius: 6px; 
                box-shadow: none !important; 
                page-break-inside: avoid; 
                font-size: 11px !important; 
                line-height: 1.5 !important;
            }}
            
            .summary p {{ 
                font-size: 11px !important; 
                line-height: 1.5 !important; 
            }}
            
            /* Footer */
            .footer {{ 
                page-break-before: avoid; 
                padding: 12px 15px !important; 
                margin-top: 15px; 
            }}
            
            .footer span {{ 
                font-size: 10px !important; 
            }}
            
            .footer .logo {{ 
                height: 18px !important; 
            }}
            
            h2, h3 {{ 
                page-break-after: avoid; 
                orphans: 3; 
                widows: 3; 
            }}
            
            /* Typography consistency */
            p, span, div, li {{
                font-size: 10px !important;
                line-height: 1.4 !important;
            }}
            
            strong, b {{
                font-weight: 700 !important;
            }}
        }}
                /* Tablet Styles (1024px and below) */
                @media (max-width: 1024px) {{ 
                    .charts-grid {{ 
                        grid-template-columns: 1fr; 
                    }} 
                    
                    .citations-grid {{
                        grid-template-columns: 1fr;
                    }}
                    
                    .main-nav {{
                        gap: 10px;
                    }}

                    .main-nav > a, .main-nav > .nav-dropdown > .nav-dropdown-toggle {{
                        font-size: 13px;
                        padding: 5px 8px;
                    }}
                    
                    .content {{ 
                        padding: 30px 40px; 
                    }} 
                    
                    .site-header {{
                        padding: 16px 30px;
                    }}
                    
                    .footer {{
                        padding: 20px 40px;
                    }}
                    
                    table {{
                        font-size: 12px;
                    }}
                    
                    table th, table td {{
                        padding: 12px 10px;
                    }}
                    
                    .section-header h2 {{
                        font-size: 22px;
                    }}
                    
                    .chart-container {{
                        padding: 25px;
                    }}
                    
                    .chart-container h3 {{
                        font-size: 15px;
                    }}
                }}
                
                /* Mobile Styles (768px and below) */
                @media (max-width: 768px) {{ 
                    .site-header {{ 
                        padding: 12px 20px;
                        flex-wrap: wrap;
                        gap: 12px;
                    }} 
                    
                    .logo {{
                        height: 18px;
                    }}
                    .review-table {{
                font-size: 11px;
            }}
            
            .review-table th, .review-table td {{
                padding: 10px 8px;
            }}
                    .header-actions {{
                        width: 100%;
                        justify-content: space-between;
                        gap: 15px;
                    }}
                    
                    .main-nav {{
                        flex-wrap: wrap;
                        gap: 8px;
                        justify-content: center;
                    }}

                    .main-nav > a, .main-nav > .nav-dropdown > .nav-dropdown-toggle {{
                        font-size: 12px;
                        padding: 4px 8px;
                    }}

                    .nav-sep {{
                        display: none;
                    }}
                    
                    .print-btn {{
                        font-size: 11px;
                        padding: 6px 10px;
                        gap: 4px;
                    }}
                    
                    .content {{ 
                        padding: 20px 15px; 
                    }} 
                    
                    .section-header {{
                        gap: 10px;
                        margin-bottom: 20px;
                    }}
                    
                    .section-header .icon-wrapper {{
                        width: 40px;
                        height: 40px;
                    }}
                    
                    .section-header .icon-wrapper svg {{
                        width: 20px;
                        height: 20px;
                    }}
                    
                    .section-header h2 {{ 
                        font-size: 18px; 
                    }} 
                    
                    .main-group-header td {{
                        font-size: 16px !important;
                        padding: 20px 8px 8px 8px !important;
                        text-align: left !important;
                        font-weight: 700 !important;
                    }}
                    
                    .summary, .chart-container {{
                        padding: 20px 15px;
                        border-radius: 12px;
                    }}
                    
                    .summary p {{
                        font-size: 13px;
                        line-height: 1.6;
                    }}
                    
                    .charts-grid {{
                        gap: 20px;
                        margin-bottom: 30px;
                    }}
                    
                    .chart-container {{
                        padding: 15px 10px !important;
                        width: 100%;
                        overflow-x: hidden;
                    }}
                    
                    .chart-container canvas {{
                        width: 100% !important;
                        max-width: 100% !important;
                        height: auto !important;
                    }}
                    
                    .charts-grid {{
                        padding: 0;
                        margin-bottom: 20px;
                        width: 100%;
                    }}
                    
                    /* Sales Chart Mobile Fix - commented out
                    .chart-container:has(#salesChart) {{
                        padding: 10px 5px !important;
                        height: 400px;
                    }}

                    #salesChart {{
                        height: 100% !important;
                        min-height: unset !important;
                    }}
                    */
                    
                    .table-container {{
                        overflow-x: auto;
                        -webkit-overflow-scrolling: touch;
                        margin-top: 20px;
                        border-radius: 8px;
                        position: relative;
                    }}
                    
                    .table-filter-wrapper {{
                        padding: 15px 15px 0 15px;
                    }}
                    .spec-row td {{
                font-size: 11px !important;
                background: #fff !important;
            }}
            
            .spec-row td:first-child {{
                font-size: 11px !important;
                background: #f8f9fa !important;
                font-weight: 600 !important;
                text-align: left !important;
            }}
                    .filter-input {{
                        padding: 10px 40px 10px 40px;
                        font-size: 13px;
                    }}
                    
                    .filter-icon {{
                        left: 12px;
                        width: 16px;
                        height: 16px;
                    }}
                    
                    .filter-clear-btn {{
                        right: 10px;
                        width: 24px;
                        height: 24px;
                    }}
                    
                    .filter-results-info {{
                        font-size: 12px;
                    }}
                    
                    table {{
                        font-size: 11px !important;
                        min-width: 100% !important;
                        table-layout: auto !important;
                        width: 100% !important;
                    }}
                    
                    table th, table td {{
                        padding: 10px 8px !important;
                        font-size: 11px !important;
                        line-height: 1.5 !important;
                        word-wrap: break-word !important;
                        overflow-wrap: break-word !important;
                        white-space: normal !important;
                    }}
                    
                    .accordion-header td {{
                        padding: 10px 8px !important;
                        font-size: 13px;
                    }}
                    
                    .accordion-icon {{
                        font-size: 18px !important;
                        display: inline-flex !important;
                    }}
                    
                    table th:first-child,
                    table td:first-child,
                    tbody td:first-child {{
                        font-size: 11px !important;
                        font-weight: 600 !important;
                        text-align: left !important;
                        padding: 10px 8px !important;
                        min-width: 140px !important;
                        max-width: 140px !important;
                        width: 140px !important;
                        position: sticky !important;
                        left: 0 !important;
                        background: #f8f9fa !important;
                        z-index: 2 !important;
                    }}
                    tbody td:not(:first-child) {{
                text-align: center !important;
                font-size: 11px !important;
                font-weight: 400 !important;
                vertical-align: middle !important;
                padding: 10px 8px !important;
            }}
                    
                    .expandable-content {{
                font-size: 11px !important;
                -webkit-line-clamp: 2 !important;
                line-height: 1.5 !important;
            }}
                    
                    .read-more-btn {{
                font-size: 10px !important;
                padding: 2px 0 !important;
                margin-top: 4px !important;
            }}
                    .footer {{
                        padding: 15px 20px;
                        flex-direction: column;
                        gap: 8px;
                    }}
                    
                    .footer .logo {{
                        height: 20px;
                    }}
                    
                    .footer span {{
                        font-size: 11px;
                        text-align: center;
                    }}
                    
                    .citations-grid {{
                        grid-template-columns: 1fr;
                        gap: 20px;
                    }}
                    
                    .citation-card {{
                        padding: 20px 15px;
                    }}
                    
                    .citation-car-name {{
                        font-size: 18px;
                        margin-bottom: 15px;
                    }}
                    
                    .citation-items {{
                        gap: 12px;
                        max-height: 500px;
                    }}
                    
                    .citation-item {{
                        padding: 10px;
                    }}
                    
                    .citation-field-name {{
                        font-size: 11px;
                    }}
                    
                    .citation-link {{
                font-size: 11px;
                line-height: 1.5;
                padding: 4px 0;
                word-break: break-all; /* Ensure URLs break */
                max-width: 100%;
            }}
                .review-table {{
                font-size: 11px !important;
                table-layout: auto !important;
            }}
            
            review-table th, .review-table td {{
                padding: 10px 8px !important;
                font-size: 11px !important;
                text-align: left !important;
            }}
            
            .review-table-container {{
                padding: 20px 15px;
                margin-top: 20px;
            }}
            
            .review-table .read-more-btn {{
                font-size: 11px;
            }}
            .review-table td:first-child {{
                font-size: 11px !important;
                min-width: 120px !important;
                max-width: 120px !important;
                position: sticky !important;
                left: 0 !important;
                background: #f8f9fa !important;
                z-index: 2 !important;
            }}
            .review-table .expandable-content {{
                -webkit-line-clamp: 2;
            }}
                }}
                
                /* Small Mobile Styles (480px and below) */
                @media (max-width: 430px) {{
                    .site-header {{
                        padding: 10px 15px;
                    }}
                    
                    .logo {{
                        height: 16px;
                    }}
                    
                    .header-actions {{
                        flex-direction: column;
                        gap: 10px;
                    }}
                    
                    .main-nav {{
                        width: 100%;
                    }}

                    .main-nav > a, .main-nav > .nav-dropdown > .nav-dropdown-toggle {{
                        font-size: 11px;
                        padding: 3px 6px;
                    }}
                    
                    .print-btn {{
                        font-size: 10px;
                        padding: 5px 8px;
                        width: 100%;
                        justify-content: center;
                    }}
                    
                    .content {{
                        padding: 15px 10px;
                    }}
                    
                    .section-header h2 {{
                        font-size: 16px;
                    }}
                    
                    .section-header .icon-wrapper {{
                        width: 35px;
                        height: 35px;
                    }}
                    
                    .section-header .icon-wrapper svg {{
                        width: 18px;
                        height: 18px;
                    }}
                    
                    .main-group-header td {{
                        font-size: 16px;
                    }}
                    
                    .summary {{
                        padding: 15px 10px;
                    }}
                    
                    .summary p {{
                        font-size: 12px;
                    }}
                    
                    .chart-container {{
                        padding: 10px 5px !important;
                    }}
                    
                    .chart-container h3 {{
                        font-size: 12px;
                        margin-bottom: 10px;
                    }}
                    
                    /* Sales Chart Small Mobile Fix - commented out
                    .chart-container:has(#salesChart) {{
                        padding: 8px 3px !important;
                        height: 350px;
                    }}
                    */
            
                    table {{
                font-size: 10px !important;
            }}
                    
                    table th, table td {{
                font-size: 10px !important;
                padding: 8px 5px !important;
            }}
                    table td:first-child,
            tbody td:first-child {{
                font-size: 10px !important;
                min-width: 105px !important;
                max-width: 105px !important;
                width: 105px !important;
            }}
            tbody td:not(:first-child) {{
                font-size: 10px !important;
                text-align: center !important;
            }}
            
                    .accordion-header td {{
                font-size: 10px !important;
                padding: 8px 5px !important;
            }}
            .main-group-header td {{
                font-size: 13px !important;
            }}
                    
                    .filter-input {{
                        padding: 8px 35px 8px 35px;
                        font-size: 12px;
                    }}
                    
                    .citation-card {{
                        padding: 15px 10px;
                    }}
                    
                    .citation-car-name {{
                        font-size: 16px;
                    }}
                    
                    .citation-items {{
                        max-height: 400px;
                    }}

            
            .citation-link {{
                font-size: 10px;
                line-height: 1.6;
                padding: 5px 0;
                word-break: break-all;
                max-width: 100%;
            }}
                    .footer {{
                        padding: 12px 15px;
                    }}
                    
                    .footer span {{
                        font-size: 10px;
                    }}
                    
                    canvas {{
                        max-height: 250px !important;
                    }}
                    .review-table {{
                font-size: 10px;
            }}
            
            .review-table th, .review-table td {{
                padding: 8px 6px;
            }}
            
            .review-table-container {{
                padding: 15px 10px;
            }}
                }}

                /* Extra Small Mobile - 375px specific fix */
                @media (max-width: 375px) {{
                    .site-header {{
                        padding: 8px 12px;
                        flex-direction: column;
                        gap: 8px;
                        align-items: stretch;
                    }}
                    
                    .logo {{
                        height: 16px;
                        align-self: flex-start;
                    }}
                    
                    .header-actions {{
                        width: 100%;
                        flex-direction: column;
                        gap: 8px;
                    }}
                    
                    .main-nav {{
                        width: 100%;
                        flex-wrap: nowrap;
                        justify-content: space-between;
                        gap: 5px;
                        overflow-x: auto;
                        -webkit-overflow-scrolling: touch;
                        padding: 4px 0;
                    }}

                    .main-nav > a, .main-nav > .nav-dropdown > .nav-dropdown-toggle {{
                        font-size: 10px;
                        padding: 4px 6px;
                        white-space: nowrap;
                        flex-shrink: 0;
                    }}
                    
                    .print-btn {{
                        font-size: 11px;
                        padding: 6px 10px;
                        width: 100%;
                        justify-content: center;
                    }}
                    
                    .content {{
                        padding: 12px 8px;
                    }}
                    
                    .section-header h2 {{
                        font-size: 14px;
                    }}
                    
                    .section-header .icon-wrapper {{
                        width: 32px;
                        height: 32px;
                    }}
                    
                    .section-header .icon-wrapper svg {{
                        width: 16px;
                        height: 16px;
                    }}
                    
                    /* Sales Chart Extra Small Fix - commented out
                    .chart-container:has(#salesChart) {{
                        height: 380px;
                    }}
                    */
        
            
            .citation-link {{
                font-size: 10px; /* Don't go smaller than 10px */
                line-height: 1.6;
                padding: 5px 0;
                word-break: break-all;
                max-width: 100%;
            }}
                }}

            /* Image Section Styles */
            {get_image_section_styles()}

            /* Pros/Cons Table Styles */
            .proscons-table-container {{
                margin: 20px 0;
                overflow-x: auto;
            }}

            .proscons-table-container h3 {{
                margin-bottom: 15px;
                color: #2c3e50;
                font-size: 1.5em;
            }}

            .proscons-table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                font-size: 14px;
            }}

            .proscons-table thead {{
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: white;
            }}

            .proscons-table thead th {{
                padding: 15px 10px;
                text-align: left;
                font-weight: 600;
                border-right: 1px solid rgba(255,255,255,0.2);
            }}

            .proscons-table .serial-col {{
                width: 80px;
                min-width: 80px;
                text-align: center;
            }}

            .proscons-table .publication-col {{
                width: 150px;
                min-width: 150px;
            }}

            .proscons-table .link-col {{
                width: 120px;
                min-width: 120px;
                text-align: center;
            }}

            .proscons-table .positives-col {{
                width: 40%;
                background: rgba(39, 174, 96, 0.1);
            }}

            .proscons-table .negatives-col {{
                width: 40%;
                background: rgba(231, 76, 60, 0.1);
            }}

            .proscons-table tbody tr {{
                border-bottom: 1px solid #e0e0e0;
                transition: background-color 0.2s ease;
            }}

            .proscons-table tbody tr:hover {{
                background-color: #fff5f7;
                border-left: 3px solid #dd032b;
            }}

            .proscons-table .serial-cell {{
                text-align: center;
                font-weight: 600;
                padding: 15px 10px;
                color: #2c3e50;
            }}

            .proscons-table .publication-cell {{
                padding: 15px 10px;
                font-weight: 600;
                color: #34495e;
            }}

            .proscons-table .link-cell {{
                text-align: center;
                padding: 15px 10px;
            }}

            .proscons-table .link-cell a {{
                color: #000000;
                text-decoration: none;
                font-weight: 600;
                padding: 5px 10px;
                background: #ffffff;
                border: 1px solid #000000;
                border-radius: 4px;
                transition: all 0.3s ease;
            }}

            .proscons-table .link-cell a:hover {{
                background: #000000;
                color: #ffffff;
                border-color: #000000;
            }}

            /* YouTube Citation Box Styling */
            .youtube-citation-box {{
                display: inline-block;
                padding: 6px 12px;
                background: #ffffff;
                border: 1.5px solid #e0e0e0;
                border-radius: 6px;
                color: #2c3e50;
                text-decoration: none;
                font-weight: 500;
                font-size: 0.85em;
                transition: all 0.3s ease;
                box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            }}

            .youtube-citation-box:hover {{
                background: #f8f9fa;
                border-color: #dd032b;
                color: #dd032b;
                box-shadow: 0 4px 8px rgba(221,3,43,0.15);
                transform: translateY(-1px);
            }}

            .proscons-table .positives-cell {{
                padding: 15px;
                background: rgba(39, 174, 96, 0.05);
                border-left: 3px solid #27ae60;
            }}

            .proscons-table .negatives-cell {{
                padding: 15px;
                background: rgba(231, 76, 60, 0.05);
                border-left: 3px solid #e74c3c;
            }}

            .proscons-list {{
                margin: 0;
                padding-left: 20px;
                list-style-type: disc;
            }}

            .proscons-list li {{
                margin: 8px 0;
                line-height: 1.6;
                color: #2c3e50;
            }}

            .positives-cell .proscons-list li::marker {{
                color: #27ae60;
            }}

            .negatives-cell .proscons-list li::marker {{
                color: #e74c3c;
            }}

            /* Responsive */
            @media (max-width: 1024px) {{
                .proscons-table {{
                    font-size: 12px;
                }}

                .proscons-table .serial-col {{
                    width: 60px;
                    min-width: 60px;
                }}

                .proscons-table .publication-col {{
                    width: 120px;
                    min-width: 120px;
                }}

                .proscons-table .link-col {{
                    width: 100px;
                    min-width: 100px;
                }}
            }}

            @media print {{
                .proscons-table {{
                    page-break-inside: avoid;
                }}

                .proscons-table tbody tr {{
                    page-break-inside: avoid;
                }}
            }}
            </style>
</head>
<body>
    <header class="site-header">
        <a href="#"><img src="https://www.mahindra.com//sites/default/files/2025-07/mahindra-red-logo.webp" alt="Logo" class="logo"></a>
        <div class="header-actions">
            <nav class="main-nav">
                <a href="#tech-spec-section">Tech Specs</a>
                <a href="#venn-section">Feature Face-Off</a>
                <div class="nav-sep"></div>
                <div class="nav-dropdown">
                    <button class="nav-dropdown-toggle">Lifecycle</button>
                    <div class="nav-dropdown-menu" id="lifecycle-dropdown">
                    </div>
                </div>
                <div class="nav-dropdown">
                    <button class="nav-dropdown-toggle">Gallery</button>
                    <div class="nav-dropdown-menu">
                        <a href="#vehicle-highlights">Highlights</a>
                        <a href="#exterior-section">Exterior</a>
                        <a href="#interior-section">Interior</a>
                        <a href="#technology-section">Technology</a>
                        <a href="#comfort-section">Comfort</a>
                        <a href="#safety-section">Safety</a>
                    </div>
                </div>
                <div class="nav-dropdown">
                    <button class="nav-dropdown-toggle">Variants</button>
                    <div class="nav-dropdown-menu">
                        <a href="#variant-walk-section">Variant Walk</a>
                        <a href="#price-ladder-section">Price Ladder</a>
                    </div>
                </div>
                <div class="nav-sep"></div>
                <a href="#summary-section">Pros & Cons</a>
                <a href="#" id="citations-toggle" onclick="toggleCitations(event)">Citations</a>
            </nav>
            <button class="print-btn" onclick="printReport()">Save as PDF</button>
        </div>
    </header>
    {generate_hero_section(comparison_data)}
    {generate_vehicle_highlights_section(comparison_data)}
    {generate_technical_spec_section(comparison_data)}
    {generate_venn_diagram_section(comparison_data, summary_data)}
    {generate_feature_list_section(comparison_data)}
    {generate_lifecycle_section(comparison_data)}
    <div class="container">
        {generate_image_gallery_section("Exterior Highlights", comparison_data, "exterior", "exterior-section", with_ai_notes=True)}
        {generate_image_gallery_section("Interior Highlights", comparison_data, "interior", "interior-section", with_ai_notes=True)}
        {generate_image_gallery_section("Technology Highlights", comparison_data, "technology", "technology-section", with_ai_notes=True)}
        {generate_image_gallery_section("Comfort Highlights", comparison_data, "comfort", "comfort-section", with_ai_notes=True)}
        {generate_image_gallery_section("Safety Highlights", comparison_data, "safety", "safety-section", with_ai_notes=True)}
        <div class="content">
            <div class="section-header">
                <div class="icon-wrapper">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                        <polyline points="9 22 9 12 15 12 15 22"></polyline>
                    </svg>
                </div>
                <h2 id="variant-walk-section">Variant Walk</h2>
            </div>
            <div class="variant-walk-section animate-on-scroll">{generate_variant_walk_section(comparison_data)}</div>
        </div>
        <div class="content">
            <div class="section-header">
                <div class="icon-wrapper">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
                    </svg>
                </div>
                <h2 id="price-ladder-section">Price Ladder</h2>
            </div>
            <div class="price-ladder-section animate-on-scroll">{generate_price_ladder_section(comparison_data)}</div>
        </div>
        <div class="content">
            <div class="section-header"><div class="icon-wrapper"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg></div><h2 id="summary-section">YouTube Pros & Cons Analysis</h2></div>
            <div class="proscons-section animate-on-scroll">{proscons_html}</div>
        </div>
        <div class="content" id="citations-section" style="display: none;"><div class="section-header"><div class="icon-wrapper"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><line x1="10" y1="9" x2="8" y2="9"></line></svg></div><h2>Data Source Citations</h2></div><div class="citations-grid">{citations_html}</div></div>
    </div>
    <footer class="footer"><span>Copyright© 2026 Mahindra&Mahindra Ltd. All Rights Reserved.</span></footer>
    <script>
            function toggleAccordion(headerRow) {{
    headerRow.classList.toggle('active');
    let currentRow = headerRow.nextElementSibling;
    
    while (currentRow && currentRow.classList.contains('spec-row')) {{
        if (document.getElementById('specFilter').value.trim() === '') {{
            // Toggle display without changing any styles
            if (headerRow.classList.contains('active')) {{
                currentRow.style.display = 'table-row';
            }} else {{
                currentRow.style.display = 'none';
            }}
        }}
        currentRow = currentRow.nextElementSibling;
    }}
}}
            function expandAllAccordions() {{ document.querySelectorAll('.accordion-header:not(.active)').forEach(header => {{ header.classList.add('active'); let currentRow = header.nextElementSibling; while (currentRow && currentRow.classList.contains('spec-row')) {{ currentRow.style.display = 'table-row'; currentRow = currentRow.nextElementSibling; }} }}); }}
        function collapseAllAccordions() {{ document.querySelectorAll('.accordion-header.active').forEach(header => {{ header.classList.remove('active'); let currentRow = header.nextElementSibling; while (currentRow && currentRow.classList.contains('spec-row')) {{ currentRow.style.display = 'none'; currentRow = currentRow.nextElementSibling; }} }}); }}
        function filterSpecs() {{ const input = document.getElementById('specFilter'); const filter = input.value.toLowerCase().trim(); const tbody = document.getElementById('specifications-tbody'); const resultsInfo = document.getElementById('filterResults'); document.getElementById('clearFilterBtn').style.display = filter ? 'flex' : 'none'; if (filter) {{ expandAllAccordions(); }} else {{ collapseAllAccordions(); }} let visibleSpecCount = 0; const specRows = tbody.querySelectorAll('.spec-row'); specRows.forEach(row => {{ const specName = row.cells[0].textContent.toLowerCase(); if (filter && specName.includes(filter)) {{ row.style.display = 'table-row'; visibleSpecCount++; }} else if (filter) {{ row.style.display = 'none'; }} else {{ let prevSibling = row.previousElementSibling; let isUnderAccordion = false; while (prevSibling) {{ if (prevSibling.classList.contains('accordion-header')) {{ isUnderAccordion = true; break; }} if (prevSibling.classList.contains('main-group-header')) {{ break; }} prevSibling = prevSibling.previousElementSibling; }} row.style.display = isUnderAccordion ? 'none' : 'table-row'; }} }}); tbody.querySelectorAll('.accordion-header').forEach(header => {{ if (filter) {{ let hasVisibleChild = false; let currentRow = header.nextElementSibling; while (currentRow && currentRow.classList.contains('spec-row')) {{ if (currentRow.style.display !== 'none') {{ hasVisibleChild = true; break; }} currentRow = currentRow.nextElementSibling; }} header.style.display = hasVisibleChild ? 'table-row' : 'none'; }} else {{ header.style.display = 'table-row'; }} }}); tbody.querySelectorAll('.main-group-header').forEach(mainHeader => {{ if (filter) {{ mainHeader.style.display = 'none'; }} else {{ mainHeader.style.display = 'table-row'; }} }}); if (filter) {{ resultsInfo.textContent = visibleSpecCount === 0 ? 'No specifications match your search' : `Showing ${{visibleSpecCount}} matching specifications`; resultsInfo.classList.toggle('no-results', visibleSpecCount === 0); }} else {{ resultsInfo.textContent = ''; resultsInfo.classList.remove('no-results'); }} }}
        function clearFilter() {{ const input = document.getElementById('specFilter'); input.value = ''; filterSpecs(); input.focus(); }}
        function printReport() {{ window.print(); }}
        function toggleExpand(button) {{ const content = button.previousElementSibling; content.classList.toggle('expanded'); button.textContent = content.classList.contains('expanded') ? 'Read less' : 'Read more'; }}
        function toggleCitations(event) {{ event.preventDefault(); const citationsSection = document.getElementById('citations-section'); const mainContent = document.querySelectorAll('.content:not(#citations-section)'); const heroSection = document.getElementById('hero-section'); const techSpecSection = document.getElementById('tech-spec-section'); const featureListSection = document.getElementById('feature-list-section'); const lifecyclePages = document.querySelectorAll('.lifecycle-page'); const toggleButton = document.getElementById('citations-toggle'); const navLinks = document.querySelectorAll('.main-nav a:not(#citations-toggle)'); const navDropdowns = document.querySelectorAll('.nav-dropdown'); const navSeps = document.querySelectorAll('.nav-sep'); if (citationsSection.style.display === 'none') {{ citationsSection.style.display = 'block'; mainContent.forEach(section => {{ section.style.display = 'none'; }}); if (heroSection) heroSection.style.display = 'none'; if (techSpecSection) techSpecSection.style.display = 'none'; if (featureListSection) featureListSection.style.display = 'none'; lifecyclePages.forEach(page => {{ page.style.display = 'none'; }}); navLinks.forEach(link => {{ link.style.display = 'none'; }}); navDropdowns.forEach(dropdown => {{ dropdown.style.display = 'none'; }}); navSeps.forEach(sep => {{ sep.style.display = 'none'; }}); toggleButton.textContent = 'Go Back'; }} else {{ citationsSection.style.display = 'none'; mainContent.forEach(section => {{ section.style.display = 'block'; }}); if (heroSection) heroSection.style.display = ''; if (techSpecSection) techSpecSection.style.display = ''; if (featureListSection) featureListSection.style.display = ''; lifecyclePages.forEach(page => {{ page.style.display = ''; }}); navLinks.forEach(link => {{ link.style.display = ''; }}); navDropdowns.forEach(dropdown => {{ dropdown.style.display = ''; }}); navSeps.forEach(sep => {{ sep.style.display = ''; }}); toggleButton.textContent = 'Citations'; }} window.scrollTo({{ top: 0, behavior: 'smooth' }}); }}
        
        /* Chart.js code commented out - replaced with Variant Walk
        const carLabels = {json.dumps(cars)};
        const priceData = {json.dumps(prices)};
        const mileageData = {json.dumps(mileages)};
        const ratingData = {json.dumps(ratings)};
        const seatingData = {json.dumps(seating)};
        const salesVolumes = {json.dumps(sales_volumes)};
        const primaryColor = '#2E3B4E', secondaryColor = '#dd032b';
        const isMobile = window.innerWidth < 768;

        new Chart(document.getElementById('priceChart'), {{ type: 'bar', data: {{ labels: carLabels, datasets: [{{ data: priceData, backgroundColor: (ctx) => ctx.dataIndex % 2 === 0 ? primaryColor : secondaryColor }}] }}, options: {{ plugins: {{ legend: {{ display: false }} }} }} }});
        new Chart(document.getElementById('mileageChart'), {{ type: 'bar', data: {{ labels: carLabels, datasets: [{{ data: mileageData, backgroundColor: (ctx) => ctx.dataIndex % 2 === 0 ? primaryColor : secondaryColor }}] }}, options: {{ plugins: {{ legend: {{ display: false }} }} }} }});
        new Chart(document.getElementById('ratingChart'), {{ type: 'bar', data: {{ labels: carLabels, datasets: [{{ data: ratingData, backgroundColor: (ctx) => ctx.dataIndex % 2 === 0 ? primaryColor : secondaryColor }}] }}, options: {{ scales: {{ y: {{ max: 5 }} }}, plugins: {{ legend: {{ display: false }} }} }} }});
        new Chart(document.getElementById('seatingChart'), {{ type: 'bar', data: {{ labels: carLabels, datasets: [{{ data: seatingData, backgroundColor: (ctx) => ctx.dataIndex % 2 === 0 ? primaryColor : secondaryColor }}] }}, options: {{ plugins: {{ legend: {{ display: false }} }} }} }});
        */
        
        /* Sales chart commented out
        new Chart(document.getElementById('salesChart'), {{
            type: 'bar',
            data: {{
                labels: carLabels,
                datasets: [{{
                    label: 'Sales Volume (Units/Month)',
                    data: salesVolumes,
                    backgroundColor: primaryColor,
                    xAxisID: 'x'
                }}, {{
                    label: 'Price (₹ Lakhs)',
                    data: priceData,
                    backgroundColor: secondaryColor,
                    xAxisID: 'x1'
                }}]
            }},
            options: {{
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {{
                    y: {{
                        position: 'left',
                        ticks: {{
                            font: {{ size: isMobile ? 9 : 12 }},
                            autoSkip: false,
                            maxRotation: 0,
                            minRotation: 0
                        }}
                    }},
                    x: {{
                        display: true,
                        type: 'linear',
                        position: 'bottom',
                        title: {{
                            display: !isMobile,
                            text: 'Sales Volume (Units/Month)',
                            font: {{ size: isMobile ? 9 : 12 }}
                        }},
                        ticks: {{
                            display: true,
                            font: {{ size: isMobile ? 7 : 11 }},
                            callback: function(value) {{
                                if (isMobile) {{
                                    return value >= 1000 ? (value/1000).toFixed(0) + 'k' : value;
                                }}
                                return value.toLocaleString() + ' units';
                            }}
                        }},
                        grid: {{
                            display: true,
                            color: isMobile ? '#f0f0f0' : '#e9ecef'
                        }}
                    }},
                    x1: {{
                        display: true,
                        type: 'linear',
                        position: 'top',
                        title: {{
                            display: !isMobile,
                            text: 'Price (₹ Lakhs)',
                            color: '#6c757d',
                            font: {{ size: isMobile ? 9 : 12 }}
                        }},
                        grid: {{
                            drawOnChartArea: false,
                            display: false
                        }},
                        ticks: {{
                            display: true,
                            color: '#6c757d',
                            font: {{ size: isMobile ? 7 : 11 }},
                            callback: function(value) {{ return '₹' + value.toFixed(1) + 'L'; }}
                        }}
                    }}
                }},
                plugins: {{
    legend: {{
        display: false
    }},
    tooltip: {{
        enabled: true,
        callbacks: {{
            label: function(context) {{
                let label = context.dataset.label || '';
                if (label) {{ label += ': '; }}
                if (context.dataset.label.includes('Price')) {{
                    label += '₹' + context.parsed.x.toFixed(2) + ' Lakhs';
                }} else {{
                    label += context.parsed.x.toLocaleString() + ' units';
                }}
                return label;
            }}
        }}
    }}
}}
            }}
        }});
        */
        
        document.addEventListener('DOMContentLoaded', () => {{
            const observer = new IntersectionObserver((entries) => {{ entries.forEach(entry => {{ if (entry.isIntersecting) {{ entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }} }}); }}, {{ threshold: 0.1 }});
            document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el));

            // Populate lifecycle dropdown with car names
            const lifecyclePages = document.querySelectorAll('.lifecycle-page');
            const lifecycleDropdown = document.getElementById('lifecycle-dropdown');
            if (lifecycleDropdown && lifecyclePages.length > 0) {{
                lifecyclePages.forEach(page => {{
                    const pageId = page.id;
                    const titleEl = page.querySelector('.lifecycle-title');
                    if (titleEl) {{
                        const carName = titleEl.textContent.replace('Journey of ', '').replace(' so far', '');
                        const link = document.createElement('a');
                        link.href = '#' + pageId;
                        link.textContent = carName;
                        lifecycleDropdown.appendChild(link);
                    }}
                }});
            }}

            // Dropdown: close only after 200ms delay so mouse can move from button → menu
            document.querySelectorAll('.nav-dropdown').forEach(function(dd) {{
                var closeTimer = null;
                function openMenu()  {{ clearTimeout(closeTimer); dd.querySelector('.nav-dropdown-menu').style.display = 'block'; }}
                function scheduleClose() {{ closeTimer = setTimeout(function() {{ dd.querySelector('.nav-dropdown-menu').style.display = 'none'; }}, 200); }}
                dd.addEventListener('mouseenter', openMenu);
                dd.addEventListener('mouseleave', scheduleClose);
                dd.querySelector('.nav-dropdown-menu').addEventListener('mouseenter', function() {{ clearTimeout(closeTimer); }});
                dd.querySelector('.nav-dropdown-menu').addEventListener('mouseleave', scheduleClose);
            }});
        }});
    </script>
</body></html>"""
    
    return html