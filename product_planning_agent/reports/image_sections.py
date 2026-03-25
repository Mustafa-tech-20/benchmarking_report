"""
Image Section Generation for Enhanced Reports
Generates PDF-style image galleries for car comparison reports
"""

import json
from typing import Dict, Any, List
from datetime import datetime


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
            <h2 class="cover-subtitle">PRODUCT PLANNING<br>SOFT REPORT</h2>
            <p class="cover-date">{current_date}</p>
        </div>
    </div>
    '''

    # PAGE 2: Single side-by-side comparison page
    left_name = car_names[0]
    left_img = hero_images[0] if hero_images else ""
    right_cars = list(zip(car_names[1:], hero_images[1:]))

    left_img_tag = (
        f'<img src="{left_img}" alt="{left_name}" class="hero-comparison-img" onerror="this.style.display=\'none\'">'
        if left_img else '<div class="hero-comparison-placeholder"></div>'
    )

    right_panels_html = ""
    for rname, rimg in right_cars:
        img_tag = (
            f'<img src="{rimg}" alt="{rname}" class="hero-comparison-img" onerror="this.style.display=\'none\'">'
            if rimg else '<div class="hero-comparison-placeholder"></div>'
        )
        right_panels_html += f'''
        <div class="hero-comparison-car">
            <div class="hero-comparison-image-wrap">
                {img_tag}
            </div>
            <div class="hero-comparison-label">{rname}</div>
        </div>
        '''

    if not right_panels_html:
        right_panels_html = '<div class="hero-comparison-placeholder"></div>'

    comparison_page = f'''
    <div class="hero-image-page" id="hero-comparison">
        <div class="hero-page-header">
            <h1 class="hero-page-title">VEHICLE COMPARISON | <span class="highlight">PRODUCT PLANNING</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="hero-page-logo">
        </div>
        <div class="hero-comparison-container">
            <div class="hero-comparison-side hero-comparison-left-side">
                <div class="hero-comparison-image-wrap">
                    {left_img_tag}
                </div>
                <div class="hero-comparison-label">{left_name}</div>
            </div>
            <div class="hero-vs-divider">
                <div class="hero-vs-badge">VS</div>
            </div>
            <div class="hero-comparison-side hero-comparison-right-side">
                {right_panels_html}
            </div>
        </div>
        <div class="hero-page-footer"></div>
    </div>
    '''

    return cover_page + comparison_page


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


# ============================================================================
# TECHNICAL SPEC SECTION AND FEATURE LIST COMPARISON
# ============================================================================

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
    # new count features
    "Front Cup Holders":                "count",
    "Rear Cup Holders":                 "count",
    "No of Wireless Charging Pads":     "count",
    "Cup Holder at Tail Door":          "count",
    "Hooks at Tail Door":               "count",
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
    # new spec features
    "Front Door Scuff Material":        "spec",
    "Rear Door Scuff Material":         "spec",
    "Voice Assistant Type":             "spec",
    "Co-Driver Seat Adjustment":        "spec",
    "Power Seat Controls Location":     "spec",
    "Seatbelt Warning":                 "spec",
    "Display Language":                 "spec",
    "Audio Brand":                      "spec",
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
    # New features with accurate scraped data overlap
    "Crash Sensor":                 "vehicle_safety_features",
    "Seatbelt Tongue Holder 2nd Row": "seatbelt_features",
    "Infotainment Touch":           "infotainment_screen",
    "Audio Brand":                  "audio_system",

    # NEW: 18 additional mappings for 70% checklist coverage
    # ADAS Features (6)
    "Adaptive Cruise Control":      "adaptive_cruise_control",
    "Lane Keep Assist":             "lane_keep_assist",
    "Blind Spot Monitor":           "blind_spot_monitor",
    "Automatic Emergency Braking":  "automatic_emergency_braking",
    "360 Degree Camera":            "360_camera",
    "Lane Departure Warning":       "lane_departure_warning",

    # Active Safety (3)
    "Traction Control":             "traction_control",
    "Hill Descent Control":         "hill_descent_control",
    "ABS":                          "abs",

    # Technology & Connectivity (4)
    "Wireless CarPlay":             "wireless_carplay",
    "Wireless Android Auto":        "wireless_carplay",  # Same as wireless CarPlay
    "Heads-Up Display":             "heads_up_display",
    "Wireless Charging":            "wireless_charging",
    "Built-in Navigation":          "built_in_navigation",

    # Comfort & Premium Features (5)
    "Panoramic Sunroof":            "panoramic_sunroof",
    "Heated Front Seats":           "heated_seats",
    "Keyless Entry":                "keyless_entry",
    "Ambient Lighting":             "ambient_lighting",
    "Auto Headlamps":               "auto_headlamps",
}

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
    # ── New categories from reference spec sheets ──────────────────────────
    {
        "category": "Boot & Trunk", "description": "Storage & Boot Utilities",
        "features": ["Trunk Metal Anchor Points", "Trunk Storage Box",
                     "Trunk Subwoofer", "Dashcam Provision",
                     "Cup Holder at Tail Door", "Hooks at Tail Door",
                     "Warning Triangle at Tail Door", "Door Magnetic Strap"]
    },
    {
        "category": "Floor Console", "description": "Armrest & Charging",
        "features": ["Armrest Sliding", "Armrest Soft", "Armrest Storage",
                     "Wireless Charging Front Row", "No of Wireless Charging Pads"]
    },
    {
        "category": "Door & Trim", "description": "Door Panel Details",
        "features": ["Front Door Scuff Material", "Rear Door Scuff Material"]
    },
    {
        "category": "Steering & Voice", "description": "Controls & Voice Assistance",
        "features": ["Voice Recognition Steering Wheel", "Voice Assistant Type",
                     "Multi-language Voice Commands", "Amazon Alexa Voice Assistant",
                     "Active Noise Reduction", "Intelligent Voice Control",
                     "Intelligent Dodge", "Intelligent Parking Assist"]
    },
    {
        "category": "Seats Extended", "description": "Power & Memory",
        "features": ["Co-Driver Seat Adjustment", "Power Seat Controls Location",
                     "Programmable Memory Seat", "Seatbelt Warning",
                     "Seatbelt Tongue Holder 2nd Row", "Crash Sensor"]
    },
    {
        "category": "Technology Extended", "description": "Connectivity & Media",
        "features": ["Infotainment Touch", "Display Language",
                     "Phone Sync Audio", "Bluetooth Hands Free",
                     "AM/FM Radio", "Digital Radio DAB",
                     "Wireless Smartphone Integration"]
    },
    {
        "category": "Branded Audio", "description": "Sound System Details",
        "features": ["Audio Brand", "Dolby Atmos", "Speed Sensing Volume"]
    },
    {
        "category": "Others", "description": "Unique Features",
        "features": ["Transparent Car Bottom Camera", "Car Picnic Table",
                     "Safety Belt Holder 2nd Row", "Front Rear Parking Sensor Radar"]
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
      2. Single Gemini call for up to 10 essential features not in scraped data.
      3. All remaining features default to False — every feature always shown.
    """
    import os
    import json_repair

    def _is_na(val):
        if val is None:
            return True
        return str(val).strip().lower() in ("", "-", "not available", "n/a", "na", "none", "null", "not found")

    # ------------------------------------------------------------------
    # Step 1: resolve each feature from existing scraped data where possible
    # resolved[feat_name] = {car_name: value}
    # Limit to first 100 features total (most important categories first)
    # ------------------------------------------------------------------
    resolved: Dict[str, Dict] = {}
    missing_features: List[Dict] = []  # {"name": str, "category": str, "description": str}

    MAX_FEATURES = 100  # Limit total features to 100
    total_features_processed = 0

    for batch in _FEATURE_BATCHES:
        if total_features_processed >= MAX_FEATURES:
            break  # Stop if we've reached the limit

        for feat_name in batch["features"]:
            if total_features_processed >= MAX_FEATURES:
                break  # Stop if we've reached the limit

            scraped_key = _SCRAPED_KEY_MAP.get(feat_name)
            if scraped_key:
                raw_vals = {cn: comparison_data.get(cn, {}).get(scraped_key) for cn in car_names}
                if not all(_is_na(v) for v in raw_vals.values()):
                    # Normalize raw text → bool/int/short-text based on feature type
                    resolved[feat_name] = {
                        cn: _normalize_scraped_value(feat_name, v)
                        for cn, v in raw_vals.items()
                    }
                    total_features_processed += 1
                    continue
            missing_features.append({
                "name": feat_name,
                "category": batch["category"],
                "description": batch["description"],
            })
            total_features_processed += 1

    print(f"  Feature comparison: {len(resolved)} from scraped data, {len(missing_features)} need search (max 100 total)")

    # ------------------------------------------------------------------
    # Step 2: Custom Search API (1 query per feature) + batch Gemini extraction
    #         (10 features per Gemini call, all batches in parallel)
    # ------------------------------------------------------------------
    import threading
    import concurrent.futures

    gemini_resolved: Dict[str, Dict] = {}

    if missing_features:
        try:
            from benchmarking_agent.core.scraper import (
                google_custom_search, SEARCH_ENGINE_ID,
                call_gemini_simple, GEMINI_WORKERS,
            )

            cars_str = " vs ".join(car_names)
            car1 = car_names[0]
            car2 = car_names[1] if len(car_names) > 1 else "Competitor"

            # ── 2a: one Custom Search query per missing feature ────────────
            print(f"  Running {len(missing_features)} custom search queries...")
            search_results_map: Dict[str, list] = {}

            def _search_feature(feat_info):
                feat_name = feat_info["name"]
                query = f"{cars_str} {feat_name}"
                try:
                    return feat_name, google_custom_search(query, SEARCH_ENGINE_ID, num_results=3)
                except Exception:
                    return feat_name, []

            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
                for fname, results in ex.map(_search_feature, missing_features):
                    search_results_map[fname] = results

            # ── 2b: batch Gemini extraction, 10 features per call, parallel ─
            BATCH_SIZE = 10
            feat_batches = [
                missing_features[i:i + BATCH_SIZE]
                for i in range(0, len(missing_features), BATCH_SIZE)
            ]
            print(f"  {len(feat_batches)} Gemini extraction batches firing in parallel...")

            _lock = threading.Lock()

            def _extract_batch(batch):
                sections = []
                json_lines = []
                for feat_info in batch:
                    feat_name = feat_info["name"]
                    results = search_results_map.get(feat_name, [])
                    section = f"--- FEATURE: {feat_name} ---\n"
                    for i, r in enumerate(results[:3], 1):
                        section += f"[{i}] {r.get('domain', '')}: {r.get('snippet', '')}\n"
                    if not results:
                        section += "(no search results — use training knowledge)\n"
                    sections.append(section)
                    json_lines.append(
                        f'    {{"name": "{feat_name}", "{car1}": <value>, "{car2}": <value>}}'
                    )

                prompt = f"""For {cars_str}, determine each feature's value from the snippets below.

{"".join(sections)}
Rules:
- true / false for yes/no features
- integer for counts (e.g. 2 for cup holders)
- short text ≤20 chars for material/type/brand (e.g. "Leatherette")
- false if feature is absent

Return ONLY valid JSON (no markdown):
{{
  "features": [
{chr(10).join(json_lines)}
  ]
}}"""
                try:
                    text = call_gemini_simple(prompt).strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0]
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0]
                    text = text.strip()
                    if "{" in text and "}" in text:
                        text = text[text.index("{"):text.rindex("}") + 1]
                    result = json_repair.loads(text)
                    # Ensure result is a dict before calling .get()
                    if not isinstance(result, dict):
                        return []
                    features = result.get("features", [])
                    # Ensure we return a list, not a string or other type
                    return features if isinstance(features, list) else []
                except Exception as e:
                    print(f"  Extraction batch error: {e}")
                    return []

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(feat_batches)) as ex:
                future_to_batch = {ex.submit(_extract_batch, b): b for b in feat_batches}
                for future in concurrent.futures.as_completed(future_to_batch):
                    for feat_obj in future.result():
                        name = feat_obj.get("name", "")
                        if name:
                            with _lock:
                                gemini_resolved[name] = {cn: feat_obj.get(cn) for cn in car_names}

            print(f"  Fetched {len(gemini_resolved)} features via search + {len(feat_batches)} Gemini calls")

        except Exception as e:
            print(f"  Feature search/extraction error: {e}")

    # Write resolved feature values back into comparison_data so checklist_transformer can use them
    _extra_prefix = "xfeat_"
    for feat_name, car_vals in {**resolved, **gemini_resolved}.items():
        key = _extra_prefix + feat_name.lower().replace(" ", "_").replace("/", "_").replace(
            "-", "_").replace("(", "").replace(")", "").replace(".", "").replace("&", "_")
        for cn, val in car_vals.items():
            if cn in comparison_data:
                comparison_data[cn][key] = val

    # ------------------------------------------------------------------
    # Step 3: assemble into ordered category structure from _FEATURE_BATCHES
    # Always include every feature — default to False if no data available
    # ------------------------------------------------------------------
    cat_map: Dict[str, List] = {}
    for batch in _FEATURE_BATCHES:
        desc_feats = []
        for feat_name in batch["features"]:
            vals = resolved.get(feat_name) or gemini_resolved.get(feat_name)
            if not vals:
                vals = {cn: False for cn in car_names}
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
                # Guard against dict/list values (e.g. from PDF extraction)
                if isinstance(value, (dict, list)):
                    value = "-"
                elif value in EMPTY_VALUES:
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
            <h1 class="spec-page-title">TECHNICAL SPECIFICATION | <span class="highlight">PRODUCT PLANNING</span></h1>
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
            <h1 class="feature-page-title">FEATURE LIST COMPARISON | <span class="highlight">PRODUCT PLANNING {car_names_title}</span></h1>
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


def _extract_lifecycle_data(car_name: str, car_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract lifecycle timeline data using Gemini for complete 5-year timeline.

    Args:
        car_name: Name of the car
        car_data: Already scraped car data from comparison_data

    Returns:
        Dict with timeline_years, interventions, sales_data, and insights
    """
    # Extract complete lifecycle timeline using Gemini
    from product_planning_agent.extraction.lifecycle_timeline import extract_complete_lifecycle_timeline

    print(f"  Extracting 5-year lifecycle timeline for {car_name}...")
    lifecycle_timeline = extract_complete_lifecycle_timeline(car_name)

    timeline_years = lifecycle_timeline.get('timeline_years', [])
    interventions = lifecycle_timeline.get('interventions', [])

    # Generate strategic insights using existing car data
    variant_walk = car_data.get('variant_walk', {})
    insights = []
    try:
        from vertexai.generative_models import GenerativeModel
        from product_planning_agent.config import GEMINI_MAIN_MODEL

        # Build context from existing data
        context = f"""Car: {car_name}
Price Range: {car_data.get('price_range', 'N/A')}
User Rating: {car_data.get('user_rating', 'N/A')}
Seating: {car_data.get('seating_capacity', 'N/A')}
Safety Rating: {car_data.get('ncap_rating', 'N/A')}
Number of Interventions: {len(interventions)}
"""

        prompt = f"""Based on this vehicle data for {car_name}, provide 3 strategic insights about its market performance and positioning:

{context}

Return ONLY a JSON array of 3 insights (each 15-25 words):
{{"insights": ["insight 1", "insight 2", "insight 3"]}}

Focus on:
1. Product intervention strategy helping sales (mention "Regular Product interventions")
2. Revenue contribution and market significance
3. Future strategy and market share goals

Return ONLY valid JSON, no markdown."""

        model = GenerativeModel(GEMINI_MAIN_MODEL)
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Clean JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()

        import json
        data = json.loads(text)
        insights = data.get("insights", [])

    except Exception as e:
        print(f"  Note: Could not generate insights for {car_name}: {e}")
        insights = [
            f"Regular Product interventions has been consistently helping {car_name} to improve its sales",
            f"{car_name} is significant in revenue contribution for the manufacturer's portfolio",
            f"With updates, aims to sustain sales volumes in competitive market & leverage for maintaining market share"
        ]

    return {
        "timeline_years": timeline_years,
        "interventions": interventions,
        "sales_data": {
            "monthly": [],  # Could be populated from existing sales data if available
            "peak": {"month": "", "sales": 0, "market_share": 0},
            "current": {"month": "", "sales": 0, "market_share": 0}
        },
        "insights": insights
    }


def generate_lifecycle_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate lifecycle timeline and sales performance pages for each car.

    Args:
        comparison_data: Dict mapping car names to their scraped data

    Returns:
        HTML string with lifecycle pages for all cars
    """
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data
                 and not name.strip().upper().startswith("CODE:")]

    if not car_names:
        return ""

    pages_html = ""

    for car_name in car_names:
        print(f"Generating lifecycle data for {car_name}...")
        car_data = comparison_data.get(car_name, {})
        lifecycle_data = _extract_lifecycle_data(car_name, car_data)

        # Generate timeline table
        interventions = lifecycle_data.get("interventions", [])
        timeline_years = lifecycle_data.get("timeline_years", [])

        # Use timeline_years to show ALL 5 years (even if no interventions)
        if not timeline_years:
            # Fallback: create years from interventions
            years_from_interventions = set()
            for intervention in interventions:
                year = intervention.get("year")
                if year:
                    years_from_interventions.add(year)
            timeline_years = sorted(list(years_from_interventions)) if years_from_interventions else [2023]

        # Group interventions by year
        interventions_by_year = {}
        for intervention in interventions:
            year = intervention.get("year")
            if year not in interventions_by_year:
                interventions_by_year[year] = []
            interventions_by_year[year].append(intervention)

        # Generate year headers for ALL timeline years
        year_headers = ""
        for year in timeline_years:
            year_headers += f'<th colspan="4" class="year-header">CY {year}</th>'

        # Generate quarter headers
        quarter_headers = ""
        for year in timeline_years:
            quarter_headers += '<th class="quarter-header">Q1</th><th class="quarter-header">Q2</th><th class="quarter-header">Q3</th><th class="quarter-header">Q4</th>'

        # Generate intervention cells
        intervention_cells = '<td class="intervention-label">Intervention</td>'
        changes_cells = '<td class="changes-label">Key Specs/<br>Changes</td>'

        # Create a grid for ALL quarters across ALL 5 years
        total_quarters = len(timeline_years) * 4
        intervention_grid = [''] * total_quarters
        changes_grid = [''] * total_quarters

        # Fill in interventions for each year
        for year_idx, year in enumerate(timeline_years):
            year_interventions = interventions_by_year.get(year, [])

            for intervention in year_interventions:
                quarter = intervention.get("quarter", "Q1")
                q_num = int(quarter[1]) - 1 if quarter.startswith('Q') else 0  # Q1=0, Q2=1, Q3=2, Q4=3
                cell_idx = (year_idx * 4) + q_num

                title = intervention.get("title", "Update")
                date = intervention.get("date", "")
                changes = intervention.get("changes", [])

                intervention_grid[cell_idx] = f'''
                    <div class="intervention-marker">
                        <div class="marker-pin"></div>
                        <div class="marker-date">{date}</div>
                        <div class="marker-title">{title}</div>
                    </div>
                '''

                changes_html = '<br>'.join([f"- {change}" for change in changes[:4]])
                changes_grid[cell_idx] = f'<div class="changes-content">{changes_html}</div>'

        # Build cells
        for cell in intervention_grid:
            if cell:
                intervention_cells += f'<td class="intervention-cell active">{cell}</td>'
            else:
                intervention_cells += '<td class="intervention-cell"></td>'

        for cell in changes_grid:
            if cell:
                changes_cells += f'<td class="changes-cell active">{cell}</td>'
            else:
                changes_cells += '<td class="changes-cell"></td>'

        # Generate insights
        insights = lifecycle_data.get("insights", [])
        insights_html = ""
        for insight in insights:
            insights_html += f'<li>{insight}</li>'

        # Generate sales chart data (placeholder for now)
        sales_data = lifecycle_data.get("sales_data", {})

        page_html = f'''
    <div class="lifecycle-page" id="lifecycle-{car_name.replace(' ', '-').lower()}">
        <div class="lifecycle-header">
            <h1 class="lifecycle-title">Journey of {car_name} so far</h1>
            <h2 class="lifecycle-subtitle">Life cycle of {car_name.split()[-1]}</h2>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="lifecycle-logo">
        </div>

        <div class="lifecycle-content">
            <div class="timeline-table-wrapper">
                <table class="timeline-table">
                    <thead>
                        <tr class="year-row">
                            <th class="label-cell"></th>
                            {year_headers}
                        </tr>
                        <tr class="quarter-row">
                            <th class="label-cell"></th>
                            {quarter_headers}
                        </tr>
                    </thead>
                    <tbody>
                        <tr class="intervention-row">
                            {intervention_cells}
                        </tr>
                        <tr class="changes-row">
                            {changes_cells}
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="sales-chart-section">
                <h3 class="chart-title">{car_name.split()[-1]} sales performance</h3>
                <div class="chart-container" style="position: relative; height: 400px; width: 100%; margin: 20px 0;">
                    <canvas id="salesChart-{car_name.replace(' ', '-').lower()}"></canvas>
                </div>
                <div class="chart-legend">
                    <span class="legend-item"><span class="legend-bar" style="display: inline-block; width: 30px; height: 12px; background: #2E3B4E; margin-right: 5px;"></span> Sales no.s</span>
                    <span class="legend-item"><span class="legend-line" style="display: inline-block; width: 30px; height: 3px; background: #ff6b35; margin: 0 5px;"></span> Market Share in segment</span>
                </div>
            </div>

            <script>
            (function() {{
                const ctx = document.getElementById('salesChart-{car_name.replace(' ', '-').lower()}');
                if (ctx) {{
                    // Generate monthly labels from launch year to present
                    const months = {json.dumps([f"Oct'21", "Nov'21", "Dec'21", "Jan'22", "Feb'22", "Mar'22", "Apr'22", "May'22", "Jun'22", "Jul'22", "Aug'22", "Sep'22", "Oct'22", "Nov'22", "Dec'22", "Jan'23", "Feb'23", "Mar'23", "Apr'23", "May'23", "Jun'23", "Jul'23", "Aug'23", "Sep'23", "Oct'23", "Nov'23", "Dec'23", "Jan'24", "Feb'24", "Mar'24", "Apr'24", "May'24", "Jun'24", "Jul'24", "Aug'24", "Sep'24", "Oct'24", "Nov'24", "Dec'24", "Jan'25", "Feb'25", "Mar'25", "Apr'25", "May'25", "Jun'25", "Jul'25", "Aug'25", "Sep'25", "Oct'25", "Nov'25"])};

                    // Generate sample sales data (will be replaced with real data)
                    const salesData = months.map((m, i) => Math.floor(8000 + Math.random() * 12000 + Math.sin(i/6) * 5000));
                    const marketShare = months.map((m, i) => 20 + Math.sin(i/8) * 10 + Math.random() * 5);

                    new Chart(ctx, {{
                        type: 'bar',
                        data: {{
                            labels: months,
                            datasets: [
                                {{
                                    label: 'Sales no.s',
                                    data: salesData,
                                    backgroundColor: '#2E3B4E',
                                    yAxisID: 'y',
                                    order: 2
                                }},
                                {{
                                    label: 'Market Share in segment',
                                    data: marketShare,
                                    type: 'line',
                                    borderColor: '#ff6b35',
                                    backgroundColor: '#ff6b35',
                                    borderWidth: 3,
                                    pointRadius: 0,
                                    yAxisID: 'y1',
                                    order: 1,
                                    tension: 0.3
                                }}
                            ]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            interaction: {{
                                mode: 'index',
                                intersect: false
                            }},
                            plugins: {{
                                legend: {{
                                    display: false
                                }},
                                tooltip: {{
                                    callbacks: {{
                                        label: function(context) {{
                                            let label = context.dataset.label || '';
                                            if (label) {{
                                                label += ': ';
                                            }}
                                            if (context.parsed.y !== null) {{
                                                label += context.datasetIndex === 0 ? context.parsed.y.toLocaleString() : context.parsed.y.toFixed(1) + '%';
                                            }}
                                            return label;
                                        }}
                                    }}
                                }}
                            }},
                            scales: {{
                                x: {{
                                    grid: {{
                                        display: false
                                    }},
                                    ticks: {{
                                        maxRotation: 90,
                                        minRotation: 90,
                                        font: {{
                                            size: 9
                                        }}
                                    }}
                                }},
                                y: {{
                                    type: 'linear',
                                    display: true,
                                    position: 'left',
                                    title: {{
                                        display: true,
                                        text: 'Monthly Sales',
                                        font: {{
                                            size: 11
                                        }}
                                    }},
                                    ticks: {{
                                        callback: function(value) {{
                                            return value.toLocaleString();
                                        }}
                                    }}
                                }},
                                y1: {{
                                    type: 'linear',
                                    display: true,
                                    position: 'right',
                                    title: {{
                                        display: true,
                                        text: 'Market Share (%)',
                                        font: {{
                                            size: 11
                                        }}
                                    }},
                                    grid: {{
                                        drawOnChartArea: false
                                    }},
                                    ticks: {{
                                        callback: function(value) {{
                                            return value.toFixed(0) + '%';
                                        }}
                                    }},
                                    min: 0,
                                    max: 50
                                }}
                            }}
                        }}
                    }});
                }}
            }})();
            </script>

            <div class="insights-section">
                <ul class="insights-list">
                    {insights_html}
                </ul>
            </div>
        </div>

        <div class="lifecycle-footer"></div>
    </div>
        '''

        pages_html += page_html

    return pages_html


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
       HERO COMPARISON PAGE STYLES
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
        padding: 24px 50px;
    }

    .hero-page-title {
        font-size: 22px;
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

    .hero-comparison-container {
        flex: 1;
        display: flex;
        align-items: stretch;
        overflow: hidden;
        min-height: 0;
    }

    .hero-comparison-side {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        min-width: 0;
    }

    .hero-comparison-image-wrap {
        flex: 1;
        overflow: hidden;
        position: relative;
        min-height: 0;
    }

    .hero-comparison-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }

    .hero-comparison-label {
        padding: 14px 20px;
        text-align: center;
        font-size: 16px;
        font-weight: 700;
        color: #1a1a1a;
        background: #f0f0f0;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        flex-shrink: 0;
    }

    .hero-comparison-left-side .hero-comparison-label {
        background: #1a1a1a;
        color: #ffffff;
    }

    .hero-comparison-right-side {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        min-width: 0;
    }

    .hero-comparison-car {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        min-height: 0;
    }

    .hero-vs-divider {
        width: 56px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: #1a1a1a;
        flex-shrink: 0;
        z-index: 5;
    }

    .hero-vs-badge {
        width: 44px;
        height: 44px;
        background: #cc0000;
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 1px;
    }

    .hero-comparison-placeholder {
        width: 100%;
        height: 100%;
        background: #e8e8e8;
    }

    .hero-page-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 16px 50px 24px;
        border-top: 4px solid #1a1a1a;
        margin: 0 50px;
        flex-shrink: 0;
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

    /* Print Styles for Images */
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

        .hero-comparison-img {
            width: 100% !important;
            height: 100% !important;
            object-fit: cover !important;
        }

        .spec-page,
        .feature-page {
            page-break-after: always !important;
            break-after: page !important;
        }

        .spec-table,
        .feature-table {
            font-size: 10px !important;
        }

        .spec-table th,
        .feature-table th {
            padding: 8px 6px !important;
            font-size: 11px !important;
        }

        .spec-table td,
        .feature-table td {
            padding: 6px 8px !important;
        }

        .hero-section {
            page-break-after: always;
            margin: 0;
            padding: 40px 20px;
            break-after: page;
        }

        .hero-car-card {
            page-break-inside: avoid;
            break-inside: avoid;
        }

        .hero-car-card img {
            width: 100% !important;
            height: auto !important;
            max-height: 200px !important;
            object-fit: contain !important;
            display: block;
            margin: 0 auto;
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

        /* Force page break after every 6 items (2x3 grid) */
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
    }

    /* ========================================
       LIFECYCLE / JOURNEY PAGE STYLES
       ======================================== */
    .lifecycle-page {
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

    .lifecycle-header {
        position: relative;
        padding: 30px 40px 20px;
        border-bottom: 3px solid #cc0000;
    }

    .lifecycle-title {
        font-size: 32px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0 0 5px 0;
        padding-left: 20px;
        border-left: 8px solid #cc0000;
    }

    .lifecycle-subtitle {
        font-size: 16px;
        font-weight: 400;
        color: #666;
        margin: 0;
        padding-left: 28px;
    }

    .lifecycle-logo {
        position: absolute;
        top: 30px;
        right: 40px;
        height: 24px;
        width: auto;
        filter: brightness(0);
    }

    .lifecycle-content {
        flex: 1;
        padding: 20px 40px;
        overflow-x: auto;
    }

    /* Timeline Table */
    .timeline-table-wrapper {
        margin-bottom: 30px;
        overflow-x: auto;
    }

    .timeline-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
        background: white;
        border: 1px solid #dee2e6;
    }

    .timeline-table th,
    .timeline-table td {
        border: 1px solid #dee2e6;
        padding: 12px 8px;
        text-align: center;
        vertical-align: middle;
    }

    .timeline-table .year-header {
        background: #f8f9fa;
        color: #1a1a1a;
        font-weight: 700;
        font-size: 13px;
        padding: 12px;
    }

    .timeline-table .quarter-header {
        background: #e9ecef;
        color: #495057;
        font-weight: 600;
        font-size: 11px;
        padding: 8px;
    }

    .timeline-table .label-cell {
        background: #ffffff;
        border-right: 2px solid #adb5bd;
        width: 100px;
        font-weight: 700;
        text-align: left;
        padding: 12px;
    }

    .timeline-table .intervention-label,
    .timeline-table .changes-label {
        background: #f8f9fa;
        color: #1a1a1a;
        font-weight: 700;
        text-align: left;
        padding: 15px 12px;
        border-right: 2px solid #adb5bd;
    }

    .timeline-table .intervention-cell {
        background: #ffffff;
        min-height: 100px;
        position: relative;
        padding: 15px 8px;
    }

    .timeline-table .intervention-cell.active {
        background: #f8f9fa;
    }

    .intervention-marker {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 5px;
    }

    .marker-pin {
        width: 20px;
        height: 20px;
        background: #cc0000;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        box-shadow: 0 2px 8px rgba(204, 0, 0, 0.3);
    }

    .marker-date {
        font-size: 11px;
        font-weight: 600;
        color: #cc0000;
        margin-top: 5px;
    }

    .marker-title {
        font-size: 12px;
        font-weight: 700;
        color: #1a1a1a;
        text-align: center;
        margin-top: 2px;
    }

    .timeline-table .changes-cell {
        background: #ffffff;
        text-align: left;
        padding: 12px 10px;
        font-size: 10px;
        line-height: 1.5;
        min-height: 80px;
    }

    .timeline-table .changes-cell.active {
        background: #fffbf0;
        border-left: 3px solid #ffc107;
    }

    .changes-content {
        color: #333;
        font-weight: 500;
    }

    /* Sales Chart Section */
    .sales-chart-section {
        margin: 30px 0;
        padding: 20px;
        background: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #dee2e6;
    }

    .chart-title {
        font-size: 18px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 0 0 20px 0;
        text-align: center;
    }

    .chart-placeholder {
        background: white;
        padding: 20px;
        border-radius: 4px;
        min-height: 300px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    .sales-chart {
        width: 100%;
        height: 300px;
    }

    .chart-note {
        font-size: 14px;
        fill: #999;
        font-style: italic;
    }

    .chart-container {
        background: white;
        padding: 20px;
        border-radius: 4px;
        min-height: 400px;
        position: relative;
    }

    .chart-legend {
        display: flex;
        justify-content: center;
        gap: 30px;
        margin-top: 15px;
        font-size: 12px;
    }

    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .legend-bar {
        width: 20px;
        height: 12px;
        background: #2E3B4E;
        border-radius: 2px;
    }

    .legend-line {
        width: 25px;
        height: 3px;
        background: #ff6b35;
        border-radius: 1px;
    }

    /* Insights Section */
    .insights-section {
        margin-top: 20px;
        padding: 20px;
        background: #fff8e1;
        border-left: 4px solid #ffc107;
        border-radius: 4px;
    }

    .insights-list {
        margin: 0;
        padding-left: 20px;
        list-style: none;
    }

    .insights-list li {
        font-size: 13px;
        line-height: 1.6;
        color: #333;
        margin-bottom: 10px;
        padding-left: 10px;
        position: relative;
    }

    .insights-list li:before {
        content: "■";
        position: absolute;
        left: -10px;
        color: #1a1a1a;
        font-weight: bold;
    }

    .lifecycle-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 15px 40px 20px;
        border-top: 4px solid #1a1a1a;
        margin: 0 40px;
    }

    /* Mobile Responsive */
    @media (max-width: 768px) {
        .cover-page {
            padding: 30px;
            height: auto;
            min-height: 100vh;
        }

        .cover-title {
            font-size: 28px;
        }

        .cover-subtitle {
            font-size: 22px;
        }

        .cover-logo {
            top: 20px;
            right: 30px;
        }

        .hero-page-header {
            flex-direction: column;
            gap: 15px;
            padding: 20px;
        }

        .hero-page-title {
            font-size: 16px;
        }

        .hero-comparison-container {
            flex-direction: column;
        }

        .hero-vs-divider {
            width: 100%;
            height: 40px;
            flex-direction: row;
        }

        .spec-page-header,
        .feature-page-header {
            flex-direction: column;
            padding: 20px;
            gap: 15px;
        }

        .spec-page-title,
        .feature-page-title {
            font-size: 18px;
        }

        .spec-table-container,
        .feature-table-container {
            padding: 0 15px 15px;
        }

        .spec-table,
        .feature-table {
            font-size: 10px;
        }

        .spec-table th,
        .feature-table th {
            padding: 8px 4px;
            font-size: 11px;
        }

        .spec-table td,
        .feature-table td {
            padding: 6px 4px;
        }

        .hero-title {
            font-size: 28px;
        }

        .hero-subtitle {
            font-size: 12px;
        }

        .hero-images-grid {
            grid-template-columns: 1fr;
            gap: 20px;
        }

        .image-gallery {
            grid-template-columns: 1fr;
            gap: 15px;
        }

        .gallery-item img {
            height: 180px;
        }

        .lifecycle-header {
            padding: 20px 15px;
        }

        .lifecycle-title {
            font-size: 22px;
            padding-left: 15px;
            border-left: 6px solid #cc0000;
        }

        .lifecycle-subtitle {
            font-size: 14px;
            padding-left: 21px;
        }

        .lifecycle-logo {
            top: 20px;
            right: 15px;
            height: 20px;
        }

        .lifecycle-content {
            padding: 15px;
        }

        .timeline-table {
            font-size: 9px;
        }

        .timeline-table th,
        .timeline-table td {
            padding: 6px 4px;
        }

        .marker-date,
        .marker-title {
            font-size: 9px;
        }

        .changes-content {
            font-size: 8px;
        }

        .chart-title {
            font-size: 16px;
        }

        .insights-list li {
            font-size: 11px;
        }
    }
    '''
