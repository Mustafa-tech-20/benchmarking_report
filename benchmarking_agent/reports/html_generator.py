
from typing import Dict, Any, Optional

import json
import re

from benchmarking_agent.reports.image_sections import (
    generate_hero_section,
    generate_image_gallery_section,
    generate_technical_spec_section,
    generate_feature_list_section,
    generate_drivetrain_comparison_section,
    generate_summary_comparison_section,
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



def _generate_consolidated_review_html(comparison_data: Dict[str, Any]) -> str:
    """
    Generate consolidated review summary table from scraped spec data.
    Combines multiple related specs into review categories.
    Includes expandable "Read more" feature for long reviews.
    """

    # Extract car names from comparison data
    car_names = list(comparison_data.keys())

    # Define review categories mapped to actual spec fields we extract
    # Each category maps to a list of related specs to combine
    review_categories = [
        ("Ride & Handling", ["ride", "ride_quality", "bumps", "stiff_on_pot_holes", "shocks"]),
        ("Steering", ["steering", "telescopic_steering", "turning_radius"]),
        ("Braking", ["braking", "brakes", "brake_performance", "grabby", "spongy"]),
        ("Performance & Drivability", ["performance", "driveability", "performance_feel", "acceleration", "torque"]),
        ("4x4 Operation", ["off_road", "manoeuvring"]),
        ("NVH", ["nvh", "powertrain_nvh", "road_nvh", "wind_nvh", "wind_noise", "tire_noise"]),
        ("GSQ", ["gear_shift", "gear_selection", "manual_transmission_performance", "automatic_transmission_performance", "transmission"])
    ]

    def get_combined_review(car_data: Dict, spec_fields: list) -> str:
        """Combine multiple spec values into a single review text."""
        parts = []
        for field in spec_fields:
            value = car_data.get(field, "")
            if value and value not in ["Not Available", "Not found", "N/A", "Error", ""]:
                # Clean and add the value
                clean_value = str(value).strip()
                if clean_value and len(clean_value) > 3:
                    # Add field name as context
                    field_name = field.replace("_", " ").title()
                    parts.append(f"{field_name}: {clean_value}")

        if parts:
            return " | ".join(parts)
        return ""
    
    # Helper function to count words
    def count_words(text: str) -> int:
        return len(str(text).split())
    
    # Helper function to count characters
    def count_chars(text: str) -> int:
        return len(str(text))
    
    WORD_THRESHOLD = 50  
    CHAR_THRESHOLD = 200  
    
    
    num_cars = len(car_names)
    category_width = 20  # 20% for category column
    car_column_width = (100 - category_width) / num_cars

    review_html = f"""
    <div class="review-table-container animate-on-scroll">
        <table class="review-table">
            <thead>
                <tr>
                    <th style="width: {category_width}%;">Category</th>
    """

    # Add column headers for each car with equal widths
    for car_name in car_names:
        review_html += f'<th style="width: {car_column_width}%;">{car_name.upper()}</th>'
    
    review_html += """
                </tr>
            </thead>
            <tbody>
    """
    
    # Add rows for each review category
    for category_name, spec_fields in review_categories:
        review_html += f"""
            <tr>
                <td class="review-category">{category_name}:</td>
        """

        for car_name in car_names:
            car_data = comparison_data.get(car_name) or {}

            # Get combined review from multiple spec fields
            combined_review = get_combined_review(car_data, spec_fields)

            if combined_review:
                display_value = combined_review
                word_count = count_words(display_value)
                char_count = count_chars(display_value)

                review_html += "<td>"

                # Apply expandable content if text is long
                if word_count > WORD_THRESHOLD or char_count > CHAR_THRESHOLD:
                    review_html += f'<div class="expandable-content">{display_value}</div>'
                    review_html += '<button onclick="toggleExpand(this)" class="read-more-btn">Read more</button>'
                else:
                    review_html += display_value

                review_html += "</td>"
            else:
                review_html += '<td style="color: #6c757d; font-style: italic;">Review not available</td>'

        review_html += '</tr>\n'
    
    review_html += """
            </tbody>
        </table>
    </div>
    """

    return review_html


def create_comparison_chart_html(
    comparison_data: Dict[str, Any],
    summary: str,
    summary_data: Optional[Dict[str, Any]] = None
) -> str:
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
        summary: Text summary of the comparison (legacy, kept for compatibility)
        summary_data: Optional dict with 'features_not_in_car1' and 'features_in_car1_only'

    Returns:
        Complete HTML string ready to be saved as a file
    """
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
        .header-actions {{ display: flex; align-items: center; gap: 30px; }}
        .main-nav {{ display: flex; gap: 25px; }}
        .main-nav a {{ text-decoration: none; color: #212529; font-size: 14px; font-weight: 500; transition: color 0.2s ease-in-out; }}
        .main-nav a:hover {{ color: #dd032b; }}
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
        #comparison-section, #analytics-section, #summary-section {{ scroll-margin-top: 90px; }}
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
                        gap: 15px; 
                    }} 
                    
                    .main-nav a {{
                        font-size: 13px;
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
                        gap: 10px;
                        justify-content: center;
                    }}
                    
                    .main-nav a {{
                        font-size: 12px;
                        padding: 4px 8px;
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
                    
                    .main-nav a {{
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
                    
                    .main-nav a {{
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

            /* Checklist Table Styles */
            .checklist-table-container {{
                margin: 20px 0;
                overflow-x: auto;
            }}

            .checklist-table-container h3 {{
                margin-bottom: 15px;
                color: #2c3e50;
                font-size: 1.5em;
            }}

            .checklist-table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                font-size: 14px;
                table-layout: auto;
            }}

            .checklist-table thead {{
                background: white;
                border-bottom: 2px solid #e0e0e0;
            }}

            .checklist-table thead th {{
                padding: 16px 20px;
                text-align: left;
                font-weight: 600;
                color: #333333;
                border-right: none;
            }}

            .checklist-table .category-col {{
                width: 120px;
                min-width: 120px;
            }}

            .checklist-table .feature-col {{
                width: 250px;
                min-width: 250px;
            }}

            .checklist-table .car-col {{
                width: 150px;
                text-align: center;
            }}

            .checklist-table tbody tr {{
                border-bottom: 1px solid #e0e0e0;
            }}

            .checklist-table tbody tr:hover {{
                background-color: #f9f9f9;
            }}

            /* Checklist Accordion Styles */
            .checklist-accordion-container {{
                margin: 20px 0;
            }}

            .checklist-section {{
                margin-bottom: 0;
                border: 1px solid #e0e0e0;
                border-bottom: none;
            }}

            .checklist-section:last-child {{
                border-bottom: 1px solid #e0e0e0;
            }}

            .checklist-category-header {{
                background: linear-gradient(90deg, #3d4357 0%, #c41e3a 100%);
                color: white;
                font-weight: 600;
                padding: 14px 20px;
                font-size: 15px;
                cursor: pointer;
                display: flex;
                justify-content: space-between;
                align-items: center;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}

            .checklist-category-header:hover {{
                opacity: 0.95;
            }}

            .checklist-toggle-icon {{
                font-size: 12px;
                transition: transform 0.3s ease;
            }}

            .checklist-section.collapsed .checklist-toggle-icon {{
                transform: rotate(-90deg);
            }}

            .checklist-section-content {{
                overflow: hidden;
                transition: max-height 0.3s ease;
            }}

            .checklist-section.collapsed .checklist-section-content {{
                display: none;
            }}

            .checklist-section .checklist-table {{
                border: none;
                box-shadow: none;
                margin: 0;
            }}

            .checklist-section .checklist-table thead {{
                background: #f8f9fa;
            }}

            @media print {{
                .checklist-category-header {{
                    background: linear-gradient(90deg, #3d4357 0%, #c41e3a 100%) !important;
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                }}

                .checklist-section.collapsed .checklist-section-content {{
                    display: block !important;
                }}

                .checklist-toggle-icon {{
                    display: none !important;
                }}
            }}

            .checklist-table .category-cell {{
                background: #ececec;
                color: #2c3e50;
                font-weight: 600;
                padding: 14px 20px;
                border-right: 1px solid #d0d0d0;
                width: 150px;
                text-align: left;
                vertical-align: top;
                font-size: 14px;
            }}

            .checklist-table .feature-cell {{
                padding: 14px 20px;
                color: #2c3e50;
                border-right: 1px solid #e0e0e0;
                width: auto;
                background: white;
                font-weight: 500;
                font-size: 14px;
                text-align: center;
            }}

            .checklist-table .value-cell {{
                padding: 14px 20px;
                text-align: center;
                border-right: 1px solid #e0e0e0;
                background: white;
                font-size: 14px;
            }}

            .checklist-table .value-cell:last-child {{
                border-right: none;
            }}

            /* Checklist value styling */
            .check-yes {{
                color: #27ae60;
                font-size: 20px;
                font-weight: bold;
            }}

            .check-no {{
                color: #e74c3c;
                font-size: 18px;
                font-weight: bold;
            }}

            .check-number {{
                color: #2980b9;
                font-weight: 600;
                font-size: 16px;
            }}

            .check-text {{
                color: #34495e;
                font-size: 14px;
            }}

            /* Responsive */
            @media (max-width: 1024px) {{
                .checklist-table {{
                    font-size: 12px;
                }}

                .checklist-table .category-col {{
                    width: 100px;
                    min-width: 100px;
                }}

                .checklist-table .feature-col {{
                    width: 200px;
                    min-width: 200px;
                }}

                .checklist-table .car-col {{
                    width: 120px;
                }}
            }}

            @media print {{
                .checklist-table {{
                    page-break-inside: avoid;
                }}

                .checklist-table .category-header {{
                    page-break-after: avoid;
                }}
            }}
            </style>
</head>
<body>
    <header class="site-header">
        <a href="#"><img src="https://www.mahindra.com//sites/default/files/2025-07/mahindra-red-logo.webp" alt="Logo" class="logo"></a>
        <div class="header-actions">
            <nav class="main-nav">
                <a href="#exterior-section">Exterior</a>
                <a href="#interior-section">Interior</a>
                <a href="#technology-section">Technology</a>
                <a href="#summary-section">Summary</a>
                <a href="#" id="citations-toggle" onclick="toggleCitations(event)">Citations</a>
            </nav>
            <button class="print-btn" onclick="printReport()">Save as PDF</button>
        </div>
    </header>
    {generate_hero_section(comparison_data)}
    {generate_technical_spec_section(comparison_data)}
    {generate_feature_list_section(comparison_data)}
    <div class="container">
        {generate_image_gallery_section("Exterior Highlights", comparison_data, "exterior", "exterior-section")}
        {generate_image_gallery_section("Interior Highlights", comparison_data, "interior", "interior-section")}
        {generate_image_gallery_section("Technology Highlights", comparison_data, "technology", "technology-section")}
        {generate_image_gallery_section("Comfort Highlights", comparison_data, "comfort", "comfort-section")}
        {generate_image_gallery_section("Safety Highlights", comparison_data, "safety", "safety-section")}
        {generate_drivetrain_comparison_section(comparison_data)}
        {generate_summary_comparison_section(summary_data, cars, 20) if summary_data else ''}
        <div class="content" id="citations-section" style="display: none;"><div class="section-header"><div class="icon-wrapper"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><line x1="10" y1="9" x2="8" y2="9"></line></svg></div><h2>Data Source Citations</h2></div><div class="citations-grid">{citations_html}</div></div>
    </div>
    <footer class="footer"><span>Copyright© 2026 Mahindra&Mahindra Ltd. All Rights Reserved.</span></footer>
    <script>
        function toggleAccordion(headerRow) {{
            headerRow.classList.toggle('active');
            let currentRow = headerRow.nextElementSibling;
            while (currentRow && currentRow.classList.contains('spec-row')) {{
                if (document.getElementById('specFilter').value.trim() === '') {{
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
        function toggleCitations(event) {{ event.preventDefault(); const citationsSection = document.getElementById('citations-section'); const mainContent = document.querySelectorAll('.content:not(#citations-section)'); const toggleButton = document.getElementById('citations-toggle'); const navLinks = document.querySelectorAll('.main-nav a:not(#citations-toggle)'); if (citationsSection.style.display === 'none') {{ citationsSection.style.display = 'block'; mainContent.forEach(section => {{ section.style.display = 'none'; }}); navLinks.forEach(link => {{ link.style.display = 'none'; }}); toggleButton.textContent = 'Go Back'; }} else {{ citationsSection.style.display = 'none'; mainContent.forEach(section => {{ section.style.display = 'block'; }}); navLinks.forEach(link => {{ link.style.display = 'block'; }}); toggleButton.textContent = 'Citations'; }} window.scrollTo({{ top: 0, behavior: 'smooth' }}); }}
        document.addEventListener('DOMContentLoaded', () => {{ const observer = new IntersectionObserver((entries) => {{ entries.forEach(entry => {{ if (entry.isIntersecting) {{ entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }} }}); }}, {{ threshold: 0.1 }}); document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el)); }});
    </script>
</body></html>"""
    
    return html