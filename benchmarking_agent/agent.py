import os
import json
import asyncio
import time
import concurrent.futures
from typing import Dict, Any, List, Optional

from google.adk.agents import Agent
from vertexai.generative_models import GenerativeModel

from benchmarking_agent.config import SIGNED_URL_EXPIRATION_HOURS
from benchmarking_agent.utils import is_code_car
from benchmarking_agent.scraper import (
    scrape_car_data,
    call_custom_search_parallel,
    extract_spec_from_search_results,
)
from benchmarking_agent.sales import scrape_sales_data
from benchmarking_agent.gcs import save_chart_to_gcs, save_json_to_gcs
from benchmarking_agent.Internal_Car_tools import (
    add_code_car_specs_tool,
    query_rag_for_code_car_specs,
    create_blank_specs_for_code_car,
    add_code_car_specs_bulk_tool,
    CAR_SPECS,
)
from benchmarking_agent.Reports_Frontend import create_comparison_chart_html


def generate_comparison_summary(comparison_data: Dict[str, Any]) -> str:
    """Use Gemini to generate a comparison summary."""
    try:
        model = GenerativeModel("gemini-2.5-flash")

        prompt = f"""
        You are an automotive industry analyst.
        Analyze the following car comparison data and provide **key industry-standard pointers** for each spec category.

        Focus on identifying what buyers should look for in each spec based on current industry trends - but **do not mention any specific car names**.

        Generate short, bullet-point insights highlighting what's ideal or desirable in each category.

        Specs to cover:
        1. Price and value for money
        2. Engine & Power (performance)
        3. Mileage/Fuel efficiency
        4. Seating capacity and practicality
        5. Key features and technology
        6. User ratings and satisfaction

        Data:
        {json.dumps(comparison_data, indent=2)}

        Format your response as clear bullet points for each category, focusing on:
        - What specifications or metrics are considered strong or industry-leading
        - What aspects buyers should prioritize
        - Keep it practical, objective, and concise (under 250 words total).
        """

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"Error generating summary: {str(e)}"


def scrape_cars_tool(car_names: str, user_decision: Optional[str] = None, use_custom_search: bool = True) -> str:
    """
    Tool to scrape car data using Custom Search API OR Gemini's direct URL analysis with ALL 19 specifications.

    IMPORTANT FOR CODE CARS:
    - If code cars are detected (names with "CODE:" prefix or ALL CAPS format),
      the agent should FIRST ask the user with three options:
      1. Manual entry (yes/manual)
      2. RAG corpus query (rag/gcs)
      3. Leave blank (blank/empty)

    Args:
        car_names: Comma-separated list of car names (minimum 2, maximum 10)
                   Example: "CODE:PROTO1, Mahindra Thar, Maruti Jimny"
        user_decision: User's choice for code cars: 'manual', 'rag', or 'blank'
        use_custom_search: If True (default), use Custom Search API; if False, use Gemini URL parsing

    Returns:
        JSON string with comparison results and chart file path
    """
    car_list = [c.strip() for c in car_names.split(",")]

    # Validation
    if len(car_list) < 2:
        return json.dumps({
            "status": "error",
            "error": f"Please provide at least 2 cars to compare. You provided {len(car_list)}."
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

        if manual_specs and manual_specs.get('left_blank'):
            print(f"[{car}] Using blank specifications")
            car_data = manual_specs
        else:
            car_data = scrape_car_data(car, manual_specs, use_custom_search=use_custom_search)

        if not car_data.get('is_code_car'):
            print(f"[{car}] Fetching sales data...")
            if use_custom_search:
                sales_query = f"{car} monthly sales units"

                def _run_sales_async() -> list:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(
                            call_custom_search_parallel(
                                {"monthly_sales": sales_query}, num_results=5, max_concurrent=1
                            )
                        ).get("monthly_sales", [])
                    finally:
                        loop.close()

                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as sex:
                        sales_results = sex.submit(_run_sales_async).result(timeout=60)
                except Exception as e:
                    print(f"[{car}] Sales fetch error: {e}")
                    sales_results = []

                if sales_results:
                    ext = extract_spec_from_search_results(car, "monthly_sales", sales_results)
                    car_data["monthly_sales"] = ext["value"]
                    car_data["monthly_sales_citation"] = {
                        "source_url": ext["source_url"],
                        "citation_text": ext["citation"],
                    }
                    if ext["source_url"] not in car_data.get("source_urls", []):
                        car_data["source_urls"].append(ext["source_url"])
                else:
                    car_data["monthly_sales"] = "Not Available"
                    car_data["monthly_sales_citation"] = {
                        "source_url": "N/A",
                        "citation_text": "No sales data found",
                    }
            else:
                sales_data = scrape_sales_data(car)
                for key, value in sales_data.items():
                    if key not in ('car_name', 'sales_source_urls'):
                        car_data[key] = value
                if sales_data.get('sales_source_urls'):
                    car_data.setdefault('source_urls', []).extend(sales_data['sales_source_urls'])
        else:
            print(f"[{car}] Skipping sales data (code car)")
            car_data["monthly_sales"] = "Not Available"
            car_data["monthly_sales_citation"] = {
                "source_url": "N/A",
                "citation_text": "Code car - sales data not applicable",
            }

        populated = sum(
            1 for f in CAR_SPECS if car_data.get(f) not in ("Not Available", "N/A", None, "")
        )
        print(f"[{car}] Done: {populated}/{len(CAR_SPECS)} specs populated")
        return car, car_data

    # Parallel processing — main thread aggregates results via as_completed
    max_workers = min(len(car_list), 5)
    print(f"\nProcessing {len(car_list)} cars in parallel (max_workers={max_workers})...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_car = {pool.submit(_process_single_car, car): car for car in car_list}
        for future in concurrent.futures.as_completed(future_to_car):
            original_car = future_to_car[future]
            try:
                car_key, car_data = future.result()
                results["comparison_data"][car_key] = car_data
            except Exception as exc:
                print(f"[{original_car}] FAILED: {exc}")
                results["comparison_data"][original_car] = {"car_name": original_car, "error": str(exc)}

    # Clear collected specs for next comparison
    if hasattr(add_code_car_specs_tool, 'collected_specs'):
        add_code_car_specs_tool.collected_specs = {}

    print("\n STEP 2: Generating AI-powered comparison summary...")
    summary = generate_comparison_summary(results["comparison_data"])
    results["summary"] = summary

    print("\n STEP 3: Creating enhanced interactive HTML report...")
    html_content = create_comparison_chart_html(results["comparison_data"], summary)

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
        "message": f"Car comparison completed! Click the URLs below to view in your browser.",
        "cars_compared": car_list,
        "code_cars_left_blank": blank_cars if blank_cars else [],
        "code_cars_with_manual_specs": manual_cars if manual_cars else [],
        "total_cars": len(car_list),

        # GCS Storage
        "gcs_folder": folder_name,
        "chart_gcs_uri": html_gcs_uri,
        "json_gcs_uri": json_gcs_uri,

        # BROWSER-VIEWABLE SIGNED URLS
        "html_report_url": html_signed_url,
        "json_data_url": json_signed_url,

        # Alternative keys for compatibility
        "chart_signed_url": html_signed_url,
        "json_signed_url": json_signed_url,

        # Metadata
        "summary": summary,
        "elapsed_time": f"{elapsed_time:.2f} seconds",
        "scraping_method": "Custom Search API" if use_custom_search else "Gemini URL Parsing",
        "signed_url_expiration_hours": SIGNED_URL_EXPIRATION_HOURS,
        "instructions": "Click 'html_report_url' to view the interactive report in your browser. All CSS and JavaScript are embedded."
    }

    return json.dumps(response, indent=2)


root_agent = Agent(

    name="Car_Comparison_AI_Agent",
    model="gemini-2.5-flash",

    description="Enhanced AI agent with 91 specification comparison for any cars, using Google Custom Search API for accurate data extraction.",

    instruction="""
        You are an enhanced car comparison specialist using Google Custom Search API.

        DATA COLLECTION METHOD
        By default, this system uses Google Custom Search API to fetch car specifications:
        This system uses a TWO-PHASE approach for maximum speed:

        PHASE 1: Best URL Scraping
        - Makes ONE general search query for the car
        - Extracts ALL 91 specs from the best result URL using Gemini
        - If ≥85/91 fields populated → STOPS (success in ~30-60 seconds)

        PHASE 2: Targeted Search (only if needed)
        - Makes parallel API calls ONLY for missing fields
        - Uses Gemini to extract specific missing data
        - Provides complete 91-spec coverage

        WORKFLOW

        1. When user requests a car comparison:
        - Check if any car names are CODE CARS — meaning:
        - They start with 'CODE:' (e.g., CODE:PROTO1)
        - OR are written in ALL CAPS (e.g., XYZ123, ABC456)

        2. If CODE CARS are detected:
        - Call 'scrape_cars_tool' FIRST to identify the code cars.
        - If the response status is "awaiting_code_car_specs", ask the user:

        > "Is this a released car or an internal product?"

        If user says RELEASED CAR / NOT INTERNAL / PUBLIC:
        - Treat it as a normal car.
        - Call `scrape_cars_tool` with `use_custom_search=True` to fetch data via Google Custom Search API.
        - Proceed with standard web scraping workflow.

        If user says INTERNAL PRODUCT / PROTOTYPE / CODE CAR:
        Ask how they want to provide specifications:

        > "Would you like to manually specify specifications for the code car(s)?"

        Provide three options:

        1. MANUAL ENTRY (ONE-BY-ONE or BULK)
        2. RAG CORPUS (Vertex RAG query)
        3. BLANK (Leave all fields empty)

        If user says YES / MANUAL:
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

        If user says RAG / GCS / CORPUS / VERTEX RAG / RAG CORPUS:
        - Call 'scrape_cars_tool' with user_decision="rag"
        - System queries Vertex RAG corpus for specifications
        - Proceeds automatically after RAG query

        If user says BLANK / EMPTY / LEAVE:
        - The agent marks all fields as "Not Available".
        - No manual entry or web scraping is done.
        - Call `scrape_cars_tool` again with `user_decision="blank"`.

         3. If NO CODE CARS detected:
        - Directly call:
        scrape_cars_tool(car_names=[...], use_custom_search=True)
        - The tool uses Custom Search API to fetch real car data and generates the comparison report.

        TOOLS AVAILABLE
        - add_code_car_specs_tool: Interactive, one-by-one entry for all 91 specifications.
        - add_code_car_specs_bulk_tool: Bulk JSON entry (all specs at once).
        - scrape_cars_tool: Main comparison and report generation tool (uses Custom Search API by default).

        IMPORTANT LOGIC RULES
        - Always call **`scrape_cars_tool` FIRST** to detect code cars.
        - Only call **manual tools** (`add_code_car_specs_tool` / `add_code_car_specs_bulk_tool`) if the user confirms manual entry.
        - After manual entry, always call `scrape_cars_tool` again to generate the final report.
        - All 91 specifications are optional — user may skip any.
        - Custom Search API is used by default for better accuracy and citations.

        ALL REPORTS ARE BROWSER-VIEWABLE:
        - HTML reports contain embedded CSS and JavaScript
        - Reports open directly in browser via signed URLs
        - No downloads required - click URL to view instantly

        98 SPECIFICATIONS TRACKED

        Original Core Specs (19):
        Price Range, Mileage, User Rating, Seating Capacity, Braking, Steering,
        Climate Control, Battery, Transmission, Brakes, Wheels, Performance, Body Type,
        Vehicle Safety Features, Lighting, Audio System, Off-Road, Interior, Seat, Monthly Sales

        Advanced Performance & Feel (72):
        Ride, Performance Feel, Driveability, Manual Transmission Performance, Pedal Operation,
        Automatic Transmission Performance, Powertrain NVH, Wind NVH, Road NVH, Visibility,
        Seats Restraint, Impact, Seat Cushion, Turning Radius, EPB, Brake Performance,
        Stiff on Pot Holes, Bumps, Jerks, Pulsation, Stability, Shakes, Shudder, Shocks,
        Grabby, Spongy, Telescopic Steering, Torque, NVH, Wind Noise, Tire Noise, Crawl,
        Gear Shift, Pedal Travel, Gear Selection, Turbo Noise, Resolution, Touch Response,
        Button, Apple CarPlay, Digital Display, Blower Noise, Soft Trims, Armrest, Sunroof,
        IRVM, ORVM, Window, Alloy Wheel, Tail Lamp, Boot Space, LED, DRL, Ride Quality,
        Infotainment Screen, Chassis, Straight Ahead Stability, Wheelbase, Egress, Ingress,
        Corner Stability, Parking, Manoeuvring, City Performance, Highway Performance,
        Wiper Control, Sensitivity, Rattle, Headrest, Acceleration, Response, Door Effort,
        Review Ride & Handling, Review Steering, Review Braking, Review Performance & Drivability,
        Review 4x4 Operation, Review NVH, Review GSQ (Gear Shift Quality)

        OUTPUT FORMAT - CRITICAL

        After comparison completes, present the results like this:

        Car Comparison Complete!

        Compared: [Car1], [Car2], [Car3]
        Time: 45.2 seconds


        VIEW REPORT IN BROWSER
        Click this URL to open the interactive report:
        [HTML_REPORT_URL]

        """,
    tools=[add_code_car_specs_tool, add_code_car_specs_bulk_tool, scrape_cars_tool]
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
    result_data = json.loads(result)

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
