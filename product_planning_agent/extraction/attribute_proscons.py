"""
Attribute-based Pros & Cons Extraction Module

Extracts pros and cons for specific vehicle attributes:
1. First tries to extract from YouTube video reviews
2. Falls back to Gemini's general knowledge for missing info
"""

import sys
sys.path.append("/app")
from shared_utils import safe_json_parse

import json
import concurrent.futures
from typing import Dict, Any, List
from vertexai.generative_models import GenerativeModel
from product_planning_agent.config import GEMINI_MAIN_MODEL

# Top 2 trusted YouTube channels for car reviews (Indian automotive channels)
TRUSTED_YOUTUBE_CHANNELS = [
    "Autocar India",
    "Overdrive"
]

# Define attribute categories and sub-attributes
ATTRIBUTE_CATEGORIES = {
    "Comfort": ["Ride", "Climate Control", "Seats"],
    "Dynamics": ["Customer Handling", "Steering"],
    "Performance": [
        "Performance Feel",
        "Driveability",
        "Manual Transmission Operation",
        "Clutch Operation",
        "Automatic Transmission Operation"
    ],
    "Safety": ["Braking", "Restraints"],
    "Space & Versatility": ["Visibility", "Package", "Usability", "Functional Hardware"],
    "NVH": ["PT-NVH", "Road NVH", "Wind NVH", "Electro Mech NVH"],
    "All Terrain Capability": ["4X4 Operation"],
    "Features": ["Infotainment System", "Night Operation"]
}


def _build_json_structure() -> str:
    """Build the expected JSON structure for the prompt."""
    structure = {}
    for category, sub_attrs in ATTRIBUTE_CATEGORIES.items():
        structure[category] = {}
        for attr in sub_attrs:
            structure[category][attr] = {"pros": ["pro1", "pro2"], "cons": ["con1", "con2"]}
    return json.dumps(structure, indent=2)


def get_attribute_proscons_from_youtube(car_name: str, channels: List[str] = None) -> Dict[str, Any]:
    """
    Extract attribute-specific pros and cons from YouTube video reviews.

    Args:
        car_name: Name of the car to analyze
        channels: List of YouTube channels to consider (default: top 3)

    Returns:
        Dictionary with attribute categories and their pros/cons
    """
    if channels is None:
        channels = TRUSTED_YOUTUBE_CHANNELS[:3]

    model = GenerativeModel(GEMINI_MAIN_MODEL)
    channels_str = ", ".join(channels)

    prompt = f"""Analyze the {car_name} based on reviews from these YouTube channels: {channels_str}

Extract SPECIFIC pros and cons for each of these vehicle attributes based on what reviewers typically mention.

ATTRIBUTES TO ANALYZE:

**Comfort:**
- Ride (suspension, bump absorption, highway comfort)
- Climate Control (AC performance, vents, climate zones)
- Seats (cushioning, support, adjustability, comfort on long drives)

**Dynamics:**
- Customer Handling (body roll, cornering, agility)
- Steering (feedback, weight, precision)

**Performance:**
- Performance Feel (power delivery, acceleration feel)
- Driveability (ease of driving in city/highway)
- Manual Transmission Operation (gear shifts, clutch effort)
- Clutch Operation (engagement, effort, feel)
- Automatic Transmission Operation (smoothness, responsiveness, modes)

**Safety:**
- Braking (bite, feel, ABS performance)
- Restraints (airbags, seatbelts, safety features)

**Space & Versatility:**
- Visibility (all-around visibility, blind spots)
- Package (boot space, storage compartments)
- Usability (practicality, daily use convenience)
- Functional Hardware (switches, controls, build quality)

**NVH (Noise, Vibration, Harshness):**
- PT-NVH (powertrain noise - engine, gearbox)
- Road NVH (tyre noise, road surface noise)
- Wind NVH (wind noise at speed)
- Electro Mech NVH (electric motor whine, mechanical sounds)

**All Terrain Capability:**
- 4X4 Operation (off-road modes, traction, ground clearance use)

**Features:**
- Infotainment System (screen, connectivity, ease of use)
- Night Operation (headlights, ambient lighting, night visibility)

RULES:
- Provide 1-3 specific pros and cons per attribute based on actual YouTube review content
- If reviewers don't typically discuss an attribute for this car, use ["Not covered in reviews"]
- Be specific with real observations (e.g., "AC cools cabin in under 3 minutes" not just "Good AC")
- If attribute doesn't apply (e.g., Manual Transmission for automatic-only), use ["N/A - not available"]

Return ONLY valid JSON in this structure:
{_build_json_structure()}
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean up response
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join([line for line in lines if not line.strip().startswith("```")])
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

        result = safe_json_parse(response_text, fallback={})
        return result

    except Exception as e:
        print(f"  [{car_name}] YouTube attribute extraction failed: {e}")
        return {}


def fill_missing_with_gemini(car_name: str, youtube_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fill in missing attribute data using Gemini's general knowledge.

    Args:
        car_name: Name of the car
        youtube_data: Existing data from YouTube extraction

    Returns:
        Complete dictionary with all attributes filled
    """
    # Find missing attributes
    missing_attrs = []
    for category, sub_attrs in ATTRIBUTE_CATEGORIES.items():
        if category not in youtube_data:
            missing_attrs.append(f"{category}: all sub-attributes")
            continue
        for attr in sub_attrs:
            if attr not in youtube_data.get(category, {}):
                missing_attrs.append(f"{category} > {attr}")
            elif not youtube_data[category][attr].get("pros") or \
                 youtube_data[category][attr]["pros"] in [["Not covered in reviews"], []]:
                missing_attrs.append(f"{category} > {attr}")

    if not missing_attrs:
        return youtube_data

    print(f"  [{car_name}] Filling {len(missing_attrs)} missing attributes with Gemini knowledge...")

    model = GenerativeModel(GEMINI_MAIN_MODEL)

    prompt = f"""Based on your general automotive knowledge about the {car_name}, provide pros and cons for these specific attributes that weren't covered in YouTube reviews:

Missing attributes:
{chr(10).join(f"- {attr}" for attr in missing_attrs)}

Provide specific, factual pros and cons based on the vehicle's known characteristics.

Return ONLY valid JSON matching this structure (only for the missing categories/attributes):
{_build_json_structure()}

Rules:
- Provide 1-2 specific pros and cons per attribute
- If attribute genuinely doesn't apply (e.g., 4X4 for FWD car), use ["N/A - not available"]
- Be factual based on known vehicle specifications and characteristics
"""

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join([line for line in lines if not line.strip().startswith("```")])
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

        gemini_data = safe_json_parse(response_text, fallback={})

        # Merge gemini data into youtube data
        for category, sub_attrs in ATTRIBUTE_CATEGORIES.items():
            if category not in youtube_data:
                youtube_data[category] = gemini_data.get(category, {})
            else:
                for attr in sub_attrs:
                    if attr not in youtube_data[category] or \
                       not youtube_data[category].get(attr, {}).get("pros") or \
                       youtube_data[category][attr]["pros"] in [["Not covered in reviews"], []]:
                        if category in gemini_data and attr in gemini_data[category]:
                            youtube_data[category][attr] = gemini_data[category][attr]

        return youtube_data

    except Exception as e:
        print(f"  [{car_name}] Gemini fallback failed: {e}")
        return youtube_data


def get_attribute_proscons(car_name: str) -> Dict[str, Any]:
    """
    Extract attribute pros/cons - first from YouTube, then fill gaps with Gemini.

    Args:
        car_name: Name of the car to analyze

    Returns:
        Dictionary with attribute categories and their pros/cons
    """
    # Step 1: Try YouTube extraction
    youtube_data = get_attribute_proscons_from_youtube(car_name)

    # Step 2: Fill missing with Gemini knowledge
    complete_data = fill_missing_with_gemini(car_name, youtube_data)

    # Ensure all categories exist
    for category, sub_attrs in ATTRIBUTE_CATEGORIES.items():
        if category not in complete_data:
            complete_data[category] = {}
        for attr in sub_attrs:
            if attr not in complete_data[category]:
                complete_data[category][attr] = {"pros": ["Data not available"], "cons": ["Data not available"]}

    return complete_data


def get_multiple_cars_attribute_proscons(car_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Extract attribute pros/cons for multiple cars in parallel.

    Args:
        car_names: List of car names to analyze

    Returns:
        Dictionary mapping car names to their attribute pros/cons
    """
    results = {}

    print(f"\nExtracting attribute pros/cons for {len(car_names)} cars...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(car_names), 5)) as executor:
        future_to_car = {
            executor.submit(get_attribute_proscons, car_name): car_name
            for car_name in car_names
        }

        for future in concurrent.futures.as_completed(future_to_car):
            car_name = future_to_car[future]
            try:
                data = future.result()
                results[car_name] = data
                print(f"  [{car_name}] Attribute pros/cons extracted")
            except Exception as e:
                print(f"  [{car_name}] Failed: {e}")
                results[car_name] = {cat: {attr: {"pros": [], "cons": []} for attr in attrs}
                                     for cat, attrs in ATTRIBUTE_CATEGORIES.items()}

    return results
