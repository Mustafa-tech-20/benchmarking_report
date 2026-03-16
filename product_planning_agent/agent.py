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

        model = GenerativeModel("gemini-2.5-flash")

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
    If CODE CARS are detected (names with "CODE:" prefix or ALL CAPS format):

    STEP 1: Call 'scrape_cars_tool' FIRST to identify the code cars.

    STEP 2: If the response status is "awaiting_code_car_specs", ask the user:

    > "Is this a **released car** or an **internal product**?"

    ---

    🚗 If user says **RELEASED CAR / NOT INTERNAL / PUBLIC**:
    - Treat it as a normal car.
    - Call `scrape_cars_tool` with `use_custom_search=True` to fetch data via Google Custom Search API.
    - Proceed with standard web scraping workflow.

    ---

    If user says **INTERNAL PRODUCT / PROTOTYPE / CODE CAR**:
    Ask how they want to provide specifications:

    > "Would you like to manually specify specifications for the code car(s)?"

    Provide **three options**:

    1. **MANUAL ENTRY** (ONE-BY-ONE or BULK)
    2. **RAG CORPUS** (Vertex RAG query)
    3. **BLANK** (Leave all fields empty)

    ---

    📝 If user says **YES / MANUAL**:
    Ask how they want to enter the data:

    1. ONE-BY-ONE METHOD
       - Call:
         add_code_car_specs_tool(car_name="CODE:PROTO1")
       - The ADK automatically prompts for all **91 specifications**, one at a time.
       - User must type a value for each spec or respond with 'skip', 'n/a', or blank to leave it empty.
       - After completion (status "success"), call `scrape_cars_tool` again to generate the comparison report.

    2. BULK / ALL-AT-ONCE METHOD
       - Call:
         add_code_car_specs_bulk_tool(car_name="CODE:PROTO1", specifications="{...}")
       - User provides all 91 specs in JSON format at once.
       - Faster but requires properly formatted JSON.
       - After this call, execute `scrape_cars_tool` again to generate the report.

    ---

    📚 If user says **RAG / GCS / CORPUS / VERTEX RAG / RAG CORPUS**:
    - Call 'scrape_cars_tool' with user_decision="rag"
    - System queries Vertex RAG corpus for specifications
    - Proceeds automatically after RAG query

    ---

    ⭕ If user says **BLANK / EMPTY / LEAVE**:
    - The agent marks all fields as "Not Available".
    - No manual entry or web scraping is done.
    - Call `scrape_cars_tool` again with `user_decision="blank"`.

    Args:
        car_names: Comma-separated list of car names (minimum 1, maximum 10)
                   Example: "Mahindra Thar" or "CODE:PROTO1, Mahindra Thar, Maruti Jimny"
                   Can be single car for individual analysis or multiple for comparison
        user_decision: User's choice for code cars: 'manual', 'rag', or 'blank'
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
        # Check if specs were collected for code cars
        collected_specs = getattr(add_code_car_specs_tool, 'collected_specs', {})
        uncollected_code_cars = [car for car in code_cars if car not in collected_specs]

        if uncollected_code_cars and not user_decision:
            return json.dumps({
                "status": "awaiting_code_car_specs",
                "message": f"I detected {len(code_cars)} CODE CAR(s): {', '.join(code_cars)}\n\n" +
                          f"For the code car(s), I can either:\n" +
                          f"1. Let you manually specify all specifications (recommended for prototypes)\n" +
                          f"2. Query the RAG corpus / GCS for specifications\n\n" +
                          f"3. Leave the specifications blank/empty\n\n" +
                          f"Please respond:\n" +
                          f"- 'yes' or 'manual' - to manually enter specifications\n" +
                          f"- 'rag' or 'gcs' - to query the RAG corpus\n" +
                          f"- 'blank' or 'empty' - to leave all specifications empty",
                "code_cars_detected": code_cars,
                "code_cars_needing_specs": uncollected_code_cars,
                "awaiting_decision": True
            }, indent=2)

        # Handle user decision
        if user_decision:
            decision = user_decision.lower().strip()

            if decision in ['blank', 'empty', 'leave', 'skip blank', 'leave blank']:
                # User wants to leave code cars blank
                print(f"\n→ User chose to leave code car(s) blank: {', '.join(uncollected_code_cars)}")
                for car in uncollected_code_cars:
                    blank_specs = create_blank_specs_for_code_car(car)
                    if not hasattr(add_code_car_specs_tool, 'collected_specs'):
                        add_code_car_specs_tool.collected_specs = {}
                    add_code_car_specs_tool.collected_specs[car] = blank_specs
                    print(f" Created blank spec structure for '{car}'")

            elif decision in ['yes', 'y', 'manual', 'enter', 'specify']:
                # User wants manual entry - offer both methods
                return json.dumps({
                    "status": "needs_manual_entry",
                    "message": f"Great! I'll collect specifications for: {', '.join(uncollected_code_cars)}\n\n" +
                              f"I have TWO methods for entering specifications:\n\n" +
                              f"**Method 1: One-by-one (Interactive)**\n" +
                              f"I'll ask you for each of the 19 specifications individually.\n" +
                              f"Tool: 'add_code_car_specs_tool'\n\n" +
                              f"**Method 2: All-at-once (Bulk)**\n" +
                              f"Provide all specifications in JSON format in one go.\n" +
                              f"Tool: 'add_code_car_specs_bulk_tool'\n\n" +
                              f"Which method would you prefer?",
                    "code_cars_needing_manual_entry": uncollected_code_cars,
                    "methods_available": ["one-by-one", "bulk"]
                }, indent=2)

            elif decision in ['rag', 'gcs', 'corpus', 'vertex rag', 'rag corpus']:
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
                    "error": f"Invalid decision: '{user_decision}'. Please respond with 'manual', 'rag', or 'blank'."
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
        pdf_specs_dict = getattr(save_pdf_car_specs_tool, 'pdf_specs', {})
        pdf_specs = pdf_specs_dict.get(car)

        if manual_specs and manual_specs.get('left_blank'):
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

        # Extract variant walk data (only for product planning agent)
        if not car_data.get('is_code_car'):
            print(f"[{car}] Extracting variant walk data...")
            from product_planning_agent.extraction.variant_walk import extract_variant_walk
            variant_data = extract_variant_walk(car)
            if variant_data and variant_data.get('variants'):
                car_data['variant_walk'] = variant_data
                print(f"[{car}] ✓ Extracted {len(variant_data.get('variants', {}))} variants")
            else:
                print(f"[{car}] ✗ No variant data found")
                car_data['variant_walk'] = None
        else:
            print(f"[{car}] Skipping variant walk (code car)")
            car_data['variant_walk'] = None

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

    print("\n STEP 2 & 2.5: Running in parallel - Comparison summary + YouTube pros/cons...")

    # Get only non-code cars for YouTube analysis
    youtube_car_names = [
        car for car in car_list
        if not results["comparison_data"].get(car, {}).get('is_code_car')
    ]

    # Run both steps in parallel using ThreadPoolExecutor for CPU-bound tasks
    import concurrent.futures

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
    model="gemini-2.5-flash",
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
- Fetches 87 specs via Custom Search API (80-90% accuracy)
- Returns browser-viewable HTML report with interactive charts

**2. Code Cars (Prototypes/Internal)**
- Detected by: "CODE:" prefix or ALL CAPS names
- Three options for specs:
  a) Manual: `add_code_car_specs_tool` (interactive) or `add_code_car_specs_bulk_tool` (JSON)
  b) RAG: Set `user_decision="rag"` to query Vertex corpus
  c) Blank: Set `user_decision="blank"` for empty specs

## HANDLING TOOL RESPONSE STATUSES

**When scrape_cars_tool returns a JSON response, check the "status" field:**

1. **"status": "awaiting_code_car_specs"**
   - Meaning: CODE car detected, need user decision
   - Action: Display the "message" field to user and wait for their response
   - Next: User will say "manual", "rag", or "blank"

2. **"status": "needs_manual_entry"**
   - Meaning: User chose manual entry, need to pick method
   - Action: Display the "message" field to user asking ONE-BY-ONE or BULK
   - Next: If user says "one by one" → call `add_code_car_specs_tool(car_name="CODE:XXX")`
   - Next: If user says "bulk" → call `add_code_car_specs_bulk_tool(car_name="CODE:XXX", specifications="{...}")`
   - After specs tool completes: Call `scrape_cars_tool` again (same car_names, no user_decision)

3. **"status": "success"**
   - Meaning: Comparison complete
   - Action: Display the HTML report URL

4. **"status": "error"**
   - Meaning: Something failed
   - Action: Display the "error" field to user

**CRITICAL: When you get "awaiting_code_car_specs" or "needs_manual_entry", you MUST:**
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

**Code Car (Multi-Step Flow):**
1. User: "Compare CODE:PROTO1 with Thar"
2. Call: `scrape_cars_tool(car_names="CODE:PROTO1, Mahindra Thar")`
   → Returns: `"status": "awaiting_code_car_specs"` with message
3. Show the message to user and wait for their decision
4. User says: "manual" (or "yes", "manual entry", etc.)
5. Call: `scrape_cars_tool(car_names="CODE:PROTO1, Mahindra Thar", user_decision="manual")`
   → Returns: `"status": "needs_manual_entry"` asking for ONE-BY-ONE or BULK
6. Show the message to user and wait for their choice
7a. If user says "one by one" (or "interactive", "step by step"):
    Call: `add_code_car_specs_tool(car_name="CODE:PROTO1")`
    → Tool will interactively prompt for all 91 specs
    → After completion, call: `scrape_cars_tool(car_names="CODE:PROTO1, Mahindra Thar")`
7b. If user says "bulk" (or "all at once", "json"):
    Call: `add_code_car_specs_bulk_tool(car_name="CODE:PROTO1", specifications="{...}")`
    → User provides JSON with all specs
    → After completion, call: `scrape_cars_tool(car_names="CODE:PROTO1, Mahindra Thar")`
8. Alternative decisions at step 4:
   - User says "rag": Call `scrape_cars_tool(car_names="...", user_decision="rag")`
   - User says "blank": Call `scrape_cars_tool(car_names="...", user_decision="blank")`

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
