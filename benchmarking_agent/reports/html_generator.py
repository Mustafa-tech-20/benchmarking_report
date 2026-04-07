
from typing import Dict, Any, Optional

import json
import re
import os

from google import genai
from google.genai import types

from benchmarking_agent.config import GEMINI_MAIN_MODEL
from benchmarking_agent.reports.image_sections import (
    generate_hero_section,
    generate_image_gallery_section,
    generate_technical_spec_section,
    generate_feature_list_section,
    generate_drivetrain_comparison_section,
    generate_venn_diagram_section,
    generate_variant_walk_section,
    generate_price_ladder_section,
    generate_vehicle_highlights_section,
    generate_summary_comparison_section,
    get_image_section_styles
)


# ============================================================================
# ADAS COMPARISON SECTION
# ============================================================================

# Initialize Gemini client for Google Search grounding
_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
_GROUNDING_LOCATION = "us-central1"
_adas_gemini_client = genai.Client(vertexai=True, project=_PROJECT_ID, location=_GROUNDING_LOCATION)


def _fetch_single_car_adas(car_name: str) -> tuple:
    """
    Fetch ADAS data for a single car. Returns (car_name, adas_data).
    """
    try:
        print(f"  Fetching ADAS data: {car_name}")
        prompt = f"""Search for the latest and most comprehensive ADAS (Advanced Driver Assistance Systems) features for the {car_name} car in India.

Provide a detailed breakdown of ALL available ADAS features in the following categories:

1. **Collision Prevention**
   - Autonomous Emergency Braking (AEB)
   - Forward Collision Warning (FCW)
   - Rear Cross Traffic Alert
   - Pre-collision assist

2. **Lane Management**
   - Lane Departure Warning (LDW)
   - Lane Keep Assist (LKA)
   - Lane Centering
   - Blind Spot Detection/Monitoring

3. **Cruise & Speed Control**
   - Adaptive Cruise Control (ACC)
   - Traffic Jam Assist
   - Intelligent Speed Limiter
   - Stop & Go functionality

4. **Parking Assistance**
   - 360-degree Camera
   - Front/Rear Parking Sensors
   - Automatic Parking Assist
   - Rear View Camera with guidelines

5. **Driver Monitoring**
   - Driver Attention Warning
   - Drowsiness Detection
   - Driver fatigue alert

6. **Visibility & Lighting**
   - Auto High Beam
   - Adaptive Headlights
   - Night Vision
   - Rain sensing wipers

7. **Other Safety Tech**
   - Traction Control
   - Electronic Stability Control (ESC)
   - Hill Start Assist
   - Hill Descent Control

Return as JSON with this structure:
{{
    "car_name": "{car_name}",
    "adas_level": "Level 1/2 (describe capability)",
    "categories": {{
        "Collision Prevention": [
            {{"feature": "Feature Name", "available": true/false, "details": "brief description"}}
        ],
        "Lane Management": [...],
        "Cruise & Speed Control": [...],
        "Parking Assistance": [...],
        "Driver Monitoring": [...],
        "Visibility & Lighting": [...],
        "Other Safety Tech": [...]
    }},
    "highlights": ["Key ADAS highlight 1", "Key ADAS highlight 2", "Key ADAS highlight 3"],
    "source_urls": ["url1", "url2"]
}}

Return ONLY valid JSON, no markdown or explanation."""

        response = _adas_gemini_client.models.generate_content(
            model=GEMINI_MAIN_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_modalities=["TEXT"],
                temperature=0.1,
                max_output_tokens=4096,
            ),
        )

        if response and response.text:
            import json_repair
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            text = text.strip()
            if "{" in text and "}" in text:
                text = text[text.index("{"):text.rindex("}") + 1]
            data = json_repair.loads(text)
            num_features = sum(len(cat) for cat in data.get("categories", {}).values())
            print(f"  ✓ {car_name}: {num_features} ADAS features, {data.get('adas_level', 'N/A')}")
            return (car_name, data)
    except Exception as e:
        print(f"  ✗ {car_name}: ADAS fetch error - {e}")
        return (car_name, {"error": str(e), "car_name": car_name})

    return (car_name, {"error": "No response", "car_name": car_name})


def fetch_adas_comparison_data(car_names: list) -> Dict[str, Any]:
    """
    Fetch comprehensive ADAS features for all cars using Gemini with Google Search.
    Uses parallel fetching for all cars simultaneously.
    Returns a dict with car names as keys and ADAS data as values.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    adas_data = {}

    if not car_names:
        return adas_data

    print(f"\n============================================================")
    print(f"ADAS: Parallel fetch for {len(car_names)} cars")
    print(f"============================================================")
    for car in car_names:
        print(f"  Queuing: {car}")

    print(f"\n  Launching {len(car_names)} parallel Gemini calls...\n")

    # Fetch all cars in parallel
    with ThreadPoolExecutor(max_workers=len(car_names)) as executor:
        futures = {executor.submit(_fetch_single_car_adas, car): car for car in car_names}

        for future in as_completed(futures):
            try:
                car_name, data = future.result(timeout=120)
                adas_data[car_name] = data
            except Exception as e:
                car_name = futures[future]
                print(f"  ✗ {car_name}: ADAS timeout/error - {e}")
                adas_data[car_name] = {"error": str(e), "car_name": car_name}

    print(f"\n  ADAS complete: {len(adas_data)}/{len(car_names)} cars")

    return adas_data


def generate_adas_comparison_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate ADAS comparison section with side-by-side feature comparison.
    """
    car_names = [n for n, d in comparison_data.items() if isinstance(d, dict) and "error" not in d]
    if not car_names:
        return ""

    # Fetch ADAS data for all cars
    adas_data = fetch_adas_comparison_data(car_names)

    num_cars = len(car_names)
    card_width = 100 // num_cars if num_cars > 0 else 100

    # Define category icons
    category_icons = {
        "Collision Prevention": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
        "Lane Management": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19h16M4 15h16M4 11h16M4 7h16"/></svg>',
        "Cruise & Speed Control": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
        "Parking Assistance": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 17V7h4a3 3 0 0 1 0 6H9"/></svg>',
        "Driver Monitoring": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
        "Visibility & Lighting": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
        "Other Safety Tech": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    }

    # Generate car cards HTML
    car_cards_html = ""
    for car_name in car_names:
        car_adas = adas_data.get(car_name, {})
        adas_level = car_adas.get("adas_level", "N/A")
        highlights = car_adas.get("highlights", [])
        categories = car_adas.get("categories", {})

        highlights_html = "".join([f'<li>{h}</li>' for h in highlights[:3]]) if highlights else "<li>No highlights available</li>"

        # Generate categories HTML
        categories_html = ""
        for cat_name, cat_icon in category_icons.items():
            features = categories.get(cat_name, [])
            features_html = ""
            for feat in features:
                if isinstance(feat, dict):
                    available = feat.get("available", False)
                    feature_name = feat.get("feature", "Unknown")
                    details = feat.get("details", "")
                    icon_class = "adas-available" if available else "adas-unavailable"
                    icon = "✓" if available else "✗"
                    features_html += f'''
                        <div class="adas-feature-item {icon_class}">
                            <span class="adas-feature-icon">{icon}</span>
                            <span class="adas-feature-name">{feature_name}</span>
                            {f'<span class="adas-feature-details">{details}</span>' if details else ''}
                        </div>
                    '''

            if features_html:
                categories_html += f'''
                    <div class="adas-category">
                        <div class="adas-category-header">
                            <span class="adas-category-icon">{cat_icon}</span>
                            <span class="adas-category-name">{cat_name}</span>
                        </div>
                        <div class="adas-features-list">
                            {features_html}
                        </div>
                    </div>
                '''

        car_cards_html += f'''
            <div class="adas-car-card">
                <div class="adas-car-header">
                    <h3 class="adas-car-name">{car_name}</h3>
                    <span class="adas-level-badge">{adas_level}</span>
                </div>
                <div class="adas-highlights">
                    <h4>Key Highlights</h4>
                    <ul>{highlights_html}</ul>
                </div>
                <div class="adas-categories-container">
                    {categories_html}
                </div>
            </div>
        '''

    html = f'''
    <style>
        .adas-comparison-section {{
            padding: 0;
            background: #f8f9fa;
            width: 100%;
        }}
        .adas-cards-container {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            width: 100%;
            max-width: 100%;
        }}
        /* For 3 cars, use 3 columns */
        .adas-cards-container.three-cars {{
            grid-template-columns: repeat(3, 1fr);
        }}
        .adas-car-card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            width: 100%;
            min-width: 0;
            flex: 1;
        }}
        .adas-car-header {{
            background: linear-gradient(135deg, #1c2a39 0%, #2c3e50 100%);
            color: white;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 10px;
        }}
        .adas-car-name {{
            margin: 0;
            font-size: 18px;
            font-weight: 700;
            flex-shrink: 0;
        }}
        .adas-level-badge {{
            background: #cc0000;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            line-height: 1.4;
            text-align: right;
        }}
        .adas-highlights {{
            padding: 15px 20px;
            background: #fff8f0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .adas-highlights h4 {{
            margin: 0 0 10px 0;
            font-size: 13px;
            color: #cc0000;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .adas-highlights ul {{
            margin: 0;
            padding-left: 18px;
            font-size: 13px;
            color: #333;
        }}
        .adas-highlights li {{
            margin-bottom: 5px;
        }}
        .adas-categories-container {{
            padding: 15px;
            max-height: 500px;
            overflow-y: auto;
        }}
        .adas-category {{
            margin-bottom: 15px;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            overflow: hidden;
        }}
        .adas-category-header {{
            background: #f1f3f5;
            padding: 10px 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
            font-size: 13px;
            color: #1c2a39;
        }}
        .adas-category-icon {{
            width: 18px;
            height: 18px;
        }}
        .adas-category-icon svg {{
            width: 100%;
            height: 100%;
        }}
        .adas-features-list {{
            padding: 10px 15px;
        }}
        .adas-feature-item {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            padding: 6px 0;
            border-bottom: 1px solid #f0f0f0;
            font-size: 12px;
        }}
        .adas-feature-item:last-child {{
            border-bottom: none;
        }}
        .adas-feature-icon {{
            font-weight: 700;
            font-size: 14px;
            min-width: 18px;
        }}
        .adas-available .adas-feature-icon {{
            color: #27ae60;
        }}
        .adas-unavailable .adas-feature-icon {{
            color: #e74c3c;
        }}
        .adas-unavailable {{
            opacity: 0.6;
        }}
        .adas-feature-name {{
            font-weight: 500;
            color: #333;
        }}
        .adas-feature-details {{
            display: block;
            font-size: 11px;
            color: #666;
            margin-top: 2px;
        }}
        @media (max-width: 1024px) {{
            .adas-cards-container {{
                grid-template-columns: 1fr !important;
            }}
            .adas-cards-container.three-cars {{
                grid-template-columns: 1fr !important;
            }}
        }}
    </style>
    <div class="adas-comparison-section">
        <div class="adas-cards-container{' three-cars' if num_cars >= 3 else ''}">
            {car_cards_html}
        </div>
    </div>
    '''

    return html


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
        
        # Get all citation fields - matching tech_spec_groups from image_sections.py
        citation_fields = [
            # ===== Powertrain =====
            ("engine", "Engine"),
            ("engine_displacement", "Engine CC"),
            ("max_power_kw", "Max Power (kW)"),
            ("torque", "Max Torque (Nm)"),
            # ===== Fuel =====
            ("fuel_type", "Fuel Type"),
            ("fuel_tank_capacity", "Tank Capacity"),
            # ===== Transmission =====
            ("transmission", "Transmission"),
            # ===== Drive =====
            ("drive", "Drive"),
            ("drive_mode", "Drive Mode"),
            # ===== Top Speed =====
            ("top_speed", "Top Speed (km/h)"),
            # ===== Dimension =====
            ("length", "Length (mm)"),
            ("width", "Width (mm)"),
            ("height", "Height (mm)"),
            ("wheelbase", "Wheelbase (mm)"),
            ("wheel_track", "WheelTrack F/R"),
            ("ground_clearance", "Ground clearance"),
            ("kerb_weight", "Kerb weight (kg)"),
            # ===== Steering =====
            ("steering", "Steering Type"),
            # ===== Seat =====
            ("seating_capacity", "Seating Capacity"),
            # ===== Brakes =====
            ("front_brakes", "Front Brakes"),
            ("rear_brakes", "Rear Brakes"),
            # ===== Suspension =====
            ("front_suspension", "Front Suspension"),
            ("rear_suspension", "Rear Suspension"),
            # ===== Wheel & Tyre =====
            ("front_tyre_size", "Front - Tyre size"),
            ("rear_tyre_size", "Rear - Tyre size"),
            ("spare_tyres", "Spare Tyres"),
            # ===== Boot =====
            ("boot_space", "Boot Space (L)"),
            # ===== Exterior =====
            ("full_led", "Full LED"),
            ("wheel_arch_claddings", "Wheel arch Ext. Claddings"),
            ("front_bumper_grille", "Front Bumper & Grille"),
            ("antenna_type", "Antenna Type"),
            ("foot_step", "Foot step"),
            # ===== Interior =====
            ("console_switches", "Console Switches"),
            ("upholstery", "Upholstery"),
            ("ip_dashboard", "IP/ Dashboard"),
            ("glove_box", "Glove Box"),
            # ===== Sunvisor =====
            ("sunvisor_driver", "Sunvisor Driver"),
            ("sunvisor_co_driver", "Sunvisor Co Driver"),
            # ===== Grab Handle =====
            ("grab_handle_driver", "Grab Handle Driver"),
            ("grab_handle_co_driver", "Grab Handle Co Driver"),
            ("grab_handle_2nd_row", "Grab Handle 2nd Row"),
            # ===== Sun Roof =====
            ("panoramic_sunroof", "Panoramic Sun Roof"),
            ("roller_blind_sunblind", "Roller Blind/ Sunblind"),
            # ===== Luggage rack =====
            ("luggage_rack", "Luggage rack"),
            # ===== Wipers & Demister =====
            ("front_wiper", "Front Wiper"),
            ("defogging", "Defogging"),
            ("rain_sensing_wipers", "Rain Sensing Wipers"),
            ("rear_wiper", "Rear Wiper"),
            # ===== Door =====
            ("door_front", "Door Front"),
            ("door_rear", "Door Rear"),
            # ===== Tailgate =====
            ("tailgate_type", "Tailgate Type"),
            ("power_tailgate", "Power operated tail gate"),
            # ===== ORVM =====
            ("orvm", "ORVM"),
            # ===== Steering Wheel =====
            ("steering_wheel", "Steering Wheel"),
            # ===== Bonnet =====
            ("bonnet_gas_strut", "Bonnet Gas Strut"),
            # ===== Door Trim =====
            ("bottle_holder", "Bottle Holder"),
            ("door_arm_rest", "Door arm Rest"),
            # ===== Boot/Trunk =====
            ("boot_organizer", "Boot Organizer"),
            ("boot_lamp", "Boot Lamp"),
            # ===== Power Window =====
            ("power_window_all_doors", "Power Window All Doors"),
            ("power_window_driver_door", "Power Window Driver Door"),
            ("window_one_key_lift", "Window one key lift"),
            ("window_anti_clamping", "Window anti-clamping"),
            ("multilayer_silencing_glass", "Multilayer silencing glass"),
            ("front_windshield_mute_glass", "Front windshield mute glass"),
            # ===== Steering Column =====
            ("steering_column", "Steering Column"),
            ("steering_column_lock", "Steering Column Lock"),
            # ===== Floor Console =====
            ("floor_console_armrest", "Floor Console Arm Rest"),
            ("cup_holders", "Cup Holders"),
            # ===== Wireless charging =====
            ("wireless_charging", "Wireless charging"),
            ("no_of_wireless_charging", "No of wireless charging"),
            # ===== Door Inner Scuff =====
            ("door_inner_scuff_front", "Door Inner Scuff Front"),
            ("door_inner_scuff_rear", "Door Inner Scuff Rear"),
            # ===== Voice Recognition =====
            ("voice_recognition_steering", "Voice Recognition Steering"),
            # ===== Seats =====
            ("seats", "Seats"),
            ("ventilated_seats", "Seat Ventilation"),
            ("seat_ventilation_front_passenger", "Seat Ventilation Front Passenger"),
            # ===== Safety =====
            ("airbags", "Airbags"),
            ("pab_deactivation_switch", "PAB deactivation switch"),
            ("driver_seat_belt", "Driver Seat Belt"),
            ("front_passenger_seat_belt", "Front Passenger Seat Belt"),
            ("seat_belt_2nd_row", "2nd Row Seat Belt"),
            ("child_anchor", "Child Anchor"),
            ("child_lock", "Child Lock"),
            ("seat_belt_reminder", "Seat Belt Reminder"),
            ("seat_belt_holder_2nd_row", "Seat Belt Holder 2nd Row"),
            ("crash_sensors", "Crash Sensors"),
            # ===== Technology =====
            ("infotainment_screen", "Infotainment"),
            ("smartphone_connectivity", "Smart Phone Connectivity"),
            ("bluetooth", "Bluetooth"),
            # ===== Radio =====
            ("am_fm_radio", "AM / FM Radio"),
            ("digital_radio", "Digital Radio"),
            # ===== ConnectedDrive =====
            ("connected_drive_wireless", "ConnectedDrive Wireless"),
            # ===== Branded Audio =====
            ("immersive_sound_3d", "3D Immersive Sound"),
            ("no_of_speakers", "No of speakers"),
            ("audio_brand", "Audio Brand"),
            ("dolby_atmos", "Dolby Atmos"),
            ("audio_adjustable", "Audio Adjustable"),
            # ===== Lighting =====
            ("headlamp", "Headlamp"),
            ("high_beam", "High beam"),
            ("low_beam", "Low beam"),
            ("auto_high_beam", "Auto High Beam"),
            ("headlamp_leveling", "Headlamp Leveling"),
            ("projector_led", "Projector LED"),
            ("front_fog_lamp", "Front Fog Lamp"),
            ("tail_lamp", "Tail Lamp"),
            ("welcome_lighting", "Welcome Lighting"),
            ("ambient_lighting", "Ambient Lighting"),
            ("cabin_lamps", "Cabin Lamps"),
            ("high_mounted_stop_lamp", "High Mounted Stop Lamp"),
            ("hazard_lamp", "Hazard Lamp"),
            # ===== Locking =====
            ("central_locking", "Central Locking"),
            ("door_lock", "Door Lock"),
            ("speed_sensing_door_lock", "Speed Sensing Door Lock"),
            ("panic_alarm", "Panic Alarm"),
            ("remote_lock_unlock", "Remote Lock/Unlock"),
            ("digital_key_plus", "Digital Key Plus"),
            # ===== Horn =====
            ("horn", "Electronic Horn"),
            # ===== Over speeding Bell =====
            ("over_speeding_bell", "Over speeding Bell"),
            # ===== ADAS =====
            ("active_cruise_control", "Active Cruise Control"),
            ("lane_departure_warning", "Lane Departure Warning"),
            ("automatic_emergency_braking", "Automatic Emergency Braking"),
            ("lane_keep_assist", "Lane Keep Assist"),
            ("blind_spot_detection", "Blind Spot Detection"),
            ("blind_spot_collision_warning", "Blind Spot Collision warning"),
            ("forward_collision_warning", "Forward Collision warning"),
            ("rear_collision_warning", "Rear Collision Warning"),
            ("door_open_alert", "Door Open Alert"),
            ("high_beam_assist", "High beam Assist"),
            ("traffic_sign_recognition", "Traffic Sign Recognition"),
            ("rear_cross_traffic_alert", "Rear Cross Traffic Alert"),
            ("traffic_jam_alert", "Traffic jam alert"),
            ("safe_exit_braking", "Safe Exit Braking"),
            ("surround_view_monitor", "Surround View Monitor"),
            ("smart_pilot_assist", "Smart Pilot Assist"),
            # ===== Climate =====
            ("auto_defogging", "Auto Defogging"),
            ("no_of_zone_climate", "Climate Zone"),
            ("rear_vent_ac", "Rear Vent AC"),
            ("active_carbon_filter", "Active Carbon filter"),
            ("temp_diff_control", "Temp diff control"),
            ("bottle_opener", "Bottle Opener"),
            # ===== Capabilities =====
            ("terrain_modes", "Terrain Modes"),
            ("crawl_smart", "Crawl Smart"),
            ("intelli_turn", "Intelli Turn"),
            ("off_road_info_display", "Off-road info display"),
            ("central_differential", "Central Differential"),
            ("limited_slip_differential", "Limited Slip Differential"),
            ("wading_sensing_system", "Wading sensing system"),
            ("electronic_gear_shift", "Electronic gear shift"),
            ("electric_driveline_disconnect", "Electric Driveline disconnect"),
            ("tpms", "TPMS"),
            ("hhc_uphill_start_assist", "HHC Uphill Start Assist"),
            ("engine_electronic_security", "Engine electronic security"),
            # ===== Power outlet / Charging Points =====
            ("usb_type_c_front_row", "USB Type C Front Row"),
            ("usb_type_c_front_row_count", "USB Type C Front Count"),
            ("usb_type_c_rear_row", "USB Type C Rear Row"),
            ("socket_12v", "12V Socket"),
            # ===== Brakes Detailed =====
            ("auto_hold", "Auto Hold"),
            ("rollover_mitigation", "Rollover Mitigation"),
            ("rmi_anti_rollover", "RMI Anti-rollover"),
            ("vdc_vehicle_dynamic", "VDC"),
            ("csc_corner_stability", "CSC"),
            ("epb", "EPB"),
            ("avh_auto_vehicle_hold", "AVH"),
            ("hac_hill_ascend", "HAC-HHC"),
            ("hba_hydraulic_brake", "HBA"),
            ("dbc_downhill_brake", "DBC"),
            ("ebp_electronic_brake_prefill", "EBP"),
            ("bdw_brake_disc_wiping", "BDW"),
            ("edtc_engine_drag_torque", "EDTC"),
            ("tcs_traction_control", "TCS"),
            ("ebd_electronic_brake", "EBD"),
            ("abs_antilock", "ABS"),
            ("dst_dynamic_steering", "DST"),
            ("eba_brake_assist", "EBA"),
            ("cbc_cornering_brake", "CBC"),
            ("hdc_hill_descent", "HDC"),
            # ===== Others =====
            ("active_noise_reduction", "Active noise reduction"),
            ("intelligent_voice_control", "Intelligent voice control"),
            ("transparent_car_bottom", "Transparent car bottom"),
            ("intellectual_dodge", "Intellectual dodge"),
            ("car_picnic_table", "Car picnic table"),
            ("trunk_subwoofer", "Trunk subwoofer"),
            ("dashcam_provision", "Dashcam Provision"),
            ("cup_holder_tail_door", "Cup Holder Tail door"),
            ("hooks_tail_door", "Hooks Tail door"),
            ("warning_triangle_tail_door", "Warning Triangle"),
            ("door_magnetic_strap", "Door magnetic Strap"),
            # ===== Market =====
            ("price_range", "Price Range"),
            ("monthly_sales", "Monthly Sales"),
            ("user_rating", "User Rating"),
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


def _strip_html_tags(text: str) -> str:
    """Remove all HTML tags from text."""
    if not text:
        return text
    text = re.sub(r':\s*\w+\s*>', '', text)
    text = re.sub(r'<\s*/?\s*\w+\s*/?>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\w+\s*>', '', text)
    return text.strip()


def _generate_consolidated_review_html(comparison_data: Dict[str, Any]) -> str:
    """
    Generate Functional Image Review table with 0-10 ratings and spider chart.
    Based on FI (Functional Image) attribute categories.
    """
    import random

    car_names = [n for n, d in comparison_data.items() if isinstance(d, dict) and "error" not in d]
    if not car_names:
        return ""

    # FI (Functional Image) attribute categories from the reference images
    fi_categories = {
        "Comfort": [
            ("Ride", ["ride", "ride_quality", "bumps", "stiff_on_pot_holes", "shocks"]),
            ("Climate Control", ["climate_control", "ac_performance", "hvac"]),
            ("Seats", ["seats", "seat_cushion", "seat_comfort", "seat_material"]),
        ],
        "Dynamics": [
            ("Customer Handling", ["stability", "straight_ahead_stability", "corner_stability", "handling"]),
            ("Steering", ["steering", "telescopic_steering", "turning_radius", "sensitivity"]),
        ],
        "Performance": [
            ("Performance Feel", ["performance_feel", "performance", "acceleration", "response"]),
            ("Driveability", ["driveability", "city_performance", "highway_performance"]),
            ("Manual Transmission Operation", ["manual_transmission_performance", "gear_shift"]),
            ("Clutch Operation", ["clutch", "pedal_operation", "clutch_feel"]),
            ("Automatic Transmission Operation", ["automatic_transmission_performance", "gear_selection"]),
        ],
        "Safety": [
            ("Braking", ["braking", "brakes", "brake_performance", "abs"]),
            ("Restraints", ["seats_restraint", "seatbelt_features", "airbags"]),
        ],
        "Space & Versatility": [
            ("Visibility", ["visibility", "irvm", "orvm"]),
            ("Package", ["boot_space", "wheelbase", "dimensions"]),
            ("Usability", ["usability", "ingress", "egress", "convenience"]),
            ("Functional Hardware", ["door_effort", "window", "wiper_control", "keyless_entry"]),
        ],
        "NVH": [
            ("PT-NVH", ["powertrain_nvh", "engine_noise", "turbo_noise"]),
            ("Road NVH", ["road_nvh", "tire_noise", "road_noise"]),
            ("Wind NVH", ["wind_nvh", "wind_noise"]),
            ("Electro Mech NVH", ["blower_noise", "rattle", "squeak"]),
        ],
        "All Terrain Capability": [
            ("4X4 Operation", ["off_road", "crawl", "ground_clearance", "hill_descent_control", "traction_control"]),
        ],
        "Features": [
            ("Infotainment System", ["infotainment_screen", "resolution", "touch_response", "audio_system"]),
            ("Night Operation", ["led", "drl", "auto_headlamps", "ambient_lighting"]),
        ],
    }

    def get_combined_review(car_data: Dict, spec_fields: list) -> str:
        parts = []
        for field in spec_fields:
            value = car_data.get(field, "")
            if value and value not in ["Not Available", "Not found", "N/A", "Error", ""]:
                clean_value = _strip_html_tags(str(value).strip())
                if clean_value and len(clean_value) > 3:
                    field_name = field.replace("_", " ").title()
                    parts.append(f"<strong>{field_name}:</strong> {clean_value}")
        return " | ".join(parts) if parts else ""

    # Collect all comments first, then batch call LLM for ratings
    all_comments_for_rating = {}  # {(car_name, attr_name): comment_text}
    for category, attributes in fi_categories.items():
        for attr_name, spec_fields in attributes:
            for car_name in car_names:
                car_data = comparison_data.get(car_name) or {}
                comment = get_combined_review(car_data, spec_fields)
                if comment:
                    all_comments_for_rating[(car_name, attr_name)] = comment

    # LLM call to get all ratings at once
    llm_ratings = {}  # {(car_name, attr_name): rating}
    if all_comments_for_rating:
        try:
            from vertexai.generative_models import GenerativeModel
            from benchmarking_agent.config import GEMINI_MAIN_MODEL

            # Build prompt with all comments
            rating_prompt_parts = []
            for (car_name, attr_name), comment in all_comments_for_rating.items():
                # Truncate very long comments
                truncated = comment[:500] + "..." if len(comment) > 500 else comment
                rating_prompt_parts.append(f'"{car_name}|{attr_name}": "{truncated}"')

            # List all qualitative FI attributes explicitly
            fi_attributes_list = """
QUALITATIVE ATTRIBUTES (Functional Image Review):
- Comfort: Ride, Climate Control, Seats
- Dynamics: Customer Handling, Steering
- Performance: Performance Feel, Driveability, Manual Transmission Operation, Clutch Operation, Automatic Transmission Operation
- Safety: Braking, Restraints
- Space & Versatility: Visibility, Package, Usability, Functional Hardware
- NVH: PT-NVH, Road NVH, Wind NVH, Electro Mech NVH
- All Terrain Capability: 4X4 Operation
- Features: Infotainment System, Night Operation"""

            prompt = f"""You are rating QUALITATIVE vehicle attributes for a Functional Image Review report.

{fi_attributes_list}

TASK: Based on the user comments below, provide a subjective rating (0.0-10.0) for each car's attribute.

Rating scale:
- 8-10: Excellent/Outstanding (very positive comments, praised features)
- 6-7.9: Good (mostly positive, minor issues)
- 5-5.9: Average/Neutral (mixed or basic/factual comments only)
- 3-4.9: Below Average (notable issues, complaints mentioned)
- 0-2.9: Poor (significant problems, negative feedback)

USER COMMENTS TO RATE:
{chr(10).join(rating_prompt_parts)}

Return ONLY a JSON object with ratings:
{{
{chr(10).join([f'  "{car}|{attr}": 0.0' for (car, attr) in all_comments_for_rating.keys()])}
}}"""

            model = GenerativeModel(GEMINI_MAIN_MODEL)
            response = model.generate_content(prompt)
            if response and response.text:
                import json_repair
                text = response.text.strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                text = text.strip()
                if "{" in text and "}" in text:
                    text = text[text.index("{"):text.rindex("}") + 1]
                ratings_data = json_repair.loads(text)
                for key, rating in ratings_data.items():
                    if "|" in key:
                        car, attr = key.split("|", 1)
                        if isinstance(rating, (int, float)):
                            llm_ratings[(car, attr)] = min(10.0, max(0.0, float(rating)))
        except Exception as e:
            print(f"LLM rating extraction failed: {e}")

    def extract_rating(car_name: str, attr_name: str, car_data: Dict, spec_fields: list) -> float:
        """Get subjective rating from LLM interpretation of comments."""
        # Check for LLM-provided rating
        if (car_name, attr_name) in llm_ratings:
            return llm_ratings[(car_name, attr_name)]

        # Check if any field has data
        has_data = False
        for field in spec_fields:
            value = car_data.get(field, "")
            if value and value not in ["Not Available", "Not found", "N/A", "Error", ""]:
                has_data = True
                break

        if not has_data:
            return 0  # No data

        return 5.5  # Default neutral if LLM failed

    # Collect ratings for spider chart
    all_ratings = {car: {} for car in car_names}
    all_attributes = []

    for category, attributes in fi_categories.items():
        for attr_name, spec_fields in attributes:
            all_attributes.append(attr_name)
            for car_name in car_names:
                car_data = comparison_data.get(car_name) or {}
                rating = extract_rating(car_name, attr_name, car_data, spec_fields)
                all_ratings[car_name][attr_name] = rating

    # Generate ONE mega spider chart with ALL attributes
    num_cars = len(car_names)
    car_colors = ['rgba(204, 0, 0, 0.8)', 'rgba(0, 102, 204, 0.8)', 'rgba(0, 153, 76, 0.8)', 'rgba(153, 51, 255, 0.8)']
    car_bg_colors = ['rgba(204, 0, 0, 0.15)', 'rgba(0, 102, 204, 0.15)', 'rgba(0, 153, 76, 0.15)', 'rgba(153, 51, 255, 0.15)']

    chart_id = f"fiMegaChart_{random.randint(1000, 9999)}"
    labels_js = json.dumps(all_attributes)

    # Build datasets for mega radar chart
    datasets_js = []
    for i, car_name in enumerate(car_names):
        data_values = [all_ratings[car_name].get(attr, 0) for attr in all_attributes]
        datasets_js.append(f"""{{
            label: '{car_name}',
            data: {data_values},
            borderColor: '{car_colors[i % len(car_colors)]}',
            backgroundColor: '{car_bg_colors[i % len(car_bg_colors)]}',
            borderWidth: 2,
            pointRadius: 4,
            pointBackgroundColor: '{car_colors[i % len(car_colors)]}'
        }}""")

    # Build category to attributes mapping for filter UI
    category_attrs = {json.dumps({cat: [attr[0] for attr in attrs] for cat, attrs in fi_categories.items()})}

    # Build vehicle checkboxes
    vehicle_checkboxes = "".join([f'<label class="fi-filter-checkbox"><input type="checkbox" value="{car}" checked onchange="updateFiChart_{chart_id}()">{car}</label>' for car in car_names])

    # Build attribute checkboxes grouped by category
    attr_checkboxes = ""
    for cat, attrs in fi_categories.items():
        attr_checkboxes += f'<div class="fi-filter-category"><div class="fi-filter-category-title">{cat}</div><div class="fi-filter-category-attrs">'
        for attr_name, _ in attrs:
            attr_checkboxes += f'<label class="fi-filter-checkbox"><input type="checkbox" value="{attr_name}" checked onchange="updateFiChart_{chart_id}()">{attr_name}</label>'
        attr_checkboxes += '</div></div>'

    spider_html = f"""
    <style>
        .fi-mega-spider-container {{
            background: #ffffff;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            border: 1px solid #e9ecef;
            margin-bottom: 35px;
        }}
        .fi-mega-spider-title {{
            text-align: center;
            font-size: 18px;
            font-weight: 700;
            color: #1c2a39;
            margin-bottom: 20px;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 3px solid #cc0000;
            padding-bottom: 12px;
        }}
        .fi-mega-chart-wrapper {{
            max-width: 800px;
            margin: 0 auto;
            height: 600px;
        }}
        .fi-filter-controls {{
            display: flex;
            gap: 30px;
            margin-bottom: 25px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
        }}
        .fi-filter-section {{
            flex: 1;
        }}
        .fi-filter-section-title {{
            font-weight: 700;
            font-size: 14px;
            color: #1c2a39;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #cc0000;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .fi-filter-section-title button {{
            font-size: 11px;
            padding: 4px 10px;
            background: #1c2a39;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}
        .fi-filter-section-title button:hover {{
            background: #cc0000;
        }}
        .fi-filter-vehicles {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .fi-filter-checkbox {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            color: #333;
            cursor: pointer;
            padding: 5px 10px;
            background: white;
            border-radius: 5px;
            border: 1px solid #ddd;
            transition: all 0.2s;
        }}
        .fi-filter-checkbox:hover {{
            border-color: #cc0000;
        }}
        .fi-filter-checkbox input {{
            accent-color: #cc0000;
        }}
        .fi-filter-attrs-container {{
            max-height: 200px;
            overflow-y: auto;
            padding-right: 10px;
        }}
        .fi-filter-category {{
            margin-bottom: 12px;
        }}
        .fi-filter-category-title {{
            font-weight: 600;
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .fi-filter-category-attrs {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
    </style>
    <div class="fi-mega-spider-container">
        <div class="fi-mega-spider-title">Functional Image Spider Map</div>
        <div class="fi-filter-controls">
            <div class="fi-filter-section">
                <div class="fi-filter-section-title">
                    Filter by Vehicle
                    <span>
                        <button onclick="toggleAllVehicles_{chart_id}(true)">All</button>
                        <button onclick="toggleAllVehicles_{chart_id}(false)">None</button>
                    </span>
                </div>
                <div class="fi-filter-vehicles" id="fi-vehicle-filters-{chart_id}">
                    {vehicle_checkboxes}
                </div>
            </div>
            <div class="fi-filter-section">
                <div class="fi-filter-section-title">
                    Filter by Attribute
                    <span>
                        <button onclick="toggleAllAttrs_{chart_id}(true)">All</button>
                        <button onclick="toggleAllAttrs_{chart_id}(false)">None</button>
                    </span>
                </div>
                <div class="fi-filter-attrs-container" id="fi-attr-filters-{chart_id}">
                    {attr_checkboxes}
                </div>
            </div>
        </div>
        <div class="fi-mega-chart-wrapper">
            <canvas id="{chart_id}"></canvas>
        </div>
        <script>
        (function() {{
            // Store original data for filtering
            const originalLabels_{chart_id} = {labels_js};
            const originalDatasets_{chart_id} = [{', '.join(datasets_js)}];
            let fiChart_{chart_id} = null;

            const ctx = document.getElementById('{chart_id}');
            if (ctx) {{
                fiChart_{chart_id} = new Chart(ctx, {{
                    type: 'radar',
                    data: {{
                        labels: originalLabels_{chart_id},
                        datasets: originalDatasets_{chart_id}.map(d => ({{...d}}))
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            r: {{
                                beginAtZero: true,
                                max: 10,
                                ticks: {{
                                    stepSize: 2,
                                    font: {{ size: 9 }},
                                    backdropColor: 'transparent'
                                }},
                                pointLabels: {{
                                    font: {{ size: 10, weight: '600' }},
                                    color: '#333'
                                }},
                                grid: {{
                                    color: 'rgba(0,0,0,0.1)'
                                }},
                                angleLines: {{
                                    color: 'rgba(0,0,0,0.1)'
                                }}
                            }}
                        }},
                        plugins: {{
                            legend: {{
                                position: 'top',
                                labels: {{
                                    font: {{ size: 12, weight: '600' }},
                                    padding: 20,
                                    usePointStyle: true,
                                    pointStyle: 'rect'
                                }}
                            }}
                        }}
                    }}
                }});
            }}

            // Make update function globally accessible
            window.updateFiChart_{chart_id} = function() {{
                if (!fiChart_{chart_id}) return;

                // Get selected vehicles
                const vehicleContainer = document.getElementById('fi-vehicle-filters-{chart_id}');
                const selectedVehicles = Array.from(vehicleContainer.querySelectorAll('input:checked')).map(cb => cb.value);

                // Get selected attributes
                const attrContainer = document.getElementById('fi-attr-filters-{chart_id}');
                const selectedAttrs = Array.from(attrContainer.querySelectorAll('input:checked')).map(cb => cb.value);

                // Filter labels (attributes)
                const filteredIndices = [];
                const filteredLabels = [];
                originalLabels_{chart_id}.forEach((label, idx) => {{
                    if (selectedAttrs.includes(label)) {{
                        filteredIndices.push(idx);
                        filteredLabels.push(label);
                    }}
                }});

                // Filter datasets (vehicles) and their data
                const filteredDatasets = originalDatasets_{chart_id}
                    .filter(ds => selectedVehicles.includes(ds.label))
                    .map(ds => ({{
                        ...ds,
                        data: filteredIndices.map(idx => ds.data[idx])
                    }}));

                // Update chart
                fiChart_{chart_id}.data.labels = filteredLabels;
                fiChart_{chart_id}.data.datasets = filteredDatasets;
                fiChart_{chart_id}.update();
            }};

            window.toggleAllVehicles_{chart_id} = function(checked) {{
                const container = document.getElementById('fi-vehicle-filters-{chart_id}');
                container.querySelectorAll('input').forEach(cb => cb.checked = checked);
                updateFiChart_{chart_id}();
            }};

            window.toggleAllAttrs_{chart_id} = function(checked) {{
                const container = document.getElementById('fi-attr-filters-{chart_id}');
                container.querySelectorAll('input').forEach(cb => cb.checked = checked);
                updateFiChart_{chart_id}();
            }};
        }})();
        </script>
    </div>
    """

    # Generate table with ratings
    category_width = 12
    attr_width = 15
    remaining = 100 - category_width - attr_width
    car_col_width = remaining / (num_cars * 2)  # Rating + Comment per car

    review_html = f"""
    <style>
        .fi-review-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        .fi-review-table th {{
            background: #1c2a39;
            color: white;
            padding: 10px 8px;
            text-align: center;
            font-weight: 600;
            font-size: 11px;
        }}
        .fi-review-table th.category-header {{
            background: #1c2a39;
        }}
        .fi-review-table td {{
            padding: 8px;
            border: 1px solid #e0e0e0;
            vertical-align: top;
        }}
        .fi-category-cell {{
            background: #1c2a39;
            color: white;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 11px;
            writing-mode: vertical-rl;
            text-orientation: mixed;
            text-align: center;
            min-width: 40px;
        }}
        .fi-attr-cell {{
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }}
        .fi-rating-cell {{
            text-align: center;
            font-weight: 700;
            font-size: 13px;
        }}
        .fi-rating-excellent {{ background: #d4edda; color: #155724; }}
        .fi-rating-good {{ background: #fff3cd; color: #856404; }}
        .fi-rating-average {{ background: #ffeeba; color: #856404; }}
        .fi-rating-poor {{ background: #f8d7da; color: #721c24; }}
        .fi-rating-na {{ background: #e9ecef; color: #6c757d; font-style: italic; }}
        .fi-comment-cell {{
            font-size: 11px;
            line-height: 1.4;
            max-width: 200px;
        }}
        .comment-label {{
            color: #cc0000;
            font-weight: 600;
        }}
        .fi-comment-cell .expandable-content {{
            max-height: 60px;
            overflow: hidden;
        }}
        .fi-comment-cell .expandable-content.expanded {{
            max-height: none;
        }}
    </style>
    {spider_html}
    <div class="review-table-container animate-on-scroll" style="overflow-x: auto;">
        <table class="fi-review-table">
            <thead>
                <tr>
                    <th style="width: {category_width}%;">Category</th>
                    <th style="width: {attr_width}%;">Attribute</th>
    """

    for car_name in car_names:
        review_html += f'<th style="width: {car_col_width}%;">Subjective Rating</th>'
        review_html += f'<th style="width: {car_col_width}%;">{car_name}</th>'

    review_html += """
                </tr>
            </thead>
            <tbody>
    """

    for category, attributes in fi_categories.items():
        first_in_category = True
        num_attrs = len(attributes)

        for attr_name, spec_fields in attributes:
            review_html += "<tr>"

            # Category cell (only on first row, spans all attribute rows)
            if first_in_category:
                review_html += f'<td class="fi-category-cell" rowspan="{num_attrs}">{category}</td>'
                first_in_category = False

            # Attribute name
            review_html += f'<td class="fi-attr-cell">{attr_name}</td>'

            # Rating and comments for each car
            for car_name in car_names:
                car_data = comparison_data.get(car_name) or {}
                rating = all_ratings[car_name].get(attr_name, 0)
                comment = get_combined_review(car_data, spec_fields)

                # Rating cell with color coding
                if rating == 0:
                    rating_class = "fi-rating-na"
                    rating_display = "N/A"
                elif rating >= 8:
                    rating_class = "fi-rating-excellent"
                    rating_display = f"{rating:.1f}"
                elif rating >= 6:
                    rating_class = "fi-rating-good"
                    rating_display = f"{rating:.1f}"
                elif rating >= 4:
                    rating_class = "fi-rating-average"
                    rating_display = f"{rating:.1f}"
                else:
                    rating_class = "fi-rating-poor"
                    rating_display = f"{rating:.1f}"

                review_html += f'<td class="fi-rating-cell {rating_class}">{rating_display}</td>'

                # Comment cell
                if comment:
                    if len(comment) > 150:
                        review_html += f'''<td class="fi-comment-cell">
                            <div class="expandable-content"><span class="comment-label">User Comment:</span> {comment}</div>
                            <button onclick="toggleExpand(this)" class="read-more-btn" style="font-size:10px;padding:2px 6px;">More</button>
                        </td>'''
                    else:
                        review_html += f'<td class="fi-comment-cell"><span class="comment-label">User Comment:</span> {comment}</td>'
                else:
                    review_html += '<td class="fi-comment-cell" style="color:#adb5bd;font-style:italic;">—</td>'

            review_html += "</tr>\n"

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
    consolidated_review_html = _generate_consolidated_review_html(comparison_data)

    # ============================================================================
    # PRE-COMPUTE GALLERY SECTIONS IN PARALLEL (each makes Gemini API calls)
    # ============================================================================
    from concurrent.futures import ThreadPoolExecutor, as_completed

    gallery_configs = [
        ("Exterior Highlights", "exterior", "exterior-section"),
        ("Interior Highlights", "interior", "interior-section"),
        ("Technology Highlights", "technology", "technology-section"),
        ("Comfort Highlights", "comfort", "comfort-section"),
        ("Safety Highlights", "safety", "safety-section"),
    ]

    def _generate_gallery(config):
        title, category, section_id = config
        return (category, generate_image_gallery_section(title, comparison_data, category, section_id, with_ai_notes=True))

    print("  Generating gallery sections with AI notes (5 parallel)...")
    gallery_sections = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_generate_gallery, cfg): cfg[1] for cfg in gallery_configs}
        for future in as_completed(futures):
            category = futures[future]
            try:
                cat_key, html = future.result()
                gallery_sections[cat_key] = html
            except Exception as e:
                print(f"    Warning: Gallery {category} failed: {e}")
                gallery_sections[category] = ""

    exterior_gallery_html = gallery_sections.get("exterior", "")
    interior_gallery_html = gallery_sections.get("interior", "")
    technology_gallery_html = gallery_sections.get("technology", "")
    comfort_gallery_html = gallery_sections.get("comfort", "")
    safety_gallery_html = gallery_sections.get("safety", "")

    # ============================================================================
    # PRE-COMPUTE DRIVETRAIN + ADAS SECTIONS IN PARALLEL (both make Gemini calls)
    # ============================================================================
    print("  Generating Drivetrain + ADAS sections (2 parallel)...")
    drivetrain_html = ""
    adas_html = ""

    def _gen_drivetrain():
        return generate_drivetrain_comparison_section(comparison_data)

    def _gen_adas():
        return generate_adas_comparison_section(comparison_data)

    with ThreadPoolExecutor(max_workers=4) as executor:
        drivetrain_future = executor.submit(_gen_drivetrain)
        adas_future = executor.submit(_gen_adas)

        try:
            drivetrain_html = drivetrain_future.result(timeout=180)
        except Exception as e:
            print(f"    Warning: Drivetrain generation failed: {e}")
            drivetrain_html = ""

        try:
            adas_html = adas_future.result(timeout=180)
        except Exception as e:
            print(f"    Warning: ADAS generation failed: {e}")
            adas_html = ""

    def count_words(text: str) -> int:
        return len(str(text).split())

    WORD_THRESHOLD = 12

    # Specs that should show variant columns (one column per engine variant)
    VARIANT_SPECS = {
        "engine", "engine_displacement", "max_power_kw", "torque",
        "transmission", "drive", "kerb_weight", "steering"
    }

    def _create_synthetic_variants(car_data: dict) -> list:
        """
        Create synthetic engine variants from comma-separated spec values.
        Returns list of variant dicts or empty list if no variants can be synthesized.
        """
        import re

        # Check if engine field has multiple engines (comma/slash separated or Petrol/Diesel indicators)
        engine_val = str(car_data.get("engine", ""))

        # Split patterns: "Engine1, Engine2" or "Engine1 / Engine2" or "Engine1 | Engine2"
        split_patterns = [
            r'\s*[,]\s*(?=[A-Z0-9])',  # Comma followed by capital letter or number
            r'\s*[|/]\s*',  # Pipe or slash
        ]

        engines = []
        for pattern in split_patterns:
            parts = re.split(pattern, engine_val)
            if len(parts) > 1:
                engines = [p.strip() for p in parts if p.strip()]
                break

        # If no split worked, check for Petrol/Diesel in same value
        if len(engines) < 2:
            if 'petrol' in engine_val.lower() and 'diesel' in engine_val.lower():
                # Try to extract both engine types
                engines = []
                for fuel_type in ['Petrol', 'Diesel']:
                    if fuel_type.lower() in engine_val.lower():
                        engines.append(fuel_type)
            else:
                return []  # Can't create synthetic variants

        if len(engines) < 2:
            return []

        # Build synthetic variants
        synthetic_variants = []
        for i, eng in enumerate(engines):
            variant = {"engine": eng, "variant_name": eng}

            # Try to extract corresponding values from other VARIANT_SPECS
            for spec_key in ["engine_displacement", "max_power_kw", "torque", "transmission", "drive", "kerb_weight", "steering"]:
                spec_val = str(car_data.get(spec_key, ""))

                # Try same split pattern
                for pattern in split_patterns:
                    parts = re.split(pattern, spec_val)
                    if len(parts) == len(engines) and i < len(parts):
                        variant[spec_key] = parts[i].strip()
                        break
                else:
                    # No split - use full value for all variants
                    variant[spec_key] = spec_val if spec_val else "-"

            synthetic_variants.append(variant)

        return synthetic_variants

    # Build variant info for each car
    car_variants = {}
    for car_name in cars:
        car_data = comparison_data.get(car_name, {})
        variants = car_data.get("engine_variants", [])
        if variants and len(variants) > 0:
            car_variants[car_name] = variants
        else:
            # Try synthetic variant extraction from comma-separated values
            synthetic = _create_synthetic_variants(car_data)
            if synthetic:
                car_variants[car_name] = synthetic
            else:
                # No variants - use single column with existing data
                car_variants[car_name] = [{"_single": True}]

    # Build table with grouped accordion structure and variant columns
    features_table = "<table><thead>"

    # First header row: Car names spanning their variant columns
    features_table += "<tr><th rowspan='2'>Specification</th>"
    for car_name in cars:
        num_variants = len(car_variants.get(car_name, [{"_single": True}]))
        if num_variants > 1:
            features_table += f"<th colspan='{num_variants}'>{car_name.upper()}</th>"
        else:
            features_table += f"<th rowspan='2'>{car_name.upper()}</th>"
    features_table += "</tr>"

    # Second header row: Variant names (only for cars with multiple variants)
    has_multi_variant = any(len(car_variants.get(c, [])) > 1 for c in cars)
    if has_multi_variant:
        features_table += "<tr>"
        for car_name in cars:
            variants = car_variants.get(car_name, [{"_single": True}])
            if len(variants) > 1:
                for v in variants:
                    variant_name = v.get("variant_name", v.get("engine", "Variant"))
                    # Show truncated with expandable tooltip for long names
                    if len(variant_name) > 20:
                        short_name = variant_name[:17] + "..."
                        features_table += f"""<th class='variant-subheader' title='{variant_name}'>
                            <span class='variant-short'>{short_name}</span>
                            <span class='variant-full' style='display:none;'>{variant_name}</span>
                            <button class='variant-expand-btn' onclick='toggleVariantName(this)'>▼</button>
                        </th>"""
                    else:
                        features_table += f"<th class='variant-subheader'>{variant_name}</th>"
        features_table += "</tr>"

    features_table += "</thead><tbody id=\"specifications-tbody\">"

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

        # Add empty cells for car columns (accounting for variants)
        total_cols = sum(len(car_variants.get(c, [{"_single": True}])) for c in cars)
        for _ in range(total_cols):
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
                    is_variant_spec = key in VARIANT_SPECS

                    for car_name in cars:
                        car_data = comparison_data.get(car_name, {})
                        if "error" not in car_data or car_data.get("price_range") != "Not Available":
                            variants = car_variants.get(car_name, [{"_single": True}])
                            num_variants = len(variants)

                            if is_variant_spec and num_variants > 1:
                                # Show one cell per variant
                                for v in variants:
                                    if v.get("_single"):
                                        value = car_data.get(key, 'N/A')
                                    else:
                                        value = v.get(key, '-')
                                    display_value = ", ".join(value) if isinstance(value, list) else str(value or 'N/A')
                                    word_count = count_words(display_value)

                                    features_table += "<td>"
                                    if word_count > WORD_THRESHOLD:
                                        features_table += f'<div class="expandable-content">{display_value}</div>'
                                        features_table += '<button onclick="toggleExpand(this)" class="read-more-btn">Read more</button>'
                                    else:
                                        features_table += display_value
                                    features_table += "</td>"
                            else:
                                # Non-variant spec: span all variant columns for this car
                                value = car_data.get(key, 'N/A')
                                display_value = ", ".join(value) if isinstance(value, list) else str(value or 'N/A')
                                word_count = count_words(display_value)

                                colspan = f" colspan='{num_variants}'" if num_variants > 1 else ""
                                features_table += f"<td{colspan}>"
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

                # Add empty cells for car columns (accounting for variants)
                total_cols = sum(len(car_variants.get(c, [{"_single": True}])) for c in cars)
                for i in range(total_cols):
                    if i == total_cols - 1:
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
                    is_variant_spec = key in VARIANT_SPECS

                    for car_name in cars:
                        car_data = comparison_data.get(car_name, {})
                        if "error" not in car_data or car_data.get("price_range") != "Not Available":
                            variants = car_variants.get(car_name, [{"_single": True}])
                            num_variants = len(variants)

                            if is_variant_spec and num_variants > 1:
                                # Show one cell per variant
                                for v in variants:
                                    if v.get("_single"):
                                        value = car_data.get(key, 'N/A')
                                    else:
                                        value = v.get(key, '-')
                                    display_value = ", ".join(value) if isinstance(value, list) else str(value or 'N/A')
                                    word_count = count_words(display_value)

                                    features_table += "<td>"
                                    if word_count > WORD_THRESHOLD:
                                        features_table += f'<div class="expandable-content">{display_value}</div>'
                                        features_table += '<button onclick="toggleExpand(this)" class="read-more-btn">Read more</button>'
                                    else:
                                        features_table += display_value
                                    features_table += "</td>"
                            else:
                                # Non-variant spec: span all variant columns for this car
                                value = car_data.get(key, 'N/A')
                                display_value = ", ".join(value) if isinstance(value, list) else str(value or 'N/A')
                                word_count = count_words(display_value)

                                colspan = f" colspan='{num_variants}'" if num_variants > 1 else ""
                                features_table += f"<td{colspan}>"
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
    <script src="https://cdn.jsdelivr.net/npm/@sgratzl/chartjs-chart-venn/build/index.umd.min.js"></script>
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
        table th.variant-subheader {{ background: #f8f9fa !important; color: #495057 !important; font-size: 11px; font-weight: 500; padding: 8px 10px; border-bottom: 1px solid #dee2e6; position: relative; }}
        .variant-expand-btn {{ background: none; border: none; color: #6c757d; cursor: pointer; font-size: 8px; padding: 2px 4px; margin-left: 4px; vertical-align: middle; }}
        .variant-expand-btn:hover {{ color: #dd032b; }}
        .variant-full {{ display: block; font-size: 10px; word-wrap: break-word; max-width: 150px; }}
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

            /* ---- Feature page & table print overrides ---- */

            /* Page container — allow multi-page spanning, no fixed height */
            .feature-page {{
                min-height: unset !important;
                height: auto !important;
                display: block !important;
                page-break-after: always !important;
                break-after: page !important;
                background: #fff !important;
            }}

            .feature-page-header {{
                display: flex !important;
                justify-content: space-between !important;
                align-items: center !important;
                padding: 12px 20px !important;
                border-bottom: 2px solid #cc0000 !important;
            }}

            .feature-page-title {{
                font-size: 16px !important;
                font-weight: 400 !important;
                color: #333 !important;
            }}

            .feature-page-title .highlight {{
                color: #0066cc !important;
                font-weight: 600 !important;
                text-decoration: underline !important;
            }}

            /* Container — MUST be visible, not scrollable */
            .feature-table-container {{
                overflow: visible !important;
                width: 100% !important;
                padding: 0 20px !important;
            }}

            /* Table — auto layout so columns size to content */
            .feature-table {{
                table-layout: auto !important;
                width: 100% !important;
                border-collapse: collapse !important;
                font-size: 10px !important;
                page-break-inside: auto !important;
            }}

            /* Override the global th:first-child rule for this table */
            .feature-table th:first-child,
            .feature-table th {{
                background: #2E3B4E !important;
                color: #fff !important;
                font-size: 10px !important;
                padding: 6px 8px !important;
                width: auto !important;
                min-width: unset !important;
                max-width: unset !important;
                text-align: left !important;
            }}

            .feature-table th.car-value-header {{
                text-align: center !important;
                min-width: 80px !important;
            }}

            /* Override global tbody td:first-child rule */
            .feature-table td,
            .feature-table tbody td:first-child {{
                background: #fff !important;
                color: #333 !important;
                font-size: 10px !important;
                padding: 5px 8px !important;
                width: auto !important;
                min-width: unset !important;
                max-width: unset !important;
                text-align: left !important;
                font-weight: 400 !important;
                border: 1px solid #ddd !important;
                white-space: normal !important;
            }}

            .feature-table td.cat-cell {{
                font-weight: 700 !important;
                width: 80px !important;
            }}

            .feature-table td.desc-cell {{
                width: 100px !important;
            }}

            .feature-table td.feature-cell {{
                width: 160px !important;
            }}

            .feature-table td.car-value-cell {{
                text-align: center !important;
                font-size: 11px !important;
                padding: 5px 6px !important;
                min-width: 70px !important;
            }}

            .feature-table td.car-value-cell.cell-superior {{
                background: #c8f7c5 !important;
            }}

            .feature-table td.car-value-cell.cell-inferior {{
                background: #ffcdd2 !important;
            }}

            .feature-table tr {{
                page-break-inside: avoid !important;
            }}

            .check-mark {{
                color: #28a745 !important;
                font-size: 13px !important;
                font-weight: bold !important;
            }}

            .x-mark {{
                color: #dc3545 !important;
                font-size: 13px !important;
                font-weight: bold !important;
            }}

            .value-text {{
                font-size: 10px !important;
                font-weight: 500 !important;
                color: #1a1a1a !important;
            }}

            .feature-legend {{
                display: flex !important;
                gap: 20px !important;
                padding: 6px 20px !important;
                font-size: 10px !important;
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
                <a href="#vehicle-highlights">Highlights</a>
                <div class="nav-dropdown">
                    <button class="nav-dropdown-toggle">Specs</button>
                    <div class="nav-dropdown-menu">
                        <a href="#tech-spec-section">Tech Specs</a>
                        <a href="#feature-list-section">Feature Specs</a>
                        <a href="#venn-section">Feature Face-Off</a>
                    </div>
                </div>
                <div class="nav-dropdown">
                    <button class="nav-dropdown-toggle">Gallery</button>
                    <div class="nav-dropdown-menu">
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
                        <a href="#drivetrain-section">Drivetrain</a>
                        <a href="#variant-walk-section">Variant Walk</a>
                        <a href="#price-ladder-section">Price Ladder</a>
                    </div>
                </div>
                <div class="nav-dropdown">
                    <button class="nav-dropdown-toggle">Analysis</button>
                    <div class="nav-dropdown-menu">
                        <a href="#fi-review-section">Functional Image Review</a>
                        <a href="#adas-section">ADAS Comparison</a>
                        <a href="#feature-list-section">Feature Comparison</a>
                    </div>
                </div>
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
    <div class="container">
        {exterior_gallery_html}
        {interior_gallery_html}
        {technology_gallery_html}
        {comfort_gallery_html}
        {safety_gallery_html}
        {drivetrain_html}
        {generate_variant_walk_section(comparison_data)}
        {generate_price_ladder_section(comparison_data)}
        <div class="content" id="fi-review-section">
            <div class="section-header">
                <div class="icon-wrapper">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2l10 5v3L12 5 2 10V7l10-5zM2 10v3l10 5 10-5v-3l-10 5-10-5z"/>
                    </svg>
                </div>
                <h2>Functional Image Review</h2>
            </div>
            <div class="consolidated-review-section animate-on-scroll">{consolidated_review_html}</div>
        </div>
        <div class="content" id="adas-section">
            <div class="section-header">
                <div class="icon-wrapper">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                        <path d="M12 8v4M12 16h.01"/>
                    </svg>
                </div>
                <h2>ADAS Comparison</h2>
            </div>
            <div class="animate-on-scroll">{adas_html}</div>
        </div>
        {generate_summary_comparison_section(summary_data, cars, 20) if summary_data else ''}
    </div>
    <div class="content" id="citations-section" style="display: none;"><div class="section-header"><div class="icon-wrapper"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><line x1="10" y1="9" x2="8" y2="9"></line></svg></div><h2>Data Source Citations</h2></div><div class="citations-grid">{citations_html}</div></div>
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
        function toggleVariantName(button) {{ const th = button.parentElement; const shortSpan = th.querySelector('.variant-short'); const fullSpan = th.querySelector('.variant-full'); if (shortSpan.style.display === 'none') {{ shortSpan.style.display = 'inline'; fullSpan.style.display = 'none'; button.textContent = '▼'; }} else {{ shortSpan.style.display = 'none'; fullSpan.style.display = 'block'; button.textContent = '▲'; }} }}
        function toggleCitations(event) {{ event.preventDefault(); const citationsSection = document.getElementById('citations-section'); const mainContent = document.querySelectorAll('.content:not(#citations-section), .cover-page, .hero-image-page, .spec-page, .feature-page, .drivetrain-page, .summary-comparison-page, .container'); const toggleButton = document.getElementById('citations-toggle'); const navLinks = document.querySelectorAll('.main-nav a:not(#citations-toggle)'); const navDropdowns = document.querySelectorAll('.nav-dropdown'); const navSeps = document.querySelectorAll('.nav-sep'); if (citationsSection.style.display === 'none') {{ citationsSection.style.display = 'block'; citationsSection.style.position = 'relative'; mainContent.forEach(section => {{ section.style.display = 'none'; }}); navLinks.forEach(link => {{ link.style.display = 'none'; }}); navDropdowns.forEach(dropdown => {{ dropdown.style.display = 'none'; }}); navSeps.forEach(sep => {{ sep.style.display = 'none'; }}); toggleButton.textContent = 'Go Back'; }} else {{ citationsSection.style.display = 'none'; mainContent.forEach(section => {{ if (section.classList.contains('container')) {{ section.style.display = 'block'; }} else if (section.classList.contains('content')) {{ section.style.display = 'block'; }} else {{ section.style.display = 'flex'; }} }}); navLinks.forEach(link => {{ link.style.display = 'block'; }}); navDropdowns.forEach(dropdown => {{ dropdown.style.display = 'block'; }}); navSeps.forEach(sep => {{ sep.style.display = 'block'; }}); toggleButton.textContent = 'Citations'; }} window.scrollTo({{ top: 0, behavior: 'smooth' }}); }}
        document.addEventListener('DOMContentLoaded', () => {{
            const observer = new IntersectionObserver((entries) => {{ entries.forEach(entry => {{ if (entry.isIntersecting) {{ entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }} }}); }}, {{ threshold: 0.1 }});
            document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el));

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