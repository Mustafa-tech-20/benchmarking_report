"""
PDF/Document Analysis Tool for Car Benchmarking Agent
Analyzes PDFs containing car specifications or reviews.
"""
import sys
sys.path.append("/app")
from shared_utils import safe_json_parse, clean_json_response
import base64
import json
from typing import Optional
from vertexai.generative_models import GenerativeModel, Part
from product_planning_agent.config import GEMINI_MAIN_MODEL


def analyze_document_tool(
    document_data: str,
    task: str = "summarize",
    extract_car_names: bool = False,
    car_names: str = ""
) -> str:
    """
    Analyze PDF/document containing car specifications or reviews.

    Args:
        document_data: Base64 encoded PDF/document data
        task: Analysis task - "summarize", "extract_specs", "compare", "analyze"
        extract_car_names: If True, extract car names from document for comparison
        car_names: Comma-separated car names to compare alongside extracted names (e.g., "Mahindra Thar, Maruti Swift")

    Returns:
        JSON string with analysis results and optionally car names for comparison

    Example:
        analyze_document_tool(
            document_data=base64_pdf,
            task="analyze",
            extract_car_names=True,
            car_names="Mahindra Thar, Maruti Swift, Tata Nexon"
        )
    """
    try:
        # Decode base64 data
        try:
            doc_bytes = base64.b64decode(document_data)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": f"Invalid base64 data: {str(e)}"
            })

        # Create document part for Gemini
        doc_part = Part.from_data(doc_bytes, mime_type="application/pdf")

        # Build prompt based on task
        prompts = {
            "summarize": """Summarize this document concisely:
1. Main topic/focus
2. Key points (3-5 bullets)
3. Important specifications or data mentioned
4. Conclusions or recommendations

Keep summary under 200 words.""",

            "extract_specs": """Extract car specifications from this document.

Return a JSON object with:
- car_name: Name of the car
- specifications: Dict of spec names to values
- key_highlights: List of notable features
- source: Document title/source if mentioned

Be thorough in extracting all numeric specs (price, mileage, power, etc.).""",

            "compare": """Analyze this document for car comparison data.

Extract:
1. Car models mentioned
2. Comparative data (which car is better at what)
3. Specifications table if present
4. Pros/cons for each car
5. Recommendations

Format as structured JSON.""",

            "analyze": """Perform comprehensive analysis of this automotive document.

Analyze:
- Document type (review, spec sheet, comparison, test drive)
- Cars mentioned with key details
- Technical specifications
- Performance metrics
- User feedback or ratings
- Recommendations or conclusions

Provide insights useful for product development team."""
        }

        prompt = prompts.get(task, prompts["summarize"])

        # Add car name extraction if requested
        if extract_car_names:
            prompt += """

IMPORTANT: Also extract ALL car names/models mentioned in this document.
Return them as a list in the JSON response under "car_names_found" key."""

        # Call Gemini with document
        model = GenerativeModel(GEMINI_MAIN_MODEL)
        response = model.generate_content([prompt, doc_part])
        analysis = response.text.strip()

        # Parse response
        result = {
            "status": "success",
            "task": task,
            "analysis": analysis,
        }

        # Extract car names if requested
        if extract_car_names:
            try:
                # Try to parse JSON response
                if "{" in analysis and "}" in analysis:
                    start = analysis.index("{")
                    end = analysis.rindex("}") + 1
                    json_str = analysis[start:end]
                    parsed = safe_json_parse(json_str, fallback={})
                    car_names_found = parsed.get("car_names_found", [])
                else:
                    car_names_found = []

                # Combine with provided car names
                all_car_names = []
                if car_names_found:
                    all_car_names.extend(car_names_found)
                if car_names:
                    # Parse comma-separated car names
                    provided_names = [c.strip() for c in car_names.split(",") if c.strip()]
                    all_car_names.extend(provided_names)

                # Remove duplicates while preserving order
                all_car_names = list(dict.fromkeys(all_car_names))

                if all_car_names:
                    # Format as comma-separated string for scrape_cars_tool
                    car_names_str = ", ".join(all_car_names)
                    result["car_names_for_comparison"] = car_names_str
                    result["comparison_ready"] = True
                    result["message"] = (
                        f"Found {len(all_car_names)} car(s) for comparison. "
                        f"Call scrape_cars_tool with car_names=\"{car_names_str}\""
                    )
            except Exception as e:
                result["extraction_warning"] = f"Could not extract car names: {str(e)}"

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": f"Document analysis failed: {str(e)}"
        }, indent=2)


def quick_pdf_summary(document_data: str) -> str:
    """
    Quick summary of PDF document.
    Convenience wrapper for analyze_document_tool.

    Args:
        document_data: Base64 encoded PDF data

    Returns:
        JSON string with summary
    """
    return analyze_document_tool(document_data, task="summarize", extract_car_names=False)
