"""
Image Section Generation for Enhanced Reports
Generates PDF-style image galleries for car comparison reports
"""

from typing import Dict, Any, List
from datetime import datetime

from vehicle_development_agent.config import GEMINI_LITE_MODEL


def generate_hero_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate cover page and hero car image pages for PDF-style report.

    Args:
        comparison_data: Dict mapping car names to their scraped data

    Returns:
        HTML string for cover page + hero image pages
    """
    car_names = []
    hero_images = []

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            car_names.append(car_name)
            images = car_data.get("images") or {}
            hero_imgs = images.get("hero", [])
            if hero_imgs:
                first_img = hero_imgs[0]
                if isinstance(first_img, (list, tuple)) and len(first_img) >= 1:
                    img_url = first_img[0]
                    if img_url and isinstance(img_url, str):
                        hero_images.append(img_url)
                    else:
                        hero_images.append("")
                elif isinstance(first_img, str):
                    hero_images.append(first_img)
                else:
                    hero_images.append("")
            else:
                hero_images.append("")

    if not car_names:
        return ""

    # Generate title from car names
    title = " | ".join([name.upper() for name in car_names])

    # Current date
    current_date = datetime.now().strftime("%d.%m.%Y")

    # PAGE 1: Cover Page with geometric pattern
    cover_page = f'''
    <div class="cover-page" id="hero-section">
        <div class="cover-geometric-pattern">
            <svg viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
                <defs>
                    <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#d4a574;stop-opacity:0.6" />
                        <stop offset="100%" style="stop-color:#c9956c;stop-opacity:0.3" />
                    </linearGradient>
                </defs>
                <!-- Geometric lines pattern -->
                <path d="M0 200 L400 100 L600 300 L800 150 L1000 350 L1200 200" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.7"/>
                <path d="M0 300 L300 200 L500 400 L700 250 L900 450 L1100 300 L1200 350" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.6"/>
                <path d="M0 400 L200 300 L450 500 L650 350 L850 550 L1050 400 L1200 450" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.5"/>
                <path d="M100 100 L350 250 L550 150 L750 350 L950 200 L1150 400" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.5"/>
                <path d="M50 500 L250 400 L500 550 L700 400 L950 600 L1200 500" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.4"/>
                <!-- Angular shapes -->
                <polygon points="300,150 450,100 500,200 400,280 280,220" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.5"/>
                <polygon points="550,200 700,150 780,280 680,380 520,320" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.4"/>
                <polygon points="700,80 850,50 920,150 850,250 720,200" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.45"/>
                <polygon points="400,350 550,300 620,420 540,500 380,450" stroke="url(#lineGradient)" stroke-width="1.5" fill="none" opacity="0.35"/>
            </svg>
        </div>
        <div class="cover-logo">
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra">
        </div>
        <div class="cover-content">
            <h1 class="cover-title">{title}</h1>
            <h2 class="cover-subtitle">BENCHMARKING VEHICLES<br>SOFT REPORT</h2>
            <p class="cover-date">{current_date}</p>
        </div>
    </div>
    '''

    # PAGE 2+: Hero image pages for each car
    hero_pages = ""
    for i, (name, img_url) in enumerate(zip(car_names, hero_images)):
        if img_url:
            page_num = i + 2  # Page 2, 3, etc.
            hero_pages += f'''
            <div class="hero-image-page">
                <div class="hero-page-header">
                    <h1 class="hero-page-title">FEATURE COMPARISION | <span class="highlight">BENCHMARKING</span></h1>
                    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="hero-page-logo">
                </div>
                <div class="hero-image-container">
                    <img src="{img_url}" alt="{name}" class="hero-full-image" onerror="this.style.display='none'">
                </div>
                <div class="hero-page-footer">
                </div>
            </div>
            '''

    return cover_page + hero_pages


def generate_technical_spec_section(comparison_data: Dict[str, Any], page_start: int = 3) -> str:
    """
    Generate Technical Specification pages with the new format.

    Args:
        comparison_data: Dict mapping car names to their scraped data
        page_start: Starting page number

    Returns:
        HTML string for technical specification pages
    """
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data]

    if not car_names:
        return ""

    # First car is the reference (Mahindra car)
    reference_car = car_names[0] if car_names else ""

    # Keys to exclude — metadata, citations, image blobs
    METADATA_KEYS = {
        'car_name', 'method', 'source_urls', 'images', 'gcs_folder',
        'scraping_method', 'timestamp', 'chart_gcs_uri', 'chart_signed_url',
        'summary_data',
    }

    # Comprehensive organized spec groups
    tech_spec_groups = {
        "Powertrain": [
            ("Engine Displacement", "engine_displacement"),
            ("Fuel Type", "fuel_type"),
            ("Torque", "torque"),
            ("Mileage / Fuel Economy", "mileage"),
            ("Acceleration (0-100 kmph)", "acceleration"),
            ("Performance Feel", "performance_feel"),
            ("Driveability", "driveability"),
            ("Response", "response"),
            ("City Performance", "city_performance"),
            ("Highway Performance", "highway_performance"),
            ("Off-Road Capability", "off_road"),
            ("Crawl / 4WD Modes", "crawl"),
        ],
        "Transmission": [
            ("Manual Transmission", "manual_transmission_performance"),
            ("Automatic Transmission", "automatic_transmission_performance"),
            ("Pedal Operation", "pedal_operation"),
            ("Gear Shift", "gear_shift"),
            ("Gear Selection", "gear_selection"),
            ("Pedal Travel", "pedal_travel"),
        ],
        "Dimensions": [
            ("Wheelbase (mm)", "wheelbase"),
            ("Ground Clearance (mm)", "ground_clearance"),
            ("Boot Space", "boot_space"),
            ("Turning Radius (m)", "turning_radius"),
            ("Seating Capacity", "seating_capacity"),
        ],
        "Chassis": [
            ("Chassis Type", "chasis"),
        ],
        "Safety": [
            ("Airbags", "airbags"),
            ("Airbag Types", "airbag_types_breakdown"),
            ("NCAP Rating", "ncap_rating"),
            ("Impact Rating", "impact"),
            ("ADAS System", "adas"),
            ("Vehicle Safety Features", "vehicle_safety_features"),
            ("Brakes", "brakes"),
            ("Braking", "braking"),
            ("Brake Performance", "brake_performance"),
            ("EPB / Hill Hold", "epb"),
            ("Stability Control", "stability"),
            ("Parking Sensors", "parking_sensors"),
            ("Parking Camera", "parking_camera"),
            ("Parking", "parking"),
            ("Seatbelt Features", "seatbelt_features"),
            ("Seats Restraint", "seats_restraint"),
        ],
        "Steering & Handling": [
            ("Steering Type", "steering"),
            ("Sensitivity", "sensitivity"),
            ("Telescopic Steering", "telescopic_steering"),
            ("Manoeuvring", "manoeuvring"),
            ("Corner Stability", "corner_stability"),
            ("Straight-Ahead Stability", "straight_ahead_stability"),
        ],
        "Ride Quality": [
            ("Ride", "ride"),
            ("Ride Quality", "ride_quality"),
            ("Bumps / Potholes", "stiff_on_pot_holes"),
            ("Bumps", "bumps"),
            ("Shocks / Suspension", "shocks"),
            ("Jerks", "jerks"),
            ("Shakes", "shakes"),
            ("Shudder", "shudder"),
            ("Pulsation", "pulsation"),
            ("Grabby", "grabby"),
            ("Spongy", "spongy"),
        ],
        "NVH": [
            ("Overall NVH", "nvh"),
            ("Powertrain Noise", "powertrain_nvh"),
            ("Wind NVH", "wind_nvh"),
            ("Road NVH", "road_nvh"),
            ("Wind Noise", "wind_noise"),
            ("Tire Noise", "tire_noise"),
            ("Turbo Noise", "turbo_noise"),
            ("Blower Noise", "blower_noise"),
            ("Rattle", "rattle"),
        ],
        "Wheels & Tyres": [
            ("Tyre Size", "tyre_size"),
            ("Wheel Size", "wheel_size"),
            ("Alloy Wheels", "alloy_wheel"),
        ],
        "Exterior": [
            ("LED Headlamps", "led"),
            ("DRL (Daytime Running Lights)", "drl"),
            ("Tail Lamps", "tail_lamp"),
            ("Sunroof", "sunroof"),
            ("ORVM", "orvm"),
            ("Wiper Control", "wiper_control"),
        ],
        "Interior & Comfort": [
            ("Interior Quality", "interior"),
            ("Climate Control", "climate_control"),
            ("Seat Material", "seat_material"),
            ("Seat Cushion", "seat_cushion"),
            ("Seat Features", "seat_features_detailed"),
            ("Seats", "seats"),
            ("Ventilated Seats", "ventilated_seats"),
            ("Rear Seat Features", "rear_seat_features"),
            ("Armrest", "armrest"),
            ("Headrest", "headrest"),
            ("Soft Touch Trims", "soft_trims"),
            ("Visibility", "visibility"),
            ("Ingress (Entry)", "ingress"),
            ("Egress (Exit)", "egress"),
            ("IRVM", "irvm"),
            ("Power Windows", "window"),
            ("Door Effort", "door_effort"),
        ],
        "Technology": [
            ("Infotainment Screen", "infotainment_screen"),
            ("Resolution", "resolution"),
            ("Touch Response", "touch_response"),
            ("Digital Display", "digital_display"),
            ("Apple CarPlay / Android Auto", "apple_carplay"),
            ("Audio System", "audio_system"),
            ("Cruise Control", "cruise_control"),
            ("Push Button Start", "button"),
        ],
        "Market": [
            ("Price Range", "price_range"),
            ("Monthly Sales", "monthly_sales"),
            ("User Rating", "user_rating"),
        ],
    }

    EMPTY_VALUES = {None, "", "-", "N/A", "Not Available", "not available", "n/a"}

    # Track which keys have been covered by the organized groups
    covered_keys = set()
    for specs in tech_spec_groups.values():
        for _, key in specs:
            covered_keys.add(key)

    # Dynamically collect any remaining keys from the actual data not yet covered
    all_data_keys = set()
    for car_name in car_names:
        car_data = comparison_data.get(car_name, {})
        for k in car_data.keys():
            if (not k.endswith('_citation')
                    and k not in METADATA_KEYS
                    and k not in covered_keys):
                all_data_keys.add(k)

    # Append remaining keys as an "Additional Specs" group
    if all_data_keys:
        tech_spec_groups["Additional Specs"] = [
            (k.replace('_', ' ').title(), k) for k in sorted(all_data_keys)
        ]

    # Generate table rows
    rows_html = ""

    def _render_rows(category, specs):
        nonlocal rows_html
        category_printed = False
        for label, key in specs:
            values = []
            for car_name in car_names:
                car_data = comparison_data.get(car_name, {})
                value = car_data.get(key, "-")
                if value in EMPTY_VALUES:
                    value = "-"
                values.append(value)

            if all(v == "-" for v in values):
                continue

            cat_display = category if not category_printed else ""
            category_printed = True

            ref_val = values[0] if values else "-"
            rows_html += f'<tr><td class="cat-cell">{cat_display}</td><td class="param-cell">{label}</td>'
            for i, value in enumerate(values):
                if i == 0:
                    # Reference car — always white/neutral
                    rows_html += f'<td>{value}</td>'
                else:
                    # Competitor car — color based on presence vs reference
                    if ref_val != "-" and value == "-":
                        cell_class = "inferior-cell"   # competitor is missing this spec
                    elif ref_val == "-" and value != "-":
                        cell_class = "superior-cell"   # competitor has it, reference doesn't
                    else:
                        cell_class = ""
                    rows_html += f'<td class="{cell_class}">{value}</td>'
            rows_html += '</tr>'

    for category, specs in tech_spec_groups.items():
        _render_rows(category, specs)

    # Build the page
    cars_header = "".join([f'<th colspan="1">{name}</th>' for name in car_names])

    html = f'''
    <div class="spec-page" id="tech-spec-section">
        <div class="spec-page-header">
            <h1 class="spec-page-title">TECHNICAL SPECIFICATION | <span class="highlight">BENCHMARKING</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="spec-page-logo">
        </div>
        <div class="spec-legend">
            <div class="legend-item"><span class="legend-color superior"></span> Superior to {car_names[-1] if len(car_names) > 1 else 'Competitor'}</div>
            <div class="legend-item"><span class="legend-color inferior"></span> Inferior to {car_names[-1] if len(car_names) > 1 else 'Competitor'}</div>
        </div>
        <div class="spec-table-container">
            <table class="spec-table">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>Parameter</th>
                        {cars_header}
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        <div class="spec-page-footer">
        </div>
    </div>
    '''

    return html


# Maps feature display name → existing scraped data key.
# Features here are served directly from comparison_data — no Gemini needed.
# Features NOT in this map are collected and sent to Gemini in batches of 10.
# Feature type classification — controls how raw scraped text is converted to display values:
#   "count"  → extract integer from text (e.g. "6 Airbags" → 6)
#   "spec"   → show cleaned short text (e.g. "Leatherette" stays as "Leatherette")
#   "binary" → (default) non-NA text → True (✓), NA text → False (✗)
_FEATURE_TYPES: Dict[str, str] = {
    # count features
    "Total Airbags":            "count",
    "Front Airbags":            "count",
    "Side Airbags":             "count",
    "Curtain Airbags":          "count",
    "Knee Airbag":              "count",
    "Screen Size (inches)":     "count",
    "Wheel Size (inches)":      "count",
    "Seating Capacity":         "count",
    "Engine Displacement (cc)": "count",
    "Max Torque (Nm)":          "count",
    "Max Power (bhp)":          "count",
    "Fuel Efficiency (kmpl)":   "count",
    "Ground Clearance (mm)":    "count",
    "Turning Radius (m)":       "count",
    "Wheelbase (mm)":           "count",
    "Boot Space (litres)":      "count",
    "Speaker Count":            "count",
    "Power Adjustment Ways (Driver)": "count",
    "Total USB Ports":          "count",
    "Tow Capacity (kg)":        "count",
    "NCAP Safety Rating":       "count",
    # spec features — show meaningful text
    "Seat Material":            "spec",
    "Fuel Type":                "spec",
    "Brake Type":               "spec",
    "Chassis Type":             "spec",
    "Tyre Size":                "spec",
    "Spare Tyre Type":          "spec",
    "Surround View Monitor":    "spec",
    "Audio System":             "spec",
    "Drive Modes":              "spec",
    "Terrain Modes":            "spec",
    # everything else defaults to "binary"
}

_SCRAPED_KEY_MAP = {
    # Safety
    "Total Airbags":                "airbags",
    "NCAP Safety Rating":           "ncap_rating",
    "Impact Protection Rating":     "impact",
    "ISOFIX Child Seat Anchors":    "seatbelt_features",
    "Electronic Stability Control": "stability",
    "Electronic Parking Brake":     "epb",
    "Hill Hold Control":            "epb",
    "Rear Parking Sensors":         "parking_sensors",
    "Brake Type":                   "brakes",
    "Vehicle Safety Features":      "vehicle_safety_features",
    # Technology
    "Touchscreen Display":          "infotainment_screen",
    "Screen Size (inches)":         "resolution",
    "Apple CarPlay":                "apple_carplay",
    "Android Auto":                 "apple_carplay",
    "Digital Instrument Cluster":   "digital_display",
    "Audio System":                 "audio_system",
    "Parking Camera":               "parking_camera",
    # Interior / Comfort
    "Seat Material":                "seat_material",
    "Ventilated Front Seats":       "ventilated_seats",
    "Seating Capacity":             "seating_capacity",
    "Rear Reclining Seats":         "rear_seat_features",
    "Rear Foldable Seats":          "rear_seat_features",
    "Armrest":                      "armrest",
    "Sunroof":                      "sunroof",
    "Automatic Climate Control":    "climate_control",
    "Dual Zone Climate Control":    "climate_control",
    "Rear AC Vents":                "climate_control",
    "Push Button Start":            "button",
    "Auto Dimming IRVM":            "irvm",
    "Power Windows All Doors":      "window",
    "Cruise Control":               "cruise_control",
    # Exterior
    "LED Headlamps":                "led",
    "LED Daytime Running Lights":   "drl",
    "LED Tail Lamps":               "tail_lamp",
    "Alloy Wheels":                 "alloy_wheel",
    "Wheel Size (inches)":          "wheel_size",
    "Tyre Size":                    "tyre_size",
    # Performance
    "Fuel Type":                    "fuel_type",
    "Engine Displacement (cc)":     "engine_displacement",
    "Max Torque (Nm)":              "torque",
    "Fuel Efficiency (kmpl)":       "mileage",
    "Manual Transmission":          "manual_transmission_performance",
    "Automatic Transmission":       "automatic_transmission_performance",
    # Handling / Dimensions
    "Ground Clearance (mm)":        "ground_clearance",
    "Telescopic Steering Column":   "telescopic_steering",
    "Turning Radius (m)":           "turning_radius",
    "Wheelbase (mm)":               "wheelbase",
    "Boot Space (litres)":          "boot_space",
    "Chassis Type":                 "chasis",
}

# Pre-defined feature batches — ~10 features each, all run in parallel
_FEATURE_BATCHES = [
    {
        "category": "Safety", "description": "Airbags & Passive Safety",
        "features": ["Total Airbags", "Front Airbags", "Side Airbags", "Curtain Airbags",
                     "Knee Airbag", "Seatbelt Pretensioner", "Rear Seatbelts",
                     "NCAP Safety Rating", "ISOFIX Child Seat Anchors", "Impact Protection Rating"]
    },
    {
        "category": "Safety", "description": "Active Safety",
        "features": ["ABS", "Electronic Stability Control", "Traction Control",
                     "Hill Hold Control", "Electronic Parking Brake", "Auto Hold",
                     "Brake Assist", "Hill Descent Control", "Rear Parking Sensors",
                     "Front Parking Sensors"]
    },
    {
        "category": "Safety", "description": "ADAS",
        "features": ["Forward Collision Warning", "Automatic Emergency Braking",
                     "Lane Keep Assist", "Lane Departure Warning", "Blind Spot Monitor",
                     "Rear Cross Traffic Alert", "Adaptive Cruise Control",
                     "Traffic Sign Recognition", "360 Degree Camera", "Driver Fatigue Detection"]
    },
    {
        "category": "Technology", "description": "Infotainment",
        "features": ["Touchscreen Display", "Screen Size (inches)", "Apple CarPlay",
                     "Android Auto", "Wireless CarPlay", "Wireless Android Auto",
                     "OTA Updates", "Built-in Navigation", "Voice Control",
                     "Digital Instrument Cluster"]
    },
    {
        "category": "Technology", "description": "Audio & Connectivity",
        "features": ["Speaker Count", "Premium Sound System", "Subwoofer",
                     "USB Type-C Front Row", "USB Type-C Rear Row", "Wireless Charging",
                     "Bluetooth", "Wi-Fi Hotspot", "Heads-Up Display",
                     "Rear Entertainment System"]
    },
    {
        "category": "Interior", "description": "Seats",
        "features": ["Seat Material", "Ventilated Front Seats", "Heated Front Seats",
                     "Power Driver Seat", "Power Co-Driver Seat", "Driver Memory Seat",
                     "Power Adjustment Ways (Driver)", "Rear Reclining Seats",
                     "Rear Foldable Seats", "Seating Capacity"]
    },
    {
        "category": "Interior", "description": "Comfort & Climate",
        "features": ["Sunroof", "Panoramic Sunroof", "Automatic Climate Control",
                     "Dual Zone Climate Control", "Rear AC Vents", "PM2.5 Air Filter",
                     "Push Button Start", "Keyless Entry", "Auto Dimming IRVM",
                     "Ambient Lighting"]
    },
    {
        "category": "Exterior", "description": "Lighting & Wheels",
        "features": ["LED Headlamps", "LED Daytime Running Lights", "LED Tail Lamps",
                     "Auto Headlamps", "Cornering Lights", "Follow Me Home Lights",
                     "Alloy Wheels", "Wheel Size (inches)", "Tyre Size", "Roof Rails"]
    },
    {
        "category": "Performance", "description": "Engine & Transmission",
        "features": ["Fuel Type", "Engine Displacement (cc)", "Max Power (bhp)",
                     "Max Torque (Nm)", "Turbo Engine", "Fuel Efficiency (kmpl)",
                     "Manual Transmission", "Automatic Transmission",
                     "Paddle Shifters", "Drive Modes"]
    },
    {
        "category": "Handling", "description": "Off-Road & Dynamics",
        "features": ["4WD / AWD", "Electronic Locking Differential", "Hill Descent Control",
                     "Terrain Modes", "Ground Clearance (mm)", "Electronic Power Steering",
                     "Telescopic Steering Column", "Turning Radius (m)",
                     "Tow Hook", "Skid Plates"]
    },
    {
        "category": "Convenience", "description": "Windows & Controls",
        "features": ["Power Windows All Doors", "One-Touch Window Up/Down",
                     "Rain Sensing Wipers", "Rear Wiper & Washer", "Auto Folding ORVM",
                     "Heated ORVM", "TPMS (Tyre Pressure Monitor)",
                     "Cruise Control", "Speed Alert System", "Rear Sunshade"]
    },
    {
        "category": "Dimensions & Storage", "description": "Space & Capacity",
        "features": ["Wheelbase (mm)", "Boot Space (litres)", "Spare Tyre Type",
                     "Cargo Net", "Rear Armrest with Cupholder", "Front Cup Holders",
                     "Rear Cup Holders", "Total USB Ports", "12V Power Outlet",
                     "Tow Capacity (kg)"]
    },
]


def _normalize_scraped_value(feat_name: str, raw_val):
    """
    Convert raw scraped text to the appropriate display type:
      - count features  → extract integer (e.g. "6 Airbags" → 6)
      - spec features   → clean short text  (e.g. "Leatherette" → "Leatherette")
      - binary features → True if non-NA, False if NA
    """
    import re as _re

    _NA = {"", "-", "not available", "n/a", "na", "none", "null", "not found", "false", "no"}

    if raw_val is None:
        return False
    if isinstance(raw_val, bool):
        return raw_val
    if isinstance(raw_val, (int, float)):
        return raw_val

    s = str(raw_val).strip()
    if s.lower() in _NA:
        return False

    feat_type = _FEATURE_TYPES.get(feat_name, "binary")

    if feat_type == "count":
        m = _re.search(r'\d+\.?\d*', s)
        if m:
            num = float(m.group())
            return int(num) if num == int(num) else num
        return True  # has it but no number found

    if feat_type == "spec":
        # strip long qualifiers, keep first meaningful part (max 25 chars)
        clean = s.split(",")[0].split("(")[0].strip()
        return clean[:25] if len(clean) > 25 else clean

    # binary — any non-NA value means the feature is present
    return True


def _fetch_binary_feature_comparison(car_names: List[str], comparison_data: Dict[str, Any]) -> List[Dict]:
    """
    Build the feature comparison table efficiently:
      1. Serve features that map to existing scraped keys directly (free, instant).
      2. Collect remaining features → re-batch into groups of 10 → parallel Gemini calls.
    This avoids re-fetching data we already have.
    """
    import os
    import json_repair
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _is_na(val):
        if val is None:
            return True
        return str(val).strip().lower() in ("", "-", "not available", "n/a", "na", "none", "null", "not found")

    # ------------------------------------------------------------------
    # Step 1: resolve each feature from existing scraped data where possible
    # resolved[feat_name] = {car_name: value}
    # ------------------------------------------------------------------
    resolved: Dict[str, Dict] = {}
    missing_features: List[Dict] = []  # {"name": str, "category": str, "description": str}

    for batch in _FEATURE_BATCHES:
        for feat_name in batch["features"]:
            scraped_key = _SCRAPED_KEY_MAP.get(feat_name)
            if scraped_key:
                raw_vals = {cn: comparison_data.get(cn, {}).get(scraped_key) for cn in car_names}
                if not all(_is_na(v) for v in raw_vals.values()):
                    # Normalize raw text → bool/int/short-text based on feature type
                    resolved[feat_name] = {
                        cn: _normalize_scraped_value(feat_name, v)
                        for cn, v in raw_vals.items()
                    }
                    continue
            missing_features.append({
                "name": feat_name,
                "category": batch["category"],
                "description": batch["description"],
            })

    print(f"  Feature comparison: {len(resolved)} from scraped data, "
          f"{len(missing_features)} need Gemini search")

    # ------------------------------------------------------------------
    # Step 2: re-batch missing features into groups of 10 → parallel Gemini
    # ------------------------------------------------------------------
    gemini_resolved: Dict[str, Dict] = {}

    if missing_features:
        try:
            from google import genai
            from google.genai import types

            PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
            client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

            car1 = car_names[0]
            car2 = car_names[1] if len(car_names) > 1 else "Competitor"
            cars_str = " vs ".join(car_names)

            # Split missing into batches of 10
            gemini_batches = [
                missing_features[i:i + 10]
                for i in range(0, len(missing_features), 10)
            ]

            def _call_batch(feats: List[Dict]) -> List[Dict]:
                feat_list = "\n".join(f"- {f['name']}" for f in feats)
                prompt = f"""For {cars_str}, look up each feature and return whether each car has it.

Features:
{feat_list}

Rules:
- true/false for yes/no features
- integer for counts (e.g. Total Airbags → 6)
- short text max 20 chars for type/size (e.g. Seat Material → "Leather")
- false if the car does not have the feature

Return ONLY valid JSON:
{{
  "features": [
    {{"name": "Feature Name", "{car1}": true, "{car2}": false}},
    {{"name": "Speaker Count", "{car1}": 8, "{car2}": 6}}
  ]
}}"""
                try:
                    tools = [types.Tool(google_search=types.GoogleSearch())]
                    config = types.GenerateContentConfig(
                        tools=tools, temperature=0.1, max_output_tokens=1024
                    )
                    response = client.models.generate_content(
                        model=GEMINI_LITE_MODEL, contents=prompt, config=config
                    )
                    if response and response.text:
                        text = response.text.strip()
                        if "```json" in text:
                            text = text.split("```json")[1].split("```")[0]
                        elif "```" in text:
                            text = text.split("```")[1].split("```")[0]
                        text = text.strip()
                        if "{" in text and "}" in text:
                            text = text[text.index("{"):text.rindex("}") + 1]
                        result = json_repair.loads(text)
                        return result.get("features", [])
                except Exception as e:
                    print(f"  Gemini batch error: {e}")
                return []

            # Fire all Gemini batches in parallel
            with ThreadPoolExecutor(max_workers=len(gemini_batches)) as executor:
                futures = {executor.submit(_call_batch, b): b for b in gemini_batches}
                for future in as_completed(futures):
                    for feat_obj in future.result():
                        name = feat_obj.get("name", "")
                        if name:
                            gemini_resolved[name] = {
                                cn: feat_obj.get(cn) for cn in car_names
                            }

            print(f"  Gemini returned {len(gemini_resolved)} features "
                  f"via {len(gemini_batches)} parallel calls")

        except Exception as e:
            print(f"  Gemini feature fetch error: {e}")

    # ------------------------------------------------------------------
    # Step 3: assemble into ordered category structure from _FEATURE_BATCHES
    # ------------------------------------------------------------------
    cat_map: Dict[str, List] = {}
    for batch in _FEATURE_BATCHES:
        desc_feats = []
        for feat_name in batch["features"]:
            vals = resolved.get(feat_name) or gemini_resolved.get(feat_name)
            if vals:
                feat_obj = {"name": feat_name}
                feat_obj.update(vals)
                desc_feats.append(feat_obj)
        if desc_feats:
            cat_map.setdefault(batch["category"], []).append(
                {"description": batch["description"], "features": desc_feats}
            )

    return [{"category": cat, "descriptions": descs} for cat, descs in cat_map.items()]


def _build_fallback_categories(car_names: List[str], comparison_data: Dict[str, Any]) -> List[Dict]:
    """Build category structure from existing scraped data when Gemini is unavailable."""
    feature_groups = {
        "Safety": {
            "Airbags": [("Number of Airbags", "airbags"), ("Airbag Types", "airbag_types_breakdown")],
            "Sensors": [("NCAP Rating", "ncap_rating"), ("Impact Rating", "impact"), ("ADAS System", "adas")],
            "Controls": [("Electronic Stability", "stability"), ("Hill Hold", "epb"),
                         ("Parking Sensors", "parking_sensors"), ("Parking Camera", "parking_camera")],
            "Restraints": [("Seatbelt Features", "seats_restraint"), ("Safety Features", "vehicle_safety_features")],
        },
        "Technology": {
            "Infotainment": [("Instrument Cluster", "digital_display"), ("Touchscreen", "infotainment_screen"),
                             ("Touch Response", "touch_response")],
            "Connectivity": [("Apple CarPlay", "apple_carplay"), ("Cruise Control", "cruise_control")],
            "Audio": [("Audio System", "audio_system")],
        },
        "Exterior": {
            "Lighting": [("LED Headlamps", "led"), ("DRL", "drl"), ("Tail Lamps", "tail_lamp")],
            "Wheels": [("Alloy Wheels", "alloy_wheel"), ("Tyre Size", "tyre_size")],
            "Roof": [("Sunroof", "sunroof")],
        },
        "Interior": {
            "Seats": [("Seat Material", "seat_material"), ("Ventilated Seats", "ventilated_seats"),
                      ("Seating Capacity", "seating_capacity")],
            "Climate": [("Climate Control", "climate_control")],
            "Comfort": [("Armrest", "armrest"), ("Soft Touch Trims", "soft_trims"),
                        ("Push Button Start", "button"), ("Power Windows", "window")],
        },
        "Performance": {
            "Engine": [("Fuel Type", "fuel_type"), ("Displacement", "engine_displacement"),
                       ("Torque", "torque"), ("Mileage", "mileage")],
        },
        "Dimensions": {
            "Size": [("Wheelbase", "wheelbase"), ("Ground Clearance", "ground_clearance"),
                     ("Boot Space", "boot_space"), ("Chassis Type", "chasis")],
        },
    }

    def _is_na(val):
        if val is None:
            return True
        return str(val).strip().lower() in ("", "-", "not available", "n/a", "na", "none", "null", "✗", "no")

    categories = []
    for cat_name, descs in feature_groups.items():
        desc_list = []
        for desc_name, features in descs.items():
            feat_list = []
            for feat_label, feat_key in features:
                feat_obj = {"name": feat_label}
                for cn in car_names:
                    raw = comparison_data.get(cn, {}).get(feat_key)
                    feat_obj[cn] = None if _is_na(raw) else raw
                feat_list.append(feat_obj)
            desc_list.append({"description": desc_name, "features": feat_list})
        categories.append({"category": cat_name, "descriptions": desc_list})
    return categories


def generate_feature_list_section(comparison_data: Dict[str, Any], page_start: int = 4) -> str:
    """
    Generate Feature List Comparison pages — ticks and crosses only (no text columns).
    Uses Gemini + Google Search for a comprehensive 80-120 feature binary list.
    Falls back to existing scraped data if Gemini is unavailable.
    """
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data]

    if not car_names:
        return ""

    # Fetch comprehensive binary feature data (Gemini → fallback)
    categories = _fetch_binary_feature_comparison(car_names, comparison_data)
    if not categories:
        categories = _build_fallback_categories(car_names, comparison_data)

    import re as _re

    def _is_positive(val):
        """True if value represents a feature being present/enabled."""
        if val is None or val is False:
            return False
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val > 0
        s = str(val).strip().lower()
        return s not in ("", "-", "not available", "n/a", "na", "none", "null", "false", "no", "0")

    def _render_cell(val):
        """Render value as ✓, ✗, number, or short text."""
        if val is None or val is False:
            return '<span class="x-mark">✗</span>'
        if isinstance(val, bool):
            return '<span class="check-mark">✓</span>'
        if isinstance(val, (int, float)):
            display = int(val) if val == int(val) else val
            return f'<span class="value-text">{display}</span>'
        s = str(val).strip()
        sl = s.lower()
        if sl in ("", "-", "not available", "n/a", "na", "none", "null", "false", "no", "0"):
            return '<span class="x-mark">✗</span>'
        if sl in ("true", "yes"):
            return '<span class="check-mark">✓</span>'
        return f'<span class="value-text">{s}</span>'

    # Features where a lower numeric value is better
    LOWER_IS_BETTER = {"Turning Radius (m)", "Engine Displacement (cc)"}

    def _cell_classes(feat_name, vals):
        """Return per-car CSS class list — green cell for winner, red cell for loser."""
        n = len(vals)
        if n < 2:
            return [""] * n

        pos = [_is_positive(v) for v in vals]

        # Binary difference: one has it, others don't
        if any(pos) and not all(pos):
            return ["cell-superior" if p else "cell-inferior" for p in pos]

        # All present or all absent — try numeric tiebreak
        def _num(v):
            if isinstance(v, (int, float)):
                return float(v)
            m = _re.search(r'\d+\.?\d*', str(v) if v else "")
            return float(m.group()) if m else None

        nums = [_num(v) for v in vals]
        if all(x is not None for x in nums) and len(set(nums)) > 1:
            lower_better = feat_name in LOWER_IS_BETTER
            best = min(nums) if lower_better else max(nums)
            worst = max(nums) if lower_better else min(nums)
            classes = []
            for x in nums:
                if x == best:
                    classes.append("cell-superior")
                elif x == worst:
                    classes.append("cell-inferior")
                else:
                    classes.append("")
            return classes

        return [""] * n

    rows_html = ""
    for cat_obj in categories:
        cat_name = cat_obj.get("category", "")
        first_cat = True
        for desc_obj in cat_obj.get("descriptions", []):
            desc_name = desc_obj.get("description", "")
            first_desc = True
            for feat in desc_obj.get("features", []):
                feat_name = feat.get("name", "")
                vals = [feat.get(cn) for cn in car_names]
                cc_list = _cell_classes(feat_name, vals)
                cells = "".join(
                    f'<td class="car-value-cell {cc}">{_render_cell(v)}</td>'
                    for v, cc in zip(vals, cc_list)
                )
                rows_html += f'''
                <tr>
                    <td class="cat-cell">{cat_name if first_cat else ""}</td>
                    <td class="desc-cell">{desc_name if first_desc else ""}</td>
                    <td class="feature-cell">{feat_name}</td>
                    {cells}
                </tr>'''
                first_cat = False
                first_desc = False

    car_names_title = " | ".join(n.upper() for n in car_names)
    car_headers = "".join(f'<th class="car-value-header">{n}</th>' for n in car_names)
    competitor = car_names[-1] if len(car_names) > 1 else "Competitor"

    return f'''
    <div class="feature-page" id="feature-list-section">
        <div class="feature-page-header">
            <h1 class="feature-page-title">FEATURE LIST COMPARISON | <span class="highlight">BENCHMARKING {car_names_title}</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="feature-page-logo">
        </div>
        <div class="feature-legend">
            <div class="legend-item"><span class="legend-color superior"></span> Superior to {competitor}</div>
            <div class="legend-item"><span class="legend-color inferior"></span> Inferior to {competitor}</div>
        </div>
        <div class="feature-table-container">
            <table class="feature-table">
                <thead>
                    <tr>
                        <th class="cat-header">Category</th>
                        <th class="desc-header">Description</th>
                        <th class="feature-header">Features</th>
                        {car_headers}
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        <div class="feature-page-footer">
        </div>
    </div>
    '''


def _generate_single_drivetrain_section(
    drivetrain_data: Dict[str, Any],
    page_num: int
) -> str:
    """
    Generate one drivetrain page for a single car.

    The comparison_with column is fully dynamic — determined by Gemini
    based on the car's actual drivetrain type (4WD, AWD, FWD, EV, etc.)
    """
    car_name = drivetrain_data.get("car_name", "")
    system_name = drivetrain_data.get("system_name", "Drivetrain System")
    intro_text = drivetrain_data.get("intro_text", "")
    features = drivetrain_data.get("features", [])
    explanations = drivetrain_data.get("explanations", [])
    images = drivetrain_data.get("images", [])
    # Dynamic comparison column — Gemini chose this based on the car's drivetrain type
    comparison_with = drivetrain_data.get("comparison_with", "Conventional Drivetrain")

    # Feature table rows
    feature_rows = ""
    for feature in features:
        feature_rows += f'''
        <tr>
            <td class="feature-name">{feature.get("name", "")}</td>
            <td class="feature-car">{feature.get("car_value", "")}</td>
            <td class="feature-conventional">{feature.get("conventional_value", "")}</td>
        </tr>
        '''

    # Explanations list
    explanations_html = ""
    for i, explanation in enumerate(explanations):
        explanations_html += f'''
        <li><span class="explanation-title">{explanation.get("title", "")}:</span> {explanation.get("description", "")}</li>
        '''

    # Images
    images_html = ""
    for img in images[:2]:
        images_html += f'''
        <div class="drivetrain-image">
            <img src="{img}" alt="{car_name} drivetrain" onerror="this.parentElement.style.display='none'">
        </div>
        '''

    # Highlight keywords in intro text
    highlighted_intro = intro_text
    for keyword in drivetrain_data.get("highlight_keywords", []):
        if keyword:
            highlighted_intro = highlighted_intro.replace(
                keyword,
                f'<span class="highlight-green">{keyword}</span>'
            )

    return f'''
    <div class="drivetrain-page" id="drivetrain-section">
        <div class="drivetrain-header">
            <h1 class="drivetrain-title">FEATURE COMPARISION | <span class="highlight">BENCHMARKING</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="drivetrain-logo">
        </div>

        <div class="drivetrain-content">
            <div class="drivetrain-left">
                <p class="drivetrain-intro">{highlighted_intro}</p>

                <table class="drivetrain-table">
                    <thead>
                        <tr>
                            <th class="feature-header">Feature</th>
                            <th class="car-header">{car_name}<br><span style="font-weight:400;font-size:11px">{system_name}</span></th>
                            <th class="conventional-header">{comparison_with}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {feature_rows}
                    </tbody>
                </table>

                <ol class="drivetrain-explanations">
                    {explanations_html}
                </ol>
            </div>

            <div class="drivetrain-right">
                {images_html}
            </div>
        </div>

        <div class="drivetrain-footer">
        </div>
    </div>
    '''


def generate_drivetrain_comparison_section(
    comparison_data: Dict[str, Any],
    drivetrain_data: Dict[str, Any] = None,
    page_num: int = 19
) -> str:
    """
    Generate drivetrain/powertrain feature comparison sections — ONE per car.

    Runs one Gemini call per car in parallel (3 cars = 3 parallel calls).
    Each section has a dynamic comparison_with column based on the car's
    actual drivetrain type (4WD vs Conventional 4WD, FWD vs Conventional FWD,
    EV vs Conventional ICE, etc.)

    Args:
        comparison_data: Dict mapping car names to their scraped data
        drivetrain_data: Ignored (kept for backward compatibility)
        page_num: Starting page number

    Returns:
        HTML string — concatenated drivetrain sections for all cars
    """
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data
                 and not name.strip().upper().startswith("CODE:")]

    if not car_names:
        return ""

    # Fetch drivetrain data for ALL cars in parallel
    all_drivetrain = _extract_all_drivetrain_data(car_names, comparison_data)

    if not all_drivetrain:
        return ""

    # Generate one section per car
    html_parts = []
    for i, car_dt_data in enumerate(all_drivetrain):
        if car_dt_data and car_dt_data.get("features"):
            html_parts.append(_generate_single_drivetrain_section(car_dt_data, page_num + i))

    return "\n".join(html_parts)


def _extract_all_drivetrain_data(
    car_names: List[str],
    comparison_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Fetch drivetrain data for ALL cars using parallel Gemini calls.
    Sync wrapper around the async parallel fetcher.
    """
    import asyncio
    import concurrent.futures

    try:
        from vehicle_development_agent.extraction.drivetrain_fetcher import fetch_all_cars_drivetrain_parallel

        try:
            asyncio.get_running_loop()
            # Already in an event loop — run in a thread pool
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    fetch_all_cars_drivetrain_parallel(car_names, comparison_data)
                )
                return future.result(timeout=180)
        except RuntimeError:
            # No event loop running
            return asyncio.run(
                fetch_all_cars_drivetrain_parallel(car_names, comparison_data)
            )

    except Exception as e:
        print(f"  Drivetrain parallel fetch error: {e}")

    # Fallback: try building from existing comparison_data for each car
    fallback_results = []
    for car_name in car_names:
        car_data = comparison_data.get(car_name, {})
        fallback = _fallback_drivetrain_extraction(car_name, car_data)
        if fallback:
            # Attach images from existing data
            if not fallback.get("images"):
                fallback["images"] = []
            images = car_data.get("images", {})
            for category in ["technology", "exterior"]:
                for img in images.get(category, [])[:2]:
                    if isinstance(img, (list, tuple)):
                        fallback["images"].append(img[0])
                    elif isinstance(img, str):
                        fallback["images"].append(img)
                if fallback["images"]:
                    break
            fallback_results.append(fallback)

    return fallback_results


def _fallback_drivetrain_extraction(car_name: str, car_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback extraction from existing comparison data if Gemini fails.
    """
    drivetrain_data = {
        "car_name": car_name,
        "features": [],
        "explanations": [],
        "images": [],
        "highlight_keywords": [],
        "system_name": "Intelligent 4WD",
        "intro_text": ""
    }

    # Try to extract what we can from existing data
    off_road = car_data.get("off_road", "")
    if off_road and off_road not in ["N/A", "Not Available", "-", ""]:
        drivetrain_data["features"].append({
            "name": "Off-Road Capability",
            "car_value": off_road,
            "conventional_value": "Basic off-road"
        })

    ground_clearance = car_data.get("ground_clearance", "")
    if ground_clearance and ground_clearance not in ["N/A", "Not Available", "-", ""]:
        drivetrain_data["features"].append({
            "name": "Ground Clearance",
            "car_value": ground_clearance,
            "conventional_value": "150-180 mm"
        })

    stability = car_data.get("stability", "")
    if stability and stability not in ["N/A", "Not Available", "-", ""]:
        drivetrain_data["features"].append({
            "name": "Stability Control",
            "car_value": stability,
            "conventional_value": "Basic ESC"
        })

    if drivetrain_data["features"]:
        drivetrain_data["intro_text"] = f"The {car_name} offers capable off-road performance with features designed to maximize traction and stability across various terrains."
        return drivetrain_data

    return None


def generate_summary_comparison_section(
    summary_data: Dict[str, Any],
    car_names: List[str],
    page_num: int = 20
) -> str:
    """
    Generate summary comparison section showing features available/not available in each car.

    Args:
        summary_data: Dict with 'features_not_in_car1' and 'features_in_car1_only' keys
        car_names: List of car names being compared
        page_num: Page number for footer

    Returns:
        HTML string for summary comparison section
    """
    if not summary_data or len(car_names) < 2:
        return ""

    car1 = car_names[0]
    car2 = car_names[1]

    # Get feature lists
    features_not_in_car1 = summary_data.get("features_not_in_car1", {})
    features_in_car1_only = summary_data.get("features_in_car1_only", {})

    def build_two_column_categories(feature_dict: Dict[str, List[str]], icon: str) -> str:
        """Build two-column layout for categories."""
        categories = list(feature_dict.keys())
        if not categories:
            return '<p class="no-features">No significant differences found</p>'

        # Split categories into two columns
        mid = (len(categories) + 1) // 2
        left_cats = categories[:mid]
        right_cats = categories[mid:]

        def build_column(cats):
            html = ""
            for cat in cats:
                items = feature_dict.get(cat, [])
                if items:
                    items_html = "".join([f'<li>{icon}&nbsp;&nbsp;{item}</li>' for item in items])
                    html += f'''
                    <div class="summary-category">
                        <h4 class="category-title">{cat}</h4>
                        <ul class="feature-list">
                            {items_html}
                        </ul>
                    </div>
                    '''
            return html

        left_html = build_column(left_cats)
        right_html = build_column(right_cats)

        return f'''
        <div class="two-column-grid">
            <div class="column-left">{left_html}</div>
            <div class="column-right">{right_html}</div>
        </div>
        '''

    # Build sections
    not_available_content = build_two_column_categories(features_not_in_car1, "-")
    available_content = build_two_column_categories(features_in_car1_only, "+")

    html = f'''
    <div class="summary-comparison-page" id="summary-section">
        <div class="summary-comp-header">
            <h1 class="summary-comp-title">FEATURE COMPARISION | <span class="highlight">SUMMARY</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="summary-comp-logo">
        </div>

        <div class="summary-comp-content">
            <!-- Features NOT in Car1 but Present in Car2 -->
            <div class="summary-section">
                <h2 class="section-title not-available-title">Features Not Available in {car1} but Present in {car2}:</h2>
                <div class="section-box">
                    {not_available_content}
                </div>
            </div>

            <!-- Features IN Car1 but NOT in Car2 -->
            <div class="summary-section">
                <h2 class="section-title available-title">Features Available in {car1} but not present in {car2}:</h2>
                <div class="section-box">
                    {available_content}
                </div>
            </div>
        </div>

        <div class="summary-comp-footer">
        </div>
    </div>
    '''

    return html


def generate_image_gallery_section(
    title: str,
    comparison_data: Dict[str, Any],
    image_category: str,
    section_id: str = ""
) -> str:
    """
    Generate an image gallery section for a specific category.

    Args:
        title: Section title (e.g., "Exterior Highlights")
        comparison_data: Dict mapping car names to their scraped data
        image_category: Category key in images dict ("exterior", "interior", etc.)
        section_id: Optional HTML id for the section

    Returns:
        HTML string for image gallery section
    """
    # Collect all images from all cars for this category
    all_images = []

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            images = car_data.get("images") or {}
            category_images = images.get(image_category, [])

            # Handle multiple formats: list, tuple, or string
            for img_item in category_images:
                img_url = None
                feature_caption = image_category.title()

                if isinstance(img_item, (list, tuple)) and len(img_item) >= 1:
                    # Format: [url, caption] or (url, caption)
                    img_url = img_item[0]
                    if len(img_item) >= 2:
                        feature_caption = img_item[1]
                elif isinstance(img_item, str):
                    # Fallback for simple URL format
                    img_url = img_item

                # Add all valid image URLs
                if img_url and isinstance(img_url, str):
                    all_images.append({
                        "url": img_url,
                        "feature": feature_caption,  # e.g., "Headlights"
                        "car_name": car_name,        # e.g., "Mahindra Thar"
                        "alt": f"{car_name} {feature_caption}"
                    })

    if not all_images:
        return ""  # Don't show section if no images

    # Generate image grid
    images_html = ""
    for img_data in all_images[:12]:  # Max 12 images per section
        images_html += f'''
        <div class="gallery-item">
            <img src="{img_data['url']}" alt="{img_data['alt']}"
                 onerror="this.parentElement.style.display='none'">
            <div class="gallery-feature">{img_data['feature']}</div>
            <div class="gallery-car-name">{img_data['car_name']}</div>
        </div>
        '''

    id_attr = f'id="{section_id}"' if section_id else ""

    html = f'''
    <div class="content image-gallery-section" {id_attr}>
        <div class="section-header">
            <div class="icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                </svg>
            </div>
            <h2>{title}</h2>
        </div>
        <div class="image-gallery">
            {images_html}
        </div>
    </div>
    '''

    return html


def get_image_section_styles() -> str:
    """
    Returns CSS styles for image sections.
    """
    return '''
    /* ========================================
       COVER PAGE STYLES
       ======================================== */
    .cover-page {
        width: 100%;
        height: 100vh;
        min-height: 700px;
        background: #f5f5f5;
        position: relative;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        padding: 60px;
        box-sizing: border-box;
        page-break-after: always;
        break-after: page;
    }

    .cover-geometric-pattern {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        z-index: 1;
    }

    .cover-geometric-pattern svg {
        width: 100%;
        height: 100%;
    }

    .cover-logo {
        position: absolute;
        top: 40px;
        right: 60px;
        z-index: 10;
    }

    .cover-logo img {
        height: 28px;
        width: auto;
        filter: brightness(0);
    }

    .cover-content {
        position: relative;
        z-index: 10;
        text-align: right;
        padding-right: 20px;
    }

    .cover-title {
        font-size: 38px;
        font-weight: 800;
        color: #1a1a1a;
        margin: 0 0 10px 0;
        letter-spacing: 1px;
        line-height: 1.2;
    }

    .cover-subtitle {
        font-size: 32px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0 0 30px 0;
        letter-spacing: 0.5px;
        line-height: 1.3;
    }

    .cover-date {
        font-size: 16px;
        font-weight: 500;
        color: #0066cc;
        margin: 0;
    }

    /* ========================================
       HERO IMAGE PAGE STYLES
       ======================================== */
    .hero-image-page {
        width: 100%;
        height: 100vh;
        min-height: 700px;
        background: #ffffff;
        position: relative;
        display: flex;
        flex-direction: column;
        page-break-after: always;
        break-after: page;
        box-sizing: border-box;
    }

    .hero-page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 30px 50px;
        border-bottom: none;
    }

    .hero-page-title {
        font-size: 24px;
        font-weight: 400;
        color: #333;
        margin: 0;
        letter-spacing: 1px;
    }

    .hero-page-title .highlight {
        color: #0066cc;
        font-weight: 600;
    }

    .hero-page-logo {
        height: 24px;
        width: auto;
        filter: brightness(0);
    }

    .hero-image-container {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px 50px;
        overflow: hidden;
    }

    .hero-full-image {
        max-width: 100%;
        max-height: 100%;
        width: auto;
        height: auto;
        object-fit: contain;
    }

    .hero-page-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 20px 50px 30px;
        border-top: 4px solid #1a1a1a;
        margin: 0 50px;
    }

    .hero-page-number {
        font-size: 14px;
        font-weight: 500;
        color: #666;
    }

    /* Image Gallery Section Styles */
    .image-gallery-section {
        margin-top: 40px;
    }

    .image-gallery {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 25px;
        padding: 20px 0;
    }

    .gallery-item {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        cursor: pointer;
    }

    .gallery-item:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    }

    .gallery-item img {
        width: 100%;
        height: 200px;
        object-fit: cover;
        display: block;
    }

    .gallery-feature {
        padding: 12px 15px 8px 15px;
        text-align: center;
        font-size: 13px;
        font-weight: 700;
        color: #1c2a39;
        background: #f8f9fa;
        line-height: 1.3;
    }

    .gallery-car-name {
        padding: 0 15px 12px 15px;
        text-align: center;
        font-size: 11px;
        font-weight: 500;
        color: #6c757d;
        background: #f8f9fa;
    }

    /* ========================================
       DRIVETRAIN COMPARISON PAGE STYLES
       ======================================== */
    .drivetrain-page {
        width: 100%;
        min-height: 100vh;
        background: #ffffff;
        position: relative;
        display: flex;
        flex-direction: column;
        page-break-after: always;
        break-after: page;
        box-sizing: border-box;
        padding: 0;
    }

    .drivetrain-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 25px 40px;
        border-bottom: 3px solid #cc0000;
    }

    .drivetrain-title {
        font-size: 26px;
        font-weight: 400;
        color: #333;
        margin: 0;
        letter-spacing: 1px;
    }

    .drivetrain-title .highlight {
        color: #0066cc;
        font-weight: 600;
        text-decoration: underline;
    }

    .drivetrain-logo {
        height: 24px;
        width: auto;
        filter: brightness(0);
    }

    .drivetrain-content {
        flex: 1;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 30px;
        padding: 30px 40px;
    }

    .drivetrain-left {
        display: flex;
        flex-direction: column;
        gap: 20px;
    }

    .drivetrain-intro {
        font-size: 14px;
        line-height: 1.7;
        color: #333;
        text-decoration: underline;
    }

    .drivetrain-intro .highlight-green {
        background: #90EE90;
        padding: 2px 4px;
        text-decoration: none;
    }

    .drivetrain-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }

    .drivetrain-table th {
        padding: 12px 15px;
        text-align: left;
        font-weight: 600;
        border: 1px solid #dee2e6;
    }

    .drivetrain-table th.feature-header {
        background: #d4a574;
        color: #333;
        width: 30%;
    }

    .drivetrain-table th.car-header {
        background: #d4a574;
        color: #333;
        width: 35%;
    }

    .drivetrain-table th.conventional-header {
        background: #e9ecef;
        color: #333;
        width: 35%;
    }

    .drivetrain-table td {
        padding: 10px 15px;
        border: 1px solid #dee2e6;
        vertical-align: middle;
    }

    .drivetrain-table td.feature-name {
        font-weight: 600;
        background: #f8f9fa;
    }

    .drivetrain-table td.feature-car {
        background: #fff;
    }

    .drivetrain-table td.feature-conventional {
        background: #f8f9fa;
        color: #666;
    }

    .drivetrain-explanations {
        list-style-type: lower-alpha;
        padding-left: 20px;
        font-size: 13px;
        line-height: 1.8;
        color: #333;
    }

    .drivetrain-explanations li {
        margin-bottom: 8px;
    }

    .drivetrain-explanations .explanation-title {
        font-weight: 600;
        text-decoration: underline;
    }

    .drivetrain-right {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }

    .drivetrain-image {
        flex: 1;
        border-radius: 8px;
        overflow: hidden;
    }

    .drivetrain-image img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .drivetrain-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 15px 40px 20px;
        border-top: 4px solid #1a1a1a;
        margin: 0 40px;
    }

    .drivetrain-page-number {
        font-size: 13px;
        font-weight: 500;
        color: #666;
    }

    /* Print Styles */
    @media print {
        .cover-page {
            page-break-after: always !important;
            break-after: page !important;
            height: 100vh !important;
            min-height: 100vh !important;
        }

        .hero-image-page {
            page-break-after: always !important;
            break-after: page !important;
            height: 100vh !important;
            min-height: 100vh !important;
        }

        .hero-full-image {
            max-width: 90% !important;
            max-height: 70vh !important;
        }

        .image-gallery {
            display: grid !important;
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 10px !important;
            page-break-inside: auto !important;
        }

        .gallery-item {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            margin-bottom: 10px !important;
            box-shadow: none !important;
            border: 1px solid #ddd !important;
        }

        .gallery-item:nth-child(6n) {
            page-break-after: always !important;
            break-after: page !important;
        }

        .gallery-item img {
            width: 100% !important;
            height: 180px !important;
            max-height: 180px !important;
            object-fit: contain !important;
            display: block;
            margin: 0 auto;
            background: #f8f9fa;
        }

        .image-gallery-section {
            page-break-before: auto;
            page-break-after: auto;
            page-break-inside: auto;
            break-before: auto;
            break-after: auto;
            break-inside: auto;
            margin-bottom: 0;
        }

        .section-header {
            page-break-after: avoid;
            break-after: avoid;
        }

        .gallery-feature,
        .gallery-car-name {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            text-align: center;
            font-size: 10px !important;
            padding: 6px 8px !important;
        }

        .spec-page,
        .feature-page {
            page-break-after: always !important;
            break-after: page !important;
        }
    }

    /* ========================================
       TECHNICAL SPECIFICATION PAGE STYLES
       ======================================== */
    .spec-page,
    .feature-page {
        width: 100%;
        min-height: 100vh;
        background: #ffffff;
        position: relative;
        display: flex;
        flex-direction: column;
        page-break-after: always;
        break-after: page;
        box-sizing: border-box;
        padding: 0;
    }

    .spec-page-header,
    .feature-page-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 25px 40px;
        border-bottom: 3px solid #cc0000;
    }

    .spec-page-title,
    .feature-page-title {
        font-size: 26px;
        font-weight: 400;
        color: #333;
        margin: 0;
        letter-spacing: 1px;
    }

    .spec-page-title .highlight,
    .feature-page-title .highlight {
        color: #0066cc;
        font-weight: 600;
        text-decoration: underline;
    }

    .spec-page-logo,
    .feature-page-logo {
        height: 24px;
        width: auto;
        filter: brightness(0);
    }

    .spec-legend,
    .feature-legend {
        display: flex;
        justify-content: flex-end;
        gap: 30px;
        padding: 15px 40px;
        background: #fff;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        color: #666;
    }

    .legend-color {
        width: 20px;
        height: 14px;
        border-radius: 2px;
    }

    .legend-color.superior {
        background: #c8f7c5;
    }

    .legend-color.inferior {
        background: #ffcdd2;
    }

    .spec-table-container,
    .feature-table-container {
        flex: 1;
        padding: 0 40px 20px;
        overflow-x: auto;
    }

    .spec-table,
    .feature-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
    }

    .spec-table thead tr,
    .feature-table thead tr {
        background: #2E3B4E;
    }

    .spec-table th,
    .feature-table th {
        padding: 12px 10px;
        text-align: center;
        font-weight: 600;
        color: #fff;
        border: 1px solid #dee2e6;
        font-size: 13px;
    }

    .spec-table th:first-child,
    .spec-table th:nth-child(2),
    .feature-table th.cat-header,
    .feature-table th.desc-header,
    .feature-table th.feature-header {
        text-align: left;
        background: #495057;
    }

    .spec-table td,
    .feature-table td {
        padding: 10px 12px;
        border: 1px solid #dee2e6;
        vertical-align: middle;
        text-align: center;
    }

    .spec-table td.cat-cell,
    .feature-table td.cat-cell {
        font-weight: 700;
        text-align: left;
        background: #f8f9fa;
        color: #1a1a1a;
        width: 120px;
        border-bottom: 1px solid #adb5bd;
    }

    .spec-table td.param-cell,
    .feature-table td.desc-cell {
        font-weight: 600;
        text-align: left;
        color: #333;
        width: 150px;
    }

    .feature-table td.feature-cell {
        text-align: left;
        color: #333;
        width: 250px;
    }

    .spec-table td.superior-cell,
    .feature-table td.superior-cell {
        background: #c8f7c5;
    }

    .spec-table td.inferior-cell,
    .feature-table td.inferior-cell {
        background: #ffcdd2;
    }

    /* Cell-level coloring — only the car's value cell gets colored */
    .feature-table td.car-value-cell.cell-superior {
        background: #c8f7c5 !important;
    }

    .feature-table td.car-value-cell.cell-inferior {
        background: #ffcdd2 !important;
    }

    /* Single car value column */
    .feature-table th.car-value-header {
        text-align: center;
        background: #2E3B4E;
        color: #fff;
        min-width: 160px;
        font-size: 13px;
    }

    .feature-table td.car-value-cell {
        text-align: center;
        padding: 8px 12px;
        min-width: 160px;
        font-size: 12px;
    }

    .check-mark {
        color: #28a745;
        font-weight: bold;
        font-size: 16px;
    }

    .x-mark {
        color: #dc3545;
        font-weight: bold;
        font-size: 16px;
    }

    .value-text {
        color: #1a1a1a;
        font-weight: 500;
        font-size: 11px;
        line-height: 1.3;
    }

    .feature-table td.value-cell {
        text-align: center;
        background: #ffffff;
        font-size: 11px;
        padding: 8px 6px;
    }

    .feature-table td.superior-cell .check-mark {
        font-size: 18px;
    }

    .feature-table td.inferior-cell .x-mark {
        font-size: 18px;
    }

    .spec-page-footer,
    .feature-page-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 15px 40px 20px;
        border-top: 4px solid #1a1a1a;
        margin: 0 40px;
    }

    .spec-page-number,
    .feature-page-number {
        font-size: 13px;
        font-weight: 500;
        color: #666;
    }

    /* Mobile Responsive */
    @media (max-width: 768px) {
        .cover-page {
            padding: 30px;
            height: auto;
            min-height: 100vh;
        }

        .cover-logo {
            top: 20px;
            right: 30px;
        }

        .cover-logo img {
            height: 20px;
        }

        .cover-title {
            font-size: 24px;
        }

        .cover-subtitle {
            font-size: 20px;
        }

        .hero-page-header {
            padding: 20px 30px;
        }

        .hero-page-title {
            font-size: 16px;
        }

        .hero-image-container {
            padding: 20px 30px;
        }

        .hero-page-footer {
            margin: 0 30px;
            padding: 15px 30px 20px;
        }

        .image-gallery {
            grid-template-columns: 1fr;
            gap: 15px;
        }

        .gallery-item img {
            height: 180px;
        }
    }

    /* ========================================
       SUMMARY COMPARISON PAGE STYLES
       ======================================== */
    .summary-comparison-page {
        width: 100%;
        min-height: 100vh;
        background: #ffffff;
        position: relative;
        display: flex;
        flex-direction: column;
        page-break-after: always;
        break-after: page;
        box-sizing: border-box;
    }

    .summary-comp-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 40px;
        border-bottom: none;
    }

    .summary-comp-title {
        font-size: 28px;
        font-weight: 400;
        color: #333;
        margin: 0;
        letter-spacing: 1px;
    }

    .summary-comp-title .highlight {
        color: #0066cc;
        font-weight: 600;
        text-decoration: underline;
    }

    .summary-comp-logo {
        height: 28px;
        width: auto;
        filter: brightness(0);
    }

    .summary-comp-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 25px;
        padding: 20px 40px;
    }

    .summary-section {
        display: flex;
        flex-direction: column;
    }

    .section-title {
        font-size: 16px;
        font-weight: 400;
        margin: 0 0 10px 0;
        text-decoration: underline;
        text-underline-offset: 4px;
    }

    .section-title.not-available-title {
        color: #cc0000;
    }

    .section-title.available-title {
        color: #28a745;
    }

    .section-box {
        border: 1px solid #333;
        background: #fff;
        padding: 20px 25px;
    }

    .two-column-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 30px;
    }

    .column-left,
    .column-right {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }

    .summary-category {
        margin-bottom: 0;
    }

    .category-title {
        font-size: 12px;
        font-weight: 700;
        color: #333;
        margin: 0 0 8px 0;
        text-decoration: underline;
        text-underline-offset: 3px;
    }

    .feature-list {
        list-style: none;
        margin: 0;
        padding: 0;
    }

    .feature-list li {
        font-size: 11px;
        color: #333;
        padding: 3px 0;
        line-height: 1.5;
    }

    .no-features {
        font-size: 13px;
        color: #6c757d;
        text-align: center;
        padding: 20px;
        font-style: italic;
    }

    .summary-comp-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 15px 40px 20px;
    }

    .summary-comp-page-number {
        font-size: 13px;
        font-weight: 500;
        color: #666;
    }

    @media print {
        .summary-comparison-page {
            page-break-after: always !important;
            break-after: page !important;
            min-height: 100vh !important;
            background: #ffffff !important;
            display: flex !important;
            flex-direction: column !important;
        }

        .summary-comp-header {
            display: flex !important;
            justify-content: space-between !important;
            align-items: center !important;
            padding: 16px 30px !important;
            border-bottom: 2px solid #cc0000 !important;
        }

        .summary-comp-title {
            font-size: 18px !important;
            font-weight: 400 !important;
            color: #333 !important;
            letter-spacing: 0.5px !important;
        }

        .summary-comp-title .highlight {
            color: #0066cc !important;
            font-weight: 600 !important;
            text-decoration: underline !important;
        }

        .summary-comp-logo {
            height: 22px !important;
            width: auto !important;
        }

        .summary-comp-content {
            flex: 1 !important;
            display: flex !important;
            flex-direction: column !important;
            gap: 16px !important;
            padding: 16px 30px !important;
        }

        .summary-section {
            display: flex !important;
            flex-direction: column !important;
        }

        .section-title {
            font-size: 13px !important;
            font-weight: 600 !important;
            margin: 0 0 8px 0 !important;
            text-decoration: underline !important;
        }

        .section-title.not-available-title {
            color: #cc0000 !important;
        }

        .section-title.available-title {
            color: #28a745 !important;
        }

        .section-box {
            border: 1px solid #333 !important;
            background: #fff !important;
            padding: 14px 18px !important;
        }

        .two-column-grid {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 20px !important;
        }

        .column-left,
        .column-right {
            display: flex !important;
            flex-direction: column !important;
            gap: 10px !important;
        }

        .summary-category {
            margin-bottom: 4px !important;
        }

        .category-title {
            font-size: 11px !important;
            font-weight: 700 !important;
            color: #333 !important;
            margin: 0 0 4px 0 !important;
            text-decoration: underline !important;
        }

        .feature-list {
            list-style: none !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        .feature-list li {
            font-size: 10px !important;
            color: #333 !important;
            padding: 2px 0 !important;
            line-height: 1.4 !important;
        }
    }

    @media (max-width: 768px) {
        .summary-comp-content {
            padding: 20px;
        }

        .two-column-grid {
            grid-template-columns: 1fr;
            gap: 15px;
        }

        .summary-comp-header {
            padding: 20px;
        }

        .summary-comp-title {
            font-size: 18px;
        }
    }
    '''
