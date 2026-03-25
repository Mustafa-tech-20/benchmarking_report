import os
import json
import asyncio
import time
import concurrent.futures
from typing import Dict, Any, List, Optional

from google.adk.agents import Agent
from shared_utils import safe_json_parse, clean_json_response
from vertexai.generative_models import GenerativeModel

from benchmarking_agent.config import SIGNED_URL_EXPIRATION_HOURS, GOOGLE_API_KEY
from product_planning_agent.config import GEMINI_MAIN_MODEL
from benchmarking_agent.utils.helpers import is_code_car
from benchmarking_agent.core.scraper import (
    scrape_car_data,
    call_custom_search_parallel,
    extract_spec_from_search_results,
)
from product_planning_agent.core.interleaved_processor import scrape_cars_parallel_sync
# from benchmarking_agent.extraction.sales import scrape_sales_data
from benchmarking_agent.utils.gcs import save_chart_to_gcs, save_json_to_gcs
from benchmarking_agent.core.internal_car_tools import (
    add_code_car_specs_tool,
    query_rag_for_code_car_specs,
    create_blank_specs_for_code_car,
    add_code_car_specs_bulk_tool,
    CAR_SPECS,
)
from product_planning_agent.reports.html_generator import create_comparison_chart_html
from product_planning_agent.extraction.youtube_proscons import get_multiple_cars_proscons
from product_planning_agent.reports.youtube_proscons_html import save_youtube_proscons_html
from product_planning_agent.reports.technical_specs_html import save_technical_specs_html


def generate_comparison_summary(comparison_data: Dict[str, Any]) -> str:
    """Generate industry-standard benchmarks and pointers for product team reference."""
    try:
        # Extract only key specs (no citations) to reduce token count
        key_specs = [
            "price_range", "mileage", "user_rating", "seating_capacity",
            "performance", "torque", "transmission", "acceleration",
            "vehicle_safety_features", "braking", "steering",
            "ride_quality", "nvh", "off_road", "interior",
            "infotainment_screen", "boot_space", "sunroof"
        ]

        # Build condensed data
        condensed_data = {}
        for car_name, car_data in comparison_data.items():
            if isinstance(car_data, dict) and "error" not in car_data:
                condensed_data[car_name] = {"car_name": car_data.get("car_name", car_name)}
                for spec in key_specs:
                    value = car_data.get(spec, "")
                    if value and value not in ["Not Available", "Not found", "N/A"]:
                        condensed_data[car_name][spec] = str(value)[:100]

        model = GenerativeModel(GEMINI_MAIN_MODEL)

        prompt = f"""You are an automotive industry analyst providing strategic guidance for a product development team.

Based on this competitor analysis data, provide focused recommendations for each category. Each category should be a 3-5 line paragraph explaining what to focus on and what to avoid.

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
- Explain what the product team SHOULD prioritize
- Explain what they should AVOID or de-prioritize
- Keep total response under 400 words
- Start directly with the first category heading"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"Error generating summary: {str(e)}"


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
                   Can be single car for individual analysis or multiple for comparison
        user_decision: User's choice for code cars: 'rag'
        use_custom_search: If True (default), use Custom Search API; if False, use Gemini URL parsing

    Returns:
        JSON string with comparison results and chart file path
    """
    car_list = [c.strip() for c in car_names.split(",")]

    # Validation
    if len(car_list) < 1 or not car_list[0]:
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

    # --- Interleaved Parallel Car Processing ---
    # Separate code cars from web-scrape cars
    pdf_specs_store = getattr(save_pdf_car_specs_tool, 'pdf_specs', {})
    code_cars_list = []
    web_scrape_cars = []

    for car in car_list:
        manual_specs = manual_specs_dict.get(car)
        pdf_specs = pdf_specs_store.get(car)

        if is_code_car(car):
            # CODE: internal cars must NEVER be web-scraped
            if manual_specs and not manual_specs.get('left_blank'):
                print(f"[{car}] Using RAG/manual specs (no web search)")
                car_data = manual_specs
            elif pdf_specs:
                print(f"[{car}] Using PDF-uploaded specs (no web search)")
                car_data = create_blank_specs_for_code_car(car)
                car_data['left_blank'] = False
                car_data['manual_entry'] = False
                car_data['source_urls'] = ["PDF uploaded by user"]
                car_data['images'] = {}
                for field, value in pdf_specs.items():
                    if field.endswith("_citation"):
                        continue
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
                print(f"[{car}] No specs available for CODE car, using blank")
                car_data = create_blank_specs_for_code_car(car)
            car_data['variant_walk'] = None
            car_data['generation_comparison'] = None
            results["comparison_data"][car] = car_data
            code_cars_list.append(car)
        elif manual_specs and manual_specs.get('left_blank'):
            print(f"[{car}] Using blank specifications")
            manual_specs['variant_walk'] = None
            manual_specs['generation_comparison'] = None
            results["comparison_data"][car] = manual_specs
        else:
            # Parse car name into brand/model for interleaved processor
            parts = car.split(" ", 1)
            brand = parts[0] if parts else car
            model = parts[1] if len(parts) > 1 else ""
            web_scrape_cars.append({"brand": brand, "model": model, "original_name": car})

    # Use interleaved processor for web-scrape cars (TRUE PARALLEL PIPELINES)
    if web_scrape_cars:
        print(f"\nProcessing {len(web_scrape_cars)} cars with INTERLEAVED PARALLEL PROCESSING...")
        try:
            parallel_results = scrape_cars_parallel_sync(web_scrape_cars)

            # Map results back to original car names
            for car_info in web_scrape_cars:
                car_id = f"{car_info['brand'].lower().replace(' ', '_')}_{car_info['model'].lower().replace(' ', '_')}"
                original_name = car_info['original_name']

                if car_id in parallel_results.get("results", {}):
                    car_data = parallel_results["results"][car_id]
                    car_data['variant_walk'] = None
                    car_data['generation_comparison'] = None
                    results["comparison_data"][original_name] = car_data

                    # Print summary
                    empty_values = ("Not Available", "N/A", "Not found", "not found", None, "", "—", "-", "None")
                    populated = sum(
                        1 for f in CAR_SPECS
                        if car_data.get(f) not in empty_values and str(car_data.get(f, "")).strip() not in empty_values
                    )
                    total = len(CAR_SPECS)
                    percentage = (populated / total * 100) if total > 0 else 0
                    print(f"[{original_name}] Done: {populated}/{total} specs found ({percentage:.1f}%)")
                else:
                    print(f"[{original_name}] FAILED: No results from parallel processor")
                    results["comparison_data"][original_name] = {"car_name": original_name, "error": "Processing failed"}

        except Exception as exc:
            print(f"Interleaved processor failed: {exc}")
            # Fallback to sequential processing
            for car_info in web_scrape_cars:
                original_name = car_info['original_name']
                try:
                    car_data = scrape_car_data(original_name, manual_specs_dict.get(original_name),
                                              use_custom_search=use_custom_search,
                                              pdf_specs=pdf_specs_store.get(original_name))
                    car_data['variant_walk'] = None
                    car_data['generation_comparison'] = None
                    results["comparison_data"][original_name] = car_data
                except Exception as e:
                    print(f"[{original_name}] FAILED: {e}")
                    results["comparison_data"][original_name] = {"car_name": original_name, "error": str(e)}

    # --- Parallel variant walk and generation comparison extraction ---
    from product_planning_agent.extraction.variant_walk import extract_variant_walk
    from product_planning_agent.extraction.generation_comparison import extract_old_generation_data

    def _fetch_variant_and_generation(car_name: str):
        """Fetch both variant walk and generation comparison data in parallel."""
        car_data = results["comparison_data"].get(car_name, {})
        if car_data.get('is_code_car') or "error" in car_data:
            return car_name, None, None

        print(f"[{car_name}] Extracting variant walk and generation comparison in parallel...")

        def extract_variant():
            return extract_variant_walk(car_name)

        def extract_generation():
            return extract_old_generation_data(car_name, {})

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                variant_future = executor.submit(extract_variant)
                gen_future = executor.submit(extract_generation)

                variant_data = variant_future.result()
                gen_data = gen_future.result()

            # Log variant results
            if variant_data and variant_data.get('variants'):
                print(f"[{car_name}] ✓ Extracted {len(variant_data.get('variants', {}))} variants")
            else:
                print(f"[{car_name}] ✗ Variant walk: No variants found")
                variant_data = None

            # Log generation comparison results
            if gen_data and gen_data.get('has_old_generation'):
                old_gen_name = gen_data.get('old_generation', {}).get('name', 'previous generation')
                print(f"[{car_name}] ✓ Old vs new comparison (vs {old_gen_name})")
            else:
                if gen_data and gen_data.get('error'):
                    print(f"[{car_name}] ✗ Generation comparison error: {gen_data.get('error')}")
                else:
                    print(f"[{car_name}] ℹ No previous generation for comparison")
                gen_data = None

            return car_name, variant_data, gen_data

        except Exception as err:
            print(f"[{car_name}] Error during extraction: {err}")
            return car_name, None, None

    non_code_cars = [c for c in results["comparison_data"] if not results["comparison_data"][c].get('is_code_car') and "error" not in results["comparison_data"][c]]
    if non_code_cars:
        print(f"\nFetching variant walk and generation comparison for {len(non_code_cars)} cars in parallel...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(non_code_cars)) as vex:
            for car_name, variant_data, gen_data in vex.map(_fetch_variant_and_generation, non_code_cars):
                if car_name in results["comparison_data"]:
                    results["comparison_data"][car_name]['variant_walk'] = variant_data
                    results["comparison_data"][car_name]['generation_comparison'] = gen_data

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

    print("\n STEP 2 & 2.5: Running in parallel - Comparison summary + YouTube pros/cons...")

    # Get only non-code cars for YouTube analysis
    youtube_car_names = [
        car for car in car_list
        if not results["comparison_data"].get(car, {}).get('is_code_car')
    ]

    # Run both steps in parallel using ThreadPoolExecutor for CPU-bound tasks
    def run_summary():
        return generate_comparison_summary(results["comparison_data"])

    def run_youtube():
        if youtube_car_names:
            try:
                data = get_multiple_cars_proscons(youtube_car_names, num_channels=2)
                print(f"✓ YouTube pros/cons extracted for {len(data)} cars from 2 channels each")
                return data
            except Exception as e:
                print(f"✗ YouTube pros/cons extraction failed: {e}")
                print("  Continuing without YouTube data...")
                return None
        else:
            print("ℹ Only code cars detected - skipping YouTube analysis")
            return None

    # Execute both in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        summary_future = executor.submit(run_summary)
        youtube_future = executor.submit(run_youtube)

        # Wait for both to complete
        summary = summary_future.result()
        proscons_data = youtube_future.result()

    results["summary"] = summary
    if proscons_data:
        results["youtube_proscons"] = proscons_data

    print("\n STEP 3: Creating enhanced interactive HTML report...")
    html_content = create_comparison_chart_html(results["comparison_data"], summary, proscons_data)

    # Upload HTML and JSON to GCS in parallel
    print("  Uploading HTML and JSON to GCS in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_html = executor.submit(save_chart_to_gcs, html_content, folder_name)
        future_json = executor.submit(save_json_to_gcs, results, folder_name)

        html_gcs_uri, html_signed_url = future_html.result()
        json_gcs_uri, json_signed_url = future_json.result()

    results["chart_gcs_uri"] = html_gcs_uri
    results["chart_signed_url"] = html_signed_url
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


def generate_technical_specs_report_tool(car_names: str) -> str:
    """
    Generate a technical specifications report for specified cars.

    This tool creates a professional technical specifications report with detailed
    comparisons across engine specs, performance, features, safety, and pricing.

    Args:
        car_names: Comma-separated list of car names (e.g., "Hyundai Creta, Kia Seltos")

    Returns:
        JSON string with report file path and summary

    Example:
        generate_technical_specs_report_tool("Hyundai Creta, Kia Seltos, Maruti Grand Vitara")
    """
    import time
    from datetime import datetime

    start_time = time.time()

    # Parse car names
    car_list = [c.strip() for c in car_names.split(",")]

    if not car_list:
        return json.dumps({
            "status": "error",
            "error": "Please provide at least one car name"
        })

    if len(car_list) > 10:
        return json.dumps({
            "status": "error",
            "error": f"Maximum 10 cars can be analyzed at once. You provided {len(car_list)}."
        })

    print(f"\n{'='*70}")
    print(f"TECHNICAL SPECIFICATIONS REPORT")
    print(f"{'='*70}")
    print(f"Cars: {', '.join(car_list)}")
    print(f"{'='*70}\n")

    try:
        # Scrape car data (use internal scraping logic)
        print("Scraping car specifications...")

        comparison_data = {}
        for car_name in car_list:
            print(f"  Scraping {car_name}...")
            car_data = scrape_car_data(car_name)
            comparison_data[car_name] = car_data

        # Generate technical specs HTML report
        print("\nGenerating technical specifications report...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"technical_specs_report_{timestamp}.html"
        report_path = save_technical_specs_html(comparison_data, filename)

        # Calculate statistics
        total_specs_found = sum(
            len([v for k, v in car_data.items() if v and v not in ["Not Available", "Not found", "N/A", ""]])
            for car_data in comparison_data.values()
            if isinstance(car_data, dict)
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        print(f"\n{'='*70}")
        print(f"REPORT GENERATED SUCCESSFULLY!")
        print(f"{'='*70}")
        print(f"File: {report_path}")
        print(f"Cars analyzed: {len(car_list)}")
        print(f"Total specifications: {total_specs_found}")
        print(f"Time taken: {elapsed_time:.2f} seconds")
        print(f"{'='*70}\n")

        response = {
            "status": "success",
            "message": f"Technical Specifications report generated successfully!",
            "report_file": report_path,
            "cars_analyzed": car_list,
            "total_cars": len(car_list),
            "total_specifications": total_specs_found,
            "elapsed_time": f"{elapsed_time:.2f} seconds",
            "instructions": f"Open {report_path} in your browser to view the report with tables and charts"
        }

        return json.dumps(response, indent=2)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        })


def generate_youtube_proscons_report_tool(car_names: str, num_channels: int = 2) -> str:
    """
    Generate a standalone YouTube Pros & Cons report for specified cars.

    This tool analyzes car reviews from trusted Indian YouTube channels and generates
    a professional HTML report with detailed pros and cons from multiple sources.

    Args:
        car_names: Comma-separated list of car names (e.g., "Mahindra Thar, Tata Punch")
        num_channels: Number of YouTube channels to analyze per car (default: 2, max: 5)

    Returns:
        JSON string with report file path and summary

    Example:
        generate_youtube_proscons_report_tool("Mahindra Thar, Hyundai Creta", num_channels=2)
    """
    import time
    from datetime import datetime

    start_time = time.time()

    # Parse car names
    car_list = [c.strip() for c in car_names.split(",")]

    if not car_list:
        return json.dumps({
            "status": "error",
            "error": "Please provide at least one car name"
        })

    if len(car_list) > 10:
        return json.dumps({
            "status": "error",
            "error": f"Maximum 10 cars can be analyzed at once. You provided {len(car_list)}."
        })

    if num_channels < 1 or num_channels > 5:
        return json.dumps({
            "status": "error",
            "error": "num_channels must be between 1 and 5"
        })

    print(f"\n{'='*70}")
    print(f"YOUTUBE PROS & CONS ANALYSIS")
    print(f"{'='*70}")
    print(f"Cars: {', '.join(car_list)}")
    print(f"Channels per car: {num_channels}")
    print(f"{'='*70}\n")

    try:
        # Extract pros/cons from YouTube
        print("Extracting pros/cons from YouTube reviews...")
        proscons_data = get_multiple_cars_proscons(car_list, num_channels=num_channels)

        # Generate HTML report
        print("\nGenerating HTML report...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"youtube_proscons_report_{timestamp}.html"
        report_path = save_youtube_proscons_html(proscons_data, filename)

        # Calculate statistics
        total_channels = sum(len(reviews) for reviews in proscons_data.values())
        total_pros = sum(
            len(review.get('positives', []))
            for reviews in proscons_data.values()
            for review in reviews
        )
        total_cons = sum(
            len(review.get('negatives', []))
            for reviews in proscons_data.values()
            for review in reviews
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        print(f"\n{'='*70}")
        print(f"REPORT GENERATED SUCCESSFULLY!")
        print(f"{'='*70}")
        print(f"File: {report_path}")
        print(f"Cars analyzed: {len(car_list)}")
        print(f"Total reviews: {total_channels}")
        print(f"Total pros: {total_pros}")
        print(f"Total cons: {total_cons}")
        print(f"Time taken: {elapsed_time:.2f} seconds")
        print(f"{'='*70}\n")

        response = {
            "status": "success",
            "message": f"YouTube Pros & Cons report generated successfully!",
            "report_file": report_path,
            "cars_analyzed": car_list,
            "total_cars": len(car_list),
            "channels_per_car": num_channels,
            "total_reviews": total_channels,
            "statistics": {
                "total_pros": total_pros,
                "total_cons": total_cons,
                "total_points": total_pros + total_cons
            },
            "elapsed_time": f"{elapsed_time:.2f} seconds",
            "instructions": f"Open {report_path} in your browser to view the interactive report"
        }

        return json.dumps(response, indent=2)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        })


root_agent = Agent(
    name="Product_Planning_AI_Agent",
    model=GEMINI_MAIN_MODEL,
    description="AI agent for product planning and strategic vehicle comparison with 87 specs using Custom Search API. Supports PDFs, prototypes, and market vehicles.",

    instruction="""You are a car benchmarking specialist. You compare vehicles using 87 specifications.

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
- Returns browser-viewable HTML report with interactive charts

**2. Code Cars (Prototypes/Internal)**
- Detected by: "CODE:" prefix
- Two options for specs:
  a) RAG: Set `user_decision="rag"` to query Vertex corpus automatically
  b) PDF: User uploads PDF and says "compare CODE:[name] from uploaded PDF with [external car]"
     - Read the PDF, extract CODE car specs, call `save_pdf_car_specs_tool(car_name="CODE:X", specs_json='{...}')`
     - Then call `scrape_cars_tool(car_names="CODE:X, ExternalCar")` — no user_decision needed
     - Internal car specs pre-filled from PDF; external cars sourced via scarpe_cars_tool

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
        generate_youtube_proscons_report_tool,
        generate_technical_specs_report_tool,
    ]
)


def run_car_comparison(car_names: List[str], use_custom_search: bool = True):
    """
    Run enhanced car comparison with 98 specifications for any cars.
    Results are uploaded to GCS and viewable in browser via signed URLs.

    Args:
        car_names: List of car names to compare
        use_custom_search: If True (default), use Custom Search API
    """
    if len(car_names) < 2:
        print(f"Error: Need at least 2 cars to compare, got {len(car_names)}")
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
