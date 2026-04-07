"""
Image Section Generation for Enhanced Reports
Generates PDF-style image galleries for car comparison reports
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime


def _generate_ai_notes_for_gallery(
    images_list: List[Dict[str, Any]],
    category: str,
    comparison_data: Dict[str, Any],
) -> List[str]:
    """
    Generate spec-based notes for each gallery image using actual scraped data.
    Creates 1-2 line notes elaborating on the specific spec data for each car.
    """
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        from product_planning_agent.config import GEMINI_LITE_MODEL, GEMINI_LITE_LOCATION, PROJECT_ID

        # Return empty if no images
        if not images_list:
            print(f"  No images for {category} - skipping AI notes")
            return []

        print(f"  Generating spec-based AI notes for {len(images_list)} {category} images...")

        # Initialize vertexai with lite model location (us-central1)
        vertexai.init(project=PROJECT_ID, location=GEMINI_LITE_LOCATION)

        # Map feature names to relevant spec fields
        FEATURE_SPEC_MAP = {
            # Exterior features
            "headlight": ["led", "headlamp", "lighting", "projector"],
            "drl": ["drl", "daytime_running", "led"],
            "tail": ["tail_lamp", "rear_light", "led"],
            "wheel": ["alloy_wheel", "wheel_size", "tyre_size"],
            "exterior": ["led", "drl", "alloy_wheel", "sunroof"],
            "front": ["led", "grille", "bumper"],
            "rear": ["tail_lamp", "boot_space"],
            "side": ["alloy_wheel", "wheel_size", "door"],

            # Interior features
            "steering": ["steering", "telescopic_steering", "cruise_control"],
            "seat": ["seat_material", "ventilated_seats", "seat_features_detailed", "seating_capacity"],
            "infotainment": ["infotainment_screen", "resolution", "apple_carplay", "digital_display"],
            "cluster": ["digital_display", "instrument_cluster"],
            "console": ["armrest", "button", "gear_shift"],
            "interior": ["seat_material", "climate_control", "soft_trims"],

            # Technology features
            "touchscreen": ["infotainment_screen", "resolution", "touch_response"],
            "display": ["digital_display", "resolution", "infotainment_screen"],
            "screen": ["infotainment_screen", "resolution"],
            "technology": ["infotainment_screen", "digital_display", "apple_carplay", "audio_system"],

            # Comfort features
            "sunroof": ["sunroof", "panoramic"],
            "ac": ["climate_control", "rear_ac_vents"],
            "armrest": ["armrest", "center_armrest"],
            "comfort": ["climate_control", "ventilated_seats", "armrest"],

            # Safety features
            "airbag": ["airbags", "airbag_types_breakdown", "safety_features"],
            "safety": ["airbags", "ncap_rating", "adas", "vehicle_safety_features"],
        }

        # Build per-image entries with relevant specs
        image_entries = []
        for i, img in enumerate(images_list):
            car_name = img['car_name']
            feature_name = img['feature'].lower()

            # Get car data
            car_data = comparison_data.get(car_name, {})
            if not isinstance(car_data, dict) or "error" in car_data:
                car_data = {}

            # Find relevant specs for this feature
            relevant_specs = {}
            for keyword, spec_fields in FEATURE_SPEC_MAP.items():
                if keyword in feature_name:
                    for field in spec_fields:
                        if field in car_data:
                            val = car_data[field]
                            if val and val not in ["Not Available", "N/A", "-", ""]:
                                relevant_specs[field] = str(val)[:150]

            # If no specific mapping found, include category-based specs
            if not relevant_specs:
                category_lower = category.lower()
                for keyword, spec_fields in FEATURE_SPEC_MAP.items():
                    if keyword in category_lower:
                        for field in spec_fields:
                            if field in car_data:
                                val = car_data[field]
                                if val and val not in ["Not Available", "N/A", "-", ""]:
                                    relevant_specs[field] = str(val)[:150]

            # Format specs for prompt
            specs_text = "; ".join(f"{k}: {v}" for k, v in relevant_specs.items()) if relevant_specs else "No specific data available"

            image_entries.append(
                f"{i+1}. Car: {car_name} | Feature: {img['feature']}\n"
                f"   Scraped specs: {specs_text}"
            )

        image_list_text = "\n\n".join(image_entries)

        prompt = f"""You are writing detailed notes for a car benchmarking report.

For each image below, write a factual note based ONLY on the scraped spec data provided.

RULES:
1. Use ONLY the "Scraped specs" data - don't make up information
2. MUST be 2-3 lines (25-35 words minimum) - never less than 2 sentences
3. Be specific and highlight key numbers/features with context
4. If no specs available, write a descriptive placeholder with general observations
5. Professional, factual tone with comparative insights where possible

Examples of good notes:
- "Features LED projector headlamps with DRL signature lighting. The lighting package offers excellent visibility and a premium appearance that matches the segment leaders."
- "10.25-inch touchscreen with wireless Apple CarPlay and Android Auto connectivity. The responsive display provides intuitive controls for navigation and entertainment functions."
- "Dual-tone leatherette seats with ventilation and lumbar support for long-distance comfort. The cushioning and bolstering are designed for extended drives."
- "6 airbags including side and curtain for comprehensive protection. This safety configuration meets global standards and provides occupant protection in various collision scenarios."

Images to caption:
{image_list_text}

Return ONLY a JSON object:
{{"notes": ["note 1", "note 2", ...]}}

Array must have exactly {len(images_list)} entries."""

        model = GenerativeModel(GEMINI_LITE_MODEL)
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)
        notes = data.get("notes", [])

        # Pad or trim to match images count
        while len(notes) < len(images_list):
            notes.append("")

        print(f"  ✓ Generated {len(notes)} spec-based AI notes for {category}")
        return notes[:len(images_list)]

    except Exception as e:
        print(f"  ✗ AI notes generation failed for {category}: {e}")
        print(f"  Using fallback notes instead...")
        # Fallback: use spec data directly
        fallback_notes = []
        for img in images_list:
            car_name = img.get('car_name', 'Car')
            feature = img.get('feature', 'Feature')
            note = f"{car_name} {feature.lower()}"
            fallback_notes.append(note)
        return fallback_notes


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
    section_id: str = "",
    with_ai_notes: bool = False,
) -> str:
    """
    Generate an image gallery section with 1:1 comparison layout.
    Groups same-feature images from all cars in horizontal rows for easy comparison.

    Args:
        title: Section title (e.g., "Exterior Highlights")
        comparison_data: Dict mapping car names to their scraped data
        image_category: Category key in images dict ("exterior", "interior", etc.)
        section_id: Optional HTML id for the section
        with_ai_notes: If True, generate AI analytical notes below each image

    Returns:
        HTML string for image gallery section with comparison layout
    """
    # Get car names in consistent order
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data]

    if not car_names:
        return ""

    num_cars = len(car_names)

    # Collect images per car with their features
    car_images: Dict[str, List[Dict]] = {name: [] for name in car_names}

    for car_name in car_names:
        car_data = comparison_data.get(car_name, {})
        images = car_data.get("images") or {}
        category_images = images.get(image_category, [])

        for idx, img_item in enumerate(category_images):
            img_url = None
            feature_caption = f"{image_category.title()} {idx + 1}"

            if isinstance(img_item, (list, tuple)) and len(img_item) >= 1:
                img_url = img_item[0]
                if len(img_item) >= 2:
                    feature_caption = img_item[1]
            elif isinstance(img_item, str):
                img_url = img_item

            if img_url and isinstance(img_url, str):
                car_images[car_name].append({
                    "url": img_url,
                    "feature": feature_caption,
                    "index": idx
                })

    # Find max images per car to create comparison rows
    max_images = max(len(imgs) for imgs in car_images.values()) if car_images else 0

    if max_images == 0:
        return ""

    # Limit to 6 comparison rows max
    max_images = min(max_images, 6)

    # Generate AI notes if requested
    all_display_images = []
    for row_idx in range(max_images):
        for car_name in car_names:
            imgs = car_images.get(car_name, [])
            if row_idx < len(imgs):
                all_display_images.append({
                    "url": imgs[row_idx]["url"],
                    "feature": imgs[row_idx]["feature"],
                    "car_name": car_name,
                    "alt": f"{car_name} {imgs[row_idx]['feature']}"
                })

    ai_notes: List[str] = []
    if with_ai_notes and all_display_images:
        ai_notes = _generate_ai_notes_for_gallery(all_display_images, image_category, comparison_data)

    # Build comparison rows HTML
    rows_html = ""
    note_idx = 0

    for row_idx in range(max_images):
        # Get feature name from first car that has this image
        feature_name = f"{image_category.title()} {row_idx + 1}"
        for car_name in car_names:
            imgs = car_images.get(car_name, [])
            if row_idx < len(imgs):
                feature_name = imgs[row_idx]["feature"]
                break

        # Build cells for each car in this row
        cells_html = ""
        for car_name in car_names:
            imgs = car_images.get(car_name, [])
            if row_idx < len(imgs):
                img_data = imgs[row_idx]
                note = ai_notes[note_idx] if ai_notes and note_idx < len(ai_notes) else ""
                note_html = f'<div class="comparison-ai-note"><span class="ai-note-label">AI Note:</span> {note}</div>' if note else ""
                note_idx += 1

                cells_html += f'''
                <div class="comparison-cell">
                    <div class="comparison-car-label">{car_name}</div>
                    <div class="comparison-image-wrapper">
                        <img src="{img_data['url']}" alt="{car_name} {img_data['feature']}"
                             onerror="this.parentElement.innerHTML='<div class=\\'no-image\\'>No Image</div>'">
                    </div>
                    {note_html}
                </div>
                '''
            else:
                # No image for this car at this position
                cells_html += f'''
                <div class="comparison-cell no-image-cell">
                    <div class="comparison-car-label">{car_name}</div>
                    <div class="comparison-image-wrapper">
                        <div class="no-image">No Image Available</div>
                    </div>
                </div>
                '''

        rows_html += f'''
        <div class="comparison-row">
            <div class="comparison-feature-label">{feature_name}</div>
            <div class="comparison-cells" style="--num-cars: {num_cars};">
                {cells_html}
            </div>
        </div>
        '''

    id_attr = f'id="{section_id}"' if section_id else ""

    html = f'''
    <div class="content image-gallery-section comparison-gallery" {id_attr}>
        <div class="section-header">
            <div class="icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                </svg>
            </div>
            <h2>{title}</h2>
            <div class="comparison-legend">
                {"".join(f'<span class="legend-car">{name}</span>' for name in car_names)}
            </div>
        </div>
        <div class="comparison-gallery-grid">
            {rows_html}
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
    # Step 2: Sequential CSE searches + parallel Gemini extraction (3 at a time)
    # ------------------------------------------------------------------
    import concurrent.futures

    gemini_resolved: Dict[str, Dict] = {}

    if missing_features:
        try:
            from benchmarking_agent.core.scraper import google_custom_search, SEARCH_ENGINE_ID
            import vertexai
            from vertexai.generative_models import GenerativeModel, GenerationConfig
            from product_planning_agent.config import GEMINI_LITE_LOCATION, PROJECT_ID

            # Initialize vertexai with lite model location
            vertexai.init(project=PROJECT_ID, location=GEMINI_LITE_LOCATION)

            car1 = car_names[0]
            car2 = car_names[1] if len(car_names) > 1 else "Competitor"
            cars_str = " vs ".join(car_names)

            # Step 2a: Sequential CSE searches
            print(f"  Searching {len(missing_features)} features...")
            search_results = {}
            for i, feat in enumerate(missing_features):
                try:
                    results = google_custom_search(f"{cars_str} {feat['name']}", SEARCH_ENGINE_ID, num_results=2)
                    search_results[feat['name']] = results
                except Exception:
                    search_results[feat['name']] = []
                if (i + 1) % 20 == 0:
                    print(f"    Searches: {i + 1}/{len(missing_features)}")
            print(f"    Searches: {len(missing_features)}/{len(missing_features)} done")

            # Step 2b: Create batches of 10
            BATCH_SIZE = 10
            batches = [missing_features[i:i + BATCH_SIZE] for i in range(0, len(missing_features), BATCH_SIZE)]

            # Gemini extraction function
            def extract_batch(batch):
                sections = []
                feat_names = []
                for feat in batch:
                    name = feat['name']
                    feat_names.append(name)
                    results = search_results.get(name, [])
                    if results:
                        snippet = results[0].get('snippet', '')[:120]
                        sections.append(f"[{name}]: {snippet}")
                    else:
                        sections.append(f"[{name}]: (use knowledge)")

                prompt = f"""For {car1} vs {car2}, determine feature presence.

{chr(10).join(sections)}

Return JSON only: {{"features": [{{"name": "X", "{car1}": true/false, "{car2}": true/false}}, ...]}}"""

                try:
                    model = GenerativeModel("gemini-2.5-flash-lite")
                    resp = model.generate_content(prompt, generation_config=GenerationConfig(temperature=0.1, max_output_tokens=2048))
                    text = resp.text.strip() if hasattr(resp, 'text') else ""
                    if not text:
                        print(f"    [DEBUG] Empty response for batch: {feat_names[:3]}...")
                        return []
                    # Debug: print first 200 chars of raw response
                    print(f"    [DEBUG] Raw response ({len(text)} chars): {text[:200]}...")
                    if "```" in text:
                        text = text.split("```")[1] if "```json" not in text else text.split("```json")[1]
                        text = text.split("```")[0]
                    text = text.strip()
                    if "{" in text:
                        text = text[text.index("{"):text.rindex("}") + 1]
                    result = json_repair.loads(text)
                    features = result.get("features", []) if isinstance(result, dict) else []
                    print(f"    [DEBUG] Parsed {len(features)} features from batch")
                    return features
                except Exception as e:
                    print(f"    [DEBUG] Exception in extract_batch: {type(e).__name__}: {e}")
                    return []

            # Step 2c: Process batches with 4 parallel Gemini calls
            print(f"  Extracting features ({len(batches)} batches, 4 parallel)...")
            for i in range(0, len(batches), 4):
                batch_group = batches[i:i + 4]
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                    futures = [ex.submit(extract_batch, b) for b in batch_group]
                    for future in concurrent.futures.as_completed(futures):
                        for feat in future.result():
                            name = feat.get("name", "")
                            if name:
                                gemini_resolved[name] = {cn: feat.get(cn) for cn in car_names}

            print(f"  Fetched {len(gemini_resolved)} features via {len(missing_features)} searches + {len(batches)} Gemini calls")

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
    Supports multiple engine variant columns per car for variant-specific specs.

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

    # Specs that should show variant columns (one column per engine variant)
    VARIANT_SPECS = {
        "engine", "engine_displacement", "max_power_kw", "torque",
        "transmission", "drive", "kerb_weight", "steering"
    }

    # Build variant info for each car
    car_variants = {}
    for car_name in car_names:
        car_data = comparison_data.get(car_name, {})
        variants = car_data.get("engine_variants", [])
        if variants and len(variants) > 0:
            car_variants[car_name] = variants
        else:
            # Fallback: Check if any VARIANT_SPECS have comma-separated values
            # and create synthetic variants from them
            max_values = 1
            variant_values = {}
            for key in VARIANT_SPECS:
                val = car_data.get(key, "")
                if isinstance(val, str) and ", " in val:
                    parts = [p.strip() for p in val.split(", ")]
                    variant_values[key] = parts
                    max_values = max(max_values, len(parts))
                elif isinstance(val, list):
                    variant_values[key] = val
                    max_values = max(max_values, len(val))

            if max_values > 1:
                # Create synthetic variants from comma-separated values
                synthetic_variants = []
                for i in range(max_values):
                    variant = {"_synthetic": True}
                    for key in VARIANT_SPECS:
                        if key in variant_values and i < len(variant_values[key]):
                            variant[key] = variant_values[key][i]
                        else:
                            # Use the single value or first value if available
                            original = car_data.get(key, "-")
                            if isinstance(original, list) and len(original) > 0:
                                variant[key] = original[0] if i >= len(original) else original[i]
                            elif isinstance(original, str) and ", " in original:
                                parts = [p.strip() for p in original.split(", ")]
                                variant[key] = parts[0] if i >= len(parts) else parts[i]
                            else:
                                variant[key] = original
                    synthetic_variants.append(variant)
                car_variants[car_name] = synthetic_variants
            else:
                # No variants - use single column with existing data
                car_variants[car_name] = [{"_single": True}]

    # Calculate total columns for variant specs
    total_variant_cols = sum(len(v) for v in car_variants.values())

    # Keys to exclude — metadata, citations, image blobs
    METADATA_KEYS = {
        'car_name', 'method', 'source_urls', 'images', 'gcs_folder',
        'scraping_method', 'timestamp', 'chart_gcs_uri', 'chart_signed_url',
        'summary_data', 'engine_variants',
    }

    # Comprehensive organized spec groups - matching exact order from Images 1-11
    tech_spec_groups = {
        # ===== IMAGE 1: Technical Specifications =====
        "Powertrain": [
            ("Engine", "engine"),
            ("Engine CC", "engine_displacement"),
            ("Max Power (kW)", "max_power_kw"),
            ("Max Torque (Nm)", "torque"),
        ],
        "Fuel": [
            ("Type", "fuel_type"),
            ("Tank Capacity", "fuel_tank_capacity"),
        ],
        "Transmission": [
            ("Transmission", "transmission"),
        ],
        "Drive": [
            ("Drive", "drive"),
        ],
        "Drive Mode": [
            ("Drive Mode", "drive_mode"),
        ],
        "Top Speed": [
            ("Top Speed (km/h)", "top_speed"),
        ],
        "Dimension": [
            ("Length (mm)", "length"),
            ("Width (mm)", "width"),
            ("Height (mm)", "height"),
            ("Wheelbase (mm)", "wheelbase"),
            ("WheelTrack F/R", "wheel_track"),
            ("Ground clearance", "ground_clearance"),
            ("Kerb weight (kg)", "kerb_weight"),
        ],
        "Steering": [
            ("Type", "steering"),
        ],
        "Seat": [
            ("Seating Capacity", "seating_capacity"),
        ],
        "Brakes": [
            ("Front Brakes", "front_brakes"),
            ("Rear Brakes", "rear_brakes"),
        ],
        "Suspension": [
            ("Front Suspension", "front_suspension"),
            ("Rear Suspension", "rear_suspension"),
        ],
        "Wheel & Tyre": [
            ("Front - Tyre size", "front_tyre_size"),
            ("Rear - Tyre size", "rear_tyre_size"),
            ("Spare Tyres", "spare_tyres"),
        ],
        "Boot": [
            ("Space (L)", "boot_space"),
        ],
        # ===== IMAGE 2: Exterior =====
        "Exterior": [
            ("Full LED", "full_led"),
            ("Wheel arch Ext. Claddings", "wheel_arch_claddings"),
            ("Front Bumper & Grille", "front_bumper_grille"),
            ("Antenna Type", "antenna_type"),
            ("Foot step", "foot_step"),
        ],
        # ===== IMAGE 2: Interior =====
        "Interior": [
            ("Console Switches", "console_switches"),
            ("Upholstery", "upholstery"),
            ("IP/ Dashboard", "ip_dashboard"),
        ],
        "Glove Box": [
            ("Glove Box", "glove_box"),
        ],
        "Sunvisor": [
            ("Driver", "sunvisor_driver"),
            ("Co Driver", "sunvisor_co_driver"),
        ],
        # ===== IMAGE 3: Grab Handle, Sun Roof, etc. =====
        "Grab Handle": [
            ("Driver", "grab_handle_driver"),
            ("Co Driver", "grab_handle_co_driver"),
            ("2nd Row Both side", "grab_handle_2nd_row"),
        ],
        "Sun Roof / Fixed Roof": [
            ("Panoramic Sun Roof", "panoramic_sunroof"),
            ("Roller Blind/ Sunblind", "roller_blind_sunblind"),
        ],
        "Luggage rack": [
            ("Luggage rack", "luggage_rack"),
        ],
        "Wipers & Demister": [
            ("Front Wiper", "front_wiper"),
            ("Defogging", "defogging"),
            ("Rain Sensing Wipers", "rain_sensing_wipers"),
            ("Rear Wiper", "rear_wiper"),
        ],
        "Door": [
            ("Front", "door_front"),
            ("Rear", "door_rear"),
        ],
        "Tailgate": [
            ("Type", "tailgate_type"),
            ("Power operated tail gate + eLatch", "power_tailgate"),
        ],
        "ORVM": [
            ("ORVM", "orvm"),
        ],
        # ===== IMAGE 4: Steering Wheel, Bonnet, Door Trim, Boot/Trunk =====
        "Steering Wheel": [
            ("Steering Wheel", "steering_wheel"),
        ],
        "Bonnet Stay Mechanism": [
            ("Bonnet Gas Strut", "bonnet_gas_strut"),
        ],
        "Door Trim": [
            ("Bottle Holder", "bottle_holder"),
            ("Door arm Rest", "door_arm_rest"),
        ],
        "Boot/Trunk": [
            ("Boot Organizer", "boot_organizer"),
            ("Lamp", "boot_lamp"),
        ],
        # ===== IMAGE 5: Power Window, Floor Console, Wireless charging =====
        "Power Window": [
            ("All Doors", "power_window_all_doors"),
            ("Driver Door", "power_window_driver_door"),
            ("Window one key lift function", "window_one_key_lift"),
            ("Window anti-clamping function", "window_anti_clamping"),
            ("Multilayer silencing glass at the front door", "multilayer_silencing_glass"),
            ("Front windshield multilayer mute glass", "front_windshield_mute_glass"),
        ],
        "Steering Column": [
            ("Steering Column", "steering_column"),
            ("Steering Column Lock", "steering_column_lock"),
        ],
        "Floor Console": [
            ("Arm Rest", "floor_console_armrest"),
            ("No Of Cup Holder", "cup_holders"),
        ],
        "Wireless charging": [
            ("Wireless charging", "wireless_charging"),
            ("No of wireless charging", "no_of_wireless_charging"),
        ],
        "Door Inner Scuff": [
            ("Front", "door_inner_scuff_front"),
            ("Rear", "door_inner_scuff_rear"),
        ],
        "Voice Recognition Button On Steering Wheel Control": [
            ("Voice Recognition Button On Steering Wheel Control", "voice_recognition_steering"),
        ],
        # ===== IMAGE 6: Seats, Safety =====
        "Seats": [
            ("Seats", "seats"),
            ("Seat Ventilation", "ventilated_seats"),
            ("Driver and Front Passenger", "seat_ventilation_front_passenger"),
        ],
        "Safety": [
            ("Airbags", "airbags"),
            ("PAB deactivation switch", "pab_deactivation_switch"),
            ("Driver Seat Belt", "driver_seat_belt"),
            ("Front Passenger Seat Belt", "front_passenger_seat_belt"),
            ("2nd Row Seat Belt", "seat_belt_2nd_row"),
            ("Child Anchor", "child_anchor"),
            ("Child Lock", "child_lock"),
            ("Seat Belt Reminder with Buzzer", "seat_belt_reminder"),
            ("Seat Belt Holder - 2nd Row", "seat_belt_holder_2nd_row"),
            ("Sensors", "crash_sensors"),
        ],
        # ===== IMAGE 8: Technology =====
        "Technology": [
            ("Infotainment", "infotainment_screen"),
            ("Smart Phone Connectivity", "smartphone_connectivity"),
            ("Bluetooth", "bluetooth"),
        ],
        "Radio": [
            ("AM / FM", "am_fm_radio"),
            ("Digital", "digital_radio"),
        ],
        "ConnectedDrive": [
            ("Wireless", "connected_drive_wireless"),
        ],
        "Branded Audio": [
            ("3D Immersive Sound", "immersive_sound_3d"),
            ("No of speakers", "no_of_speakers"),
            ("Brand", "audio_brand"),
            ("Dolby", "dolby_atmos"),
            ("Adjustable", "audio_adjustable"),
        ],
        # ===== IMAGE 9: Lighting =====
        "Lighting": [
            ("Headlamp", "headlamp"),
            ("High beam", "high_beam"),
            ("Low beam", "low_beam"),
            ("Auto High Beam", "auto_high_beam"),
            ("Headlamp Leveling", "headlamp_leveling"),
            ("Projector LED", "projector_led"),
            ("Front Fog Lamp", "front_fog_lamp"),
            ("Tail Lamp", "tail_lamp"),
            ("Welcome Lighting", "welcome_lighting"),
            ("Ambient Lighting System", "ambient_lighting"),
            ("Cabin Lamps", "cabin_lamps"),
            ("High Mounted Stop Lamp", "high_mounted_stop_lamp"),
            ("Hazard Lamp", "hazard_lamp"),
        ],
        # ===== IMAGE 9: Locking =====
        "Locking": [
            ("Locking", "central_locking"),
            ("Door Lock", "door_lock"),
            ("Speed Sensing Door Lock", "speed_sensing_door_lock"),
            ("Panic Alarm", "panic_alarm"),
            ("Remote Lock/Unlock", "remote_lock_unlock"),
            ("Digital Key Plus", "digital_key_plus"),
        ],
        # ===== IMAGE 10: Horn, ADAS =====
        "Horn": [
            ("Electronic Horn - dual tone", "horn"),
        ],
        "Over speeding Bell": [
            ("Over speeding Bell", "over_speeding_bell"),
        ],
        "ADAS": [
            ("Active Cruise Control with Stop & Go", "active_cruise_control"),
            ("Lane Departure Warning", "lane_departure_warning"),
            ("Automatic Emergency Braking (Stop Assist)", "automatic_emergency_braking"),
            ("Lane Keep Assist", "lane_keep_assist"),
            ("Blind Spot Detection", "blind_spot_detection"),
            ("Blind Spot Collision warning", "blind_spot_collision_warning"),
            ("Forward Collision warning", "forward_collision_warning"),
            ("Rear Collision Warning", "rear_collision_warning"),
            ("Door Open Alert", "door_open_alert"),
            ("High beam Assist", "high_beam_assist"),
            ("Traffic Sign Recognition", "traffic_sign_recognition"),
            ("Rear Cross Traffic Alert", "rear_cross_traffic_alert"),
            ("Traffic jam alert", "traffic_jam_alert"),
            ("Safe Exit Braking/ Warning", "safe_exit_braking"),
            ("Surround View Monitor", "surround_view_monitor"),
            ("Smart Pilot Assist", "smart_pilot_assist"),
        ],
        # ===== IMAGE 11: Climate =====
        "Climate": [
            ("Auto Defogging", "auto_defogging"),
            ("No of Zone", "no_of_zone_climate"),
            ("Rear Vent AC", "rear_vent_ac"),
            ("Active Carbon filter", "active_carbon_filter"),
            ("Temp diff control", "temp_diff_control"),
            ("Bottle Opener", "bottle_opener"),
        ],
        # ===== IMAGE 11: Capabilities =====
        "Capabilities": [
            ("Drive Modes", "drive_mode"),
            ("Terrain Modes", "terrain_modes"),
            ("Crawl Smart", "crawl_smart"),
            ("Intelli Turn", "intelli_turn"),
            ("Off-road information display", "off_road_info_display"),
            ("Central Differential", "central_differential"),
            ("Limited Slip Differential At Rear Bridge", "limited_slip_differential"),
            ("Wading sensing system", "wading_sensing_system"),
            ("Electronic gear shift", "electronic_gear_shift"),
            ("Electric Driveline disconnect on front axle", "electric_driveline_disconnect"),
            ("TPMS (Tyre Pressure Monitoring System)", "tpms"),
            ("HHC Uphill Start Assist System", "hhc_uphill_start_assist"),
            ("Engine electronic security", "engine_electronic_security"),
        ],
        # ===== IMAGE 11: Power outlet / Charging Points =====
        "Power outlet / Charging Points": [
            ("No of Front row - USB Type C Port", "usb_type_c_front_row"),
            ("Front row - USB Type C Port", "usb_type_c_front_row_count"),
            ("No of Rear row - USB Type C Port", "usb_type_c_rear_row"),
            ("12V conventional socket", "socket_12v"),
        ],
        # ===== IMAGE 11: Brakes Detailed =====
        "Brakes Detailed": [
            ("Auto Hold", "auto_hold"),
            ("TPMS", "tpms"),
            ("Rollover", "rollover_mitigation"),
            ("RMI", "rmi_anti_rollover"),
            ("VDC", "vdc_vehicle_dynamic"),
            ("CSC", "csc_corner_stability"),
            ("EPB", "epb"),
            ("AVH", "avh_auto_vehicle_hold"),
            ("HAC-HHC", "hac_hill_ascend"),
            ("HBA", "hba_hydraulic_brake"),
            ("DBC", "dbc_downhill_brake"),
            ("EBP", "ebp_electronic_brake_prefill"),
            ("BDW", "bdw_brake_disc_wiping"),
            ("EDTC", "edtc_engine_drag_torque"),
            ("TCS", "tcs_traction_control"),
            ("EBD", "ebd_electronic_brake"),
            ("ABS", "abs_antilock"),
            ("DST", "dst_dynamic_steering"),
            ("EBA", "eba_brake_assist"),
            ("CBC", "cbc_cornering_brake"),
            ("HDC", "hdc_hill_descent"),
        ],
        # ===== IMAGE 11: Others =====
        "Others": [
            ("Active noise reduction", "active_noise_reduction"),
            ("Intelligent voice control", "intelligent_voice_control"),
            ("Dynamic transparent car bottom", "transparent_car_bottom"),
            ("Intellectual dodge", "intellectual_dodge"),
            ("Car picnic table", "car_picnic_table"),
            ("Trunk subwoofer", "trunk_subwoofer"),
            ("Dashcam Provision", "dashcam_provision"),
            ("Cup Holder at Tail door", "cup_holder_tail_door"),
            ("Hooks at Tail door", "hooks_tail_door"),
            ("Warning Triangle at packed with tail door", "warning_triangle_tail_door"),
            ("1st | 2nd row door magnetic Strap", "door_magnetic_strap"),
        ],
        # ===== Market Info =====
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

    # Generate table rows with collapsible groups
    rows_html = ""
    group_index = 0
    num_cars = len(car_names)

    def _render_rows(category, specs, grp_idx):
        nonlocal rows_html
        # Check if this group has any non-empty rows
        has_data = False
        for label, key in specs:
            is_variant_spec = key in VARIANT_SPECS
            if is_variant_spec:
                # Check variant data
                for car_name in car_names:
                    variants = car_variants.get(car_name, [{}])
                    for v in variants:
                        if v.get("_single"):
                            car_data = comparison_data.get(car_name, {})
                            val = car_data.get(key, "-")
                        else:
                            val = v.get(key, "-")
                        if val and val not in EMPTY_VALUES and val != "-":
                            has_data = True
                            break
                    if has_data:
                        break
            else:
                for car_name in car_names:
                    car_data = comparison_data.get(car_name, {})
                    value = car_data.get(key, "-")
                    if isinstance(value, (dict, list)):
                        value = "-"
                    elif value in EMPTY_VALUES:
                        value = "-"
                    if value != "-":
                        has_data = True
                        break
            if has_data:
                break

        if not has_data:
            return

        # Group header row with toggle button
        collapsed_class = "" if grp_idx == 0 else "collapsed"
        toggle_icon = "−" if grp_idx == 0 else "+"
        rows_html += f'''<tr class="spec-group-header {collapsed_class}" data-group="spec-group-{grp_idx}" onclick="toggleSpecGroup(this)">
            <td colspan="{total_variant_cols + 2}">
                <span class="group-toggle-btn">{toggle_icon}</span>
                <span class="group-title">{category}</span>
            </td>
        </tr>'''

        # Data rows for this group
        for label, key in specs:
            is_variant_spec = key in VARIANT_SPECS
            hidden_class = "" if grp_idx == 0 else "group-row-hidden"

            if is_variant_spec:
                # Variant spec: one column per engine variant
                all_empty = True
                cells_html = ""
                first_val = None

                for car_idx, car_name in enumerate(car_names):
                    variants = car_variants.get(car_name, [{}])
                    for v_idx, v in enumerate(variants):
                        if v.get("_single"):
                            # No variant data - use car's main data
                            car_data = comparison_data.get(car_name, {})
                            val = car_data.get(key, "-")
                        else:
                            val = v.get(key, "-")

                        if isinstance(val, (dict, list)):
                            val = "-"
                        elif val in EMPTY_VALUES or not val:
                            val = "-"

                        if val != "-":
                            all_empty = False

                        if first_val is None:
                            first_val = val

                        # Determine cell class for comparison
                        cell_class = ""
                        if car_idx > 0 or v_idx > 0:  # Not the first cell
                            if first_val != "-" and val == "-":
                                cell_class = "inferior-cell"
                            elif first_val == "-" and val != "-":
                                cell_class = "superior-cell"

                        cells_html += f'<td class="{cell_class}">{val}</td>'

                if all_empty:
                    continue

                rows_html += f'<tr class="spec-data-row {hidden_class}" data-group="spec-group-{grp_idx}"><td class="cat-cell"></td><td class="param-cell">{label}</td>{cells_html}</tr>'

            else:
                # Non-variant spec: span columns for each car
                all_empty = True
                cells_html = ""
                first_val = None

                for car_idx, car_name in enumerate(car_names):
                    car_data = comparison_data.get(car_name, {})
                    value = car_data.get(key, "-")
                    if isinstance(value, (dict, list)):
                        value = "-"
                    elif value in EMPTY_VALUES:
                        value = "-"

                    if value != "-":
                        all_empty = False

                    if first_val is None:
                        first_val = value

                    num_variant_cols = len(car_variants.get(car_name, [{}]))
                    cell_class = ""
                    if car_idx > 0:
                        if first_val != "-" and value == "-":
                            cell_class = "inferior-cell"
                        elif first_val == "-" and value != "-":
                            cell_class = "superior-cell"

                    if num_variant_cols > 1:
                        cells_html += f'<td class="{cell_class}" colspan="{num_variant_cols}">{value}</td>'
                    else:
                        cells_html += f'<td class="{cell_class}">{value}</td>'

                if all_empty:
                    continue

                rows_html += f'<tr class="spec-data-row {hidden_class}" data-group="spec-group-{grp_idx}"><td class="cat-cell"></td><td class="param-cell">{label}</td>{cells_html}</tr>'

    for category, specs in tech_spec_groups.items():
        _render_rows(category, specs, group_index)
        group_index += 1

    # Build the table header with variant columns
    # Row 1: Car names (spanning all their variant columns)
    car_name_header = ""
    for car_name in car_names:
        num_cols = len(car_variants.get(car_name, [{}]))
        car_name_header += f'<th colspan="{num_cols}">{car_name}</th>'

    # Row 2: Engine variant names (for cars with multiple variants)
    variant_header = ""
    for car_name in car_names:
        variants = car_variants.get(car_name, [{}])
        for v_idx, v in enumerate(variants):
            if v.get("_single"):
                # Single column - no variant name needed
                variant_header += f'<th class="variant-header">-</th>'
            elif v.get("_synthetic"):
                # Synthetic variant - use engine displacement or engine name as header
                engine_disp = v.get("engine_displacement", "")
                engine_name = v.get("engine", "")
                header_text = engine_disp if engine_disp and engine_disp != "-" else engine_name
                if not header_text or header_text == "-":
                    header_text = f"Variant {v_idx + 1}"
                # Shorten if too long
                if len(header_text) > 25:
                    header_text = header_text[:22] + "..."
                variant_header += f'<th class="variant-header">{header_text}</th>'
            else:
                engine_name = v.get("engine", "-")
                # Shorten engine name if too long
                if len(engine_name) > 25:
                    engine_name = engine_name[:22] + "..."
                variant_header += f'<th class="variant-header">{engine_name}</th>'

    # Check if we need the variant row (if any car has multiple variants)
    has_multiple_variants = any(len(v) > 1 for v in car_variants.values())

    if has_multiple_variants:
        header_html = f'''
                <thead>
                    <tr>
                        <th rowspan="2">Description</th>
                        <th rowspan="2">Parameter</th>
                        {car_name_header}
                    </tr>
                    <tr>
                        {variant_header}
                    </tr>
                </thead>'''
    else:
        header_html = f'''
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>Parameter</th>
                        {car_name_header}
                    </tr>
                </thead>'''

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
                {header_html}
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        <div class="spec-page-footer">
        </div>
    </div>
    <style>
        .spec-group-header {{
            background: #f8f9fa;
            cursor: pointer;
            user-select: none;
            transition: background 0.2s ease;
        }}
        .spec-group-header:hover {{
            background: #e9ecef;
        }}
        .spec-group-header td {{
            padding: 14px 16px !important;
            font-weight: 700;
            color: #1c2a39;
            border-bottom: 2px solid #dee2e6 !important;
        }}
        .group-toggle-btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            background: #dd032b;
            color: #fff;
            border-radius: 4px;
            font-size: 18px;
            font-weight: 700;
            margin-right: 12px;
            line-height: 1;
            transition: transform 0.2s ease;
        }}
        .spec-group-header.collapsed .group-toggle-btn {{
            background: #dd032b;
        }}
        .group-title {{
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .spec-data-row {{
            transition: all 0.2s ease;
        }}
        .group-row-hidden {{
            display: none;
        }}
        .variant-header {{
            font-size: 11px;
            font-weight: 600;
            background: #f8f9fa;
            color: #333;
            padding: 8px 6px !important;
            text-align: center;
            border-bottom: 2px solid #dd032b;
            white-space: nowrap;
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        @media print {{
            .spec-group-header {{
                background: #f8f9fa !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .group-toggle-btn {{
                display: none;
            }}
            .group-row-hidden {{
                display: table-row !important;
            }}
            .variant-header {{
                background: #f8f9fa !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
    </style>
    <script>
        function toggleSpecGroup(headerRow) {{
            var groupId = headerRow.getAttribute('data-group');
            var isCollapsed = headerRow.classList.contains('collapsed');
            var toggleBtn = headerRow.querySelector('.group-toggle-btn');
            var rows = document.querySelectorAll('tr[data-group="' + groupId + '"]:not(.spec-group-header)');

            if (isCollapsed) {{
                headerRow.classList.remove('collapsed');
                toggleBtn.textContent = '−';
                rows.forEach(function(row) {{
                    row.classList.remove('group-row-hidden');
                }});
            }} else {{
                headerRow.classList.add('collapsed');
                toggleBtn.textContent = '+';
                rows.forEach(function(row) {{
                    row.classList.add('group-row-hidden');
                }});
            }}
        }}
    </script>
    '''

    return html


def generate_feature_list_section(comparison_data: Dict[str, Any], page_start: int = 4) -> str:
    """
    Generate Feature List Comparison pages — ticks and crosses only (no text columns).
    Uses the same specs as Technical Specifications but displays them in checklist format.
    """
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data]

    if not car_names:
        return ""

    # Use the same tech_spec_groups as Technical Specifications section
    tech_spec_groups = {
        "Powertrain": [
            ("Engine", "engine"),
            ("Engine CC", "engine_displacement"),
            ("Max Power (kW)", "max_power_kw"),
            ("Max Torque (Nm)", "torque"),
        ],
        "Fuel": [
            ("Type", "fuel_type"),
            ("Tank Capacity", "fuel_tank_capacity"),
        ],
        "Transmission": [
            ("Transmission", "transmission"),
        ],
        "Drive": [
            ("Drive", "drive"),
            ("Drive Mode", "drive_mode"),
        ],
        "Top Speed": [
            ("Top Speed (km/h)", "top_speed"),
        ],
        "Dimension": [
            ("Length (mm)", "length"),
            ("Width (mm)", "width"),
            ("Height (mm)", "height"),
            ("Wheelbase (mm)", "wheelbase"),
            ("WheelTrack F/R", "wheel_track"),
            ("Ground clearance", "ground_clearance"),
            ("Kerb weight (kg)", "kerb_weight"),
        ],
        "Steering": [
            ("Type", "steering"),
        ],
        "Seat": [
            ("Seating Capacity", "seating_capacity"),
        ],
        "Brakes": [
            ("Front Brakes", "front_brakes"),
            ("Rear Brakes", "rear_brakes"),
        ],
        "Suspension": [
            ("Front Suspension", "front_suspension"),
            ("Rear Suspension", "rear_suspension"),
        ],
        "Wheel & Tyre": [
            ("Front - Tyre size", "front_tyre_size"),
            ("Rear - Tyre size", "rear_tyre_size"),
            ("Spare Tyres", "spare_tyres"),
        ],
        "Boot": [
            ("Space (L)", "boot_space"),
        ],
        "Exterior": [
            ("Full LED", "full_led"),
            ("Wheel arch Ext. Claddings", "wheel_arch_claddings"),
            ("Front Bumper & Grille", "front_bumper_grille"),
            ("Antenna Type", "antenna_type"),
            ("Foot step", "foot_step"),
        ],
        "Interior": [
            ("Console Switches", "console_switches"),
            ("Upholstery", "upholstery"),
            ("IP/ Dashboard", "ip_dashboard"),
            ("Glove Box", "glove_box"),
        ],
        "Sunvisor": [
            ("Driver", "sunvisor_driver"),
            ("Co Driver", "sunvisor_co_driver"),
        ],
        "Grab Handle": [
            ("Driver", "grab_handle_driver"),
            ("Co Driver", "grab_handle_co_driver"),
            ("2nd Row Both side", "grab_handle_2nd_row"),
        ],
        "Sun Roof / Fixed Roof": [
            ("Panoramic Sun Roof", "panoramic_sunroof"),
            ("Roller Blind/ Sunblind", "roller_blind_sunblind"),
        ],
        "Luggage rack": [
            ("Luggage rack", "luggage_rack"),
        ],
        "Wipers & Demister": [
            ("Front Wiper", "front_wiper"),
            ("Defogging", "defogging"),
            ("Rain Sensing Wipers", "rain_sensing_wipers"),
            ("Rear Wiper", "rear_wiper"),
        ],
        "Door": [
            ("Front", "door_front"),
            ("Rear", "door_rear"),
        ],
        "Tailgate": [
            ("Type", "tailgate_type"),
            ("Power operated tail gate + eLatch", "power_tailgate"),
        ],
        "ORVM": [
            ("ORVM", "orvm"),
        ],
        "Steering Wheel": [
            ("Steering Wheel", "steering_wheel"),
        ],
        "Bonnet Stay Mechanism": [
            ("Bonnet Gas Strut", "bonnet_gas_strut"),
        ],
        "Door Trim": [
            ("Bottle Holder", "bottle_holder"),
            ("Door arm Rest", "door_arm_rest"),
        ],
        "Boot/Trunk": [
            ("Boot Organizer", "boot_organizer"),
            ("Lamp", "boot_lamp"),
        ],
        "Power Window": [
            ("All Doors", "power_window_all_doors"),
            ("Driver Door", "power_window_driver_door"),
            ("Window one key lift function", "window_one_key_lift"),
            ("Window anti-clamping function", "window_anti_clamping"),
            ("Multilayer silencing glass at the front door", "multilayer_silencing_glass"),
            ("Front windshield multilayer mute glass", "front_windshield_mute_glass"),
        ],
        "Steering Column": [
            ("Steering Column", "steering_column"),
            ("Steering Column Lock", "steering_column_lock"),
        ],
        "Floor Console": [
            ("Arm Rest", "floor_console_armrest"),
            ("No Of Cup Holder", "cup_holders"),
        ],
        "Wireless charging": [
            ("Wireless charging", "wireless_charging"),
            ("No of wireless charging", "no_of_wireless_charging"),
        ],
        "Door Inner Scuff": [
            ("Front", "door_inner_scuff_front"),
            ("Rear", "door_inner_scuff_rear"),
        ],
        "Voice Recognition": [
            ("Voice Recognition Button On Steering Wheel Control", "voice_recognition_steering"),
        ],
        "Seats": [
            ("Seats", "seats"),
            ("Seat Ventilation", "ventilated_seats"),
            ("Driver and Front Passenger", "seat_ventilation_front_passenger"),
        ],
        "Safety": [
            ("Airbags", "airbags"),
            ("PAB deactivation switch", "pab_deactivation_switch"),
            ("Driver Seat Belt", "driver_seat_belt"),
            ("Front Passenger Seat Belt", "front_passenger_seat_belt"),
            ("2nd Row Seat Belt", "seat_belt_2nd_row"),
            ("Child Anchor", "child_anchor"),
            ("Child Lock", "child_lock"),
            ("Seat Belt Reminder with Buzzer", "seat_belt_reminder"),
            ("Seat Belt Holder - 2nd Row", "seat_belt_holder_2nd_row"),
            ("Sensors", "crash_sensors"),
        ],
        "Technology": [
            ("Infotainment", "infotainment_screen"),
            ("Smart Phone Connectivity", "smartphone_connectivity"),
            ("Bluetooth", "bluetooth"),
        ],
        "Radio": [
            ("AM / FM", "am_fm_radio"),
            ("Digital", "digital_radio"),
        ],
        "ConnectedDrive": [
            ("Wireless", "connected_drive_wireless"),
        ],
        "Branded Audio": [
            ("3D Immersive Sound", "immersive_sound_3d"),
            ("No of speakers", "no_of_speakers"),
            ("Brand", "audio_brand"),
            ("Dolby", "dolby_atmos"),
            ("Adjustable", "audio_adjustable"),
        ],
        "Lighting": [
            ("Headlamp", "headlamp"),
            ("High beam", "high_beam"),
            ("Low beam", "low_beam"),
            ("Auto High Beam", "auto_high_beam"),
            ("Headlamp Leveling", "headlamp_leveling"),
            ("Projector LED", "projector_led"),
            ("Front Fog Lamp", "front_fog_lamp"),
            ("Tail Lamp", "tail_lamp"),
            ("Welcome Lighting", "welcome_lighting"),
            ("Ambient Lighting System", "ambient_lighting"),
            ("Cabin Lamps", "cabin_lamps"),
            ("High Mounted Stop Lamp", "high_mounted_stop_lamp"),
            ("Hazard Lamp", "hazard_lamp"),
        ],
        "Locking": [
            ("Locking", "central_locking"),
            ("Door Lock", "door_lock"),
            ("Speed Sensing Door Lock", "speed_sensing_door_lock"),
            ("Panic Alarm", "panic_alarm"),
            ("Remote Lock/Unlock", "remote_lock_unlock"),
            ("Digital Key Plus", "digital_key_plus"),
        ],
        "Horn": [
            ("Electronic Horn - dual tone", "horn"),
        ],
        "Over speeding Bell": [
            ("Over speeding Bell", "over_speeding_bell"),
        ],
        "ADAS": [
            ("Active Cruise Control with Stop & Go", "active_cruise_control"),
            ("Lane Departure Warning", "lane_departure_warning"),
            ("Automatic Emergency Braking (Stop Assist)", "automatic_emergency_braking"),
            ("Lane Keep Assist", "lane_keep_assist"),
            ("Blind Spot Detection", "blind_spot_detection"),
            ("Blind Spot Collision warning", "blind_spot_collision_warning"),
            ("Forward Collision warning", "forward_collision_warning"),
            ("Rear Collision Warning", "rear_collision_warning"),
            ("Door Open Alert", "door_open_alert"),
            ("High beam Assist", "high_beam_assist"),
            ("Traffic Sign Recognition", "traffic_sign_recognition"),
            ("Rear Cross Traffic Alert", "rear_cross_traffic_alert"),
            ("Traffic jam alert", "traffic_jam_alert"),
            ("Safe Exit Braking/ Warning", "safe_exit_braking"),
            ("Surround View Monitor", "surround_view_monitor"),
            ("Smart Pilot Assist", "smart_pilot_assist"),
        ],
        "Climate": [
            ("Auto Defogging", "auto_defogging"),
            ("No of Zone", "no_of_zone_climate"),
            ("Rear Vent AC", "rear_vent_ac"),
            ("Active Carbon filter", "active_carbon_filter"),
            ("Temp diff control", "temp_diff_control"),
            ("Bottle Opener", "bottle_opener"),
        ],
        "Capabilities": [
            ("Drive Modes", "drive_mode"),
            ("Terrain Modes", "terrain_modes"),
            ("Crawl Smart", "crawl_smart"),
            ("Intelli Turn", "intelli_turn"),
            ("Off-road information display", "off_road_info_display"),
            ("Central Differential", "central_differential"),
            ("Limited Slip Differential At Rear Bridge", "limited_slip_differential"),
            ("Wading sensing system", "wading_sensing_system"),
            ("Electronic gear shift", "electronic_gear_shift"),
            ("Electric Driveline disconnect on front axle", "electric_driveline_disconnect"),
            ("TPMS (Tyre Pressure Monitoring System)", "tpms"),
            ("HHC Uphill Start Assist System", "hhc_uphill_start_assist"),
            ("Engine electronic security", "engine_electronic_security"),
        ],
        "Power outlet / Charging Points": [
            ("No of Front row - USB Type C Port", "usb_type_c_front_row"),
            ("Front row - USB Type C Port", "usb_type_c_front_row_count"),
            ("No of Rear row - USB Type C Port", "usb_type_c_rear_row"),
            ("12V conventional socket", "socket_12v"),
        ],
        "Brakes Detailed": [
            ("Auto Hold", "auto_hold"),
            ("TPMS", "tpms"),
            ("Rollover", "rollover_mitigation"),
            ("RMI", "rmi_anti_rollover"),
            ("VDC", "vdc_vehicle_dynamic"),
            ("CSC", "csc_corner_stability"),
            ("EPB", "epb"),
            ("AVH", "avh_auto_vehicle_hold"),
            ("HAC-HHC", "hac_hill_ascend"),
            ("HBA", "hba_hydraulic_brake"),
            ("DBC", "dbc_downhill_brake"),
            ("EBP", "ebp_electronic_brake_prefill"),
            ("BDW", "bdw_brake_disc_wiping"),
            ("EDTC", "edtc_engine_drag_torque"),
            ("TCS", "tcs_traction_control"),
            ("EBD", "ebd_electronic_brake"),
            ("ABS", "abs_antilock"),
            ("DST", "dst_dynamic_steering"),
            ("EBA", "eba_brake_assist"),
            ("CBC", "cbc_cornering_brake"),
            ("HDC", "hdc_hill_descent"),
        ],
        "Others": [
            ("Active noise reduction", "active_noise_reduction"),
            ("Intelligent voice control", "intelligent_voice_control"),
            ("Dynamic transparent car bottom", "transparent_car_bottom"),
            ("Intellectual dodge", "intellectual_dodge"),
            ("Car picnic table", "car_picnic_table"),
            ("Trunk subwoofer", "trunk_subwoofer"),
            ("Dashcam Provision", "dashcam_provision"),
            ("Cup Holder at Tail door", "cup_holder_tail_door"),
            ("Hooks at Tail door", "hooks_tail_door"),
            ("Warning Triangle at packed with tail door", "warning_triangle_tail_door"),
            ("1st | 2nd row door magnetic Strap", "door_magnetic_strap"),
        ],
        "Market": [
            ("Price Range", "price_range"),
            ("Monthly Sales", "monthly_sales"),
            ("User Rating", "user_rating"),
        ],
    }

    # Build categories structure from tech_spec_groups
    categories = []
    for category_name, specs in tech_spec_groups.items():
        features = []
        for display_name, data_key in specs:
            feat = {"name": display_name}
            for car_name in car_names:
                car_data = comparison_data.get(car_name, {})
                feat[car_name] = car_data.get(data_key)
            features.append(feat)
        categories.append({
            "category": category_name,
            "descriptions": [{"description": category_name, "features": features}]
        })

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
    num_cars = len(car_names)
    total_cols = num_cars + 3  # Category + Description + Features + car columns

    cat_index = 0
    for cat_obj in categories:
        cat_name = cat_obj.get("category", "")
        descriptions = cat_obj.get("descriptions", [])

        if not descriptions:
            continue

        # Category header row with toggle
        cat_collapsed = "" if cat_index == 0 else "collapsed"
        cat_toggle = "−" if cat_index == 0 else "+"
        rows_html += f'''
        <tr class="feat-cat-header {cat_collapsed}" data-cat="feat-cat-{cat_index}" onclick="toggleFeatCategory(this)">
            <td colspan="{total_cols}">
                <span class="group-toggle-btn">{cat_toggle}</span>
                <span class="group-title">{cat_name}</span>
            </td>
        </tr>'''

        desc_index = 0
        for desc_obj in descriptions:
            desc_name = desc_obj.get("description", "")
            features = desc_obj.get("features", [])

            if not features:
                continue

            # Description sub-header row with toggle
            cat_hidden = "" if cat_index == 0 else "cat-row-hidden"
            desc_collapsed = "" if (cat_index == 0 and desc_index == 0) else "collapsed"
            desc_toggle = "−" if (cat_index == 0 and desc_index == 0) else "+"
            rows_html += f'''
            <tr class="feat-desc-header {cat_hidden} {desc_collapsed}" data-cat="feat-cat-{cat_index}" data-desc="feat-desc-{cat_index}-{desc_index}" onclick="toggleFeatDescription(event, this)">
                <td></td>
                <td colspan="{total_cols - 1}">
                    <span class="subgroup-toggle-btn">{desc_toggle}</span>
                    <span class="subgroup-title">{desc_name}</span>
                </td>
            </tr>'''

            # Feature rows
            for feat in features:
                feat_name = feat.get("name", "")
                vals = [feat.get(cn) for cn in car_names]
                cc_list = _cell_classes(feat_name, vals)
                cells = "".join(
                    f'<td class="car-value-cell {cc}">{_render_cell(v)}</td>'
                    for v, cc in zip(vals, cc_list)
                )
                feat_hidden = "" if (cat_index == 0 and desc_index == 0) else "desc-row-hidden"
                if cat_index != 0:
                    feat_hidden += " cat-row-hidden"
                rows_html += f'''
                <tr class="feat-data-row {feat_hidden}" data-cat="feat-cat-{cat_index}" data-desc="feat-desc-{cat_index}-{desc_index}">
                    <td class="cat-cell"></td>
                    <td class="desc-cell"></td>
                    <td class="feature-cell">{feat_name}</td>
                    {cells}
                </tr>'''

            desc_index += 1
        cat_index += 1

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
    <style>
        .feat-cat-header, .feat-desc-header {{
            background: #f8f9fa;
            cursor: pointer;
            user-select: none;
            transition: background 0.2s ease;
        }}
        .feat-cat-header:hover, .feat-desc-header:hover {{
            background: #e9ecef;
        }}
        .feat-cat-header td {{
            padding: 14px 16px !important;
            font-weight: 700;
            color: #1c2a39;
            border-bottom: 2px solid #dee2e6 !important;
        }}
        .feat-desc-header td {{
            padding: 10px 16px !important;
            font-weight: 600;
            color: #495057;
            border-bottom: 1px solid #dee2e6 !important;
            background: #fff;
        }}
        .group-toggle-btn, .subgroup-toggle-btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            background: #dd032b;
            color: #fff;
            border-radius: 4px;
            font-size: 18px;
            font-weight: 700;
            margin-right: 12px;
            line-height: 1;
        }}
        .subgroup-toggle-btn {{
            width: 20px;
            height: 20px;
            font-size: 16px;
            background: #6c757d;
            margin-right: 10px;
        }}
        .group-title {{
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .subgroup-title {{
            font-size: 13px;
            letter-spacing: 0.3px;
        }}
        .feat-data-row {{
            transition: all 0.2s ease;
        }}
        .cat-row-hidden, .desc-row-hidden {{
            display: none;
        }}
        @media print {{
            .feat-cat-header, .feat-desc-header {{
                background: #f8f9fa !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .group-toggle-btn, .subgroup-toggle-btn {{
                display: none;
            }}
            .cat-row-hidden, .desc-row-hidden {{
                display: table-row !important;
            }}
        }}
    </style>
    <script>
        function toggleFeatCategory(headerRow) {{
            var catId = headerRow.getAttribute('data-cat');
            var isCollapsed = headerRow.classList.contains('collapsed');
            var toggleBtn = headerRow.querySelector('.group-toggle-btn');
            var childRows = document.querySelectorAll('tr[data-cat="' + catId + '"]:not(.feat-cat-header)');

            if (isCollapsed) {{
                headerRow.classList.remove('collapsed');
                toggleBtn.textContent = '−';
                childRows.forEach(function(row) {{
                    row.classList.remove('cat-row-hidden');
                    // If it's a desc header that's not collapsed, show its feature rows
                    if (row.classList.contains('feat-desc-header') && !row.classList.contains('collapsed')) {{
                        var descId = row.getAttribute('data-desc');
                        var featRows = document.querySelectorAll('tr.feat-data-row[data-desc="' + descId + '"]');
                        featRows.forEach(function(fr) {{
                            fr.classList.remove('desc-row-hidden');
                        }});
                    }}
                }});
            }} else {{
                headerRow.classList.add('collapsed');
                toggleBtn.textContent = '+';
                childRows.forEach(function(row) {{
                    row.classList.add('cat-row-hidden');
                }});
            }}
        }}

        function toggleFeatDescription(event, headerRow) {{
            event.stopPropagation();
            var descId = headerRow.getAttribute('data-desc');
            var isCollapsed = headerRow.classList.contains('collapsed');
            var toggleBtn = headerRow.querySelector('.subgroup-toggle-btn');
            var featRows = document.querySelectorAll('tr.feat-data-row[data-desc="' + descId + '"]');

            if (isCollapsed) {{
                headerRow.classList.remove('collapsed');
                toggleBtn.textContent = '−';
                featRows.forEach(function(row) {{
                    row.classList.remove('desc-row-hidden');
                }});
            }} else {{
                headerRow.classList.add('collapsed');
                toggleBtn.textContent = '+';
                featRows.forEach(function(row) {{
                    row.classList.add('desc-row-hidden');
                }});
            }}
        }}
    </script>
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
    import concurrent.futures

    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data
                 and not name.strip().upper().startswith("CODE:")]

    if not car_names:
        return ""

    # Extract lifecycle data for all cars in parallel
    print(f"Extracting lifecycle data for {len(car_names)} cars in parallel...")
    lifecycle_data_map = {}

    def extract_lifecycle_for_car(car_name):
        print(f"  [{car_name}] Extracting 5-year lifecycle timeline...")
        car_data = comparison_data.get(car_name, {})
        return car_name, _extract_lifecycle_data(car_name, car_data)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(car_names), 5)) as executor:
        futures = [executor.submit(extract_lifecycle_for_car, name) for name in car_names]
        for future in concurrent.futures.as_completed(futures):
            car_name, lifecycle_data = future.result()
            lifecycle_data_map[car_name] = lifecycle_data
            print(f"  [{car_name}] ✓ Lifecycle data extracted")

    pages_html = ""

    for car_name in car_names:
        lifecycle_data = lifecycle_data_map.get(car_name, {})

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


# ---------------------------------------------------------------------------
# Vehicle Highlights Section
# ---------------------------------------------------------------------------

def _get_val(car_data: Dict[str, Any], key: str) -> str:
    """Return a scraped value, falling back to empty string for N/A variants."""
    raw = car_data.get(key, "")
    if not raw or str(raw).strip().lower() in ("not available", "n/a", "none", ""):
        return ""
    return str(raw).strip()


def generate_vehicle_highlights_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate a 'Vehicle Highlights' section in tabular format.
    Rows are metrics/features, columns are vehicles.
    Uses already-scraped data — no additional API calls.
    """
    if not comparison_data:
        return ""

    car_entries = [
        (name, data) for name, data in comparison_data.items()
        if isinstance(data, dict) and "error" not in data
    ]
    if not car_entries:
        return ""

    # Define highlight groups and their metrics
    highlight_groups = [
        ("Overview", [
            ("Price Range", "price_range"),
            ("User Rating", "user_rating"),
            ("Monthly Sales", "monthly_sales"),
            ("Seating Capacity", "seating_capacity"),
        ]),
        ("Performance", [
            ("Acceleration", "acceleration"),
            ("Torque", "torque"),
            ("Mileage", "mileage"),
            ("City Performance", "city_performance"),
            ("Highway Performance", "highway_performance"),
        ]),
        ("Safety", [
            ("NCAP Rating", "ncap_rating"),
            ("Airbags", "airbags"),
            ("ADAS", "adas"),
            ("Safety Features", "vehicle_safety_features"),
        ]),
        ("Comfort & Technology", [
            ("Climate Control", "climate_control"),
            ("Infotainment Screen", "infotainment_screen"),
            ("Connectivity", "apple_carplay"),
            ("Sunroof", "sunroof"),
            ("Ventilated Seats", "ventilated_seats"),
            ("Audio System", "audio_system"),
        ]),
        ("Ride & Handling", [
            ("Ride Quality", "ride_quality"),
            ("Stability", "stability"),
            ("NVH", "nvh"),
        ]),
    ]

    # Build table header with car names
    header_cells = '<th class="vh-feature-col">Feature</th>'
    for car_name, cd in car_entries:
        header_cells += f'<th class="vh-car-col">{car_name}</th>'

    # Build table rows grouped by category
    rows_html = ""
    for group_name, metrics in highlight_groups:
        # Group header row
        colspan = len(car_entries) + 1
        rows_html += f'''
        <tr class="vh-group-header">
            <td colspan="{colspan}">{group_name}</td>
        </tr>'''

        # Metric rows
        for label, field_key in metrics:
            rows_html += f'<tr class="vh-data-row"><td class="vh-feature-name">{label}</td>'
            for car_name, cd in car_entries:
                value = _get_val(cd, field_key)
                if not value:
                    value = "—"
                # Truncate long values with read more
                TRUNC = 100
                if len(str(value)) > TRUNC:
                    uid = abs(hash(car_name + label)) % 9999999
                    short = str(value)[:TRUNC]
                    rest = str(value)[TRUNC:]
                    cell_html = (
                        f'{short}'
                        f'<span class="vh-val-rest" id="vh-rest-{uid}" style="display:none;">{rest}</span>'
                        f'<button class="vh-read-more" '
                        f'onclick="var r=document.getElementById(\'vh-rest-{uid}\');'
                        f'var show=r.style.display===\'none\';'
                        f'r.style.display=show?\'inline\':\'none\';'
                        f'this.textContent=show?\' read less\':\'… read more\';">'
                        f'… read more</button>'
                    )
                else:
                    cell_html = value
                rows_html += f'<td class="vh-car-value">{cell_html}</td>'
            rows_html += '</tr>'

    html = f'''
    <div class="content vh-section" id="vehicle-highlights">
        <div class="section-header">
            <div class="icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
            </div>
            <h2>Vehicle Highlights</h2>
        </div>
        <p class="vh-subtitle">Key metrics and features comparison across all vehicles</p>
        <div class="vh-table-container">
            <table class="vh-table">
                <thead>
                    <tr>{header_cells}</tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>

    <style>
        .vh-section {{
            margin-top: 40px;
        }}

        .vh-subtitle {{
            font-size: 13px;
            color: #6c757d;
            margin: -8px 0 24px 0;
        }}

        .vh-table-container {{
            overflow-x: auto;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            border: 1px solid #e9ecef;
            background: #fff;
        }}

        .vh-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        .vh-table thead tr {{
            background: linear-gradient(135deg, #1c2a39 0%, #2E3B4E 100%);
        }}

        .vh-table thead th {{
            padding: 16px 14px;
            font-weight: 600;
            color: #fff;
            text-align: center;
            border-bottom: 2px solid #dee2e6;
            white-space: nowrap;
        }}

        .vh-table thead th.vh-feature-col {{
            text-align: left;
            background: #dd032b;
            min-width: 160px;
        }}

        .vh-table thead th.vh-car-col {{
            min-width: 200px;
        }}

        .vh-group-header td {{
            background: #f8f9fa;
            font-weight: 700;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #dd032b;
            padding: 12px 14px;
            border-bottom: 2px solid #dee2e6;
        }}

        .vh-data-row td {{
            padding: 12px 14px;
            border-bottom: 1px solid #e9ecef;
            vertical-align: top;
            line-height: 1.6;
        }}

        .vh-data-row:hover td {{
            background: #f8f9fa;
        }}

        .vh-feature-name {{
            font-weight: 600;
            color: #1c2a39;
            background: #fafafa;
        }}

        .vh-car-value {{
            text-align: left;
            color: #495057;
        }}

        .vh-read-more {{
            background: none;
            border: none;
            padding: 0;
            margin: 0;
            font-size: 11px;
            font-weight: 600;
            color: #dd032b;
            cursor: pointer;
            text-decoration: underline;
            line-height: inherit;
            vertical-align: baseline;
        }}

        .vh-read-more:hover {{
            color: #a80020;
        }}

        @media print {{
            .vh-val-rest {{
                display: inline !important;
            }}
            .vh-read-more {{
                display: none !important;
            }}
            .vh-table-container {{
                box-shadow: none;
            }}
            .vh-table {{
                page-break-inside: avoid;
            }}
        }}

        @media (max-width: 768px) {{
            .vh-table {{
                font-size: 12px;
            }}
            .vh-table thead th,
            .vh-table td {{
                padding: 10px 8px;
            }}
            .vh-table thead th.vh-feature-col {{
                min-width: 120px;
            }}
            .vh-table thead th.vh-car-col {{
                min-width: 150px;
            }}
        }}
    </style>
    '''

    return html


# ============================================================================
# VENN DIAGRAM SECTION
# ============================================================================

def _derive_venn_from_summary(
    summary_data: Dict[str, Any],
    comparison_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build Venn feature sets directly from summary_data which already has
    features_not_in_car1 (car2-unique) and features_in_car1_only (car1-unique).
    Makes a small Gemini call only to identify COMMON features shared by both cars.
    Returns {"features": [...], "_car_names": [...], "car1_unique": [...], "car2_unique": [...], "common": [...]}
    """
    SKIP_KEYS = {
        "images", "source_urls", "gcs_folder", "scraping_method", "timestamp",
        "chart_gcs_uri", "chart_signed_url", "summary_data", "variant_walk",
        "car_name", "method", "is_code_car",
    }
    EMPTY = {"Not Available", "N/A", "not available", "n/a", "-", "", "None", "Not found"}

    car_names = [n for n, d in comparison_data.items()
                 if isinstance(d, dict) and "error" not in d]
    if len(car_names) < 2 or not summary_data:
        return {}

    car1, car2 = car_names[0], car_names[1]

    # Flatten car1-unique features from features_in_car1_only
    car1_unique: List[str] = []
    for category, items in (summary_data.get("features_in_car1_only") or {}).items():
        if isinstance(items, list):
            for item in items:
                s = str(item).strip()
                if s:
                    car1_unique.append(s)

    # Flatten car2-unique features from features_not_in_car1
    car2_unique: List[str] = []
    for category, items in (summary_data.get("features_not_in_car1") or {}).items():
        if isinstance(items, list):
            for item in items:
                s = str(item).strip()
                if s:
                    car2_unique.append(s)

    # Build condensed spec data (for common-feature extraction)
    condensed: Dict[str, dict] = {}
    for car_name, car_data in comparison_data.items():
        if not isinstance(car_data, dict) or "error" in car_data:
            continue
        condensed[car_name] = {
            k: str(v)[:120]
            for k, v in car_data.items()
            if k not in SKIP_KEYS
            and not k.endswith("_citation")
            and v and str(v).strip() not in EMPTY
        }

    # Ask Gemini only for COMMON features (much smaller prompt)
    common_features: List[str] = []
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        from product_planning_agent.config import GEMINI_LITE_LOCATION, PROJECT_ID
        vertexai.init(project=PROJECT_ID, location=GEMINI_LITE_LOCATION)
        model = GenerativeModel("gemini-2.5-flash-lite")

        # Build a clearer comparison of what both cars have
        car1_data = condensed.get(car1, {})
        car2_data = condensed.get(car2, {})

        # Find specs that exist in both cars
        shared_specs = {}
        for key in car1_data:
            if key in car2_data:
                shared_specs[key] = {car1: car1_data[key], car2: car2_data[key]}

        prompt = f"""You are an automotive analyst comparing two vehicles:
- {car1}
- {car2}

Here are specifications/features that BOTH cars have (key: value for each car):
{json.dumps(shared_specs, indent=2)[:4000]}

TASK: Identify 15-25 COMMON features that both cars share. Look for:
1. Safety features both have (airbags, ABS, ESP, parking sensors, cameras, ISOFIX)
2. Comfort features both have (AC, power windows, power steering, central locking)
3. Infotainment both have (touchscreen, Bluetooth, USB, speakers)
4. Convenience both have (keyless entry, push start, cruise control)
5. Exterior both have (alloy wheels, LED lights, fog lamps)
6. Body type similarities (SUV, 5-seater, similar dimensions)
7. Engine/transmission types both offer (petrol, diesel, automatic, manual options)

For each common feature, write a SHORT description (3-8 words) like:
- "6 Airbags standard"
- "Touchscreen infotainment system"
- "Automatic climate control"
- "LED headlamps with DRLs"
- "Rear parking camera"

DO NOT include features that are DIFFERENT between the cars.
ONLY include features genuinely present in BOTH vehicles.

Return ONLY valid JSON:
{{"common_features": ["Feature 1", "Feature 2", ...]}}"""

        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        data = json.loads(text)
        common_features = data.get("common_features", [])
    except Exception as e:
        print(f"[Venn] Common features extraction failed: {e}")
        common_features = []

    # Build the unified features list in the original format
    features: List[Dict] = []
    for item in car1_unique:
        features.append({"name": item, "present_in": [car1]})
    for item in car2_unique:
        features.append({"name": item, "present_in": [car2]})
    for item in common_features:
        features.append({"name": item, "present_in": [car1, car2]})

    return {
        "features": features,
        "_car_names": car_names,
        # Pre-computed sets for quick access
        "car1_unique": car1_unique,
        "car2_unique": car2_unique,
        "common": common_features,
    }


def _compute_window_sets(features: List[Dict], window: List[str]) -> Dict[str, List[str]]:
    """
    Given a list of {name, present_in} features and a window of car names,
    compute which features belong to each region:
      unique_<car>        — only that car within window
      pair_<A>_<B>        — shared by exactly A & B (for 3 or 4-car windows)
      triple_<A>_<B>_<C>  — shared by exactly 3 cars (4-car windows only)
      common              — all cars in window
    """
    window_set = set(window)
    regions: Dict[str, List[str]] = {"common": []}
    for car in window:
        regions[f"unique_{car}"] = []
    # pair regions for 3 and 4-car windows
    if len(window) >= 3:
        for i in range(len(window)):
            for j in range(i + 1, len(window)):
                regions[f"pair_{window[i]}_{window[j]}"] = []
    # triple regions for 4-car window
    if len(window) == 4:
        for i in range(len(window)):
            for j in range(i + 1, len(window)):
                for k in range(j + 1, len(window)):
                    regions[f"triple_{window[i]}_{window[j]}_{window[k]}"] = []

    for feat in features:
        present = set(feat.get("present_in", [])) & window_set
        if not present:
            continue
        name = feat["name"]
        if present == window_set:
            regions["common"].append(name)
        elif len(present) == 1:
            [car] = present
            regions[f"unique_{car}"].append(name)
        elif len(present) == 2:
            [c1, c2] = sorted(present, key=lambda x: window.index(x))
            key = f"pair_{c1}_{c2}"
            if key in regions:
                regions[key].append(name)
        elif len(present) == 3 and len(window) == 4:
            [c1, c2, c3] = sorted(present, key=lambda x: window.index(x))
            key = f"triple_{c1}_{c2}_{c3}"
            if key in regions:
                regions[key].append(name)
    return regions


def generate_venn_diagram_section(
    comparison_data: Dict[str, Any],
    summary_data: Dict[str, Any] = None,
) -> str:
    """
    Render Venn diagram in the style of the reference image:
    - Large semi-transparent pastel overlapping circles
    - Short spec names placed directly inside each region (unique + intersections)
    - Car names bold in each unique region, like the reference
    - Detailed expandable list below
    - 2 cars → 2-circle | 3 cars → 3-circle triangle | 4 cars → 2×2 grid
    - 5+ cars → sliding windows of 4
    """
    if not summary_data:
        return ""
    venn_data = _derive_venn_from_summary(summary_data, comparison_data)
    if not venn_data:
        return ""

    car_names: List[str] = venn_data.get("_car_names", [])
    features: List[Dict] = venn_data.get("features", [])
    if len(car_names) < 2 or not features:
        return ""

    import re as _re

    n = len(car_names)

    # Mahindra brand colors - red, blue, gray palette (no yellow)
    FILLS   = [
        "rgba(180,180,190,0.50)",   # soft gray
        "rgba(220,100,100,0.50)",   # mahindra red/coral
        "rgba(100,150,220,0.50)",   # mahindra blue
        "rgba(160,160,170,0.50)",   # medium gray
    ]
    STROKES = ["#8888a0", "#cc0000", "#0066cc", "#888899"]
    ALPHA   = [
        "rgba(180,180,190,0.13)",
        "rgba(220,100,100,0.13)",
        "rgba(100,150,220,0.13)",
        "rgba(160,160,170,0.13)",
    ]

    # Shorten a feature description to a concise spec name (2-3 words max)
    def _short(desc: str, max_words: int = 3) -> str:
        s = _re.sub(r'\s*\([^)]*\)', '', str(desc)).strip()
        s = _re.sub(r'\s*—.*$', '', s).strip()
        words = s.split()
        return ' '.join(words[:max_words])

    # Build sliding windows — up to 4 cars per diagram
    if n <= 4:
        windows = [car_names[:]]
    else:
        windows = [car_names[i:i+4] for i in range(n - 3)]

    # ── helper: collapsible detail list below the SVG ────────────────────────
    MAX_VISIBLE = 12

    def region_items_html(items: List[str], color: str, bg: str) -> str:
        if not items:
            return '<p class="venn-empty-inline">None identified</p>'
        shown  = items[:MAX_VISIBLE]
        hidden = items[MAX_VISIBLE:]
        lis = "".join(
            f'<li class="venn-item-text" style="border-left:3px solid {color};">{item}</li>'
            for item in shown
        )
        extra = ""
        if hidden:
            uid = abs(hash(str(items[:3])))
            extra_lis = "".join(
                f'<li class="venn-item-text" style="border-left:3px solid {color};">{item}</li>'
                for item in hidden
            )
            extra  = f'<ul class="venn-item-list venn-hidden-items" id="vx{uid}" style="display:none;">{extra_lis}</ul>'
            extra += (f'<button class="venn-show-more" '
                      f'onclick="document.getElementById(\'vx{uid}\').style.display=\'block\';'
                      f'this.style.display=\'none\';">+ {len(hidden)} more</button>')
        return f'<ul class="venn-item-list">{lis}</ul>{extra}'

    # ── foreignObject helper: places text block at a region centroid ─────────
    # Shows car name (bold) in unique regions + short spec names
    MAX_IN_CIRCLE = 5   # items shown inside SVG per region

    def _fo(x: int, y: int, w: int, h: int,
            title: str, title_color: str,
            items: List[str], is_intersection: bool = False) -> str:
        """Render a foreignObject text block centred at (x,y)."""
        short_items = [_short(i) for i in items[:MAX_IN_CIRCLE]]
        overflow    = len(items) - MAX_IN_CIRCLE
        items_html  = ", ".join(short_items)
        overflow_el = f'<div class="vr-more">+{overflow} more</div>' if overflow > 0 else ""
        title_el    = (f'<div class="vr-title" style="color:{title_color};">{title}</div>'
                       if title else "")
        content_cls = "vr-inter" if is_intersection else "vr-unique"
        return (
            f'<foreignObject x="{x - w//2}" y="{y - h//2}" width="{w}" height="{h}">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" class="vr-box {content_cls}">'
            f'{title_el}'
            f'<div class="vr-items">{items_html}{overflow_el}</div>'
            f'</div></foreignObject>'
        )

    # ── build each window diagram ─────────────────────────────────────────────
    diagrams_html = ""

    def _make_venn_svg(window: List[str], regions: Dict) -> str:
        common = regions.get("common", [])
        w = len(window)

        # ── 2-car ──────────────────────────────────────────────────────────
        if w == 2:
            ca, cb   = window
            sa, sb   = STROKES[0], STROKES[1]
            aa, ab_  = ALPHA[0], ALPHA[1]
            u_a = regions.get(f"unique_{ca}", [])
            u_b = regions.get(f"unique_{cb}", [])

            fo_a    = _fo(148, 210, 175, 200, ca, sa, u_a)
            fo_com  = _fo(450, 210, 160, 200, "", "#444", common, True)
            fo_b    = _fo(752, 210, 175, 200, cb, sb, u_b)

            svg = f"""<svg viewBox="0 0 900 420" width="100%" preserveAspectRatio="xMidYMid meet"
     style="font-family:Georgia,serif;">
  <circle cx="305" cy="210" r="195" fill="{FILLS[0]}" stroke="{sa}" stroke-width="1.2"/>
  <circle cx="595" cy="210" r="195" fill="{FILLS[1]}" stroke="{sb}" stroke-width="1.2"/>
  {fo_a}{fo_com}{fo_b}
</svg>"""
            panels = _detail_panels(window, regions, STROKES, ALPHA, common)
            return f'<div class="venn-svg-outer">{svg}</div>{panels}'

        # ── 3-car (triangle) ───────────────────────────────────────────────
        if w == 3:
            ca, cb, cc = window
            sa, sb, sc = STROKES[0], STROKES[1], STROKES[2]
            u_a  = regions.get(f"unique_{ca}", [])
            u_b  = regions.get(f"unique_{cb}", [])
            u_c  = regions.get(f"unique_{cc}", [])
            p_ab = regions.get(f"pair_{ca}_{cb}", [])
            p_ac = regions.get(f"pair_{ca}_{cc}", [])
            p_bc = regions.get(f"pair_{cb}_{cc}", [])

            fo_a   = _fo(450,  75, 175, 155, ca, sa, u_a)
            fo_b   = _fo(155, 440, 175, 130, cb, sb, u_b)
            fo_c   = _fo(745, 440, 175, 130, cc, sc, u_c)
            fo_ab  = _fo(346, 248, 130, 100, "", "#666", p_ab,  True)
            fo_ac  = _fo(554, 248, 130, 100, "", "#666", p_ac,  True)
            fo_bc  = _fo(450, 408, 130, 100, "", "#666", p_bc,  True)
            fo_com = _fo(450, 308, 140, 100, "", "#333", common, True)

            svg = f"""<svg viewBox="0 0 900 580" width="100%" preserveAspectRatio="xMidYMid meet"
     style="font-family:Georgia,serif;">
  <circle cx="450" cy="220" r="180" fill="{FILLS[0]}" stroke="{sa}" stroke-width="1.2"/>
  <circle cx="305" cy="365" r="180" fill="{FILLS[1]}" stroke="{sb}" stroke-width="1.2"/>
  <circle cx="595" cy="365" r="180" fill="{FILLS[2]}" stroke="{sc}" stroke-width="1.2"/>
  {fo_a}{fo_b}{fo_c}{fo_ab}{fo_ac}{fo_bc}{fo_com}
</svg>"""
            panels = _detail_panels(window, regions, STROKES, ALPHA, common)
            return f'<div class="venn-svg-outer">{svg}</div>{panels}'

        # ── 4-car (2×2 grid, like reference image) ─────────────────────────
        if w == 4:
            ca, cb, cc, cd = window
            sa, sb, sc, sd = STROKES[0], STROKES[1], STROKES[2], STROKES[3]
            u_a  = regions.get(f"unique_{ca}", [])
            u_b  = regions.get(f"unique_{cb}", [])
            u_c  = regions.get(f"unique_{cc}", [])
            u_d  = regions.get(f"unique_{cd}", [])
            p_ab = regions.get(f"pair_{ca}_{cb}", [])
            p_cd = regions.get(f"pair_{cc}_{cd}", [])
            p_ac = regions.get(f"pair_{ca}_{cc}", [])
            p_bd = regions.get(f"pair_{cb}_{cd}", [])
            p_ad = regions.get(f"pair_{ca}_{cd}", [])
            p_bc = regions.get(f"pair_{cb}_{cc}", [])

            # Unique corner blocks — positioned in the outermost region of each circle
            fo_a  = _fo(148, 180, 160, 145, ca, sa, u_a)
            fo_b  = _fo(752, 180, 160, 145, cb, sb, u_b)
            fo_c  = _fo(148, 560, 160, 145, cc, sc, u_c)
            fo_d  = _fo(752, 560, 160, 145, cd, sd, u_d)
            # Pair intersections
            fo_ab = _fo(450, 180, 135,  95, "", "#555", p_ab, True)
            fo_cd = _fo(450, 560, 135,  95, "", "#555", p_cd, True)
            fo_ac = _fo(175, 370, 130,  95, "", "#555", p_ac, True)
            fo_bd = _fo(725, 370, 130,  95, "", "#555", p_bd, True)
            fo_ad = _fo(528, 290, 120,  85, "", "#777", p_ad, True)
            fo_bc = _fo(372, 450, 120,  85, "", "#777", p_bc, True)
            # Center — common to all 4
            fo_com = _fo(450, 370, 145, 105, "", "#222", common, True)

            svg = f"""<svg viewBox="0 0 900 740" width="100%" preserveAspectRatio="xMidYMid meet"
     style="font-family:Georgia,serif;">
  <circle cx="308" cy="280" r="200" fill="{FILLS[0]}" stroke="{sa}" stroke-width="1.2"/>
  <circle cx="592" cy="280" r="200" fill="{FILLS[1]}" stroke="{sb}" stroke-width="1.2"/>
  <circle cx="308" cy="460" r="200" fill="{FILLS[2]}" stroke="{sc}" stroke-width="1.2"/>
  <circle cx="592" cy="460" r="200" fill="{FILLS[3]}" stroke="{sd}" stroke-width="1.2"/>
  {fo_a}{fo_b}{fo_c}{fo_d}
  {fo_ab}{fo_cd}{fo_ac}{fo_bd}{fo_ad}{fo_bc}
  {fo_com}
</svg>"""
            panels = _detail_panels(window, regions, STROKES, ALPHA, common)
            return f'<div class="venn-svg-outer">{svg}</div>{panels}'

        return ""

    def _detail_panels(window, regions, strokes, alpha, common) -> str:
        """Collapsible detail grid shown below the SVG."""
        parts = []
        for car, col, alp in zip(window, strokes, alpha):
            u = regions.get(f"unique_{car}", [])
            parts.append(f'<div class="venn-region venn-multi-region" style="border-color:{col};background:{alp};">'
                         f'<div class="venn-region-title" style="color:{col};border-bottom:2px solid {col};">'
                         f'Only in {car} <span class="venn-count-badge" style="background:{col};">{len(u)}</span></div>'
                         f'{region_items_html(u, col, alp)}</div>')
        wn = len(window)
        for i in range(wn):
            for j in range(i+1, wn):
                p = regions.get(f"pair_{window[i]}_{window[j]}", [])
                if p:
                    parts.append(f'<div class="venn-region venn-multi-region" style="border-color:#6b7280;background:rgba(107,114,128,0.1);">'
                                 f'<div class="venn-region-title" style="color:#6b7280;border-bottom:2px solid #6b7280;">'
                                 f'{window[i]} &amp; {window[j]} <span class="venn-count-badge" style="background:#6b7280;">{len(p)}</span></div>'
                                 f'{region_items_html(p,"#6b7280","rgba(107,114,128,0.1)")}</div>')
        lbl = f"All {wn}" if wn > 2 else "Both"
        parts.append(f'<div class="venn-region venn-multi-region" style="border-color:#374151;background:rgba(55,65,81,0.1);">'
                     f'<div class="venn-region-title" style="color:#374151;border-bottom:2px solid #374151;">'
                     f'Common to {lbl} <span class="venn-count-badge" style="background:#374151;">{len(common)}</span></div>'
                     f'{region_items_html(common,"#374151","rgba(55,65,81,0.1)")}</div>')
        return f'<div class="venn-text-layout venn-multi-layout">{"".join(parts)}</div>'

    for w_idx, window in enumerate(windows):
        regions  = _compute_window_sets(features, window)
        subtitle = f"Window {w_idx+1}: {' · '.join(window)}" if len(windows) > 1 else ""
        diagrams_html += f"""
    <div class="venn-block">
        {"<div class='venn-window-label'>" + subtitle + "</div>" if subtitle else ""}
        <div class="venn-canvas-wrap">
            {_make_venn_svg(window, regions)}
        </div>
    </div>"""

    html = f"""
    <div class="content venn-section" id="venn-section">
        <div class="section-header">
            <div class="icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="9" cy="12" r="6"/><circle cx="15" cy="12" r="6"/>
                </svg>
            </div>
            <h2>Feature Overlap Analysis</h2>
        </div>
        {diagrams_html}
        <div class="venn-note">
            <strong>Note:</strong> Unique &amp; common features derived from AI analysis of spec data.
            {"Sliding window of 4 cars per diagram." if len(windows) > 1 else ""}
        </div>
    </div>

    <style>
        .venn-section {{ margin-bottom: 40px; }}

        .venn-block {{
            margin-bottom: 48px;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            overflow: hidden;
            background: #fff;
            box-shadow: 0 2px 14px rgba(0,0,0,0.07);
        }}

        .venn-window-label {{
            padding: 10px 20px;
            background: #1a1a1a;
            color: #fff;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}

        .venn-canvas-wrap {{
            padding: 12px 12px 0 12px;
            background: #fff;
        }}

        .venn-svg-outer {{
            background: #fff;
            overflow: visible;
        }}

        /* ── text blocks inside SVG regions ── */
        .vr-box {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            height: 100%;
            padding: 4px;
            box-sizing: border-box;
        }}
        .vr-title {{
            font-family: Georgia, serif;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
            line-height: 1.2;
        }}
        .vr-items {{
            font-family: Georgia, serif;
            font-size: 11px;
            color: #2d2d2d;
            line-height: 1.55;
        }}
        .vr-more {{
            font-size: 9.5px;
            color: #888;
            font-style: italic;
            margin-top: 2px;
        }}
        .vr-inter .vr-items {{ font-size: 10.5px; color: #333; }}

        /* ── detail panels below diagram ── */
        .venn-text-layout {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 0;
            border: 1px solid #e5e7eb;
            border-top: none;
            border-radius: 0 0 10px 10px;
            overflow: hidden;
            margin: 0 4px 14px 4px;
        }}

        .venn-region {{
            padding: 0;
            border-right: 1px solid #e5e7eb;
            display: flex;
            flex-direction: column;
        }}
        .venn-region:last-child {{ border-right: none; }}
        .venn-multi-region {{ border-bottom: 1px solid #e5e7eb; }}

        .venn-region-title {{
            padding: 9px 11px;
            font-size: 11.5px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
        }}

        .venn-count-badge {{
            color: #fff;
            padding: 2px 7px;
            border-radius: 10px;
            font-size: 10.5px;
            font-weight: 800;
            flex-shrink: 0;
        }}

        .venn-item-list {{
            list-style: none;
            padding: 6px 9px;
            margin: 0;
            flex: 1;
        }}

        .venn-item-text {{
            padding: 3px 7px 3px 9px;
            font-size: 11px;
            line-height: 1.5;
            color: #1f2937;
            margin-bottom: 2px;
            border-radius: 0 3px 3px 0;
        }}

        .venn-empty-inline {{
            font-size: 11px;
            color: #9ca3af;
            font-style: italic;
            padding: 7px 9px;
            margin: 0;
        }}

        .venn-hidden-items {{ padding: 0 9px; margin: 0; }}

        .venn-show-more {{
            background: none;
            border: none;
            color: #6b7280;
            font-size: 10.5px;
            cursor: pointer;
            padding: 2px 9px 7px;
            text-decoration: underline;
            font-weight: 600;
        }}
        .venn-show-more:hover {{ color: #374151; }}

        .venn-note {{
            margin: 4px 0 0;
            padding: 7px 13px;
            background: #f9fafb;
            border-radius: 6px;
            font-size: 11px;
            border-left: 4px solid #555;
            color: #6b7280;
        }}

        @media (max-width: 768px) {{
            .venn-text-layout {{ grid-template-columns: 1fr !important; }}
            .venn-region {{ border-right: none !important; border-bottom: 1px solid #e5e7eb; }}
        }}
        @media print {{
            .venn-block {{ page-break-inside: avoid; break-inside: avoid; }}
            .venn-hidden-items {{ display: block !important; }}
            .venn-show-more {{ display: none !important; }}
        }}
    </style>
    """

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
       1:1 COMPARISON GALLERY STYLES
       ======================================== */
    .comparison-gallery {
        margin-top: 40px;
    }

    .comparison-gallery .section-header {
        display: flex;
        align-items: center;
        gap: 15px;
        flex-wrap: wrap;
    }

    .comparison-legend {
        display: flex;
        gap: 15px;
        margin-left: auto;
    }

    .legend-car {
        padding: 6px 14px;
        background: #1c2a39;
        color: white;
        font-size: 12px;
        font-weight: 600;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .legend-car:nth-child(2) {
        background: #cc0000;
    }

    .legend-car:nth-child(3) {
        background: #2E3B4E;
    }

    .legend-car:nth-child(4) {
        background: #8b0000;
    }

    .legend-car:nth-child(5) {
        background: #4a5568;
    }

    .comparison-gallery-grid {
        display: flex;
        flex-direction: column;
        gap: 30px;
        padding: 25px 0;
    }

    .comparison-row {
        background: white;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid #e9ecef;
    }

    .comparison-feature-label {
        background: #1c2a39;
        color: white;
        padding: 14px 25px;
        font-size: 15px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        text-align: center;
        border-bottom: 3px solid #cc0000;
    }

    .comparison-cells {
        display: grid;
        grid-template-columns: repeat(var(--num-cars, 2), 1fr);
        gap: 0;
    }

    .comparison-cell {
        display: flex;
        flex-direction: column;
        border-right: 1px solid #e9ecef;
        background: #fafbfc;
    }

    .comparison-cell:last-child {
        border-right: none;
    }

    .comparison-car-label {
        padding: 12px 15px;
        text-align: center;
        font-size: 13px;
        font-weight: 700;
        color: #1c2a39;
        background: #f0f2f5;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid #e9ecef;
    }

    .comparison-cell:nth-child(1) .comparison-car-label {
        background: #1c2a39;
        color: white;
    }

    .comparison-cell:nth-child(2) .comparison-car-label {
        background: #cc0000;
        color: white;
    }

    .comparison-cell:nth-child(3) .comparison-car-label {
        background: #2E3B4E;
        color: white;
    }

    .comparison-cell:nth-child(4) .comparison-car-label {
        background: #8b0000;
        color: white;
    }

    .comparison-cell:nth-child(5) .comparison-car-label {
        background: #4a5568;
        color: white;
    }

    .comparison-image-wrapper {
        flex: 1;
        min-height: 220px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 15px;
        background: white;
    }

    .comparison-image-wrapper img {
        max-width: 100%;
        max-height: 200px;
        object-fit: contain;
        border-radius: 8px;
        transition: transform 0.3s ease;
    }

    .comparison-image-wrapper img:hover {
        transform: scale(1.05);
    }

    .comparison-cell.no-image-cell .comparison-image-wrapper {
        background: #f8f9fa;
    }

    .no-image {
        color: #adb5bd;
        font-size: 13px;
        font-style: italic;
        text-align: center;
        padding: 40px 20px;
    }

    .comparison-ai-note {
        padding: 12px 15px;
        font-size: 12px;
        font-weight: 400;
        color: #495057;
        background: #f8f9fa;
        line-height: 1.5;
        border-top: 1px solid #e9ecef;
    }

    .ai-note-label {
        color: #cc0000;
        font-weight: 600;
        font-style: normal;
    }

    /* Responsive adjustments for comparison gallery */
    @media (max-width: 768px) {
        .comparison-cells {
            grid-template-columns: 1fr;
        }

        .comparison-cell {
            border-right: none;
            border-bottom: 1px solid #e9ecef;
        }

        .comparison-cell:last-child {
            border-bottom: none;
        }

        .comparison-image-wrapper {
            min-height: 180px;
        }

        .comparison-legend {
            margin-left: 0;
            width: 100%;
            justify-content: center;
            margin-top: 10px;
        }
    }

    @media print {
        .comparison-row {
            page-break-inside: avoid;
            break-inside: avoid;
        }

        .comparison-image-wrapper img:hover {
            transform: none;
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
