"""
Generation Comparison Extraction for Product Planning Agent
Extracts ONLY old generation data needed for comparison.
New generation data is reused from existing variant_walk extraction.
Uses Google Search grounding for up-to-date information.
"""
import json
import os
from typing import Dict, Any
from json_repair import repair_json
from google import genai
from google.genai import types

# Initialize Gemini client with Google Search grounding
_gemini_search_client = genai.Client(
    vertexai=True,
    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "srv-ad-nvoc-dev-445421"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
)
GEMINI_SEARCH_MODEL = "gemini-2.5-flash"


def extract_old_generation_data(car_name: str, new_gen_variants: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract ONLY old generation data for comparison using Google Search grounding.
    New generation data is already available from variant_walk.

    Args:
        car_name: Name of the car (current/new generation)
        new_gen_variants: Variant data from variant_walk for the new generation

    Returns:
        Dictionary with:
        - old_generation: {name, launch_year}
        - old_variants: {fuel_trans: [{variant, price}]}
        - variant_mapping: Maps old variants to new variants with price diff and features added
    """
    try:
        # Extract new generation variant names from variant_walk for context
        new_variant_names = list(new_gen_variants.get('variants', {}).keys()) if new_gen_variants else []

        print(f"  Extracting old generation data for {car_name} (with Google Search)...")

        prompt = f"""Search for old generation (previous generation) data for {car_name} car in India.

CONTEXT: We already have the NEW generation data. We ONLY need old generation info.

New generation variants we already have: {', '.join(new_variant_names[:10])}

TASK: Provide ONLY old/previous generation information:
1. Old generation name and launch year
2. ALL old generation variant names with ex-showroom prices
3. Map each old variant to corresponding new variant (based on positioning/price/features)
4. For mapped variants, list ONLY the key features ADDED in new variant

RULES:
- Organize by fuel type (petrol/diesel) and transmission (MT/AT/CVT)
- Prices in lakhs (e.g., "5.49" for ₹5.49 lakh)
- Only include SIGNIFICANT feature additions (safety, tech, comfort - not minor trim)
- If no old generation exists, return status: "no_old_generation"

Return ONLY valid JSON:
{{
    "old_generation": {{
        "name": "Tata Punch 2021-2024" (or actual old gen name),
        "launch_year": "2021"
    }},
    "old_variants": {{
        "petrol_mt": [
            {{"variant": "Pure", "price": "5.49"}},
            {{"variant": "Adventure", "price": "6.55"}},
            {{"variant": "Accomplished +", "price": "7.70"}}
        ],
        "petrol_at": [
            {{"variant": "Creative +", "price": "8.69"}}
        ],
        "diesel_mt": [],
        "diesel_at": []
    }},
    "variant_mapping": {{
        "petrol_mt": [
            {{
                "old_variant": "Pure",
                "new_variant": "Smart",
                "features_added": ["6 Airbags", "LED Headlamps", "iTPMS", "Remote key"]
            }},
            {{
                "old_variant": "Accomplished +",
                "new_variant": "Accomplished",
                "features_added": ["Telematics", "Auto Dimming IRVM", "360 view", "Connected LED Tail lamp", "Ambient lighting", "Air purifier", "6 Airbags"]
            }}
        ],
        "petrol_at": [],
        "diesel_mt": [],
        "diesel_at": []
    }}
}}

If no old generation: {{"status": "no_old_generation"}}

Return ONLY valid JSON, no markdown or explanation."""

        # Use Google Search grounding for up-to-date generation data
        response = _gemini_search_client.models.generate_content(
            model=GEMINI_SEARCH_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_modalities=["TEXT"],
                temperature=0.1,
            )
        )

        if not response or not response.text:
            print(f"  Old generation: No response from Gemini")
            return {"has_old_generation": False, "message": "No response"}

        response_text = response.text.strip()

        # Clean markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            if response_text.startswith("json"):
                response_text = response_text[4:].strip()

        # Parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            repaired = repair_json(response_text)
            data = json.loads(repaired)

        # Validate
        if data.get("status") == "no_old_generation":
            print(f"  ℹ No previous generation for {car_name}")
            return {
                "has_old_generation": False,
                "message": "No previous generation available"
            }

        old_gen_name = data.get("old_generation", {}).get("name", "Unknown")
        print(f"  ✓ Old generation found: {old_gen_name}")
        data["has_old_generation"] = True
        return data

    except Exception as e:
        print(f"Error extracting old generation data for {car_name}: {str(e)}")
        return {
            "has_old_generation": False,
            "error": str(e)
        }
