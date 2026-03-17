"""
Drivetrain Feature Fetcher using Gemini with Google Search Grounding
Fetches detailed drivetrain comparison data for EACH car in the comparison,
running all Gemini calls in PARALLEL (3 calls for 3 cars, 5 for 5 cars, etc.)
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional

from google import genai
from google.genai import types
from json_repair import repair_json

logger = logging.getLogger(__name__)

# Initialize Gemini client for Google Search grounding (requires Vertex AI)
_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
gemini_client = genai.Client(vertexai=True, project=_PROJECT_ID, location="global")


def _extract_json_from_response(text: str) -> str:
    """Extract JSON object/array from Gemini response text."""
    if not text or not text.strip():
        return ""

    text = text.strip()

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    obj_start = text.find('{')
    arr_start = text.find('[')

    if obj_start == -1 and arr_start == -1:
        return ""
    elif obj_start == -1:
        start = arr_start
        opening, closing = '[', ']'
    elif arr_start == -1:
        start = obj_start
        opening, closing = '{', '}'
    else:
        start = min(obj_start, arr_start)
        opening, closing = ('{', '}') if start == obj_start else ('[', ']')

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if not in_string:
            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]

    return text[start:]


async def _fetch_single_car_drivetrain(
    car_name: str,
    existing_data: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch drivetrain data for a SINGLE car using Gemini + Google Search grounding.

    The comparison_with field is dynamic — Gemini determines the appropriate
    conventional baseline (4WD, AWD, FWD, ICE, etc.) based on the car's drivetrain.

    Args:
        car_name: Name of the car
        existing_data: Optional existing comparison data for image fallback

    Returns:
        Structured drivetrain comparison dict or None if fetch fails
    """
    print(f"  Fetching drivetrain data: {car_name}")

    prompt = f'''You are an automotive expert. Search the web and extract DETAILED drivetrain/powertrain system specifications for "{car_name}".

I need SPECIFIC technical data for a feature comparison table. Search official brand websites, automotive review sites (autocar, motortrend, caranddriver, topgear, autocarindia, team-bhp), and specification databases.

Return a JSON object with this EXACT structure:
{{
    "car_name": "{car_name}",
    "system_name": "<Official name of the drivetrain system — e.g., 'Part-time 4WD with Manual Shift Transfer Case', 'Intelligent 4MOTION AWD', 'e-AWD Dual Motor', 'FWD with Torque Vectoring'>",
    "intro_text": "<A detailed 2-3 sentence description of the drivetrain system. Mention the system name, key technologies, and what makes it special compared to a conventional drivetrain.>",
    "highlight_keywords": ["<system_name_short>", "<key_feature_1>", "<key_feature_2>"],
    "comparison_with": "<Choose the most appropriate conventional baseline to compare against. Options: 'Conventional 4WD' for off-road 4WD cars, 'Conventional AWD' for intelligent AWD cars, 'Conventional FWD' for front-wheel drive cars, 'Conventional RWD' for rear-wheel drive cars, 'Conventional ICE Drivetrain' for EVs, 'Conventional Hybrid Drivetrain' for plug-in hybrids. Pick whichever best contrasts this car's drivetrain technology.>",
    "features": [
        {{
            "name": "Mode Switching",
            "car_value": "<SPECIFIC value for {car_name} — e.g., 'Automatic 2WD ↔ 4WD based on traction need', 'Always-on AWD with torque vectoring', 'Fixed FWD with electronic traction control'>",
            "conventional_value": "<What a conventional version of this drivetrain type would have — e.g., 'Manual lever/button', 'Basic open differential', 'Manual selector'>"
        }},
        {{
            "name": "Differential",
            "car_value": "<SPECIFIC type for {car_name}>",
            "conventional_value": "<Conventional equivalent>"
        }},
        {{
            "name": "Driving Modes",
            "car_value": "<SPECIFIC modes for {car_name} with count and names>",
            "conventional_value": "<Conventional equivalent — e.g., 'Usually 2-3 modes', 'No terrain modes'>"
        }},
        {{
            "name": "Terrain / Road Adaptability",
            "car_value": "<SPECIFIC features for {car_name}>",
            "conventional_value": "<Conventional equivalent>"
        }},
        {{
            "name": "User Convenience",
            "car_value": "<SPECIFIC automation level for {car_name}>",
            "conventional_value": "<Conventional equivalent>"
        }}
    ],
    "explanations": [
        {{
            "title": "<Technology name 1>",
            "description": "<Explain this technology specific to {car_name}>"
        }},
        {{
            "title": "<Technology name 2>",
            "description": "<Explain this technology>"
        }},
        {{
            "title": "<Technology name 3>",
            "description": "<Explain this technology>"
        }},
        {{
            "title": "<Technology name 4>",
            "description": "<Explain this technology>"
        }}
    ],
    "specs": {{
        "ground_clearance": "<value in mm>",
        "approach_angle": "<value in degrees or Not Available>",
        "departure_angle": "<value in degrees or Not Available>",
        "breakover_angle": "<value in degrees or Not Available>",
        "water_wading_depth": "<value in mm or Not Available>",
        "low_range_gearbox": "<Yes/No and ratio, or Not Available>"
    }}
}}

CRITICAL INSTRUCTIONS:
1. SEARCH for actual specifications — do NOT use generic placeholders
2. comparison_with MUST be chosen dynamically based on this car's drivetrain type
3. Feature conventional_value MUST match the chosen comparison_with type
4. Include at least 5 features in the features array
5. Include 4-6 explanations covering the key drivetrain technologies
6. highlight_keywords should be terms to highlight in green in the report
7. If a value is genuinely unavailable, use "Not Available"

Return ONLY valid JSON, no markdown or explanation text.'''

    try:
        tools = [types.Tool(google_search=types.GoogleSearch())]
        config = types.GenerateContentConfig(
            tools=tools,
            temperature=0.2,
            max_output_tokens=4096,
        )

        from benchmarking_agent.config import GEMINI_MAIN_MODEL
        response = await gemini_client.aio.models.generate_content(
            model=GEMINI_MAIN_MODEL,
            contents=prompt,
            config=config,
        )

        if not response or not response.text:
            logger.warning(f"[DRIVETRAIN] Empty response for {car_name}")
            return None

        response_text = response.text.strip()
        json_str = _extract_json_from_response(response_text)

        if not json_str:
            logger.error(f"[DRIVETRAIN] Could not extract JSON for {car_name}")
            return None

        try:
            drivetrain_data = repair_json(json_str)
            if isinstance(drivetrain_data, str):
                drivetrain_data = json.loads(drivetrain_data)
        except Exception as e:
            logger.error(f"[DRIVETRAIN] JSON parse error for {car_name}: {e}")
            return None

        if not isinstance(drivetrain_data, dict):
            logger.error(f"[DRIVETRAIN] Response is not a dict for {car_name}")
            return None

        if not drivetrain_data.get("features"):
            logger.warning(f"[DRIVETRAIN] No features for {car_name}")
            return None

        # Attach images from existing data if available
        if existing_data and not drivetrain_data.get("images"):
            car_data = existing_data.get(car_name, {})
            if isinstance(car_data, dict):
                images = car_data.get("images", {})
                drivetrain_data["images"] = []
                for category in ["technology", "exterior"]:
                    for img in images.get(category, [])[:2]:
                        if isinstance(img, (list, tuple)):
                            drivetrain_data["images"].append(img[0])
                        elif isinstance(img, str):
                            drivetrain_data["images"].append(img)
                    if drivetrain_data["images"]:
                        break

        print(f"  ✓ {car_name}: {len(drivetrain_data.get('features', []))} features, "
              f"compares with '{drivetrain_data.get('comparison_with', 'N/A')}'")
        return drivetrain_data

    except Exception as e:
        logger.error(f"[DRIVETRAIN] Error fetching {car_name}: {e}")
        print(f"  ✗ {car_name}: {e}")
        return None


async def fetch_all_cars_drivetrain_parallel(
    car_names: List[str],
    existing_data: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Fetch drivetrain data for ALL cars IN PARALLEL.

    Runs one Gemini call per car simultaneously:
    - 3 cars  → 3 parallel Gemini calls
    - 5 cars  → 5 parallel Gemini calls

    Args:
        car_names: List of car names to fetch drivetrain data for
        existing_data: Optional existing comparison data for image fallback

    Returns:
        List of drivetrain data dicts (one per car, in same order as car_names)
    """
    if not car_names:
        return []

    print(f"\n{'='*60}")
    print(f"DRIVETRAIN: Parallel fetch for {len(car_names)} cars")
    print(f"{'='*60}")
    for car in car_names:
        print(f"  Queuing: {car}")
    print(f"\n  Launching {len(car_names)} parallel Gemini calls...\n")

    tasks = [_fetch_single_car_drivetrain(car, existing_data) for car in car_names]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_data = []
    for car_name, result in zip(car_names, results):
        if isinstance(result, Exception):
            print(f"  ✗ {car_name}: Exception — {result}")
        elif result and isinstance(result, dict) and result.get("features"):
            all_data.append(result)
        else:
            print(f"  ○ {car_name}: No drivetrain data extracted")

    print(f"\n  Drivetrain complete: {len(all_data)}/{len(car_names)} cars")
    return all_data


async def fetch_drivetrain_data(
    car_names: List[str],
    existing_data: Dict[str, Any] = None
) -> Optional[Dict[str, Any]]:
    """
    Backward-compatible wrapper — returns data for the first car only.
    New code should use fetch_all_cars_drivetrain_parallel instead.
    """
    all_data = await fetch_all_cars_drivetrain_parallel(car_names, existing_data)
    return all_data[0] if all_data else None


def check_has_drivetrain_data(comparison_data: Dict[str, Any]) -> bool:
    """Check if comparison_data has sufficient drivetrain-related information."""
    drivetrain_keys = [
        "drive_type", "drive_mode", "differential", "4wd_system",
        "awd_system", "traction_control", "terrain_modes", "off_road"
    ]
    required_count = 2

    for car_name, car_data in comparison_data.items():
        if not isinstance(car_data, dict) or "error" in car_data:
            continue
        found_count = sum(
            1 for key in drivetrain_keys
            if car_data.get(key) not in ["N/A", "Not Available", "-", "", None]
        )
        if found_count >= required_count:
            return True

    return False
