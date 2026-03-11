"""
Detailed Review Extraction for Vehicle Development Agent
Extracts detailed reviews from automotive publication sites using Gemini.
"""
import sys
sys.path.append("/app")
from shared_utils import safe_json_parse, clean_json_response
import json
from typing import Dict, Any, List
from vertexai.generative_models import GenerativeModel


def extract_detailed_reviews(car_names: List[str], search_sites: List[str]) -> Dict[str, Any]:
    """
    Extract detailed reviews for each car from automotive publications.
    Similar to the Edmunds.com format with performance, comfort, etc. ratings.

    Args:
        car_names: List of car names to get reviews for
        search_sites: List of automotive publication sites to reference

    Returns:
        Dictionary with detailed review data for each car
    """
    try:
        model = GenerativeModel("gemini-2.5-flash")

        # Format car list and site list for prompt
        cars_list = ", ".join(car_names)
        sites_list = ", ".join(search_sites[:10])  # Use top 10 sites

        prompt = f"""Extract detailed professional reviews for these cars: {cars_list}

Reference these automotive publication sites for review insights: {sites_list}

TASK:
For each car, provide detailed categorical reviews with ratings (out of 10) and specific feedback points.
Format should match professional automotive review standards (like Edmunds, AutoCar, OverDrive).

Return ONLY valid JSON in this exact format:
{{
    "car1_name": {{
        "overall_rating": 7.6,
        "publication": "AutoCar India",
        "categories": {{
            "performance": {{
                "rating": 6.5,
                "positives": [
                    "Bronco Sport is a blast to drive in the dirt.",
                    "Engine delivers good power in city driving"
                ],
                "negatives": [
                    "But less enjoyable on the street.",
                    "Braking and steering are not up to par.",
                    "Transmission shifts are occasionally jerky at low speeds."
                ]
            }},
            "comfort": {{
                "rating": 8.0,
                "positives": [
                    "Smooth ride and quiet cabin.",
                    "Padded leather seats are comfortable for all drives."
                ],
                "negatives": [
                    "Lacks the smooth ride from rivals.",
                    "Rear seats are tight for adults."
                ]
            }},
            "fuel_efficiency": {{
                "rating": 7.2,
                "positives": [
                    "Competitive city mileage of 14.5 kmpl",
                    "Highway efficiency is impressive at 18.2 kmpl"
                ],
                "negatives": [
                    "Could be better for the segment",
                    "Real-world figures vary significantly"
                ]
            }},
            "interior_quality": {{
                "rating": 8.5,
                "positives": [
                    "Premium materials throughout cabin",
                    "Well laid out dashboard with intuitive controls",
                    "Good build quality with minimal squeaks"
                ],
                "negatives": [
                    "Some hard plastics in lower areas",
                    "Infotainment system can be slow to respond"
                ]
            }},
            "technology": {{
                "rating": 7.8,
                "positives": [
                    "Large touchscreen with crisp graphics",
                    "Good smartphone connectivity",
                    "Comprehensive safety features"
                ],
                "negatives": [
                    "Interface could be more intuitive",
                    "Missing some advanced driver aids"
                ]
            }},
            "value_for_money": {{
                "rating": 7.5,
                "positives": [
                    "Competitive pricing in segment",
                    "Good feature list for the price",
                    "Strong warranty package"
                ],
                "negatives": [
                    "Higher variants get expensive",
                    "Some features are optional extras"
                ]
            }},
            "handling": {{
                "rating": 7.0,
                "positives": [
                    "Stable at highway speeds",
                    "Good grip in corners"
                ],
                "negatives": [
                    "Steering feels slightly numb",
                    "Body roll is noticeable in sharp turns"
                ]
            }}
        }}
    }},
    "car2_name": {{
        "overall_rating": 8.1,
        "publication": "OverDrive",
        "categories": {{
            "performance": {{...}},
            "comfort": {{...}},
            ...
        }}
    }}
}}

CRITICAL RULES:
- Include ALL {len(car_names)} cars
- Ratings must be numeric decimals between 0.0 and 10.0
- Provide 2-4 specific positive points per category
- Provide 1-3 specific negative points per category
- Use actual review language (not generic)
- Focus on categories: performance, comfort, fuel_efficiency, interior_quality, technology, value_for_money, handling
- Base on real professional automotive review standards
- Use "Not Tested" only if category is truly not applicable (like performance for electric cars)
"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        reviews_data = safe_json_parse(response_text, fallback={})
        return reviews_data

    except json.JSONDecodeError as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Response text: {response_text[:500]}")
        return {}
    except Exception as e:
        print(f"Error extracting detailed reviews: {e}")
        return {}
