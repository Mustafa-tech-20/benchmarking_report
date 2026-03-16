"""
Drivetrain Feature Fetcher using Gemini with Google Search Grounding
Fetches detailed drivetrain/4WD comparison data when not available in scraped data
"""

import json
import logging
from typing import Dict, Any, List, Optional

from google import genai
from google.genai import types

from vehicle_development_agent.config import GOOGLE_API_KEY, SEARCH_SITES

logger = logging.getLogger(__name__)


async def fetch_drivetrain_data(
    car_names: List[str],
    existing_data: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed drivetrain/4WD comparison data using Gemini with Google Search grounding.

    Args:
        car_names: List of car names to compare
        existing_data: Optional existing comparison data to supplement

    Returns:
        Structured drivetrain comparison data or None if fetch fails
    """
    if not car_names:
        return None

    # Focus on the first car for the detailed comparison
    primary_car = car_names[0]

    # Build search query focusing on trusted sites
    trusted_sites = " OR ".join([f"site:{site}" for site in SEARCH_SITES[:10]])

    prompt = f"""
    Search for detailed drivetrain and 4WD/AWD system information for: {primary_car}

    Focus on finding:
    1. The official name of the drivetrain/4WD system
    2. Mode switching capabilities (automatic vs manual)
    3. Differential type (electronic limited-slip, mechanical, etc.)
    4. Available driving modes (list all modes)
    5. Terrain adaptability features
    6. User convenience features
    7. Technical specifications (ground clearance, approach/departure angles)

    Return the data as a JSON object with this structure:
    {{
        "car_name": "{primary_car}",
        "system_name": "Name of the 4WD/AWD system",
        "intro_text": "A 2-3 sentence description of the drivetrain system highlighting key features",
        "highlight_keywords": ["keyword1", "keyword2"],
        "comparison_with": "Conventional 4WD",
        "features": [
            {{"name": "Mode Switching", "car_value": "value for this car", "conventional_value": "conventional comparison"}},
            {{"name": "Differential", "car_value": "value", "conventional_value": "comparison"}},
            {{"name": "Driving Modes", "car_value": "value", "conventional_value": "comparison"}},
            {{"name": "Terrain adaptability", "car_value": "value", "conventional_value": "comparison"}},
            {{"name": "User convenience", "car_value": "value", "conventional_value": "comparison"}}
        ],
        "explanations": [
            {{"title": "Feature Name", "description": "Brief explanation of the feature"}},
            {{"title": "Feature Name 2", "description": "Brief explanation"}}
        ],
        "images": []
    }}

    Only return valid JSON, no markdown or other formatting.
    """

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)

        # Configure Google Search grounding
        google_search_tool = types.Tool(
            google_search=types.GoogleSearch()
        )

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.3,
                max_output_tokens=2000,
            )
        )

        if response and response.text:
            # Parse JSON from response
            response_text = response.text.strip()

            # Clean up response if wrapped in markdown
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            drivetrain_data = json.loads(response_text.strip())

            # Add images from existing data if available
            if existing_data:
                for car_name, car_data in existing_data.items():
                    if isinstance(car_data, dict) and "error" not in car_data:
                        images = car_data.get("images", {})
                        tech_images = images.get("technology", [])
                        for img in tech_images[:2]:
                            if isinstance(img, (list, tuple)):
                                drivetrain_data.setdefault("images", []).append(img[0])
                            elif isinstance(img, str):
                                drivetrain_data.setdefault("images", []).append(img)
                        break

            logger.info(f"[DRIVETRAIN] Successfully fetched drivetrain data for {primary_car}")
            return drivetrain_data

    except json.JSONDecodeError as e:
        logger.error(f"[DRIVETRAIN] Failed to parse JSON response: {e}")
    except Exception as e:
        logger.error(f"[DRIVETRAIN] Error fetching drivetrain data: {e}")

    return None


def check_has_drivetrain_data(comparison_data: Dict[str, Any]) -> bool:
    """
    Check if comparison_data has sufficient drivetrain-related information.

    Args:
        comparison_data: Dict mapping car names to their scraped data

    Returns:
        True if sufficient drivetrain data exists, False otherwise
    """
    drivetrain_keys = [
        "drive_type", "drive_mode", "differential", "4wd_system",
        "awd_system", "traction_control", "terrain_modes", "off_road"
    ]

    required_count = 2  # Need at least 2 drivetrain-related fields

    for car_name, car_data in comparison_data.items():
        if not isinstance(car_data, dict) or "error" in car_data:
            continue

        found_count = 0
        for key in drivetrain_keys:
            value = car_data.get(key)
            if value and value not in ["N/A", "Not Available", "-", "", None]:
                found_count += 1

        if found_count >= required_count:
            return True

    return False
