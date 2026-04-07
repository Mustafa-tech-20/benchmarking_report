"""
Excel/Spreadsheet Analysis Tool for Product Planning Agent
Analyzes Excel files containing car specifications.
"""
import sys
sys.path.append("/app")
from shared_utils import safe_json_parse, clean_json_response
import base64
import json
import io
from typing import Optional, Dict, Any, List
from vertexai.generative_models import GenerativeModel
from product_planning_agent.config import GEMINI_MAIN_MODEL

# Try to import pandas and openpyxl for Excel parsing
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def parse_excel_to_text(excel_bytes: bytes) -> str:
    """
    Parse Excel file bytes to text representation for LLM analysis.

    Args:
        excel_bytes: Raw bytes of the Excel file

    Returns:
        Text representation of Excel content
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas and openpyxl are required for Excel parsing. Install with: pip install pandas openpyxl")

    # Read Excel file
    excel_file = io.BytesIO(excel_bytes)

    # Try to read all sheets
    try:
        xlsx = pd.ExcelFile(excel_file)
        sheet_names = xlsx.sheet_names
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {str(e)}")

    text_parts = []

    for sheet_name in sheet_names:
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name)

            if df.empty:
                continue

            text_parts.append(f"\n=== SHEET: {sheet_name} ===\n")

            # Convert DataFrame to string representation
            # Include column headers
            headers = list(df.columns)
            text_parts.append(f"Columns: {', '.join(str(h) for h in headers)}\n")
            text_parts.append("-" * 50 + "\n")

            # Add rows
            for idx, row in df.iterrows():
                row_text = " | ".join(f"{col}: {val}" for col, val in row.items() if pd.notna(val))
                if row_text.strip():
                    text_parts.append(f"Row {idx + 1}: {row_text}\n")

            text_parts.append("\n")

        except Exception as e:
            text_parts.append(f"\n[Error reading sheet '{sheet_name}': {str(e)}]\n")

    return "".join(text_parts)


def analyze_excel_tool(
    document_data: str,
    task: str = "extract_specs",
    extract_car_names: bool = True,
    car_names: str = ""
) -> str:
    """
    Analyze Excel file containing car specifications.

    Args:
        document_data: Base64 encoded Excel file data (.xlsx, .xls)
        task: Analysis task - "extract_specs", "summarize", "compare"
        extract_car_names: If True, extract car names from document
        car_names: Comma-separated car names to compare alongside extracted names

    Returns:
        JSON string with analysis results and extracted specifications

    Example:
        analyze_excel_tool(
            document_data=base64_excel,
            task="extract_specs",
            extract_car_names=True,
            car_names="Mahindra Thar"
        )
    """
    try:
        # Decode base64 data
        try:
            excel_bytes = base64.b64decode(document_data)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": f"Invalid base64 data: {str(e)}"
            })

        # Parse Excel to text
        try:
            excel_text = parse_excel_to_text(excel_bytes)
        except ImportError as e:
            return json.dumps({
                "status": "error",
                "error": str(e)
            })
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": f"Failed to parse Excel file: {str(e)}"
            })

        if not excel_text.strip():
            return json.dumps({
                "status": "error",
                "error": "Excel file appears to be empty or unreadable"
            })

        # Build prompt based on task
        prompts = {
            "extract_specs": """You are analyzing an Excel spreadsheet containing car specifications.

Extract ALL car specifications from this data. Map each specification to the standard 87-spec field names used in car comparison reports.

Standard spec field names include:
- price_range, ex_showroom_price, on_road_price
- mileage, fuel_type, engine_displacement, performance (bhp), torque
- transmission, drive_type, ground_clearance
- seating_capacity, boot_space, fuel_tank_capacity
- length, width, height, wheelbase
- airbags, ncap_rating, abs, ebd, esc, traction_control
- infotainment_screen, android_auto, apple_carplay
- sunroof, climate_control, cruise_control
- And many more...

Return a JSON object with this structure:
{
    "cars_found": [
        {
            "car_name": "Car Model Name",
            "specifications": {
                "price_range": "value",
                "mileage": "value",
                "performance": "value",
                ... (all found specs mapped to standard field names)
            }
        }
    ],
    "car_names_found": ["Car1", "Car2", ...],
    "unmapped_specs": ["any specs that couldn't be mapped to standard fields"]
}

Be thorough - extract EVERY specification you can find and map it to the appropriate field name.""",

            "summarize": """Summarize this Excel spreadsheet containing car data:
1. What cars are mentioned?
2. What types of specifications are included?
3. Key highlights or notable data points
4. Data quality (completeness, any missing values)

Return as JSON with "summary" and "car_names_found" keys.""",

            "compare": """Analyze this Excel spreadsheet for car comparison data.

Extract:
1. All car models mentioned
2. Comparative specifications for each car
3. Which car excels in which category
4. Any notes or recommendations

Return as structured JSON with specs mapped to standard field names."""
        }

        prompt = prompts.get(task, prompts["extract_specs"])

        # Add car name extraction reminder
        if extract_car_names:
            prompt += """

IMPORTANT: Include ALL car names/models found in the "car_names_found" array."""

        # Combine prompt with Excel content
        full_prompt = f"""{prompt}

=== EXCEL FILE CONTENT ===
{excel_text}
=== END OF EXCEL CONTENT ===

Return ONLY valid JSON, no markdown or explanation."""

        # Call Gemini
        model = GenerativeModel(GEMINI_MAIN_MODEL)
        response = model.generate_content(full_prompt)
        analysis = response.text.strip()

        # Parse response
        result = {
            "status": "success",
            "task": task,
        }

        # Try to parse JSON response
        try:
            if "```json" in analysis:
                analysis = analysis.split("```json")[1].split("```")[0]
            elif "```" in analysis:
                analysis = analysis.split("```")[1].split("```")[0]

            if "{" in analysis and "}" in analysis:
                start = analysis.index("{")
                end = analysis.rindex("}") + 1
                json_str = analysis[start:end]
                parsed = safe_json_parse(json_str, fallback={})
                result["analysis"] = parsed

                # Extract car names
                car_names_found = parsed.get("car_names_found", [])
                if not car_names_found and "cars_found" in parsed:
                    car_names_found = [c.get("car_name") for c in parsed.get("cars_found", []) if c.get("car_name")]

                result["car_names_found"] = car_names_found

                # Combine with provided car names
                all_car_names = list(car_names_found) if car_names_found else []
                if car_names:
                    provided_names = [c.strip() for c in car_names.split(",") if c.strip()]
                    all_car_names.extend(provided_names)

                # Remove duplicates
                all_car_names = list(dict.fromkeys(all_car_names))

                if all_car_names:
                    car_names_str = ", ".join(all_car_names)
                    result["car_names_for_comparison"] = car_names_str
                    result["comparison_ready"] = True
                    result["message"] = (
                        f"Found {len(all_car_names)} car(s) for comparison. "
                        f"Call scrape_cars_tool with car_names=\"{car_names_str}\""
                    )
            else:
                result["analysis"] = analysis

        except Exception as e:
            result["analysis"] = analysis
            result["parse_warning"] = f"Could not parse as JSON: {str(e)}"

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": f"Excel analysis failed: {str(e)}"
        }, indent=2)


def extract_specs_from_excel(document_data: str, car_name: str = "") -> Dict[str, Any]:
    """
    Extract car specifications from Excel file and return as a dict ready for save_excel_car_specs_tool.

    Args:
        document_data: Base64 encoded Excel file
        car_name: Optional specific car name to extract specs for

    Returns:
        Dict with car specifications mapped to standard field names
    """
    result = analyze_excel_tool(
        document_data=document_data,
        task="extract_specs",
        extract_car_names=True,
        car_names=car_name
    )

    try:
        parsed = json.loads(result)
        if parsed.get("status") == "success":
            analysis = parsed.get("analysis", {})
            cars_found = analysis.get("cars_found", [])

            if cars_found:
                # If specific car requested, find it
                if car_name:
                    for car in cars_found:
                        if car_name.lower() in car.get("car_name", "").lower():
                            return {
                                "car_name": car.get("car_name"),
                                "specifications": car.get("specifications", {})
                            }

                # Return first car found
                return {
                    "car_name": cars_found[0].get("car_name"),
                    "specifications": cars_found[0].get("specifications", {})
                }

        return {"error": parsed.get("error", "No specifications found")}

    except Exception as e:
        return {"error": str(e)}
