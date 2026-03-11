"""
Comparative Graphs Data Extraction for Vehicle Development Agent
Extracts comparative data for visual graphs using Gemini.
"""
import sys
sys.path.append("/app")
from shared_utils import safe_json_parse, clean_json_response
import json
from typing import Dict, Any, List
from vertexai.generative_models import GenerativeModel


def extract_comparative_graphs_data(car_names: List[str], existing_spec_data: Dict[str, Any] = None, detailed_reviews: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Extract comparative data for 10-15 graphs using Gemini.
    Uses existing spec data and detailed reviews (with overall ratings) where available.

    Args:
        car_names: List of car names to compare
        existing_spec_data: Dictionary of already extracted spec data for each car
        detailed_reviews: Dictionary with detailed reviews including overall_rating for each car

    Returns:
        Dictionary with graph data for multiple comparison categories
    """
    try:
        model = GenerativeModel("gemini-2.5-flash")

        # Format car list for prompt
        cars_list = ", ".join(car_names)

        # Build context from existing data if available
        existing_data_context = ""
        if existing_spec_data:
            existing_data_context = "\nEXISTING DATA (use this where available):\n"
            for car_name in car_names:
                car_data = existing_spec_data.get(car_name, {})
                if car_data and isinstance(car_data, dict):
                    relevant_specs = {
                        "mileage": car_data.get("mileage", ""),
                        "price_range": car_data.get("price_range", ""),
                        "performance": car_data.get("performance", ""),
                        "torque": car_data.get("torque", ""),
                        "seating_capacity": car_data.get("seating_capacity", ""),
                        "boot_space": car_data.get("boot_space", ""),
                        "ground_clearance": car_data.get("ground_clearance", ""),
                        "turning_radius": car_data.get("turning_radius", ""),
                    }
                    existing_data_context += f"\n{car_name}: {json.dumps(relevant_specs, indent=2)}"

        # Extract overall ratings from detailed reviews if available
        ratings_context = ""
        overall_ratings = {}
        if detailed_reviews:
            ratings_context = "\n\nOVERALL RATINGS FROM DETAILED REVIEWS (include these in graphs):\n"
            for car_name in car_names:
                review_data = detailed_reviews.get(car_name, {})
                if review_data and isinstance(review_data, dict):
                    overall_rating = review_data.get("overall_rating", None)
                    if overall_rating is not None:
                        overall_ratings[car_name] = overall_rating
                        ratings_context += f"{car_name}: {overall_rating}/10\n"

        prompt = f"""Extract comparative data for visual graphs comparing these cars: {cars_list}
{existing_data_context}{ratings_context}

TASK:
Provide detailed numerical data for creating 15 comparison graphs. For each car, extract specific numeric values.
Use existing data provided above where available. For missing data, provide from your knowledge.
IMPORTANT: Include the overall_rating values from the detailed reviews data provided above.

Return ONLY valid JSON in this exact format:
{{
    "overall_rating": {{
        "car1_name": 7.6,
        "car2_name": 8.1
    }},
    "price_comparison": {{
        "car1_name": {{"base": 10.5, "top": 15.0}},
        "car2_name": {{"base": 12.0, "top": 17.5}}
    }},
    "mileage_comparison": {{
        "car1_name": {{"city": 14.5, "highway": 18.2}},
        "car2_name": {{"city": 15.0, "highway": 19.0}}
    }},
    "performance_comparison": {{
        "car1_name": {{"horsepower": 150, "torque": 250}},
        "car2_name": {{"horsepower": 160, "torque": 270}}
    }},
    "dimensions_comparison": {{
        "car1_name": {{"length": 4500, "width": 1850, "height": 1700, "wheelbase": 2700}},
        "car2_name": {{"length": 4450, "width": 1800, "height": 1680, "wheelbase": 2650}}
    }},
    "capacity_comparison": {{
        "car1_name": {{"seating": 7, "boot_space": 448, "fuel_tank": 60}},
        "car2_name": {{"seating": 5, "boot_space": 350, "fuel_tank": 50}}
    }},
    "ground_clearance": {{
        "car1_name": 205,
        "car2_name": 180
    }},
    "turning_radius": {{
        "car1_name": 5.6,
        "car2_name": 5.2
    }},
    "safety_features": {{
        "car1_name": {{"airbags": 6, "ncap_rating": 5, "adas_features": 8}},
        "car2_name": {{"airbags": 6, "ncap_rating": 4, "adas_features": 5}}
    }},
    "transmission_types": {{
        "car1_name": ["Manual", "Automatic"],
        "car2_name": ["Manual", "DCT"]
    }},
    "fuel_types": {{
        "car1_name": ["Petrol", "Diesel"],
        "car2_name": ["Petrol", "Diesel", "CNG"]
    }},
    "warranty_comparison": {{
        "car1_name": {{"years": 3, "km": 100000}},
        "car2_name": {{"years": 5, "km": 150000}}
    }},
    "service_cost_annual": {{
        "car1_name": 15000,
        "car2_name": 18000
    }},
    "tire_size": {{
        "car1_name": "215/60 R17",
        "car2_name": "215/65 R16"
    }},
    "kerb_weight": {{
        "car1_name": 1650,
        "car2_name": 1580
    }},
    "acceleration_0_100": {{
        "car1_name": 10.5,
        "car2_name": 11.2
    }}
}}

CRITICAL RULES:
- All values must be NUMERIC where possible (not strings like "5 years", use 5)
- For price in lakhs (10.5 = ₹10.5 Lakh)
- For mileage in kmpl
- For dimensions in mm (millimeters)
- For boot space in liters
- For fuel tank in liters
- For ground clearance in mm
- For turning radius in meters
- For warranty years/km use numbers only
- For acceleration in seconds
- For kerb weight in kg
- Use "Not Available" only if data is truly unavailable
- Include ALL {len(car_names)} cars in EVERY category
"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        graphs_data = safe_json_parse(response_text, fallback={})

        # Ensure overall_rating is included from detailed_reviews
        if overall_ratings:
            graphs_data["overall_rating"] = overall_ratings

        return graphs_data

    except json.JSONDecodeError as e:
        print(f"Error parsing Gemini response: {e}")
        print(f"Response text: {response_text[:500]}")
        return {}
    except Exception as e:
        print(f"Error extracting comparative graphs data: {e}")
        return {}
