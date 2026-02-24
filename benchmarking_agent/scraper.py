import asyncio
import aiohttp
import json
import time
import concurrent.futures
from typing import Dict, Any, List

from vertexai.generative_models import GenerativeModel, Part

from benchmarking_agent.config import GOOGLE_API_KEY, SEARCH_ENGINE_ID, CUSTOM_SEARCH_URL
from benchmarking_agent.utils import normalize_car_name_for_url, get_brand_name, count_populated_fields
from benchmarking_agent.Internal_Car_tools import CAR_SPECS


def get_spec_search_queries(car_name: str) -> Dict[str, str]:
    """
    Generate Custom Search queries for each specification.
    Returns a dictionary mapping spec name to search query.
    """
    queries = {
        "price_range": f"{car_name} price ",
        "mileage": f"{car_name} mileage kmpl",
        "user_rating": f"{car_name} user ratings",
        "seating_capacity": f"{car_name} seating capacity",
        "braking": f"{car_name} braking system features",
        "steering": f"{car_name} steering type",
        "climate_control": f"{car_name} climate control features",
        "battery": f"{car_name} battery capacity ",
        "transmission": f"{car_name} transmission features",
        "brakes": f"{car_name} brakes features",
        "wheels": f"{car_name} wheels size",
        "performance": f"{car_name} performance and acceleration power and features",
        "body": f"{car_name} body type ",
        "vehicle_safety_features": f"{car_name} safety features ",
        "lighting": f"{car_name} lighting features",
        "audio_system": f"{car_name} audio system features",
        "off_road": f"{car_name} off-road 4x4 capabilities",
        "interior": f"{car_name} interior features",
        "seat": f"{car_name} seat features ",
        "monthly_sales": f"{car_name} monthly sales units",
        "ride": f"{car_name} ride quality and comfort",
        "performance_feel": f"{car_name} driving experience",
        "driveability": f"{car_name} driveability and ease of driving",
        "manual_transmission_performance": f"{car_name} manual transmission performance",
        "pedal_operation": f"{car_name} pedal operation clutch brake features",
        "automatic_transmission_performance": f"{car_name} automatic transmission performance",
        "powertrain_nvh": f"{car_name} powertrain NVH noise vibration",
        "wind_nvh": f"{car_name} wind noise NVH",
        "road_nvh": f"{car_name} road noise NVH",
        "visibility": f"{car_name} visibility sight lines",
        "seats_restraint": f"{car_name} seats restraint safety",
        "impact": f"{car_name} impact safety crash test",
        "seat_cushion": f"{car_name} seat cushion comfort",
        "turning_radius": f"{car_name} turning radius circle",
        "epb": f"{car_name} electronic parking brake EPB",
        "brake_performance": f"{car_name} brake performance stopping distance",
        "stiff_on_pot_holes": f"{car_name} stiff pot holes suspension",
        "bumps": f"{car_name} bumps ride quality",
        "jerks": f"{car_name} jerks transmission drivetrain",
        "pulsation": f"{car_name} pulsation vibration",
        "stability": f"{car_name} stability high speed cornering",
        "shakes": f"{car_name} shakes vibration",
        "shudder": f"{car_name} shudder vibration",
        "shocks": f"{car_name} shocks suspension",
        "grabby": f"{car_name} grabby brakes clutch",
        "spongy": f"{car_name} spongy brakes pedal feel",
        "telescopic_steering": f"{car_name} telescopic steering adjustment",
        "torque": f"{car_name} torque power output",
        "nvh": f"{car_name} NVH noise vibration harshness",
        "wind_noise": f"{car_name} wind noise cabin",
        "tire_noise": f"{car_name} tire noise road noise",
        "crawl": f"{car_name} crawl low speed control",
        "gear_shift": f"{car_name} gear shift quality",
        "pedal_travel": f"{car_name} pedal travel distance",
        "gear_selection": f"{car_name} gear selection transmission",
        "turbo_noise": f"{car_name} turbo noise sound",
        "resolution": f"{car_name} display resolution screen",
        "touch_response": f"{car_name} touch response infotainment",
        "button": f"{car_name} button controls quality",
        "apple_carplay": f"{car_name} Apple CarPlay support",
        "digital_display": f"{car_name} digital display instrument cluster",
        "blower_noise": f"{car_name} blower noise AC",
        "soft_trims": f"{car_name} soft trims interior quality",
        "armrest": f"{car_name} armrest comfort",
        "sunroof": f"{car_name} sunroof panoramic",
        "irvm": f"{car_name} IRVM interior rear view mirror",
        "orvm": f"{car_name} ORVM outside rear view mirror",
        "window": f"{car_name} window power quality",
        "alloy_wheel": f"{car_name} alloy wheel design size",
        "tail_lamp": f"{car_name} tail lamp LED design",
        "boot_space": f"{car_name} boot space luggage capacity",
        "led": f"{car_name} LED lights",
        "drl": f"{car_name} DRL daytime running lights",
        "ride_quality": f"{car_name} ride quality comfort smoothness",
        "infotainment_screen": f"{car_name} infotainment screen size touchscreen",
        "chasis": f"{car_name} chassis platform construction",
        "straight_ahead_stability": f"{car_name} straight ahead stability highway",
        "wheelbase": f"{car_name} wheelbase dimensions",
        "egress": f"{car_name} egress getting out ease",
        "ingress": f"{car_name} ingress getting in ease",
        "corner_stability": f"{car_name} corner stability handling",
        "parking": f"{car_name} parking ease sensors camera",
        "manoeuvring": f"{car_name} manoeuvring city driving",
        "city_performance": f"{car_name} city performance urban driving",
        "highway_performance": f"{car_name} highway performance cruising",
        "wiper_control": f"{car_name} wiper control operation",
        "sensitivity": f"{car_name} sensitivity controls responsiveness",
        "rattle": f"{car_name} rattle interior quality",
        "headrest": f"{car_name} headrest comfort adjustment",
        "acceleration": f"{car_name} acceleration 0-100 performance",
        "response": f"{car_name} response throttle steering",
        "door_effort": f"{car_name} door effort opening closing",
        "review_ride_handling": f"{car_name} ride quality handling review expert opinion",
        "review_steering": f"{car_name} steering feel feedback review",
        "review_braking": f"{car_name} braking performance review stopping",
        "review_performance": f"{car_name} performance drivability review driving experience",
        "review_4x4_operation": f"{car_name} 4x4 off-road capability review terrain",
        "review_nvh": f"{car_name} NVH noise vibration review cabin refinement",
        "review_gsq": f"{car_name} gear shift quality transmission review smoothness"
    }
    return queries


async def call_custom_search_api_async(
    session: aiohttp.ClientSession,
    query: str,
    num_results: int = 5,
    retry_count: int = 3
) -> List[Dict[str, str]]:
    """
    Async version of Custom Search API call.

    Args:
        session: aiohttp ClientSession for connection pooling
        query: Search query string
        num_results: Number of results to return (max 10)
        retry_count: Number of retries on failure

    Returns:
        List of search results with title, snippet, and link
    """
    params = {
        "key": GOOGLE_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "q": query,
        "num": min(num_results, 10)
    }

    for attempt in range(retry_count):
        try:
            async with session.get(CUSTOM_SEARCH_URL, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    results = []
                    for item in data.get("items", []):
                        results.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "link": item.get("link", "")
                        })

                    return results

                elif response.status == 429:  # Rate limit
                    wait_time = (attempt + 1) * 2
                    print(f"   ⚠ Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                else:
                    print(f"API error {response.status} for query '{query[:50]}...'")
                    return []

        except asyncio.TimeoutError:
            print(f"Timeout for query '{query[:50]}...' (attempt {attempt + 1}/{retry_count})")
            if attempt < retry_count - 1:
                await asyncio.sleep(1)
                continue
            return []

        except Exception as e:
            print(f"    Error for query '{query[:50]}...': {e}")
            if attempt < retry_count - 1:
                await asyncio.sleep(1)
                continue
            return []

    return []


async def call_custom_search_parallel(
    queries: Dict[str, str],
    num_results: int = 5,
    max_concurrent: int = 15
) -> Dict[str, List[Dict[str, str]]]:
    """
    Execute multiple Custom Search API calls in parallel.

    Args:
        queries: Dictionary mapping spec_name to query string
        num_results: Number of results per query
        max_concurrent: Max simultaneous API calls (adjust based on rate limits)

    Returns:
        Dictionary mapping spec_name to search results
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_limit(session, spec_name, query):
        async with semaphore:
            results = await call_custom_search_api_async(session, query, num_results)
            return (spec_name, results)

    connector = aiohttp.TCPConnector(limit=max_concurrent)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [fetch_with_limit(session, spec_name, query) for spec_name, query in queries.items()]
        results = await asyncio.gather(*tasks)

    return dict(results)


async def search_youtube_for_car(car_name: str) -> str:
    """
    Search YouTube for car reviews using Custom Search API.
    Returns the first YouTube URL found.
    """
    query = f"{car_name} on youtube"
    print(f"   → Searching YouTube: '{query}'")

    connector = aiohttp.TCPConnector(limit=5)
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        results = await call_custom_search_api_async(session, query, num_results=3)

        # Find first YouTube URL
        for result in results:
            url = result.get('link', '')
            if 'youtube.com/watch' in url or 'youtu.be/' in url:
                print(f"Found YouTube video: {url}")
                return url

        print(f"    No YouTube video found")
        return None


def extract_spec_from_search_results(
    car_name: str,
    spec_name: str,
    search_results: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Use Gemini to intelligently select the best search result and extract the specification.

    Args:
        car_name: Name of the car
        spec_name: Specification to extract (e.g., 'price_range', 'mileage')
        search_results: List of search results from Custom Search API

    Returns:
        Dictionary with extracted value, citation text, and source URL (separate)
    """
    if not search_results:
        return {
            "value": "Not Available",
            "citation": "No search results found",
            "source_url": "N/A"
        }

    try:
        model = GenerativeModel("gemini-2.5-flash")

        # Format search results for Gemini
        formatted_results = ""
        for idx, result in enumerate(search_results, 1):
            formatted_results += f"""
RESULT {idx}:
TITLE: {result['title']}
SNIPPET: {result['snippet']}
LINK: {result['link']}
{'-'*80}
"""

        # Create extraction prompt
        prompt = f"""
You are analyzing search results to extract a specific car specification.

CAR: {car_name}
SPECIFICATION TO EXTRACT: {spec_name}

SEARCH RESULTS:
{formatted_results}

YOUR TASK:
1. Read ALL search results carefully
2. Identify which result(s) contain information about "{spec_name}" for "{car_name}"
3. Extract the EXACT value for this specification
4. If NONE of the results contain this information, return "Not Available"

IMPORTANT:
- Only extract the specific value requested (e.g., for "price_range", extract the price, NOT sales data)
- Be precise - don't extract unrelated information
- Provide the exact text snippet where you found this information
- For price_range ONLY: Always format as "₹Xlakhs–₹Y lakhs" (no decimals, no spaces); for single prices use "₹X lakh onwards"; convert crores to lakhs and dollars to Indian rupees in lakhs before formatting.

Return your response as JSON:
{{
    "value": "extracted value or 'Not Available'",
    "citation": "exact text snippet from the search result where you found this",
    "result_number": "which result number (1, 2, 3, etc.) or 'none' if not found"
}}

Return ONLY valid JSON, no additional text.
"""

        response = model.generate_content(prompt)

        # Parse Gemini response
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        extracted = json.loads(response_text.strip())

        source_url = "N/A"
        if extracted.get("result_number") and extracted["result_number"] != "none":
            try:
                result_idx = int(extracted["result_number"]) - 1
                if 0 <= result_idx < len(search_results):
                    source_url = search_results[result_idx]["link"]
            except:
                pass

        return {
            "value": extracted.get("value", "Not Available"),
            "citation": extracted.get("citation", "No citation available"),
            "source_url": source_url
        }

    except Exception as e:
        print(f"    Gemini extraction error: {e}")
        return {
            "value": "Not Available",
            "citation": f"Extraction failed: {str(e)}",
            "source_url": "N/A"
        }


async def scrape_car_data_with_custom_search_async(car_name: str) -> Dict[str, Any]:
    """
    OPTIMIZED: Direct CardDekho scraping first, then Custom Search fallback.

    Strategy:
    1. Generate CardDekho URL directly (no API call needed)
    2. Extract ALL 91 specs from CardDekho using Gemini
    3. If >= 86/91 fields populated, STOP (success)
    4. Otherwise, make parallel Custom Search calls ONLY for missing fields

    Args:
        car_name: Name of the car to scrape

    Returns:
        Dictionary with all car specifications and citations
    """
    print(f"\n{'='*60}")
    print(f"OPTIMIZED Scraping for: {car_name}")
    print(f"Strategy: CardDekho → YouTube → Custom Search")
    print(f"{'='*60}\n")

    start_time = time.time()
    THRESHOLD = 86  # Stop if we get 86/91 fields

    car_data = {
        "car_name": car_name,
        "source_urls": [],
        "method": "Optimized Custom Search (CardDekho First)"
    }

    # PHASE 1: Direct CardDekho URL scraping
    print(f"\n→ PHASE 1: Generating CardDekho URL...")

    brand = get_brand_name(car_name)
    url_car_name = normalize_car_name_for_url(car_name)
    cardekho_url = f"https://www.cardekho.com/{brand}/{url_car_name}"

    print(f"    CardDekho URL: {cardekho_url}")
    print(f"   → Extracting ALL specs from CardDekho using Gemini...")

    # Use Gemini to scrape the CardDekho URL
    loop = asyncio.get_event_loop()
    url_data = await loop.run_in_executor(None, extract_car_data_from_url, cardekho_url, car_name, None)

    if "error" not in url_data:
        # Merge extracted data
        for field in CAR_SPECS:
            value = url_data.get(field)
            if value and value not in ["Not Available", "N/A", None, ""]:
                car_data[field] = value

                # Store citation
                citation_key = f"{field}_citation"
                if citation_key in url_data:
                    car_data[citation_key] = {
                        "source_url": cardekho_url,
                        "citation_text": url_data[citation_key]
                    }

        car_data["source_urls"].append(cardekho_url)

        # Count populated fields
        populated = count_populated_fields(car_data, CAR_SPECS)
        print(f"    Extracted {populated}/{len(CAR_SPECS)} fields from CardDekho")

        # Check threshold
        if populated >= THRESHOLD:
            elapsed = time.time() - start_time
            print(f"\n{'='*60}")
            print(f" SUCCESS! {populated}/{len(CAR_SPECS)} fields populated")
            print(f" Threshold met ({THRESHOLD}+), stopping early")
            print(f" Completed in {elapsed:.2f} seconds")
            print(f"{'='*60}\n")

            # Fill remaining fields with "Not Available"
            for field in CAR_SPECS:
                if field not in car_data or not car_data.get(field):
                    car_data[field] = "Not Available"
                    car_data[f"{field}_citation"] = {
                        "source_url": "N/A",
                        "citation_text": "Field not required after threshold met"
                    }

            return car_data
    else:
        print(f"    CardDekho scraping failed: {url_data.get('error', 'Unknown error')}")

    # PHASE 2: Custom Search for missing fields (FULLY PARALLEL)

    missing_fields = [
        field for field in CAR_SPECS
        if car_data.get(field) in [None, "Not Available", "N/A", ""]
    ]

    if missing_fields:
        print(f"\n→ PHASE 2: Custom Search for {len(missing_fields)} missing fields...")
        print(f"   Missing: {', '.join(missing_fields[:5])}{'...' if len(missing_fields) > 5 else ''}")

        # Get queries only for missing fields
        all_queries = get_spec_search_queries(car_name)
        missing_queries = {k: v for k, v in all_queries.items() if k in missing_fields}

        print(f"   → Making {len(missing_queries)} parallel Custom Search API calls...")

        # Execute parallel searches for missing fields
        search_results = await call_custom_search_parallel(
            missing_queries, num_results=3, max_concurrent=20
        )

        print(f"    API calls completed")
        print(f"   → Processing ALL {len(search_results)} specs with Gemini in PARALLEL...")

        # PARALLEL GEMINI EXTRACTION with semaphore
        semaphore = asyncio.Semaphore(20)  # Max 20 concurrent Gemini calls

        async def extract_with_limit(spec_name, results):
            async with semaphore:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    extract_spec_from_search_results,
                    car_name,
                    spec_name,
                    results
                )

        tasks = [
            extract_with_limit(spec_name, results)
            for spec_name, results in search_results.items()
            if results
        ]

        # Wait for ALL to complete in parallel
        extracted_results = await asyncio.gather(*tasks)

        # Store results
        spec_names = [name for name, results in search_results.items() if results]
        for spec_name, extracted_data in zip(spec_names, extracted_results):
            if extracted_data and extracted_data["value"] != "Not Available":
                car_data[spec_name] = extracted_data["value"]
                car_data[f"{spec_name}_citation"] = {
                    "source_url": extracted_data["source_url"],
                    "citation_text": extracted_data["citation"]
                }

                if extracted_data["source_url"] not in car_data["source_urls"] and extracted_data["source_url"] != "N/A":
                    car_data["source_urls"].append(extracted_data["source_url"])

        print(f"    Parallel Gemini extraction completed")

    # Fill any remaining empty fields
    for field in CAR_SPECS:
        if field not in car_data or not car_data.get(field):
            car_data[field] = "Not Available"
            car_data[f"{field}_citation"] = {
                "source_url": "N/A",
                "citation_text": "Data not available from any source"
            }

    final_populated = count_populated_fields(car_data, CAR_SPECS)
    elapsed_time = time.time() - start_time

    print(f"\n{'='*60}")
    print(f" Scraping completed: {final_populated}/{len(CAR_SPECS)} fields")
    print(f" Time taken: {elapsed_time:.2f} seconds")
    print(f"{'='*60}\n")

    return car_data


def scrape_car_data_with_custom_search(car_name: str) -> Dict[str, Any]:
    """
    Smart wrapper that works in both sync and async contexts.
    """
    try:
        # Check if there's already a running event loop
        asyncio.get_running_loop()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                scrape_car_data_with_custom_search_async(car_name)
            )
            return future.result()

    except RuntimeError:
        return asyncio.run(scrape_car_data_with_custom_search_async(car_name))


def extract_car_data_from_url(url: str, car_name: str, missing_fields: List[str] = None) -> Dict[str, Any]:
    """
    Send URL directly to Gemini for analysis - extracts all specifications.
    """
    # If missing_fields is provided, only extract those fields
    if missing_fields is None:
        missing_fields = CAR_SPECS
        fields_to_extract = "all 19 fields"
    else:
        fields_to_extract = f"only these missing fields: {', '.join(missing_fields)}"

    try:
        model = GenerativeModel("gemini-2.5-flash")

        prompt = f"""
        You are visiting this car specifications webpage: {url}

        Your task: Extract accurate specifications for "{car_name}" from this webpage.

        FOCUS: Extract {"all 19 fields" if missing_fields is None else f"only these missing fields: {', '.join(missing_fields)}"}

        CRITICAL INSTRUCTIONS:
        1. Navigate through the ENTIRE webpage carefully
        2. Look for actual data values, not generic placeholders
        3. Search multiple sections: specs, features, reviews, pricing, dimensions
        4. Be thorough - data might be in tables, lists, or text blocks
        5. Only use "Not Available" if you absolutely cannot find the information
        6. Do not provide me with ranges give a definite value for all fields where possible
        7. FOR EACH FIELD: Provide the EXACT text snippet from the webpage and where you found it

        Extract these 19 fields with citations:
        {{
            "car_name": "{car_name}",
            "price_range": "Starting ex-showroom price (e.g., ₹13.66 Lakh onwards)",
            "price_range_citation": "Exact text from webpage: 'Starting price ₹13.66 Lakh' - Found in: Pricing section",
            "mileage": "Fuel efficiency (e.g., 16.5 kmpl)",
            "mileage_citation": "Exact text from webpage: 'Mileage: 16.5 kmpl' - Found in: Specifications table",
            "user_rating": "Average customer rating (e.g., 4.5/5, 4.3 out of 5 stars)",
            "user_rating_citation": "Exact text from webpage: 'User Rating: 4.5/5' - Found in: Reviews section",
            "review_ride_handling": "Complete expert review of ride quality, handling, suspension, comfort on various road conditions. Include opinions on highway stability, bump absorption, body roll, cornering. (e.g., 'Ride is firm especially at highway speeds. Praised off-road capability. Suspension is slightly stiffer than previous generation.')",
            "review_ride_handling_citation": "Exact text: 'The ride is notably firm...' - Found in: Expert Review / Ride & Handling section",

            "review_steering": "Expert review of steering feel, feedback, weight, precision, ease of use. (e.g., 'Steering lacks refinement, requires constant adjustment. Light at low speeds but vague at highway speeds.')",
            "review_steering_citation": "Exact text: 'Steering feel is lacking...' - Found in: Driving Dynamics section",

            "review_braking": "Review of braking performance, pedal feel, stopping distance, confidence. (e.g., 'Not up to par, needs longer to stop from 60 mph than rival SUVs. Brakes feel grabby at low speeds.')",
            "review_braking_citation": "Exact text: 'Braking performance is below expectations...' - Found in: Safety & Braking review",

            "review_performance": "Overall performance and drivability review including engine character, acceleration, responsiveness, ease of driving. (e.g., 'Much smoother to drive in town than previous model. Easy character and pleasant drivability. Competitively quick in this class.')",
            "review_performance_citation": "Exact text: 'The engine delivers smooth performance...' - Found in: Performance Review section",

            "review_4x4_operation": "Expert opinion on 4x4 capability, off-road performance, terrain handling. (e.g., 'More capable off-road than most rival SUVs. G.O.A.T modes improve off-road performance. 4x4 version is capable on light trails with decent grip.')",
            "review_4x4_operation_citation": "Exact text: '4x4 system performs well...' - Found in: Off-road Review section",

            "review_nvh": "Review of cabin noise, vibration, harshness - wind noise, road noise, engine noise at various speeds. (e.g., 'Noticeable wind/road noise. Perceivable wind noise at high speed. Cabin is quite noisy on the move with plenty of wind and road noise.')",
            "review_nvh_citation": "Exact text: 'Wind noise becomes noticeable...' - Found in: Refinement/NVH Review",

            "review_gsq": "Review of gear shift quality, transmission smoothness, clutch feel (if manual). (e.g., 'Transmission shifts are occasionally jerky at low speeds. Manual gearbox is smooth but clutch is heavy in traffic.')",
            "review_gsq_citation": "Exact text: 'Gear changes can be jerky...' - Found in: Transmission Review section"
            "seating_capacity": "Number of seats (e.g., 7 Seater, 5/7 Seater)",
            "seating_capacity_citation": "Exact text from webpage: '7 Seater' - Found in: Features list",
            "braking": "Braking system details (e.g., Disc/Drum, ABS, EBD)",
            "braking_citation": "Exact text from webpage: 'ABS with EBD' - Found in: Safety features",
            "steering": "Steering type (e.g., Power Steering, Electric Power Steering)",
            "steering_citation": "Exact text from webpage: 'Electric Power Steering' - Found in: Comfort features",
            "climate_control": "AC system (e.g., Manual AC, Automatic Climate Control, Dual Zone)",
            "climate_control_citation": "Exact text from webpage: 'Dual Zone Climate Control' - Found in: Interior features",
            "battery": "Battery capacity for EVs (e.g., 50 kWh, N/A for non-EVs)",
            "battery_citation": "Exact text from webpage: '50 kWh battery' - Found in: EV specifications",
            "transmission": "Transmission types (e.g., Manual & Automatic, Manual, Automatic)",
            "transmission_citation": "Exact text from webpage: 'Manual & Automatic' - Found in: Transmission section",
            "brakes": "Brake specifications (e.g., Front Disc/Rear Drum, All Disc)",
            "brakes_citation": "Exact text from webpage: 'Front Disc, Rear Drum' - Found in: Brake specifications",
            "wheels": "Wheel and tyre specs (e.g., 18-inch alloy wheels, 215/60 R17)",
            "wheels_citation": "Exact text from webpage: '18-inch alloy wheels' - Found in: Wheel specifications",
            "performance": "Acceleration and top speed (e.g., 0-100 kmph in 10.5s, Top speed 180 kmph)",
            "performance_citation": "Exact text from webpage: '0-100 in 10.5s' - Found in: Performance data",
            "body": "Body type and material (e.g., SUV, Monocoque, Ladder Frame)",
            "body_citation": "Exact text from webpage: 'SUV with Monocoque' - Found in: Body specifications",
            "vehicle_safety_features": "List 4-6 key safety features (e.g., 6 Airbags, ABS with EBD, ESP, Hill Hold Control, 360° Camera)",
            "vehicle_safety_features_citation": "Exact text from webpage: '6 Airbags, ESP, Hill Hold' - Found in: Safety section",
            "lighting": "Lighting features (e.g., LED Headlamps, LED DRLs, Auto Headlamps)",
            "lighting_citation": "Exact text from webpage: 'LED Headlamps with DRLs' - Found in: Exterior features",
            "audio_system": "Infotainment and audio (e.g., 9-inch touchscreen, 8-speaker system, Apple CarPlay)",
            "audio_system_citation": "Exact text from webpage: '9-inch touchscreen with 8 speakers' - Found in: Infotainment section",
            "off_road": "Off-road capabilities (e.g., 4x4, Hill Descent Control, Diff Lock)",
            "off_road_citation": "Exact text from webpage: '4x4 with Hill Descent' - Found in: Off-road features",
            "interior": "Interior features (e.g., Leather seats, Panoramic sunroof, Ambient lighting)",
            "interior_citation": "Exact text from webpage: 'Leather seats, Panoramic sunroof' - Found in: Interior features",
            "seat": "Seat details (e.g., Fabric/Leather, Ventilated front seats, 60:40 split rear)",
            "seat_citation": "Exact text from webpage: 'Ventilated leather seats' - Found in: Seat specifications"
        }}

        SEARCH PATTERNS FOR REVIEWS:
        Look for sections titled:
        - "Expert Review", "Editorial Review", "Road Test", "Test Drive"
        - "Ride Quality", "Handling", "Driving Dynamics", "Performance"
        - "Refinement", "NVH", "Cabin Noise"
        - "Pros and Cons", "Verdict", "What We Like/Don't Like"
        - "Driving Experience", "On-Road Behavior"

        SEARCH PATTERNS TO LOOK FOR:
        - Price: "price", "ex-showroom", "starting at", "from ₹", "Rs", "Lakh", "onwards"
        - Mileage: "mileage", "kmpl", "fuel efficiency", "km/l"
        - Rating: "/5", "out of 5", "stars", "rating"
        - Seating: "seater", "seats", "seating capacity"
        - Braking: "braking", "ABS", "EBD", "brake assist"
        - Steering: "steering", "power steering", "electric steering"
        - Climate Control: "AC", "air conditioning", "climate control", "dual zone"
        - Battery: "battery", "kWh", "battery capacity", "range"
        - Transmission: "manual", "automatic", "AMT", "CVT", "DCT"
        - Brakes: "disc brake", "drum brake", "braking system"
        - Wheels: "wheel", "tyre", "alloy", "rim size"
        - Performance: "acceleration", "0-100", "top speed", "bhp", "torque"
        - Body: "body type", "SUV", "sedan", "monocoque", "ladder frame"
        - Safety: "airbags", "ABS", "EBD", "ESP", "safety", "ADAS"
        - Lighting: "LED", "headlamp", "DRL", "fog lamp", "tail lamp"
        - Audio: "infotainment", "touchscreen", "speakers", "CarPlay", "Android Auto"
        - Off-road: "4x4", "4WD", "AWD", "diff lock", "hill descent"
        - Interior: "interior", "upholstery", "sunroof", "ambient lighting"
        - Seat: "seats", "leather", "fabric", "ventilated", "heated"

        CITATION FORMAT:
        For each field's citation, provide:
        1. The EXACT text snippet from the webpage (put in quotes)
        2. The location/section where you found it (e.g., "Found in: Pricing section")

        Return ONLY the JSON object with actual extracted values and citations, no additional text.
        If you cannot find specific information after thorough search, use "Not Available" for both value and citation.
        """

        print(f"   Gemini is fetching and analyzing the webpage...")

        response = model.generate_content([prompt])

        # Parse response
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        car_data = json.loads(response_text.strip())

        # Count valid fields extracted
        valid_fields = sum(1 for field in (missing_fields or CAR_SPECS)
                          if car_data.get(field) not in ["Not Available", "N/A", None, ""]
                          and str(car_data.get(field, "")).strip())

        print(f"    Gemini extracted {valid_fields} valid fields")
        return car_data

    except json.JSONDecodeError as e:
        print(f"   JSON parsing error: {e}")
        print(f"  Raw response: {response.text[:300]}...")
        return {
            "car_name": car_name,
            "error": "Failed to parse Gemini response as JSON"
        }
    except Exception as e:
        print(f"  Gemini URL analysis failed: {e}")
        return {
            "car_name": car_name,
            "error": f"Failed to analyze URL: {str(e)}"
        }


def extract_specs_from_youtube_video(url: str, car_name: str, missing_fields: List[str] = None) -> Dict[str, Any]:
    """
    Extract car specifications from YouTube video using Gemini's multimodal capabilities.

    Args:
        url: YouTube video URL
        car_name: Name of the car
        missing_fields: Specific fields to extract (if None, extracts all)

    Returns:
        Dictionary with extracted specs and citations
    """
    if missing_fields is None:
        missing_fields = CAR_SPECS
        fields_to_extract = "all specifications"
    else:
        fields_to_extract = f"only these fields: {', '.join(missing_fields)}"

    try:
        model = GenerativeModel("gemini-2.5-flash")

        # Note: Gemini can analyze YouTube videos directly via URL
        prompt = f"""
        You are analyzing a YouTube video about the car: {car_name}
        Video URL: {url}

        Your task: Extract specifications for "{car_name}" from this video's content.
        Focus on: {fields_to_extract}

        CRITICAL INSTRUCTIONS:
        1. Analyze the video description, title, and any visible specifications
        2. Look for reviewer comments about performance, features, comfort, etc.
        3. Extract user opinions, ratings, and real-world experiences
        4. Be thorough - data might be in spoken content or on-screen text
        5. Only use "Not Available" if information is genuinely not present
        6. Provide EXACT quotes from the video as citations

        Extract specifications with citations:
        {{
            "car_name": "{car_name}",
            "price_range": "Price mentioned in video",
            "price_range_citation": "Exact quote: 'Price is...' - From: Video timestamp XX:XX",
            "mileage": "Mileage/fuel efficiency mentioned",
            "mileage_citation": "Exact quote: 'Mileage is...' - From: Video description/timestamp",
            "user_rating": "Rating or opinion expressed",
            "user_rating_citation": "Exact quote: 'I rate it...' - From: Reviewer's opinion",
            "review_ride_handling": "Complete review of ride quality, handling, suspension from video",
            "review_ride_handling_citation": "Exact quote from reviewer about ride quality",
            "review_steering": "Steering review from video",
            "review_steering_citation": "Exact quote about steering feel",
            "review_braking": "Braking review from video",
            "review_braking_citation": "Exact quote about braking performance",
            "review_performance": "Performance review from video",
            "review_performance_citation": "Exact quote about performance",
            "review_nvh": "NVH review from video",
            "review_nvh_citation": "Exact quote about cabin noise",
            ... (include all {len(missing_fields)} fields you need)
        }}

        SEARCH PATTERNS:
        - Look in video title, description, and comments
        - Pay attention to reviewer's spoken opinions
        - Note timestamps where specs are mentioned
        - Extract both factual specs AND subjective reviews

        CITATION FORMAT:
        For each field's citation, provide:
        1. The EXACT quote from the video (in quotes)
        2. The location: "Video title", "Video description", "Timestamp XX:XX", "Reviewer comment"

        Return ONLY valid JSON with extracted values and citations.
        If information not found, use "Not Available" for value and "No mention in video" for citation.
        """

        print(f"   → Gemini analyzing YouTube video...")

        # Gemini can process YouTube URLs directly
        response = model.generate_content([prompt, Part.from_uri(url, mime_type="video/*")])

        # Parse response
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        car_data = json.loads(response_text.strip())

        # Count valid fields
        valid_fields = sum(1 for field in missing_fields
                          if car_data.get(field) not in ["Not Available", "N/A", None, ""]
                          and str(car_data.get(field, "")).strip())

        print(f"    Extracted {valid_fields} valid fields from YouTube video")
        return car_data

    except Exception as e:
        print(f"    YouTube video analysis failed: {e}")
        return {
            "car_name": car_name,
            "error": f"Failed to analyze YouTube video: {str(e)}"
        }


def scrape_car_data(car_name: str, manual_specs: Dict[str, Any] = None, use_custom_search: bool = True) -> Dict[str, Any]:
    """
    Use either Custom Search API or Gemini's direct URL analysis with smart field aggregation.

    Args:
        car_name: Name of the car to scrape
        manual_specs: Optional manual specifications (for code cars)
        use_custom_search: If True, use Custom Search API instead of Gemini URL parsing (DEFAULT: True)
    """
    print(f"\n{'='*60}")
    print(f"Scraping data for: {car_name}")
    if use_custom_search:
        print(f"Method: Google Custom Search API")
    else:
        print(f"Method: Gemini URL Parsing (Legacy)")
    print(f"{'='*60}")

    # If manual specs provided for a code car, skip web scraping entirely
    if manual_specs and manual_specs.get('is_code_car'):
        print(f" CODE CAR detected with manual specs - SKIPPING web scraping")
        manually_provided = sum(1 for k, v in manual_specs.items()
                               if v and not k.endswith('_citation')
                               and k not in ['car_name', 'is_code_car', 'manual_entry', 'source_urls', 'left_blank'])

        print(f" Using {manually_provided}/19 manually entered fields")

        # Fill any missing fields with "Not Available"
        for field in CAR_SPECS:
            if field not in manual_specs or not manual_specs[field]:
                manual_specs[field] = "Not Available"
                manual_specs[f"{field}_citation"] = {
                    "source_url": "Manual User Input",
                    "citation_text": "User skipped this specification during manual entry"
                }

        print(f" CODE CAR processing complete: {manually_provided} provided, {19-manually_provided} marked as N/A")
        return manual_specs

    if use_custom_search:
        print("→ Using NEW Custom Search API method")
        return scrape_car_data_with_custom_search(car_name)
