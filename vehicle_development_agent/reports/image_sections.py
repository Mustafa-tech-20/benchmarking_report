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
        from vehicle_development_agent.config import GEMINI_LITE_MODEL, GEMINI_LITE_LOCATION, PROJECT_ID

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
            <h2 class="cover-subtitle">BENCHMARKING VEHICLES<br>SOFT REPORT</h2>
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
            <h1 class="hero-page-title">VEHICLE COMPARISON | <span class="highlight">BENCHMARKING</span></h1>
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

    # KPI Inference hints - interpretation guidance for each spec
    KPI_INFERENCES = {
        # Powertrain
        "engine_displacement": "Higher = More power potential",
        "torque": "Higher = Better acceleration & towing",
        "mileage": "Higher = Better fuel economy",
        "acceleration": "Lower = Faster acceleration",
        "performance_feel": "Subjective driving impression",
        "driveability": "Ease of daily driving",
        "response": "Quicker = Better throttle response",
        "city_performance": "Low-end torque & maneuverability",
        "highway_performance": "Stability & cruising ability",
        "off_road": "Higher clearance & capability = Better",
        "crawl": "4WD low-range capability",
        # Transmission
        "manual_transmission_performance": "Shift quality & clutch feel",
        "automatic_transmission_performance": "Shift smoothness & response",
        "pedal_operation": "Lighter clutch = Better city use",
        "gear_shift": "Precise & short throw = Better",
        "gear_selection": "Accurate slotting = Better",
        "pedal_travel": "Shorter = More responsive",
        # Dimensions
        "wheelbase": "Longer = More cabin space & stability",
        "ground_clearance": "Higher = Better off-road capability",
        "boot_space": "Higher = More cargo capacity",
        "turning_radius": "Lower = Better maneuverability",
        "seating_capacity": "More = Higher passenger capacity",
        # Safety
        "airbags": "More = Better occupant protection",
        "airbag_types_breakdown": "More coverage = Safer",
        "ncap_rating": "Higher stars = Safer",
        "impact": "Higher scores = Better crash protection",
        "adas": "More features = Better active safety",
        "vehicle_safety_features": "More = Comprehensive safety",
        "brakes": "Disc all-round = Better stopping",
        "braking": "Shorter distance = Better",
        "brake_performance": "Progressive & strong = Better",
        "epb": "Auto-hold adds convenience",
        "stability": "Better = Safer at high speeds",
        "parking_sensors": "More sensors = Better coverage",
        "parking_camera": "360° view = Best visibility",
        # Steering & Handling
        "steering": "Weighted & responsive = Better feel",
        "sensitivity": "Well-calibrated = Better control",
        "telescopic_steering": "Tilt + telescopic = Best adjustability",
        "manoeuvring": "Easier = Better urban usability",
        "corner_stability": "Less body roll = Better",
        "straight_ahead_stability": "More planted = Safer highways",
        # Ride Quality
        "ride": "Plush & composed = Better comfort",
        "ride_quality": "Absorbs bumps well = Better",
        "stiff_on_pot_holes": "Less harshness = Better comfort",
        "bumps": "Better absorption = More comfort",
        "shocks": "Well-damped = Better ride",
        "jerks": "Smoother = Better refinement",
        "shakes": "Less vibration = Better quality",
        "shudder": "None = Better powertrain refinement",
        "pulsation": "None = Better brake condition",
        "grabby": "Progressive bite = Better control",
        "spongy": "Firm pedal = Better feedback",
        # NVH
        "nvh": "Lower = More refined cabin",
        "powertrain_nvh": "Quieter = Better insulation",
        "wind_nvh": "Lower = Better aerodynamics",
        "road_nvh": "Lower = Better sound deadening",
        "wind_noise": "Lower = Better cabin comfort",
        "tire_noise": "Quieter = Better refinement",
        "turbo_noise": "Minimal = Better insulation",
        "blower_noise": "Quieter = Better HVAC",
        "rattle": "None = Better build quality",
        # Wheels & Tyres
        "tyre_size": "Wider = Better grip",
        "wheel_size": "Larger = Better looks & handling",
        "alloy_wheel": "Diamond cut = Premium appearance",
        # Exterior
        "led": "LED/Matrix = Better visibility",
        "drl": "Signature LED = Better aesthetics",
        "tail_lamp": "Full LED = Modern look",
        "sunroof": "Panoramic = More light & space",
        "orvm": "Auto-fold + indicators = Better",
        # Interior & Comfort
        "interior": "Premium materials = Better quality",
        "climate_control": "Dual-zone = Better comfort",
        "seat_material": "Leather = Premium feel",
        "seat_cushion": "Well-padded = Better comfort",
        "seat_features_detailed": "More adjustment = Better ergonomics",
        "ventilated_seats": "Cooling = Better hot weather comfort",
        "armrest": "Padded & adjustable = Better",
        "visibility": "360° clear = Safer driving",
        "ingress": "Easier entry = Better accessibility",
        "egress": "Easier exit = Better convenience",
        # Technology
        "infotainment_screen": "Larger & responsive = Better",
        "resolution": "Higher = Sharper display",
        "touch_response": "Faster = Better usability",
        "digital_display": "Larger cluster = More info",
        "apple_carplay": "Wireless = More convenient",
        "audio_system": "Branded & more speakers = Better",
        "cruise_control": "Adaptive = Better highway driving",
        # Market
        "price_range": "Lower = Better value",
        "monthly_sales": "Higher = More market acceptance",
        "user_rating": "Higher = Better customer satisfaction",
    }

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

    # Generate table rows with collapsible groups
    rows_html = ""
    group_index = 0
    num_cars = len(car_names)

    def _render_rows(category, specs, grp_idx):
        nonlocal rows_html
        # Check if this group has any non-empty rows
        has_data = False
        for label, key in specs:
            values = []
            for car_name in car_names:
                car_data = comparison_data.get(car_name, {})
                value = car_data.get(key, "-")
                if isinstance(value, (dict, list)):
                    value = "-"
                elif value in EMPTY_VALUES:
                    value = "-"
                values.append(value)
            if not all(v == "-" for v in values):
                has_data = True
                break

        if not has_data:
            return

        # Group header row with toggle button
        collapsed_class = "" if grp_idx == 0 else "collapsed"
        toggle_icon = "−" if grp_idx == 0 else "+"
        rows_html += f'''<tr class="spec-group-header {collapsed_class}" data-group="spec-group-{grp_idx}" onclick="toggleSpecGroup(this)">
            <td colspan="{num_cars + 2}">
                <span class="group-toggle-btn">{toggle_icon}</span>
                <span class="group-title">{category}</span>
            </td>
        </tr>'''

        # Data rows for this group
        for label, key in specs:
            values = []
            for car_name in car_names:
                car_data = comparison_data.get(car_name, {})
                value = car_data.get(key, "-")
                if isinstance(value, (dict, list)):
                    value = "-"
                elif value in EMPTY_VALUES:
                    value = "-"
                values.append(value)

            if all(v == "-" for v in values):
                continue

            hidden_class = "" if grp_idx == 0 else "group-row-hidden"

            # Get KPI inference hint for this spec
            inference_hint = KPI_INFERENCES.get(key, "")
            param_html = f'{label}'
            if inference_hint:
                param_html += f'<span class="kpi-hint">{inference_hint}</span>'

            ref_val = values[0] if values else "-"
            rows_html += f'<tr class="spec-data-row {hidden_class}" data-group="spec-group-{grp_idx}"><td class="cat-cell"></td><td class="param-cell">{param_html}</td>'
            for i, value in enumerate(values):
                if i == 0:
                    rows_html += f'<td>{value}</td>'
                else:
                    if ref_val != "-" and value == "-":
                        cell_class = "inferior-cell"
                    elif ref_val == "-" and value != "-":
                        cell_class = "superior-cell"
                    else:
                        cell_class = ""
                    rows_html += f'<td class="{cell_class}">{value}</td>'
            rows_html += '</tr>'

    for category, specs in tech_spec_groups.items():
        _render_rows(category, specs, group_index)
        group_index += 1

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
            from vehicle_development_agent.core.scraper import google_custom_search, SEARCH_ENGINE_ID
            import vertexai
            from vertexai.generative_models import GenerativeModel, GenerationConfig
            from vehicle_development_agent.config import GEMINI_LITE_LOCATION, PROJECT_ID

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
            <h1 class="feature-page-title">FEATURE FACE-OFF | <span class="highlight">BENCHMARKING {car_names_title}</span></h1>
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
            # Wrap in a function to avoid binding the coroutine to the current event loop
            def _run_in_new_loop():
                return asyncio.run(fetch_all_cars_drivetrain_parallel(car_names, comparison_data))

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_in_new_loop)
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

    @media print {
        .hero-image-page {
            height: 100vh;
            page-break-after: always;
        }
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
        padding: 0 15px 8px 15px;
        text-align: center;
        font-size: 11px;
        font-weight: 500;
        color: #6c757d;
        background: #f8f9fa;
    }

    .gallery-ai-note {
        padding: 8px 14px 12px 14px;
        font-size: 11.5px;
        font-weight: 400;
        color: #3a3a3a;
        background: #ffffff;
        line-height: 1.5;
        border-top: 1px solid #e9ecef;
    }

    .gallery-ai-note .ai-note-label {
        color: #cc0000;
        font-weight: 600;
        font-style: normal;
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

        .hero-comparison-img {
            width: 100% !important;
            height: 100% !important;
            object-fit: cover !important;
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

        .gallery-ai-note {
            font-size: 10px !important;
            padding: 6px 10px 8px 10px !important;
            page-break-inside: avoid !important;
            break-inside: avoid !important;
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

    .kpi-hint {
        display: block;
        font-size: 10px;
        font-weight: 400;
        color: #6c757d;
        font-style: italic;
        margin-top: 2px;
        line-height: 1.3;
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

        .hero-vs-divider {
            width: 44px;
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


# ============================================================================
# VENN DIAGRAM SECTION  (Chart.js venn plugin + sliding window)
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
        from vertexai.generative_models import GenerativeModel
        model = GenerativeModel("gemini-2.5-flash-lite")

        unique_combined = car1_unique + car2_unique  # already-known differences
        prompt = f"""You are an automotive analyst. Two vehicles are being compared:
- {car1} (Car 1)
- {car2} (Car 2)

We already know the DIFFERENCES:
- Features unique to {car1}: {json.dumps(car1_unique[:20])}
- Features unique to {car2}: {json.dumps(car2_unique[:20])}

Shared specification data for both cars:
{json.dumps(condensed, indent=2)[:3000]}

Task: List 10-20 features/specifications that are COMMON to BOTH cars (present in both).
Focus on: safety features, engine type, transmission options, body type, shared tech, similar comfort items.
Each item should be a concise plain-English feature description.

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


def generate_spider_chart_section(
    comparison_data: Dict[str, Any],
    summary_data: Dict[str, Any] = None,
) -> str:
    """
    Generate spider/radar charts showing top 5 specs for each spec group.
    Creates multiple radar charts for different categories like Safety, Performance,
    Comfort, Technology, and Dimensions.

    Args:
        comparison_data: Dict mapping car names to their scraped data
        summary_data: Optional summary data (not used but kept for compatibility)

    Returns:
        HTML string with spider charts for all spec groups
    """
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data]

    if len(car_names) < 2:
        return ""

    # Define spec groups with their specs (top 5 most important for each category)
    SPEC_GROUPS = {
        "Safety & Security": [
            ("Airbags", "airbags", "count"),
            ("NCAP Rating", "ncap_rating", "rating"),
            ("ADAS Features", "adas", "bool"),
            ("ABS with EBD", "brakes", "bool"),
            ("Hill Hold Control", "vehicle_safety_features", "bool"),
        ],
        "Performance": [
            ("Engine Power (bhp)", "power", "numeric"),
            ("Torque (Nm)", "torque", "numeric"),
            ("0-100 km/h (sec)", "acceleration", "numeric_inverted"),
            ("Top Speed (km/h)", "top_speed", "numeric"),
            ("Fuel Efficiency (kmpl)", "mileage", "numeric"),
        ],
        "Comfort & Convenience": [
            ("Sunroof", "sunroof", "bool"),
            ("Climate Control", "climate_control", "bool"),
            ("Ventilated Seats", "ventilated_seats", "bool"),
            ("Cruise Control", "cruise_control", "bool"),
            ("Wireless Charging", "wireless_charging", "bool"),
        ],
        "Technology & Infotainment": [
            ("Infotainment Screen", "infotainment_screen", "size"),
            ("Digital Instrument Cluster", "digital_display", "bool"),
            ("Apple CarPlay", "apple_carplay", "bool"),
            ("Connected Car Features", "connected_car", "bool"),
            ("Speaker Count", "audio_system", "count"),
        ],
        "Dimensions & Capacity": [
            ("Wheelbase (mm)", "wheelbase", "numeric"),
            ("Ground Clearance (mm)", "ground_clearance", "numeric"),
            ("Boot Space (litres)", "boot_space", "numeric"),
            ("Fuel Tank (litres)", "fuel_tank_capacity", "numeric"),
            ("Seating Capacity", "seating_capacity", "count"),
        ],
    }

    import re

    def extract_number(text: str) -> float:
        """Extract numeric value from text."""
        if not text or text in ["Not Available", "N/A", "Not found", "", "-"]:
            return 0.0
        match = re.search(r'(\d+\.?\d*)', str(text))
        return float(match.group(1)) if match else 0.0

    def normalize_value(value: str, value_type: str, max_val: float = 100.0) -> float:
        """Normalize value to 0-100 scale for radar chart."""
        if not value or value in ["Not Available", "N/A", "Not found", "", "-"]:
            return 0.0

        if value_type == "bool":
            # Check for positive indicators
            val_lower = str(value).lower()
            if any(x in val_lower for x in ["yes", "available", "present", "✓"]):
                return 100.0
            if len(val_lower) > 3 and val_lower not in ["not available", "n/a", "not found"]:
                return 100.0
            return 0.0

        elif value_type == "count":
            num = extract_number(value)
            # Normalize counts (e.g., 0-10 airbags -> 0-100 scale)
            return min((num / (max_val / 100.0)) * 100, 100.0)

        elif value_type == "numeric":
            num = extract_number(value)
            return min((num / max_val) * 100, 100.0)

        elif value_type == "numeric_inverted":
            # For metrics where lower is better (e.g., 0-100 acceleration time)
            num = extract_number(value)
            if num == 0:
                return 0.0
            return max(0, 100 - (num / max_val) * 100)

        elif value_type == "rating":
            # NCAP rating (0-5 stars)
            num = extract_number(value)
            return (num / 5.0) * 100

        elif value_type == "size":
            # Screen size in inches
            num = extract_number(value)
            return min((num / 20.0) * 100, 100.0)  # Normalize to 20 inch max

        return 0.0

    # Build charts for each spec group
    charts_html = ""
    chart_id = 0

    for group_name, specs in SPEC_GROUPS.items():
        chart_id += 1

        # Collect data for this group
        labels = []
        datasets = []

        # Prepare labels (spec names)
        for spec_name, _, _ in specs:
            labels.append(spec_name.replace(" (bhp)", "").replace(" (Nm)", "").replace(" (mm)", "").replace(" (litres)", "").replace(" (sec)", "").replace(" (km/h)", "").replace(" (kmpl)", ""))

        # Prepare datasets (one per car)
        colors = [
            ("rgba(220, 53, 69, 0.6)", "rgba(220, 53, 69, 1)"),    # Red
            ("rgba(13, 110, 253, 0.6)", "rgba(13, 110, 253, 1)"),  # Blue
            ("rgba(25, 135, 84, 0.6)", "rgba(25, 135, 84, 1)"),    # Green
            ("rgba(255, 193, 7, 0.6)", "rgba(255, 193, 7, 1)"),    # Yellow
        ]

        for idx, car_name in enumerate(car_names):
            car_data = comparison_data.get(car_name, {})
            values = []

            for spec_name, spec_key, value_type in specs:
                raw_value = car_data.get(spec_key, "Not Available")

                # Determine max value for normalization
                max_val = 100.0
                if spec_key == "airbags":
                    max_val = 10.0
                elif spec_key == "power":
                    max_val = 200.0  # bhp
                elif spec_key == "torque":
                    max_val = 500.0  # Nm
                elif spec_key == "acceleration":
                    max_val = 20.0   # seconds
                elif spec_key == "top_speed":
                    max_val = 200.0  # km/h
                elif spec_key == "mileage":
                    max_val = 30.0   # kmpl
                elif spec_key == "wheelbase":
                    max_val = 3000.0  # mm
                elif spec_key == "ground_clearance":
                    max_val = 250.0   # mm
                elif spec_key == "boot_space":
                    max_val = 500.0   # litres
                elif spec_key == "fuel_tank_capacity":
                    max_val = 80.0    # litres
                elif spec_key == "seating_capacity":
                    max_val = 10.0
                elif spec_key == "audio_system":
                    max_val = 12.0    # speakers

                normalized = normalize_value(raw_value, value_type, max_val)
                values.append(normalized)

            bg_color, border_color = colors[idx % len(colors)]

            datasets.append({
                "label": car_name,
                "data": values,
                "backgroundColor": bg_color,
                "borderColor": border_color,
                "borderWidth": 2,
                "pointRadius": 4,
                "pointBackgroundColor": border_color,
            })

        # Generate Chart.js config
        import json

        chart_config = {
            "type": "radar",
            "data": {
                "labels": labels,
                "datasets": datasets
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": True,
                "plugins": {
                    "legend": {
                        "display": True,
                        "position": "bottom",
                        "labels": {
                            "font": {"size": 14, "weight": "bold"},
                            "padding": 15,
                            "usePointStyle": True,
                        }
                    },
                    "title": {
                        "display": True,
                        "text": group_name,
                        "font": {"size": 20, "weight": "bold"},
                        "padding": {"top": 10, "bottom": 20}
                    }
                },
                "scales": {
                    "r": {
                        "min": 0,
                        "max": 100,
                        "beginAtZero": True,
                        "ticks": {
                            "stepSize": 20,
                            "font": {"size": 12}
                        },
                        "pointLabels": {
                            "font": {"size": 13, "weight": "600"},
                            "color": "#333"
                        },
                        "grid": {
                            "color": "rgba(0, 0, 0, 0.1)"
                        },
                        "angleLines": {
                            "color": "rgba(0, 0, 0, 0.1)"
                        }
                    }
                }
            }
        }

        charts_html += f'''
        <div class="spider-chart-container">
            <canvas id="spiderChart{chart_id}"></canvas>
            <script>
                (function() {{
                    const ctx = document.getElementById('spiderChart{chart_id}').getContext('2d');
                    const config = {json.dumps(chart_config)};
                    new Chart(ctx, config);
                }})();
            </script>
        </div>
        '''

    # Build final HTML with all charts
    html = f'''
    <div class="spider-charts-page" id="spider-charts-section">
        <div class="spider-charts-header">
            <h1 class="spider-charts-title">SPECIFICATION COMPARISON | <span class="highlight">RADAR ANALYSIS</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Mahindra_logo.svg/1920px-Mahindra_logo.svg.png?_=20231128143513" alt="Mahindra" class="spider-charts-logo">
        </div>

        <div class="spider-charts-grid">
            {charts_html}
        </div>

        <div class="spider-charts-footer">
            <p class="spider-note">Each axis represents a normalized score (0-100) for the respective specification</p>
        </div>

        <style>
            .spider-charts-page {{
                page-break-before: always;
                padding: 50px 60px;
                min-height: 100vh;
                background: #ffffff;
                color: #1c2a39;
            }}

            .spider-charts-header {{
                text-align: center;
                margin-bottom: 40px;
                padding-bottom: 25px;
                border-bottom: 3px solid #cc0000;
            }}

            .spider-charts-title {{
                font-size: 28px;
                font-weight: 700;
                margin: 0 0 15px 0;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #1c2a39;
            }}

            .spider-charts-title .highlight {{
                color: #cc0000;
            }}

            .spider-charts-logo {{
                height: 35px;
                filter: brightness(0);
            }}

            .spider-charts-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
                gap: 30px;
                margin-bottom: 30px;
            }}

            .spider-chart-container {{
                background: #ffffff;
                border-radius: 12px;
                padding: 25px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                border: 1px solid #e9ecef;
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }}

            .spider-chart-container:hover {{
                transform: translateY(-3px);
                box-shadow: 0 8px 30px rgba(0,0,0,0.12);
                border-color: #cc0000;
            }}

            .spider-chart-container canvas {{
                max-width: 100%;
                height: auto !important;
            }}

            .spider-charts-footer {{
                text-align: center;
                padding: 15px 20px;
                background: #f8f9fa;
                border-radius: 8px;
                margin-top: 25px;
                border: 1px solid #e9ecef;
            }}

            .spider-note {{
                margin: 0;
                font-size: 13px;
                font-style: italic;
                color: #6c757d;
            }}

            @media print {{
                .spider-charts-page {{
                    padding: 30px;
                }}

                .spider-chart-container {{
                    box-shadow: none;
                    border: 1px solid #dee2e6;
                }}

                .spider-chart-container:hover {{
                    transform: none;
                }}
            }}
        </style>
    </div>
    '''

    return html


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


# ============================================================================
# VARIANT WALK SECTION
# ============================================================================

def generate_variant_walk_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate variant walk section showing features across different variants.
    Adapted from product_planning_agent for the benchmarking report.
    """
    if not comparison_data:
        return ""

    # Check if any car actually has variant_walk data
    has_any = any(
        isinstance(d, dict) and "error" not in d and d.get("variant_walk")
        for d in comparison_data.values()
    )
    if not has_any:
        return ""

    html = """
    <div class="content bm-variant-walk-section" id="variant-walk-section">
        <div class="section-header">
            <div class="icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
            </div>
            <h2>Variant Walk</h2>
        </div>
    """

    for car_name, car_data in comparison_data.items():
        if not isinstance(car_data, dict) or "error" in car_data:
            continue
        variant_walk = car_data.get("variant_walk") or {}
        variants = variant_walk.get("variants") or {} if isinstance(variant_walk, dict) else {}

        if not variants:
            continue

        variant_names = [v.get("name", k) for k, v in variants.items()]
        num_cols = len(variant_names)

        html += f"""
        <h3 class="bm-vw-car-title">{car_name}</h3>
        <div class="bm-vw-table-wrap">
            <table class="bm-vw-table">
                <thead><tr>
        """
        for vname in variant_names:
            html += f'<th>{vname}</th>'
        html += "</tr></thead><tbody><tr>"

        is_first = True
        variant_keys = list(variants.keys())
        for idx, (vkey, vdata) in enumerate(variants.items()):
            vdata = vdata or {}
            features = vdata.get("features") or []
            features_added = vdata.get("features_added") or []
            features_deleted = vdata.get("features_deleted") or []

            html += "<td>"
            if is_first:
                html += '<div class="bm-vw-section-label">Standard Features:</div>'
                is_first = False
            else:
                prev_name = variants[variant_keys[idx - 1]].get("name", variant_keys[idx - 1])
                html += f'<div class="bm-vw-section-label">In addition to {prev_name}:</div>'

            items = features_added if features_added else features[:10]
            if items:
                html += '<ul class="bm-vw-features">'
                for feat in items:
                    html += f'<li class="bm-vw-added">{feat}</li>'
                html += "</ul>"

            if features_deleted:
                html += '<div class="bm-vw-deleted-label">Removed / Replaced:</div>'
                html += '<ul class="bm-vw-features">'
                for feat in features_deleted:
                    html += f'<li class="bm-vw-deleted">{feat}</li>'
                html += "</ul>"

            html += "</td>"

        html += "</tr></tbody></table></div>"

    html += """
        <div class="bm-vw-legend">
            <strong>Note:</strong> Variant walk shows progressive feature additions across trim levels.
            <span class="bm-vw-legend-added">Green</span> = features added,
            <span class="bm-vw-legend-deleted">Red</span> = features removed or replaced.
        </div>
    </div>

    <style>
        .bm-variant-walk-section { margin-bottom: 40px; }

        .bm-vw-car-title {
            font-size: 18px;
            font-weight: 700;
            color: #1a1a1a;
            margin: 30px 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #cc0000;
        }

        .bm-vw-table-wrap { overflow-x: auto; margin-bottom: 24px; }

        .bm-vw-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 700px;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .bm-vw-table th {
            background: #1a1a1a;
            color: white;
            padding: 14px 12px;
            text-align: center;
            font-size: 13px;
            font-weight: 700;
            border: 1px solid #333;
            letter-spacing: 0.5px;
        }

        .bm-vw-table td {
            padding: 14px 12px;
            border: 1px solid #e5e7eb;
            vertical-align: top;
            font-size: 12.5px;
            line-height: 1.7;
            background: #fff;
        }

        .bm-vw-section-label {
            font-weight: 700;
            font-size: 11px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }

        .bm-vw-deleted-label {
            font-weight: 600;
            font-size: 11px;
            color: #cc0000;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 10px 0 4px 0;
        }

        .bm-vw-features { list-style: none; padding: 0; margin: 0; }

        .bm-vw-added {
            padding: 3px 0 3px 16px;
            position: relative;
            color: #059669;
            font-weight: 500;
        }
        .bm-vw-added::before { content: "+ "; position: absolute; left: 0; font-weight: 700; }

        .bm-vw-deleted {
            padding: 3px 0 3px 16px;
            position: relative;
            color: #cc0000;
            font-weight: 500;
        }
        .bm-vw-deleted::before { content: "− "; position: absolute; left: 0; font-weight: 700; }

        .bm-vw-legend {
            margin-top: 12px;
            padding: 12px 16px;
            background: #f9fafb;
            border-radius: 6px;
            font-size: 12px;
            border-left: 4px solid #cc0000;
        }
        .bm-vw-legend-added { color: #059669; font-weight: 600; }
        .bm-vw-legend-deleted { color: #cc0000; font-weight: 600; }

        @media print {
            .bm-vw-table-wrap { overflow-x: visible; }
            .bm-vw-table { page-break-inside: auto; }
            .bm-vw-table tr { page-break-inside: avoid; }
        }
    </style>
    """

    return html


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
