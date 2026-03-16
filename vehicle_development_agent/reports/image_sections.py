"""
Image Section Generation for Enhanced Reports
Generates PDF-style image galleries for car comparison reports
"""

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
    <div class="cover-page">
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
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Mahindra_%26_Mahindra_wordmark.svg/1200px-Mahindra_%26_Mahindra_wordmark.svg.png" alt="Mahindra">
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
                    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Mahindra_%26_Mahindra_wordmark.svg/1200px-Mahindra_%26_Mahindra_wordmark.svg.png" alt="Mahindra" class="hero-page-logo">
                </div>
                <div class="hero-image-container">
                    <img src="{img_url}" alt="{name}" class="hero-full-image" onerror="this.style.display='none'">
                </div>
                <div class="hero-page-footer">
                    <div class="hero-page-number">{page_num}</div>
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

    # Technical specification groups
    tech_spec_groups = {
        "Powertrain": [
            ("Engine", "engine"),
            ("Engine CC", "engine_cc"),
            ("Max Power (kW)", "max_power"),
            ("Max Torque (Nm)", "max_torque"),
        ],
        "Fuel": [
            ("Type", "fuel_type"),
            ("Tank Capacity", "fuel_tank"),
            ("Transmission", "transmission"),
            ("Drive", "drive_type"),
            ("Drive Mode", "drive_mode"),
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
            ("Front - Tyre size", "front_tyre"),
            ("Rear - Tyre size", "rear_tyre"),
            ("Spare Tyres", "spare_tyre"),
        ],
        "Boot": [
            ("Space (L)", "boot_space"),
        ],
    }

    # Generate table rows
    rows_html = ""
    current_category = ""

    for category, specs in tech_spec_groups.items():
        for i, (label, key) in enumerate(specs):
            # Show category only on first row of group
            cat_display = category if i == 0 else ""

            rows_html += f'<tr><td class="cat-cell">{cat_display}</td><td class="param-cell">{label}</td>'

            for car_name in car_names:
                car_data = comparison_data.get(car_name, {})
                value = car_data.get(key, "-")
                if value in [None, "", "N/A", "Not Available"]:
                    value = "-"

                # For comparison highlighting (simplified - can be enhanced)
                cell_class = ""
                rows_html += f'<td class="{cell_class}">{value}</td>'

            rows_html += '</tr>'

    # Build the page
    cars_header = "".join([f'<th colspan="1">{name}</th>' for name in car_names])

    html = f'''
    <div class="spec-page">
        <div class="spec-page-header">
            <h1 class="spec-page-title">TECHNICAL SPECIFICATION | <span class="highlight">BENCHMARKING</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Mahindra_%26_Mahindra_wordmark.svg/1200px-Mahindra_%26_Mahindra_wordmark.svg.png" alt="Mahindra" class="spec-page-logo">
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
            <div class="spec-page-number">{page_start}</div>
        </div>
    </div>
    '''

    return html


def generate_feature_list_section(comparison_data: Dict[str, Any], page_start: int = 4) -> str:
    """
    Generate Feature List Comparison pages with checkmarks and X marks.

    Args:
        comparison_data: Dict mapping car names to their scraped data
        page_start: Starting page number

    Returns:
        HTML string for feature list comparison pages
    """
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data]

    if not car_names:
        return ""

    # Feature groups with Category | Description | Features structure
    feature_groups = {
        "Exterior": {
            "Full LED": [
                ("Headlamps", "headlamps"),
                ("Tail lamps LED", "tail_lamps"),
            ],
            "Wheel arch Ext. Claddings": [
                ("Black Finish Cladding", "wheel_arch_cladding"),
            ],
            "Front Bumper & Grille": [
                ("Grille", "grille"),
            ],
            "Antenna Type": [
                ("Shark fin with GPS", "antenna"),
            ],
            "Foot step": [
                ("", "foot_step"),
            ],
        },
        "Interior": {
            "": [
                ("Front compartment trim cover", "front_trim"),
                ("Skid plate", "skid_plate"),
                ("Interior Material type", "interior_material"),
                ("ECM room mirror [IRVM]", "irvm"),
                ("Interior mirror with automatic anti-dazzle function", "auto_dimming_mirror"),
            ],
            "Console Switches": [
                ("Type", "console_switch_type"),
            ],
            "Upholstery": [
                ("Leatherette", "upholstery"),
            ],
            "IP/ Dashboard": [
                ("Leatherette", "dashboard_material"),
            ],
        },
        "Glove Box": {
            "": [
                ("Cooled Glove Box", "cooled_glovebox"),
                ("Non-Flocking, with Illumination", "glovebox_illumination"),
                ("Lockable Glove box", "lockable_glovebox"),
            ],
        },
        "Sunvisor": {
            "Driver": [
                ("Mirror + illumination + ticket holder", "driver_sunvisor"),
            ],
            "Co Driver": [
                ("Mirror + illumination + ticket holder", "codriver_sunvisor"),
            ],
        },
    }

    # Generate table rows
    rows_html = ""

    for category, descriptions in feature_groups.items():
        first_cat_row = True
        for description, features in descriptions.items():
            first_desc_row = True
            for feature_label, feature_key in features:
                cat_display = category if first_cat_row else ""
                desc_display = description if first_desc_row else ""

                rows_html += f'''
                <tr>
                    <td class="cat-cell">{cat_display}</td>
                    <td class="desc-cell">{desc_display}</td>
                    <td class="feature-cell">{feature_label}</td>
                '''

                for car_name in car_names:
                    car_data = comparison_data.get(car_name, {})
                    value = car_data.get(feature_key, "-")

                    # Determine if it's a boolean feature or text value
                    if value in [True, "Yes", "yes", "Available", "Standard", "✓"]:
                        cell_content = '<span class="check-mark">✓</span>'
                        cell_class = ""
                    elif value in [False, "No", "no", "Not Available", "N/A", None, "", "✗"]:
                        cell_content = '<span class="x-mark">✗</span>'
                        cell_class = "inferior-cell"
                    else:
                        cell_content = str(value) if value else "-"
                        cell_class = ""

                    rows_html += f'<td class="{cell_class}">{cell_content}</td>'

                rows_html += '</tr>'
                first_cat_row = False
                first_desc_row = False

    # Build the page
    car_names_title = " | ".join([name.upper() for name in car_names])
    cars_header = "".join([f'<th>{name}</th>' for name in car_names])

    html = f'''
    <div class="feature-page">
        <div class="feature-page-header">
            <h1 class="feature-page-title">FEATURE LIST COMPARISON | <span class="highlight">BENCHMARKING {car_names_title}</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Mahindra_%26_Mahindra_wordmark.svg/1200px-Mahindra_%26_Mahindra_wordmark.svg.png" alt="Mahindra" class="feature-page-logo">
        </div>
        <div class="feature-legend">
            <div class="legend-item"><span class="legend-color superior"></span> Superior to {car_names[-1] if len(car_names) > 1 else 'Competitor'}</div>
            <div class="legend-item"><span class="legend-color inferior"></span> Inferior to {car_names[-1] if len(car_names) > 1 else 'Competitor'}</div>
        </div>
        <div class="feature-table-container">
            <table class="feature-table">
                <thead>
                    <tr>
                        <th class="cat-header">Category</th>
                        <th class="desc-header">Description</th>
                        <th class="feature-header">Features</th>
                        {cars_header}
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        <div class="feature-page-footer">
            <div class="feature-page-number">{page_start}</div>
        </div>
    </div>
    '''

    return html


def generate_drivetrain_comparison_section(
    comparison_data: Dict[str, Any],
    drivetrain_data: Dict[str, Any] = None,
    page_num: int = 19
) -> str:
    """
    Generate drivetrain/4WD feature comparison section.

    Args:
        comparison_data: Dict mapping car names to their scraped data
        drivetrain_data: Optional pre-fetched drivetrain comparison data
        page_num: Page number for footer

    Returns:
        HTML string for drivetrain comparison section
    """
    car_names = [name for name, data in comparison_data.items()
                 if isinstance(data, dict) and "error" not in data]

    if not car_names:
        return ""

    # Try to extract drivetrain data from comparison_data if not provided
    if not drivetrain_data:
        drivetrain_data = _extract_drivetrain_data(comparison_data)

    if not drivetrain_data or not drivetrain_data.get("features"):
        return ""  # No drivetrain data available

    # Build the section HTML
    car_name = drivetrain_data.get("car_name", car_names[0])
    system_name = drivetrain_data.get("system_name", "Intelligent 4WD")
    intro_text = drivetrain_data.get("intro_text", "")
    features = drivetrain_data.get("features", [])
    explanations = drivetrain_data.get("explanations", [])
    images = drivetrain_data.get("images", [])
    comparison_with = drivetrain_data.get("comparison_with", "Conventional 4WD")

    # Build feature table rows
    feature_rows = ""
    for feature in features:
        feature_rows += f'''
        <tr>
            <td class="feature-name">{feature.get("name", "")}</td>
            <td class="feature-car">{feature.get("car_value", "")}</td>
            <td class="feature-conventional">{feature.get("conventional_value", "")}</td>
        </tr>
        '''

    # Build explanations list
    explanations_html = ""
    for i, explanation in enumerate(explanations):
        letter = chr(97 + i)  # a, b, c, d...
        explanations_html += f'''
        <li><span class="explanation-title">{explanation.get("title", "")}:</span> {explanation.get("description", "")}</li>
        '''

    # Build images HTML
    images_html = ""
    for img in images[:2]:  # Max 2 images
        images_html += f'''
        <div class="drivetrain-image">
            <img src="{img}" alt="Drivetrain" onerror="this.parentElement.style.display='none'">
        </div>
        '''

    # Highlight keywords in intro text
    highlighted_intro = intro_text
    keywords_to_highlight = drivetrain_data.get("highlight_keywords", [])
    for keyword in keywords_to_highlight:
        highlighted_intro = highlighted_intro.replace(
            keyword,
            f'<span class="highlight-green">{keyword}</span>'
        )

    html = f'''
    <div class="drivetrain-page">
        <div class="drivetrain-header">
            <h1 class="drivetrain-title">FEATURE COMPARISION | <span class="highlight">BENCHMARKING</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Mahindra_%26_Mahindra_wordmark.svg/1200px-Mahindra_%26_Mahindra_wordmark.svg.png" alt="Mahindra" class="drivetrain-logo">
        </div>

        <div class="drivetrain-content">
            <div class="drivetrain-left">
                <p class="drivetrain-intro">{highlighted_intro}</p>

                <table class="drivetrain-table">
                    <thead>
                        <tr>
                            <th class="feature-header">Feature</th>
                            <th class="car-header">{car_name}<br>{system_name}</th>
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
            <div class="drivetrain-page-number">{page_num}</div>
        </div>
    </div>
    '''

    return html


def _extract_drivetrain_data(comparison_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract drivetrain-related data from comparison_data.
    Returns structured data for drivetrain comparison section.
    """
    drivetrain_data = {
        "features": [],
        "explanations": [],
        "images": [],
        "highlight_keywords": []
    }

    # Keys that indicate drivetrain/4WD features
    drivetrain_keys = [
        "drive_type", "drive_mode", "differential", "4wd_system",
        "awd_system", "traction_control", "terrain_modes", "off_road",
        "ground_clearance", "approach_angle", "departure_angle"
    ]

    for car_name, car_data in comparison_data.items():
        if not isinstance(car_data, dict) or "error" in car_data:
            continue

        # Check if car has drivetrain-related data
        has_drivetrain_data = False
        for key in drivetrain_keys:
            if car_data.get(key) and car_data.get(key) not in ["N/A", "Not Available", "-", ""]:
                has_drivetrain_data = True
                break

        if has_drivetrain_data:
            drivetrain_data["car_name"] = car_name

            # Extract drive mode info
            drive_mode = car_data.get("drive_mode", "")
            if drive_mode and drive_mode not in ["N/A", "Not Available"]:
                drivetrain_data["features"].append({
                    "name": "Driving Modes",
                    "car_value": drive_mode,
                    "conventional_value": "Usually 2-3 modes"
                })
                drivetrain_data["highlight_keywords"].append(drive_mode.split("[")[0].strip())

            # Extract drive type
            drive_type = car_data.get("drive_type", "")
            if drive_type and drive_type not in ["N/A", "Not Available"]:
                drivetrain_data["features"].append({
                    "name": "Drive System",
                    "car_value": drive_type,
                    "conventional_value": "Standard 4WD"
                })

            # Extract off-road features
            off_road = car_data.get("off_road", "")
            if off_road and off_road not in ["N/A", "Not Available"]:
                drivetrain_data["features"].append({
                    "name": "Off-Road Capability",
                    "car_value": off_road,
                    "conventional_value": "Basic off-road"
                })

            # Get drivetrain images if available
            images = car_data.get("images", {})
            if images.get("technology"):
                for img in images["technology"][:2]:
                    if isinstance(img, (list, tuple)):
                        drivetrain_data["images"].append(img[0])
                    elif isinstance(img, str):
                        drivetrain_data["images"].append(img)

            # Generate intro text
            if drive_mode or drive_type:
                system_name = drive_type if "4WD" in str(drive_type) or "AWD" in str(drive_type) else "Intelligent Drive System"
                drivetrain_data["system_name"] = system_name
                drivetrain_data["intro_text"] = f"The {car_name} is equipped with the {system_name}. This system offers {drive_mode if drive_mode else 'multiple driving modes'} designed to maximize traction, stability, and adaptability across terrains."

            break  # Use first car with drivetrain data

    return drivetrain_data if drivetrain_data.get("features") else None


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
    <div class="summary-comparison-page">
        <div class="summary-comp-header">
            <h1 class="summary-comp-title">FEATURE COMPARISION | <span class="highlight">SUMMARY</span></h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Mahindra_%26_Mahindra_wordmark.svg/1200px-Mahindra_%26_Mahindra_wordmark.svg.png" alt="Mahindra" class="summary-comp-logo">
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
            <div class="summary-comp-page-number">{page_num}</div>
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
            height: 100vh !important;
            min-height: 100vh !important;
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
