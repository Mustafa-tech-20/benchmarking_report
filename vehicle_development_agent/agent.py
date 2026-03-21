import os
import json
import asyncio
import time
import concurrent.futures
from typing import Dict, Any, List, Optional

from google.adk.agents import Agent
from shared_utils import safe_json_parse, clean_json_response
from vertexai.generative_models import GenerativeModel

from benchmarking_agent.config import SIGNED_URL_EXPIRATION_HOURS
from vehicle_development_agent.config import GEMINI_MAIN_MODEL
from benchmarking_agent.utils.helpers import is_code_car
from benchmarking_agent.core.scraper import (
    scrape_car_data,
    call_custom_search_parallel,
    extract_spec_from_search_results,
)
# from benchmarking_agent.extraction.sales import scrape_sales_data
from benchmarking_agent.utils.gcs import save_chart_to_gcs, save_json_to_gcs
from benchmarking_agent.core.internal_car_tools import (
    add_code_car_specs_tool,
    query_rag_for_code_car_specs,
    create_blank_specs_for_code_car,
    add_code_car_specs_bulk_tool,
    CAR_SPECS,
)
from vehicle_development_agent.reports.html_generator import create_comparison_chart_html
from vehicle_development_agent.extraction.comparative_graphs import extract_comparative_graphs_data
from vehicle_development_agent.extraction.detailed_reviews import extract_detailed_reviews
from vehicle_development_agent.config import SEARCH_SITES


def generate_ai_analysis_summary(comparison_data: Dict[str, Any]) -> str:
    """Generate AI-powered analysis summary for vehicle development team, like product planning agent."""
    try:
        key_specs = [
            "price_range", "mileage", "user_rating", "seating_capacity",
            "performance", "torque", "transmission", "acceleration",
            "vehicle_safety_features", "braking", "steering",
            "ride_quality", "nvh", "off_road", "interior",
            "infotainment_screen", "boot_space", "sunroof",
            "wheelbase", "turning_radius", "ground_clearance",
            "driveability", "stability", "handling"
        ]

        condensed_data = {}
        for car_name, car_data in comparison_data.items():
            if isinstance(car_data, dict) and "error" not in car_data:
                condensed_data[car_name] = {"car_name": car_data.get("car_name", car_name)}
                for spec in key_specs:
                    value = car_data.get(spec, "")
                    if value and value not in ["Not Available", "Not found", "N/A"]:
                        condensed_data[car_name][spec] = str(value)[:100]

        model = GenerativeModel(GEMINI_MAIN_MODEL)

        prompt = f"""You are a senior automotive engineer providing strategic analysis for a vehicle development team.

Based on this competitor benchmark data, provide focused engineering insights for each category. Each category should be a 3-5 line paragraph explaining engineering targets and benchmarks.

Data from competitor analysis:
{json.dumps(condensed_data, indent=2)}

Write one paragraph (3-5 lines) for each of these categories:

**Price Positioning**
**Engine & Performance**
**Fuel Efficiency**
**Safety Standards**
**NVH Levels**
**Ride & Handling**
**Interior & Features**
**User Satisfaction**

CRITICAL FORMAT RULES:
- NO intro line (do NOT start with "Here are..." or similar)
- Each category gets a focused paragraph (3-5 lines)
- Include specific numbers/ranges from the data
- Explain what the development team SHOULD target
- Explain what they should AVOID or de-prioritize
- Keep total response under 400 words
- Start directly with the first category heading"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"Error generating AI analysis summary: {str(e)}"


def _get_ratings_batch(car_list: List[str], attributes: List[str], batch_num: int) -> Dict[str, Any]:
    """Helper function to get ratings for a batch of attributes."""
    try:
        model = GenerativeModel(GEMINI_MAIN_MODEL)

        prompt = f"""You are an automotive analyst. Based on your knowledge of user reviews, forum discussions (Team-BHP, CarWale, CarDekho, Reddit r/IndiaCars), and social media opinions for these vehicles, rate each vehicle on a scale of 1-10 for each vehicle dynamics attribute.

Vehicles to rate: {', '.join(car_list)}

Attributes to rate:
{json.dumps(attributes, indent=2)}

For each vehicle, provide ratings based on aggregated user sentiments from forums and social media. Consider:
- Team-BHP long-term owner reviews
- CarWale/CarDekho user ratings
- YouTube reviewer opinions
- Reddit/social media discussions

Return a JSON object with this exact structure:
{{
    "ratings": {{
        "Car Name 1": {{
            "Ride Quality": 7.5,
            "Handling": 8.0
        }}
    }}
}}

IMPORTANT: Return ONLY valid JSON. Rate all {len(car_list)} vehicles for all {len(attributes)} attributes. Use actual decimal values between 1.0 and 10.0."""

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        ratings_data = json.loads(response_text.strip())
        print(f"  ✓ Batch {batch_num}: Rated {len(attributes)} attributes")
        return ratings_data.get("ratings", {})

    except Exception as e:
        print(f"  ✗ Batch {batch_num} error: {str(e)}")
        return {}


def extract_vehicle_dynamics_ratings(car_list: List[str]) -> Dict[str, Any]:
    """
    Extract subjective vehicle dynamics ratings from forums/social media.
    Converts user opinions into structured ratings (0-10) for each vehicle dynamic attribute.
    Makes 3 parallel calls for efficiency.
    """
    try:
        # Split attributes into 3 batches
        all_attributes = [
            "Ride Quality", "Handling", "Steering Feel", "Braking Performance",
            "NVH (Noise/Vibration)", "Engine Performance", "Acceleration",
            "Off-road Capability", "Comfort", "Infotainment", "Value for Money"
        ]

        batch_1 = all_attributes[0:4]   # Ride Quality, Handling, Steering Feel, Braking Performance
        batch_2 = all_attributes[4:8]   # NVH, Engine Performance, Acceleration, Off-road Capability
        batch_3 = all_attributes[8:11]  # Comfort, Infotainment, Value for Money

        print(f"\n📊 Extracting ratings in 3 parallel batches...")

        # Run 3 batches in parallel using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_1 = executor.submit(_get_ratings_batch, car_list, batch_1, 1)
            future_2 = executor.submit(_get_ratings_batch, car_list, batch_2, 2)
            future_3 = executor.submit(_get_ratings_batch, car_list, batch_3, 3)

            # Get results
            ratings_1 = future_1.result()
            ratings_2 = future_2.result()
            ratings_3 = future_3.result()

        # Merge all ratings
        merged_ratings = {}
        for car in car_list:
            merged_ratings[car] = {}
            # Merge batch 1
            if car in ratings_1:
                merged_ratings[car].update(ratings_1[car])
            # Merge batch 2
            if car in ratings_2:
                merged_ratings[car].update(ratings_2[car])
            # Merge batch 3
            if car in ratings_3:
                merged_ratings[car].update(ratings_3[car])

        return {
            "attributes": all_attributes,
            "ratings": merged_ratings,
            "sources": ["Team-BHP forums", "CarWale reviews", "YouTube reviews", "Reddit r/IndiaCars"],
            "disclaimer": "Ratings derived from aggregated user opinions on automotive forums and social media"
        }

    except Exception as e:
        print(f"Error extracting vehicle dynamics ratings: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}


def generate_comparison_summary(comparison_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate feature comparison summary showing differences between cars."""
    try:
        # Get car names
        car_names = [name for name, data in comparison_data.items()
                     if isinstance(data, dict) and "error" not in data]

        if len(car_names) < 2:
            return {"features_not_in_car1": {}, "features_in_car1_only": {}}

        car1_name = car_names[0]
        car2_name = car_names[1]

        # Build condensed data for comparison
        condensed_data = {}
        for car_name, car_data in comparison_data.items():
            if isinstance(car_data, dict) and "error" not in car_data:
                condensed_data[car_name] = {}
                for key, value in car_data.items():
                    if key not in ["images", "citations", "sources"] and value:
                        if value not in ["Not Available", "Not found", "N/A", "-", ""]:
                            condensed_data[car_name][key] = str(value)[:200]

        model = GenerativeModel(GEMINI_MAIN_MODEL)

        prompt = f"""You are an automotive analyst comparing two vehicles. Analyze the specification data and identify feature differences.

Vehicle 1: {car1_name}
Vehicle 2: {car2_name}

Specification Data:
{json.dumps(condensed_data, indent=2)}

Return a JSON object with exactly this structure:
{{
    "features_not_in_car1": {{
        "Power & Torque": ["specific feature 1 with numbers if available", "feature 2"],
        "Drive Mode": ["feature descriptions"],
        "Exterior": ["feature descriptions"],
        "Capabilities": ["feature descriptions"],
        "ADAS": ["feature descriptions"],
        "Interior": ["feature descriptions"],
        "Engine": ["feature descriptions"],
        "BRAKES": ["feature descriptions"],
        "Others": ["any other notable differences"]
    }},
    "features_in_car1_only": {{
        "Exterior & Interior": ["feature descriptions"],
        "Engine": ["feature descriptions"],
        "BRAKES": ["feature descriptions"],
        "ADAS": ["feature descriptions"],
        "Others": ["any other notable differences"]
    }}
}}

RULES:
1. "features_not_in_car1" = Features that {car2_name} has but {car1_name} does NOT have
2. "features_in_car1_only" = Features that {car1_name} has but {car2_name} does NOT have
3. Include specific values/numbers when comparing (e.g., "187kW @5500 RPM (30.4% higher)")
4. Only include categories that have actual differences - omit empty categories
5. Each feature should be a concise but descriptive string
6. Return ONLY valid JSON, no markdown formatting or explanation"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean up response if wrapped in markdown
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        summary_data = json.loads(response_text.strip())
        return summary_data

    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return {"features_not_in_car1": {}, "features_in_car1_only": {}}


def save_pdf_car_specs_tool(car_name: str, specs_json: str) -> str:
    """
    Save specs extracted from an uploaded PDF for a specific car.

    Call this BEFORE scrape_cars_tool when a PDF has been uploaded and you've extracted
    car specs from it. The scraper will use these specs directly and only search for
    specs NOT found in the PDF. Citations for PDF-sourced specs will be "PDF uploaded by user".

    Args:
        car_name: Exact car name as it will be passed to scrape_cars_tool (e.g., "MG M9")
        specs_json: JSON string mapping spec field names to their extracted values.
                   Use the same spec names as the 87-spec schema where possible.
                   Example: '{"price_range": "₹35-45 Lakh", "seating_capacity": "7 Seater",
                              "performance": "174 bhp", "torque": "380 Nm"}'

    Returns:
        JSON with status and count of saved specs
    """
    try:
        specs = safe_json_parse(specs_json, fallback={})
    except Exception as e:
        return json.dumps({"status": "error", "error": f"Invalid JSON: {str(e)}"})

    if not isinstance(specs, dict):
        return json.dumps({"status": "error", "error": "specs_json must be a JSON object"})

    if not hasattr(save_pdf_car_specs_tool, 'pdf_specs'):
        save_pdf_car_specs_tool.pdf_specs = {}

    save_pdf_car_specs_tool.pdf_specs[car_name] = specs
    spec_count = len([v for v in specs.values() if v and str(v).strip() not in ("", "N/A", "Not Available")])

    return json.dumps({
        "status": "success",
        "car_name": car_name,
        "specs_saved": spec_count,
        "message": (
            f"Saved {spec_count} specs for '{car_name}' from PDF. "
            f"Now call scrape_cars_tool — only the {87 - spec_count} missing specs will be searched online. "
            f"PDF specs will have citation: 'PDF uploaded by user'."
        )
    }, indent=2)


def scrape_cars_tool(car_names: str, user_decision: Optional[str] = None, use_custom_search: bool = True) -> str:
    """
    Tool to scrape car data using Custom Search API OR Gemini's direct URL analysis with ALL 19 specifications.

    IMPORTANT FOR CODE CARS:
    If CODE CARS are detected (names with "CODE:" prefix):

    STEP 1: Call 'scrape_cars_tool' FIRST to identify the code cars.

    STEP 2: If the response status is "awaiting_code_car_specs", present the TWO options to the user.

    ---

    📚 If user says **RAG / GCS / CORPUS / VERTEX RAG / RAG CORPUS**:
    - Call 'scrape_cars_tool' with user_decision="rag"
    - System queries Vertex RAG corpus for specifications
    - Proceeds automatically after RAG query

    ---

    📄 If user uploads a PDF:
    - User must say: "compare CODE:[name] from uploaded PDF with [external car name]"
    - Read the PDF, extract all specs for the CODE car, map to the 87-spec field names
    - Call: save_pdf_car_specs_tool(car_name="CODE:PROTO1", specs_json='{...}')
    - Then call: scrape_cars_tool(car_names="CODE:PROTO1, ExternalCar") — no user_decision needed
    - CODE car specs will be pre-filled from PDF; external cars sourced normally via web search

    ---

    Args:
        car_names: Comma-separated list of car names (minimum 1, maximum 10)
                   Example: "Mahindra Thar" or "CODE:PROTO1, Mahindra Thar, Maruti Jimny"
        user_decision: User's choice for code cars: 'rag'
        use_custom_search: If True (default), use Custom Search API; if False, use Gemini URL parsing

    Returns:
        JSON string with comparison results and chart file path
    """
    car_list = [c.strip() for c in car_names.split(",")]

    # Validation
    if len(car_list) < 1:
        return json.dumps({
            "status": "error",
            "error": f"Please provide at least 1 car. You provided {len(car_list)}."
        })

    if len(car_list) > 10:
        return json.dumps({
            "status": "error",
            "error": f"Maximum 10 cars can be compared at once. You provided {len(car_list)}."
        })

    # Check for code cars
    code_cars = [car for car in car_list if is_code_car(car)]

    if code_cars:
        # Check if specs were already collected (RAG) or pre-filled via PDF upload
        collected_specs = getattr(add_code_car_specs_tool, 'collected_specs', {})
        pdf_specs_available = getattr(save_pdf_car_specs_tool, 'pdf_specs', {})
        uncollected_code_cars = [
            car for car in code_cars
            if car not in collected_specs and car not in pdf_specs_available
        ]

        if uncollected_code_cars and not user_decision:
            example_car = uncollected_code_cars[0]
            return json.dumps({
                "status": "awaiting_code_car_specs",
                "message": (
                    f"I detected {len(uncollected_code_cars)} internal CODE CAR(s): {', '.join(uncollected_code_cars)}\n\n"
                    f"Please choose how to provide the specifications:\n\n"
                    f"**Option 1 — Query RAG Corpus**\n"
                    f"Reply with: `rag`\n"
                    f"Specifications will be fetched automatically from the Vertex RAG knowledge base.\n\n"
                    f"**Option 2 — Upload PDF**\n"
                    f"1. Attach the specification PDF to your next message.\n"
                    f"2. Then say exactly:\n"
                    f"   `compare {example_car} from uploaded PDF with <external car name>`\n"
                    f"   (e.g. `compare {example_car} from uploaded PDF with Hyundai Creta`)\n"
                    f"The internal car specs will be extracted from the PDF and pre-filled; "
                    f"external cars will be sourced normally via web search."
                ),
                "code_cars_detected": code_cars,
                "code_cars_needing_specs": uncollected_code_cars,
                "awaiting_decision": True
            }, indent=2)

        # Handle user decision
        if user_decision:
            decision = user_decision.lower().strip()

            if decision in ['rag', 'gcs', 'corpus', 'vertex rag', 'rag corpus']:
                # User wants to query RAG corpus
                print(f"\n→ User chose RAG corpus query for code car(s): {', '.join(uncollected_code_cars)}")

                project = os.getenv("GOOGLE_CLOUD_PROJECT")
                location = os.getenv("GOOGLE_CLOUD_LOCATION")
                rag_corpus_id = os.getenv("RAG_CORPUS_ID")

                rag_corpus_path = f"projects/{project}/locations/{location}/ragCorpora/{rag_corpus_id}"

                for car in uncollected_code_cars:
                    rag_specs = query_rag_for_code_car_specs(car, rag_corpus_path)

                    if "error" not in rag_specs:
                        if not hasattr(add_code_car_specs_tool, 'collected_specs'):
                            add_code_car_specs_tool.collected_specs = {}
                        add_code_car_specs_tool.collected_specs[car] = rag_specs
                        print(f" Retrieved specs from RAG for '{car}'")
                    else:
                        print(f" RAG query failed for '{car}', will use blank specs")
                        blank_specs = create_blank_specs_for_code_car(car)
                        if not hasattr(add_code_car_specs_tool, 'collected_specs'):
                            add_code_car_specs_tool.collected_specs = {}
                        add_code_car_specs_tool.collected_specs[car] = blank_specs

            else:
                return json.dumps({
                    "status": "error",
                    "error": (
                        f"Invalid decision: '{user_decision}'. "
                        f"Please reply with 'rag' to query the RAG corpus, "
                        f"or upload a PDF and say "
                        f"'compare {code_cars[0]} from uploaded PDF with <external car name>'."
                    )
                })

    start_time = time.time()

    print(f"\n STEP 1: {'Using Custom Search API' if use_custom_search else 'Using Gemini URL Parsing'} to fetch car data...")

    # Get collected manual specs if any
    manual_specs_dict = getattr(add_code_car_specs_tool, 'collected_specs', {})

    # Process all cars with manual specs where available
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    folder_name = f"car_comparison_{timestamp}"

    results = {
        "cars_compared": car_list,
        "total_cars": len(car_list),
        "comparison_data": {},
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gcs_folder": folder_name,
        "scraping_method": "Custom Search API" if use_custom_search else "Gemini URL Parsing"
    }

    print(f"\n{'#'*60}")
    print(f"STARTING CAR COMPARISON ANALYSIS")
    print(f"{'#'*60}")
    print(f"Cars to Compare ({len(car_list)}): {', '.join(car_list)}")
    if manual_specs_dict:
        blank_cars = [car for car, specs in manual_specs_dict.items() if specs.get('left_blank')]
        manual_entry_cars = [car for car, specs in manual_specs_dict.items() if not specs.get('left_blank')]
        if blank_cars:
            print(f"Cars left blank: {', '.join(blank_cars)}")
        if manual_entry_cars:
            print(f"Cars with manual specs: {', '.join(manual_entry_cars)}")
    print(f"GCS Folder: {folder_name}")
    print(f"Method: {'Custom Search API' if use_custom_search else 'Gemini URL Parsing (Legacy)'}")
    print(f"{'#'*60}\n")

    # --- Parallel car processing ---

    def _process_single_car(car: str) -> tuple[str, dict]:
        """Scrape specs + sales for one car. Thread-safe: scrape_car_data() calls
        asyncio.run() internally so each thread owns its own event loop."""
        manual_specs = manual_specs_dict.get(car)
        # Check if PDF specs were saved for this car
        pdf_specs_store = getattr(save_pdf_car_specs_tool, 'pdf_specs', {})
        pdf_specs = pdf_specs_store.get(car)

        if is_code_car(car):
            # CODE: internal cars must NEVER be web-scraped
            if manual_specs and not manual_specs.get('left_blank'):
                # RAG/manually-collected specs — use directly
                print(f"[{car}] Using RAG/manual specs (no web search)")
                car_data = manual_specs
            elif pdf_specs:
                # PDF-uploaded specs — merge onto blank base
                print(f"[{car}] Using PDF-uploaded specs (no web search)")
                car_data = create_blank_specs_for_code_car(car)
                car_data['left_blank'] = False
                car_data['manual_entry'] = False
                car_data['source_urls'] = ["PDF uploaded by user"]
                car_data['images'] = {}
                for field, value in pdf_specs.items():
                    # Skip citation-like keys the agent may have included
                    if field.endswith("_citation"):
                        continue
                    # Flatten dicts/lists to a plain string
                    if isinstance(value, dict):
                        value = value.get("value") or value.get("text") or str(value)
                    elif isinstance(value, list):
                        value = ", ".join(str(v) for v in value)
                    if value and str(value).strip() not in ("", "N/A", "Not Available"):
                        car_data[field] = str(value).strip()
                        car_data[f"{field}_citation"] = {
                            "source_url": "PDF uploaded by user",
                            "citation_text": "Extracted from PDF uploaded by user"
                        }
            else:
                # No specs collected yet — use blank rather than web-scraping
                print(f"[{car}] No specs available for CODE car, using blank")
                car_data = create_blank_specs_for_code_car(car)
        elif manual_specs and manual_specs.get('left_blank'):
            print(f"[{car}] Using blank specifications")
            car_data = manual_specs
        else:
            car_data = scrape_car_data(car, manual_specs, use_custom_search=use_custom_search, pdf_specs=pdf_specs)

        # Sales data extraction commented out
        # if not car_data.get('is_code_car'):
        #     print(f"[{car}] Fetching sales data...")
        #     if use_custom_search:
        #         sales_query = f"{car} monthly sales units"
        #
        #         def _run_sales_async() -> list:
        #             loop = asyncio.new_event_loop()
        #             asyncio.set_event_loop(loop)
        #             try:
        #                 return loop.run_until_complete(
        #                     call_custom_search_parallel(
        #                         {"monthly_sales": sales_query}, num_results=5, max_concurrent=1
        #                     )
        #                 ).get("monthly_sales", [])
        #             finally:
        #                 loop.close()
        #
        #         try:
        #             with concurrent.futures.ThreadPoolExecutor(max_workers=1) as sex:
        #                 sales_results = sex.submit(_run_sales_async).result(timeout=60)
        #         except Exception as e:
        #             print(f"[{car}] Sales fetch error: {e}")
        #             sales_results = []
        #
        #         if sales_results:
        #             ext = extract_spec_from_search_results(car, "monthly_sales", sales_results)
        #             car_data["monthly_sales"] = ext["value"]
        #             car_data["monthly_sales_citation"] = {
        #                 "source_url": ext["source_url"],
        #                 "citation_text": ext["citation"],
        #             }
        #             if ext["source_url"] not in car_data.get("source_urls", []):
        #                 car_data["source_urls"].append(ext["source_url"])
        #         else:
        #             car_data["monthly_sales"] = "Not Available"
        #             car_data["monthly_sales_citation"] = {
        #                 "source_url": "N/A",
        #                 "citation_text": "No sales data found",
        #             }
        #     else:
        #         sales_data = scrape_sales_data(car)
        #         for key, value in sales_data.items():
        #             if key not in ('car_name', 'sales_source_urls'):
        #                 car_data[key] = value
        #         if sales_data.get('sales_source_urls'):
        #             car_data.setdefault('source_urls', []).extend(sales_data['sales_source_urls'])
        # else:
        #     print(f"[{car}] Skipping sales data (code car)")
        #     car_data["monthly_sales"] = "Not Available"
        #     car_data["monthly_sales_citation"] = {
        #         "source_url": "N/A",
        #         "citation_text": "Code car - sales data not applicable",
        #     }

        # Count actually found specs (exclude all empty/not-found variations)
        empty_values = ("Not Available", "N/A", "Not found", "not found", None, "", "—", "-", "None")
        populated = sum(
            1 for f in CAR_SPECS
            if car_data.get(f) not in empty_values and str(car_data.get(f, "")).strip() not in empty_values
        )
        total = len(CAR_SPECS)
        percentage = (populated / total * 100) if total > 0 else 0
        print(f"[{car}] Done: {populated}/{total} specs found ({percentage:.1f}%)")
        return car, car_data

    # Sequential processing to avoid rate limits
    print(f"\nProcessing {len(car_list)} cars sequentially")
    for car in car_list:
        try:
            car_key, car_data = _process_single_car(car)
            results["comparison_data"][car_key] = car_data
        except Exception as exc:
            print(f"[{car}] FAILED: {exc}")
            results["comparison_data"][car] = {"car_name": car, "error": str(exc)}

    # Clear collected specs and PDF specs for next comparison
    if hasattr(add_code_car_specs_tool, 'collected_specs'):
        add_code_car_specs_tool.collected_specs = {}
    if hasattr(save_pdf_car_specs_tool, 'pdf_specs'):
        save_pdf_car_specs_tool.pdf_specs = {}

    # Print data quality summary
    print("\n" + "=" * 60)
    print("DATA EXTRACTION SUMMARY")
    print("=" * 60)
    empty_values = ("Not Available", "N/A", "Not found", "not found", None, "", "—", "-", "None")
    for car_name, car_data in results["comparison_data"].items():
        if "error" not in car_data:
            found = sum(
                1 for f in CAR_SPECS
                if car_data.get(f) not in empty_values and str(car_data.get(f, "")).strip() not in empty_values
            )
            total = len(CAR_SPECS)
            percentage = (found / total * 100) if total > 0 else 0
            print(f"  {car_name}: {found}/{total} specs ({percentage:.1f}%)")
    print("=" * 60)

    print("\n STEP 2: Generating AI-powered comparison summary...")
    summary_data = generate_comparison_summary(results["comparison_data"])
    results["summary_data"] = summary_data

    print("\n STEP 3: Extracting detailed reviews from automotive publications...")
    detailed_reviews = extract_detailed_reviews(car_list, SEARCH_SITES)
    results["detailed_reviews"] = detailed_reviews

    print("\n STEP 4: Extracting comparative graphs data with overall ratings...")
    comparative_graphs = extract_comparative_graphs_data(car_list, results["comparison_data"], detailed_reviews)
    results["comparative_graphs"] = comparative_graphs

    print("\n STEP 4.5: Extracting vehicle dynamics ratings from forums/social media...")
    dynamics_ratings = extract_vehicle_dynamics_ratings(car_list)
    results["dynamics_ratings"] = dynamics_ratings

    print("\n STEP 4.6: Generating AI-powered analysis summary...")
    ai_analysis_summary = generate_ai_analysis_summary(results["comparison_data"])
    results["ai_analysis_summary"] = ai_analysis_summary

    print("\n STEP 5: Creating enhanced interactive HTML report...")
    html_content = create_comparison_chart_html(
        results["comparison_data"],
        "",
        comparative_graphs,
        detailed_reviews,
        summary_data,
        ai_analysis_summary,
        dynamics_ratings
    )

    # Upload HTML directly to GCS (viewable in browser)
    html_gcs_uri, html_signed_url = save_chart_to_gcs(html_content, folder_name)
    results["chart_gcs_uri"] = html_gcs_uri
    results["chart_signed_url"] = html_signed_url

    # Upload JSON directly to GCS
    json_gcs_uri, json_signed_url = save_json_to_gcs(results, folder_name)
    results["json_gcs_uri"] = json_gcs_uri
    results["json_signed_url"] = json_signed_url

    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"\n{'='*80}")
    print(f"COMPARISON COMPLETE!")
    print(f"{'='*80}")
    print(f"\nBROWSER-VIEWABLE REPORT:")
    print(f"   Click this URL to open in your browser:")
    print(f"   {html_signed_url}")
    print(f"\n JSON DATA:")
    print(f"   Click this URL to download:")
    print(f"   {json_signed_url}")
    print(f"\n GCS Folder: {folder_name}")
    print(f"⏱  Time: {elapsed_time:.2f} seconds")
    print(f"Method: {'Custom Search API' if use_custom_search else 'Gemini URL Parsing'}")
    print(f" URLs expire in: {SIGNED_URL_EXPIRATION_HOURS} hours")
    print(f"{'='*80}\n")

    blank_cars = [car for car, data in results["comparison_data"].items() if data.get('left_blank')]
    manual_cars = [car for car, data in results["comparison_data"].items()
                   if data.get('manual_entry') and not data.get('left_blank')]

    response = {
        "status": "success",
        "cars_compared": car_list,
        "html_report_url": html_signed_url,
        "elapsed_time": f"{elapsed_time:.2f} seconds",
    }
    if blank_cars:
        response["code_cars_left_blank"] = blank_cars
    if manual_cars:
        response["code_cars_with_manual_specs"] = manual_cars

    return json.dumps(response, indent=2)


root_agent = Agent(
    name="Vehicle_Development_AI_Agent",
    model=GEMINI_MAIN_MODEL,
    description="AI agent for vehicle development and engineering analysis with 87 specs, 15 visual graphs, and detailed reviews using Custom Search API. Supports single car analysis or multi-car comparison. Handles PDFs, prototypes, and market vehicles.",

    instruction="""You are a car benchmarking specialist. You analyze and compare vehicles using 87 specifications with comprehensive visual analytics. You can analyze a single car or compare multiple cars (up to 10).

## IMPORTANT: PDF HANDLING

When a PDF is attached to the message, YOU CAN READ IT DIRECTLY — Gemini processes it natively.
Determine what the user wants from the PDF based on their query:

**PDF Mode A — Summarize:**
- Query: "summarize this", "what is this document about", "give me a summary"
- Action: Read the PDF, produce a concise summary (topic, key points, data, conclusions)
- Do NOT call any tool. Return summary as text.

**PDF Mode B — Extract Car Specs:**
- Query: "extract specs", "what are the specs in this", "get car details from this pdf"
- Action: Read the PDF, extract all car names and their specifications
- Return a structured list of cars with their key specs (price, power, mileage, features, etc.)
- Do NOT call scrape_cars_tool. Return specs found in the PDF.

**PDF Mode C — Compare (PDF cars + optional extra cars):**
- Query: "compare", "benchmark", "compare these cars with Thar and Swift"
- Action:
  1. Read the PDF — extract all car model names AND all specs you can find for the PDF car(s)
  2. For EACH car found in the PDF that has extractable specs:
     - Map the specs to the 87-spec field names where possible (price_range, mileage, performance, torque, seating_capacity, etc.)
     - Call: `save_pdf_car_specs_tool(car_name="MG M9", specs_json='{"price_range": "...", "performance": "..."}')`
  3. Merge PDF car names with any additional car names from user's text query. Deduplicate. Max 10.
  4. Call: `scrape_cars_tool(car_names="MG M9, Mahindra Thar, Hyundai Creta")`
     - The scraper will automatically skip PDF-filled specs for the PDF car and only search online for missing ones
     - PDF-sourced specs will show citation: "PDF uploaded by user"
  5. Return the HTML report URL

**IMPORTANT for PDF Mode C spec mapping — use these exact field names where applicable:**
price_range, mileage, user_rating, seating_capacity, performance, torque, transmission, acceleration,
braking, brakes, vehicle_safety_features, steering, ride_quality, nvh, interior, climate_control,
infotainment_screen, apple_carplay, sunroof, boot_space, wheelbase, parking, off_road, lighting

**Default (no explicit instruction):**
- If the user just uploads a PDF without a clear mode, ask:
  "Would you like me to: (1) Summarize the document, (2) Extract car specs from it, or (3) Compare the cars in it (optionally with additional cars)?"

## CORE CAPABILITIES

**1. Market Cars (Public Vehicles)**
- Call `scrape_cars_tool(car_names="Car1, Car2, Car3")`
- Fetches 87 specs via Custom Search API (80-90% accuracy)
- Returns browser-viewable HTML report with interactive charts

**2. Code Cars (Prototypes/Internal)**
- Detected by: "CODE:" prefix
- Two options for specs:
  a) RAG: Set `user_decision="rag"` to query Vertex corpus automatically
  b) PDF: User uploads PDF and says "compare CODE:[name] from uploaded PDF with [external car]"
     - Read the PDF, extract CODE car specs, call `save_pdf_car_specs_tool(car_name="CODE:X", specs_json='{...}')`
     - Then call `scrape_cars_tool(car_names="CODE:X, ExternalCar")` — no user_decision needed
     - Internal car specs pre-filled from PDF; external cars sourced via web search

**PDF Mode D — Internal CODE Car from PDF (new):**
- Triggered when user uploads PDF and says "compare CODE:[name] from uploaded PDF with [external car]"
- Steps:
  1. Read the PDF — find all specs for the CODE car inside it
  2. Map specs to the 87-spec field names (price_range, mileage, performance, torque, etc.)
  3. Call: `save_pdf_car_specs_tool(car_name="CODE:PROTO1", specs_json='{...}')`
  4. Call: `scrape_cars_tool(car_names="CODE:PROTO1, ExternalCar1, ExternalCar2")`
  5. Return the HTML report URL

## HANDLING TOOL RESPONSE STATUSES

**When scrape_cars_tool returns a JSON response, check the "status" field:**

1. **"status": "awaiting_code_car_specs"**
   - Meaning: CODE car detected, need user decision
   - Action: Display the "message" field to user and wait for their response
   - Next: User will reply 'rag' OR upload a PDF and say "compare CODE:[name] from uploaded PDF with [external car]"

2. **"status": "success"**
   - Meaning: Comparison complete
   - Action: Display the HTML report URL


**CRITICAL: When you get "awaiting_code_car_specs", you MUST:**
- Show the message to user
- Wait for user response
- Then call the appropriate tool based on their answer
- Do NOT proceed to generate report until specs are collected

## WORKFLOW EXAMPLES

**Standard comparison (no PDF):**
1. User: "Compare Thar and Swift"
2. Call: `scrape_cars_tool(car_names="Mahindra Thar, Maruti Swift")`
3. Present HTML report URL

**PDF summary:**
1. User: "Summarize this PDF" + uploads PDF
2. Read PDF → return summary text

**PDF spec extraction:**
1. User: "Extract car specs from this" + uploads PDF
2. Read PDF → return structured specs for each car found

**PDF comparison with extra cars:**
1. User: "Compare the cars in this with Mahindra Thar" + uploads PDF
2. Read PDF → extract car names AND specs for each PDF car
   e.g. MG M9: price ₹38 Lakh, 174 bhp, 7 Seater, 2.0L Turbo
3. Call: `save_pdf_car_specs_tool(car_name="MG M9", specs_json='{"price_range":"₹38 Lakh","performance":"174 bhp","seating_capacity":"7 Seater","torque":"380 Nm"}')`
4. Merge car names: "MG M9, Mahindra Thar"
5. Call: `scrape_cars_tool(car_names="MG M9, Mahindra Thar")`
   → MG M9: PDF specs pre-filled, only missing specs searched; citation = "PDF uploaded by user"
   → Mahindra Thar: fully scraped as normal
6. Present HTML report URL

**Code Car via RAG:**
1. User: "Compare CODE:PROTO1 with Thar"
2. Call: `scrape_cars_tool(car_names="CODE:PROTO1, Mahindra Thar")`
   → Returns: `"status": "awaiting_code_car_specs"` with 2-option message
3. Show the message to user and wait for their decision
4. User says: "rag"
5. Call: `scrape_cars_tool(car_names="CODE:PROTO1, Mahindra Thar", user_decision="rag")`
   → RAG corpus queried automatically for CODE:PROTO1 specs
6. Present HTML report URL

**Code Car via PDF upload:**
1. User: "Compare CODE:PROTO1 with Thar"
2. Call: `scrape_cars_tool(car_names="CODE:PROTO1, Mahindra Thar")`
   → Returns: `"status": "awaiting_code_car_specs"` with 2-option message
3. Show the message to user and wait for their decision
4. User attaches PDF and says: "compare CODE:PROTO1 from uploaded PDF with Mahindra Thar"
5. Read the PDF → extract CODE:PROTO1 specs → map to 87-spec field names
6. Call: `save_pdf_car_specs_tool(car_name="CODE:PROTO1", specs_json='{...}')`
7. Call: `scrape_cars_tool(car_names="CODE:PROTO1, Mahindra Thar")`
   → CODE:PROTO1: pre-filled from PDF; citation = "PDF uploaded by user"
   → Mahindra Thar: fully scraped as normal
8. Present HTML report URL

## 87 SPECIFICATIONS

**Core (19):** Price, Mileage, Rating, Seating, Braking, Steering, Climate, Transmission, Safety, Lighting, Interior, Sales
**Performance (25):** Engine Power, Torque, Acceleration, Manual/Auto Performance, Pedal Feel, Turbo Noise, Crawl, City/Highway Performance
**Handling (15):** Ride Quality, NVH, Stability, Cornering, Turning Radius, Bumps, Shocks, Potholes
**Features (28):** Infotainment, Touchscreen, CarPlay, Digital Display, Sunroof, Parking, Visibility, Boot Space, Wheelbase, Lights, Windows, Mirrors

## OUTPUT FORMAT

**IMPORTANT: After comparison, return ONLY these 3 items (no summary, no additional text):**

```
✓ Compared: [Car1, Car2, Car3]
⏱ Time: Xs

🔗 VIEW REPORT
[HTML_REPORT_URL]
```

**DO NOT include the summary in your response** - it's already in the HTML report.

For follow-up questions (CODE car handling), keep responses brief and focused.""",

    tools=[
        scrape_cars_tool,
        save_pdf_car_specs_tool,
        add_code_car_specs_tool,
        add_code_car_specs_bulk_tool,
    ]
)


def run_car_comparison(car_names: List[str], use_custom_search: bool = True):
    """
    Run enhanced car comparison with 98 specifications for any cars.
    Results are uploaded to GCS and viewable in browser via signed URLs.

    Args:
        car_names: List of car names to analyze/compare
        use_custom_search: If True (default), use Custom Search API
    """
    if len(car_names) < 1:
        print(f"Error: Need at least 1 car to analyze, got {len(car_names)}")
        return

    if len(car_names) > 10:
        print(f" Error: Maximum 10 cars can be compared, got {len(car_names)}")
        return

    # Check for code cars and inform user
    code_cars = [car for car in car_names if is_code_car(car)]
    if code_cars:
        print(f"\n⚠️  CODE CARS DETECTED: {', '.join(code_cars)}")
        print(f" Tip: You'll be asked if you want to manually specify their specs\n")

    car_names_str = ", ".join(car_names)
    result = scrape_cars_tool(car_names_str, use_custom_search=use_custom_search)
    result_data = safe_json_parse(result, fallback={})

    if result_data.get("status") == "success":
        print(f"\n{'='*80}")
        print(" CAR COMPARISON REPORT IS READY!")
        print(f"{'='*80}")
        print(f"\n Cars Compared:")
        for car in result_data['cars_compared']:
            print(f"   • {car}")

        if result_data.get('code_cars_with_manual_specs'):
            print(f"\n📝 Code Cars (Manual Specs):")
            for car in result_data['code_cars_with_manual_specs']:
                print(f"   • {car}")

        print(f"\n{'─'*80}")
        print(" CLICK THESE URLS TO VIEW IN BROWSER:")
        print(f"{'─'*80}")

        print(f"\nInteractive HTML Report:")
        print(f"   {result_data['html_report_url']}")
        print(f"   ↳ Full comparison table with charts and analytics")

        print(f"\n Raw JSON Data:")
        print(f"   {result_data['json_data_url']}")
        print(f"   ↳ All comparison data in JSON format")

        print(f"\n{'─'*80}")
        print(f" URLs expire in: {result_data['signed_url_expiration_hours']} hours")
        print(f" Method: {result_data.get('scraping_method', 'Unknown')}")
        print(f"  Completed in: {result_data['elapsed_time']}")
        print(f" GCS Folder: {result_data['gcs_folder']}")
        print(f"{'='*80}\n")

        print("TIP: Right-click the URL and 'Open in new tab' to view the report")

    return result_data
