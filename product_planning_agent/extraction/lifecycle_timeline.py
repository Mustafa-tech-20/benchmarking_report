"""
Lifecycle Timeline Extraction for Product Planning Agent
Extracts complete 5-year timeline with interventions using Gemini.
"""
import json
from typing import Dict, Any, List
from vertexai.generative_models import GenerativeModel
from json_repair import repair_json
from product_planning_agent.config import GEMINI_MAIN_MODEL
from datetime import datetime


def extract_complete_lifecycle_timeline(car_name: str) -> Dict[str, Any]:
    """
    Extract complete 5-year lifecycle timeline with ALL interventions.

    Args:
        car_name: Name of the car

    Returns:
        Dictionary with:
        - launch_year: Year the car was launched
        - timeline_years: List of 5 years to display (e.g., [2021, 2022, 2023, 2024, 2025])
        - interventions: List of all interventions with quarter, year, title, changes
    """
    try:
        model = GenerativeModel(GEMINI_MAIN_MODEL)

        current_year = datetime.now().year

        prompt = f"""Extract the complete lifecycle timeline for {car_name} from launch to present.

TASK: Provide ALL major product interventions, updates, and launches across the car's lifecycle.

Include:
1. Launch date (month and year)
2. ALL variant launches with dates
3. Facelifts, mid-life updates, special editions
4. Major feature additions/updates
5. Engine/powertrain updates
6. Safety/technology updates

For EACH intervention provide:
- Exact date (e.g., "Oct'21", "Sep'22", "Jan'24")
- Quarter (Q1/Q2/Q3/Q4) and Year
- Title/Name of intervention
- 3-4 key specifications or changes

Return ONLY valid JSON:
{{
    "launch_year": 2021,
    "interventions": [
        {{
            "date": "Oct'21",
            "quarter": "Q2",
            "year": 2021,
            "title": "LAUNCH",
            "changes": [
                "Micro SUV [3.83m]",
                "1.2 NA Petrol",
                "GNCAP 5★",
                "Price: ₹5.5-9 Lakh"
            ]
        }},
        {{
            "date": "Sep'22",
            "quarter": "Q3",
            "year": 2022,
            "title": "Camo Edition",
            "changes": [
                "Military inspired Colour & design elements",
                "Adventure-focused styling",
                "Premium interior updates"
            ]
        }},
        {{
            "date": "Aug'23",
            "quarter": "Q2",
            "year": 2023,
            "title": "iCNG",
            "changes": [
                "Twin Cylinder CNG",
                "Sunroof",
                "Boot space optimized"
            ]
        }}
    ]
}}

IMPORTANT:
- Include ALL known interventions from launch to {current_year}
- Quarter mapping: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
- Return actual historical data, not predictions
- If uncertain about exact date, use approximate quarter
"""

        response = model.generate_content(prompt)
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

        launch_year = data.get("launch_year", current_year - 2)
        interventions = data.get("interventions", [])

        # Generate 5-year timeline from launch
        timeline_years = list(range(launch_year, launch_year + 5))

        # Ensure interventions have proper year as integer
        for intervention in interventions:
            if isinstance(intervention.get("year"), str):
                year_match = intervention["year"]
                # Extract year number
                import re
                year_num = re.search(r'\d{4}', year_match)
                if year_num:
                    intervention["year"] = int(year_num.group())
                else:
                    intervention["year"] = launch_year

        return {
            "launch_year": launch_year,
            "timeline_years": timeline_years,
            "interventions": interventions
        }

    except Exception as e:
        print(f"Error extracting lifecycle timeline for {car_name}: {str(e)}")
        # Return minimal fallback data
        current_year = datetime.now().year
        return {
            "launch_year": current_year - 2,
            "timeline_years": list(range(current_year - 2, current_year + 3)),
            "interventions": [
                {
                    "date": "Launch",
                    "quarter": "Q1",
                    "year": current_year - 2,
                    "title": "LAUNCH",
                    "changes": [f"{car_name} market entry"]
                }
            ]
        }
