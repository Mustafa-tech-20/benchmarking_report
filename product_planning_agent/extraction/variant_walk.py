"""
Variant Walk Extraction for Product Planning Agent
Extracts variant information including features and pricing using Gemini with Google Search.
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


def extract_variant_walk(car_name: str) -> Dict[str, Any]:
    """
    Extract variant walk data using Gemini with Google Search grounding.

    Args:
        car_name: Name of the car

    Returns:
        Dictionary with variant data structure including:
        - variants: Dict of variant details with features, pricing
        - price_ladder: Organized pricing by fuel type and transmission
    """
    try:
        print(f"  Extracting variant walk for {car_name} (with Google Search)...")

        prompt = f"""Search for all variant names, features, and pricing for {car_name} car in India.

TASK:
Provide the variant walk data showing how features are added AND removed across trim levels, along with petrol and diesel prices.
For each variant, identify:
1. Variant name (e.g., "E", "EX", "S", "SX", "SX(O)")
2. Key features included in that variant
3. Features added compared to previous variant
4. Features deleted/removed compared to previous variant (IMPORTANT: Some features are removed to reduce cost or replaced with better alternatives)
5. Petrol price (if available, with MT/AT variants)
6. Diesel price (if available, with MT/AT variants)

EXAMPLES OF COMMONLY DELETED FEATURES:
- Manual parking brake → replaced with Electronic parking brake
- Steel wheels → replaced with Alloy wheels
- Halogen headlamps → replaced with LED headlamps
- Basic fabric seats → replaced with Leather seats
- Manual IRVM → replaced with Auto-dimming IRVM
- Rear drum brakes → replaced with Rear disc brakes
- Lane change indicator → removed in higher variants
- Front fog lamps → removed in some variants

Return ONLY valid JSON in this format:
{{
    "variants": {{
        "BASE_VARIANT": {{
            "name": "E" or "Base" or whatever the base variant is called,
            "features": ["feature 1", "feature 2", ...],
            "features_added": [],
            "features_deleted": [],
            "petrol_price_mt": "10.5 lakh" or "Not Available",
            "petrol_price_at": "11.5 lakh" or "Not Available",
            "diesel_price_mt": "12.0 lakh" or "Not Available",
            "diesel_price_at": "13.0 lakh" or "Not Available"
        }},
        "MID_VARIANT": {{
            "name": "EX" or whatever mid variant is called,
            "features": ["all base features", "new feature 1", ...],
            "features_added": ["new feature 1", "new feature 2"],
            "features_deleted": ["feature replaced or removed"],
            "petrol_price_mt": "12.0 lakh" or "Not Available",
            "petrol_price_at": "13.0 lakh" or "Not Available",
            "diesel_price_mt": "13.5 lakh" or "Not Available",
            "diesel_price_at": "14.5 lakh" or "Not Available"
        }},
        "TOP_VARIANT": {{
            "name": "S" or "SX" or whatever,
            "features": [...],
            "features_added": ["upgraded feature"],
            "features_deleted": ["lower-spec feature replaced"],
            "petrol_price_mt": "14.0 lakh" or "Not Available",
            "petrol_price_at": "15.0 lakh" or "Not Available",
            "diesel_price_mt": "15.5 lakh" or "Not Available",
            "diesel_price_at": "16.5 lakh" or "Not Available"
        }}
    }},
    "price_ladder": {{
        "petrol": {{
            "MT": {{
                "variant1_name": "10.5 lakh",
                "variant2_name": "12.0 lakh",
                "variant3_name": "14.0 lakh"
            }},
            "AT": {{
                "variant1_name": "11.5 lakh",
                "variant2_name": "13.0 lakh",
                "variant3_name": "15.0 lakh"
            }}
        }},
        "diesel": {{
            "MT": {{
                "variant1_name": "12.0 lakh",
                "variant2_name": "13.5 lakh",
                "variant3_name": "15.5 lakh"
            }},
            "AT": {{
                "variant1_name": "13.0 lakh",
                "variant2_name": "14.5 lakh",
                "variant3_name": "16.5 lakh"
            }}
        }}
    }}
}}

IMPORTANT:
- Use actual variant names for {car_name}
- List specific features, not generic statements
- Show cascading feature additions AND deletions from base to top variant
- ACTIVELY LOOK FOR features that are removed or replaced (e.g., steel wheels replaced by alloys, halogen replaced by LED)
- Include both MT (Manual) and AT (Automatic) prices if available
- If a fuel type or transmission is not available for a variant, use "Not Available"
- Prices should be in Indian lakhs (e.g., "10.5 lakh", "12.89 lakh")
- If features_deleted is truly empty, use [] but DO look for replacements/removals
- If no variant data found, return {{"variants": {{}}, "price_ladder": {{"petrol": {{}}, "diesel": {{}}}}}}

Return ONLY valid JSON, no markdown or explanation."""

        # Use Google Search grounding for up-to-date variant data
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
            print(f"  Variant walk: No response from Gemini")
            return {"variants": {}, "price_ladder": {"petrol": {}, "diesel": {}}}

        response_text = response.text.strip()

        # Clean response
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join([line for line in lines if not line.strip().startswith("```")])
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

        # Repair and parse JSON using json-repair to handle malformed JSON
        try:
            repaired_json = repair_json(response_text)
            if isinstance(repaired_json, str):
                variant_data = json.loads(repaired_json)
            else:
                variant_data = repaired_json
        except Exception as repair_error:
            print(f"  JSON repair failed: {str(repair_error)[:100]}")
            # Fallback to standard JSON parsing
            variant_data = json.loads(response_text)

        if variant_data.get('variants'):
            num_variants = len(variant_data['variants'])
            print(f"  ✓ Variant walk: Found {num_variants} variants")
        else:
            print(f"  Variant walk: Gemini returned empty — raw snippet: {response_text[:200]}")

        return variant_data

    except Exception as e:
        print(f"  Variant extraction error: {str(e)[:100]}")
        # Return empty structure instead of None to prevent downstream errors
        return {
            "variants": {},
            "price_ladder": {
                "petrol": {"MT": {}, "AT": {}},
                "diesel": {"MT": {}, "AT": {}}
            }
        }
