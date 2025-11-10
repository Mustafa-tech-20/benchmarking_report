import requests
import vertexai
from typing import Dict, Any, List, Optional
import os
import json
from dotenv import load_dotenv
import time
from pathlib import Path
import re
import asyncio
import aiohttp
import uuid
import json as json_module 
import google.auth

from datetime import timedelta
from google.cloud import storage
from google.auth import compute_engine
from google.auth.transport import requests as auth_requests


from google.adk.agents import Agent
from google.cloud import storage
from google.oauth2 import service_account
from datetime import timedelta 
from vertexai.generative_models import GenerativeModel, Part

from benchmarking_agent.Reports_Frontend import create_comparison_chart_html
from benchmarking_agent.Internal_Car_tools import (
    add_code_car_specs_tool,
    query_rag_for_code_car_specs,
    create_blank_specs_for_code_car,
    add_code_car_specs_bulk_tool,
    CAR_SPECS
)


load_dotenv()


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-south1")
vertexai.init(project=PROJECT_ID, location=LOCATION)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
SEARCH_ENGINE_ID =os.getenv("SEARCH_ENGINE_ID") 
CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GCS_FOLDER_PREFIX = "car-comparisons/"
SIGNED_URL_EXPIRATION_HOURS = 168  # URLs expire after 6 days




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
- For price_range ONLY: Always format as “₹Xlakhs–₹Y lakhs” (no decimals, no spaces); for single prices use “₹X lakh onwards”; convert crores to lakhs and dollars to Indian rupees in lakhs before formatting.

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

def count_populated_fields(car_data: Dict[str, Any], field_list: List[str]) -> int:
    """Count how many fields have valid data (not 'Not Available')."""
    return sum(
        1 for field in field_list 
        if car_data.get(field) not in ["Not Available", "N/A", None, ""] 
        and str(car_data.get(field, "")).strip()
    )

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
    print(f"Strategy: CardDekho → YouTube → Custom Search")  # Changed this line
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
    url_data = await loop.run_in_executor(None,extract_car_data_from_url,cardekho_url,car_name,None)
    
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
    
    # PHASE 1.5: YouTube Video Analysis(slows down 2x but better results)

    # missing_fields = [
    #     field for field in CAR_SPECS 
    #     if car_data.get(field) in [None, "Not Available", "N/A", ""]
    # ]
    
    # if missing_fields:
    #     print(f"\n→ PHASE 1.5: YouTube Video Analysis for {len(missing_fields)} missing fields...")
        
    #     # Search for YouTube video
    #     youtube_url = await search_youtube_for_car(car_name)
        
    #     if youtube_url:
    #         print(f"   → Analyzing YouTube video for specs...")
            
    #         # Extract specs from YouTube video (synchronous call in executor)
    #         loop = asyncio.get_event_loop()
    #         youtube_data = await loop.run_in_executor(None,extract_specs_from_youtube_video,youtube_url,car_name,missing_fields)
            
    #         if "error" not in youtube_data:
    #             # Merge YouTube data
    #             newly_found = 0
    #             for field in missing_fields:
    #                 value = youtube_data.get(field)
    #                 if value and value not in ["Not Available", "N/A", None, ""]:
    #                     car_data[field] = value
                        
    #                     # Store citation
    #                     citation_key = f"{field}_citation"
    #                     if citation_key in youtube_data:
    #                         car_data[citation_key] = {
    #                             "source_url": youtube_url,
    #                             "citation_text": youtube_data[citation_key]
    #                         }
    #                     newly_found += 1
                
    #             if youtube_url not in car_data["source_urls"]:
    #                 car_data["source_urls"].append(youtube_url)
                
    #             print(f"    Found {newly_found} additional fields from YouTube")
                
    #             # Update missing fields
    #             missing_fields = [
    #                 field for field in CAR_SPECS 
    #                 if car_data.get(field) in [None, "Not Available", "N/A", ""]
    #             ]
                
    #             # Check threshold again after YouTube
    #             populated = count_populated_fields(car_data, CAR_SPECS)
    #             if populated >= THRESHOLD:
    #                 elapsed = time.time() - start_time
    #                 print(f"\n{'='*60}")
    #                 print(f" SUCCESS! {populated}/{len(CAR_SPECS)} fields populated")
    #                 print(f" Threshold met after YouTube analysis")
    #                 print(f" Completed in {elapsed:.2f} seconds")
    #                 print(f"{'='*60}\n")
                    
    #                 # Fill remaining fields
    #                 for field in CAR_SPECS:
    #                     if field not in car_data or not car_data.get(field):
    #                         car_data[field] = "Not Available"
    #                         car_data[f"{field}_citation"] = {
    #                             "source_url": "N/A",
    #                             "citation_text": "Field not required after threshold met"
    #                         }
                    
    #                 return car_data

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
        search_results = await call_custom_search_parallel(missing_queries,num_results=3, max_concurrent=20  # Increased from 15
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
    import concurrent.futures
    
    try:
        # Check if there's already a running event loop
        loop = asyncio.get_running_loop()
        
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


def normalize_car_name_for_url(car_name: str) -> str:
    """Normalize car name for URL format."""
    brands = ["mahindra", "tata", "hyundai", "mg", "toyota", "maruti", "suzuki", "kia", 
              "honda", "ford", "jeep", "skoda", "volkswagen", "nissan", "renault", "citroen"]
    
    car_name_lower = car_name.lower()
    for brand in brands:
        car_name_lower = car_name_lower.replace(brand + " ", "")
    
    url_name = car_name_lower.strip().replace(" ", "-")
    return url_name


def get_brand_name(car_name: str) -> str:
    """Extract brand name from car name."""
    brands = ["mahindra", "tata", "hyundai", "mg", "toyota", "maruti", "kia",
              "honda", "ford", "jeep", "skoda", "volkswagen", "nissan", "renault", "citroen"]
    
    car_name_lower = car_name.lower()
    for brand in brands:
        if brand in car_name_lower:
            return brand
    
    return car_name.split()[0].lower()


def generate_sales_data_urls(car_name: str) -> List[str]:
    """Generate URLs specifically for sales data."""
    brand = get_brand_name(car_name)
    url_car_name = normalize_car_name_for_url(car_name)
    
    sales_urls = [
        # GoodReturns - Monthly sales figures
        f"https://www.goodreturns.in/cars/{brand}-{url_car_name}-sales.html",
        
        # CardDekho News - Sales reports
   
        f"https://www.cardekho.com/india-car-news/{url_car_name}-sales-report",
        
        # AutoPortal - Sales data
        f"https://www.autoportal.com/{brand}/{url_car_name}/sales",
        f"https://www.autoportal.com/newcars/{brand}/{url_car_name}",
        
        # ZigWheels News - Sales analysis
        f"https://www.zigwheels.com/news-features/news/{brand}-{url_car_name}-sales",
        
        # CarAndBike - Sales insights
        f"https://www.carandbike.com/{brand}-cars/{url_car_name}-sales",
    ]
    
    return sales_urls

def collect_manual_specs_for_code_car(code_car_name: str) -> Dict[str, Any]:
    """
    Interactively collect specifications for a code car from user input (91 specs total).
    """
    print(f"\n{'='*60}")
    print(f"MANUAL SPECIFICATION INPUT FOR: {code_car_name}")
    print(f"{'='*60}")
    print("\nYou can provide custom specifications for this car.")
    print("Press ENTER to skip any field (will attempt web scraping for skipped fields)")
    print(f"{'='*60}\n")
    
    manual_specs = {
        "car_name": code_car_name,
        "is_code_car": True,
        "manual_entry": True,
        "source_urls": ["Manual User Input"]
    }
    
    #all specs with user-friendly prompts
    spec_prompts = [
   
        ("price_range", "Price Range (e.g., ₹13.66 Lakh onwards): "),
        ("mileage", "Mileage (e.g., 16.5 kmpl): "),
        ("user_rating", "User Rating (e.g., 4.5/5): "),
        ("seating_capacity", "Seating Capacity (e.g., 7 Seater): "),
        ("braking", "Braking System (e.g., ABS with EBD, Disc/Drum): "),
        ("steering", "Steering Type (e.g., Electric Power Steering): "),
        ("climate_control", "Climate Control (e.g., Dual Zone Automatic): "),
        ("battery", "Battery (e.g., 50 kWh, or N/A for non-EVs): "),
        ("transmission", "Transmission (e.g., Manual & Automatic): "),
        ("brakes", "Brakes (e.g., Front Disc/Rear Drum): "),
        ("wheels", "Wheels (e.g., 18-inch alloy wheels): "),
        ("performance", "Performance (e.g., 0-100 in 10.5s, 180 kmph top speed): "),
        ("body", "Body Type (e.g., SUV, Monocoque): "),
        ("vehicle_safety_features", "Safety Features (e.g., 6 Airbags, ESP, ADAS): "),
        ("lighting", "Lighting (e.g., LED Headlamps with DRLs): "),
        ("audio_system", "Audio System (e.g., 9-inch touchscreen, 8 speakers): "),
        ("off_road", "Off-Road Features (e.g., 4x4, Hill Descent Control): "),
        ("interior", "Interior Features (e.g., Leather seats, Panoramic sunroof): "),
        ("seat", "Seat Details (e.g., Ventilated leather seats): "),
        ("ride", "Ride Quality/Comfort: "),
        ("performance_feel", "Performance Feel/Driving Experience: "),
        ("driveability", "Driveability/Ease of Driving: "),
        ("manual_transmission_performance", "Manual Transmission Performance: "),
        ("pedal_operation", "Pedal Operation (Clutch/Brake/Accelerator): "),
        ("automatic_transmission_performance", "Automatic Transmission Performance: "),
        ("powertrain_nvh", "Powertrain NVH (Noise/Vibration/Harshness): "),
        ("wind_nvh", "Wind NVH: "),
        ("road_nvh", "Road NVH: "),
        ("visibility", "Visibility/Sight Lines: "),
        ("seats_restraint", "Seats Restraint/Safety: "),
        ("impact", "Impact Safety/Crash Test Ratings: "),
        ("seat_cushion", "Seat Cushion Comfort: "),
        ("turning_radius", "Turning Radius: "),
        ("epb", "Electronic Parking Brake (EPB): "),
        ("brake_performance", "Brake Performance/Stopping Distance: "),
        ("stiff_on_pot_holes", "Stiffness on Pot Holes: "),
        ("bumps", "Bumps Handling: "),
        ("jerks", "Jerks in Transmission/Drivetrain: "),
        ("pulsation", "Pulsation/Vibration: "),
        ("stability", "Stability at High Speed/Cornering: "),
        ("shakes", "Shakes/Vibration: "),
        ("shudder", "Shudder/Vibration: "),
        ("shocks", "Shocks/Suspension Quality: "),
        ("grabby", "Grabby Brakes/Clutch: "),
        ("spongy", "Spongy Brakes/Pedal Feel: "),
        ("telescopic_steering", "Telescopic Steering Adjustment: "),
        ("torque", "Torque/Power Output: "),
        ("nvh", "Overall NVH: "),
        ("wind_noise", "Wind Noise in Cabin: "),
        ("tire_noise", "Tire/Road Noise: "),
        ("crawl", "Crawl/Low Speed Control: "),
        ("gear_shift", "Gear Shift Quality: "),
        ("pedal_travel", "Pedal Travel Distance: "),
        ("gear_selection", "Gear Selection Ease: "),
        ("turbo_noise", "Turbo Noise/Sound: "),
        ("resolution", "Display Resolution: "),
        ("touch_response", "Touch Response of Infotainment: "),
        ("button", "Button Controls Quality: "),
        ("apple_carplay", "Apple CarPlay Support: "),
        ("digital_display", "Digital Display/Instrument Cluster: "),
        ("blower_noise", "Blower Noise from AC: "),
        ("soft_trims", "Soft Trims/Interior Quality: "),
        ("armrest", "Armrest Comfort: "),
        ("sunroof", "Sunroof/Panoramic Sunroof: "),
        ("irvm", "IRVM (Interior Rear View Mirror): "),
        ("orvm", "ORVM (Outside Rear View Mirror): "),
        ("window", "Window Quality/Power Windows: "),
        ("alloy_wheel", "Alloy Wheel Design/Size: "),
        ("tail_lamp", "Tail Lamp Design/LED: "),
        ("boot_space", "Boot Space/Luggage Capacity: "),
        ("led", "LED Lights: "),
        ("drl", "DRL (Daytime Running Lights): "),
        ("ride_quality", "Overall Ride Quality: "),
        ("infotainment_screen", "Infotainment Screen Size/Touchscreen: "),
        ("chasis", "Chassis/Platform Construction: "),
        ("straight_ahead_stability", "Straight Ahead Stability on Highway: "),
        ("wheelbase", "Wheelbase Dimensions: "),
        ("egress", "Egress/Ease of Getting Out: "),
        ("ingress", "Ingress/Ease of Getting In: "),
        ("corner_stability", "Corner Stability/Handling: "),
        ("parking", "Parking Ease/Sensors/Camera: "),
        ("manoeuvring", "Manoeuvring in City: "),
        ("city_performance", "City Performance/Urban Driving: "),
        ("highway_performance", "Highway Performance/Cruising: "),
        ("wiper_control", "Wiper Control/Operation: "),
        ("sensitivity", "Sensitivity of Controls: "),
        ("rattle", "Rattle/Interior Build Quality: "),
        ("headrest", "Headrest Comfort/Adjustment: "),
        ("acceleration", "Acceleration/0-100 Performance: "),
        ("response", "Response (Throttle/Steering): "),
        ("door_effort", "Door Effort/Opening-Closing Ease: ")
    ]
    
    manually_entered_count = 0
    
    for field, prompt in spec_prompts:
        user_input = input(f"{prompt}").strip()
        
        if user_input:
            manual_specs[field] = user_input
            # Create citation for manually entered data
            manual_specs[f"{field}_citation"] = {
                "source_url": "Manual User Input",
                "citation_text": f"Manually entered by user: '{user_input}'"
            }
            manually_entered_count += 1
            print(f"Saved")
        else:
            manual_specs[field] = None  # Mark as not provided
            print(f"  Skipped (will attempt web scraping)")
    
    print(f"\n{'='*60}")
    print(f"Manual Entry Complete: {manually_entered_count}/91 fields provided")
    print(f"{'='*60}\n")
    
    return manual_specs


def is_code_car(car_name: str) -> bool:
    """
    Check if a car name is a code/custom car.
    Code cars are identified by 'CODE:' prefix or all uppercase format.
    """
    car_name_upper = car_name.strip().upper()
    return (car_name.startswith("CODE:") or 
            car_name.startswith("code:") or
            (car_name_upper == car_name and len(car_name.split()) <= 2))

def extract_sales_data_from_url(url: str, car_name: str) -> Dict[str, Any]:
    """
    Use Gemini to extract ONLY sales data from a URL.
    """
    try:
        model = GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""
        You are visiting this webpage: {url}
        
        Your task: Extract SALES DATA for "{car_name}" from this webpage.
        
        CRITICAL INSTRUCTIONS:
        1. Look for sales figures, units sold, market performance
        2. Search for monthly sales, yearly sales, market share data
        3. Look in news articles, sales reports, market analysis sections
        4. Extract actual numbers and percentages
        5. Only use "Not Available" if you absolutely cannot find the information
        
        Extract these SALES fields:
        {{
            "car_name": "{car_name}",
            "monthly_sales": "Average monthly sales units (e.g., 5,000 units/month, 5K units)",
            "monthly_sales_citation": "Exact text: 'Monthly sales average 5,000 units' - Found in: Sales Report section"
        }}
        
        SEARCH PATTERNS TO LOOK FOR:
        - Sales figures: "units sold", "monthly sales", "yearly sales", "annual sales"
        - Numbers: "5,000 units", "60K sales", "5000 units/month"
        - Market: "market share", "segment share", "% of market"
        - Trends: "YoY", "year-over-year", "growth", "decline", "increase", "decrease"
        - Time periods: "in 2024", "last month", "Q1 2025", "FY2024"
        
        CITATION FORMAT:
        For each field's citation, provide:
        1. The EXACT text snippet from the webpage (in quotes)
        2. The location/section where you found it
        
        Return ONLY the JSON object with actual extracted sales values, no additional text.
        If you cannot find specific sales information, use "Not Available" for both value and citation.
        """
        
        response = model.generate_content([prompt])
        
        # Parse response
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        sales_data = json.loads(response_text.strip())
        return sales_data
        
    except json.JSONDecodeError as e:
        print(f"   JSON parsing error for sales data: {e}")
        return {"car_name": car_name, "error": "Failed to parse sales data"}
    except Exception as e:
        print(f"    Sales data extraction failed: {e}")
        return {"car_name": car_name, "error": f"Failed to extract sales data: {str(e)}"}
    

def scrape_sales_data(car_name: str) -> Dict[str, Any]:
    """
    Scrape sales data for a car from multiple sources.
    Uses a separate Gemini call focused only on sales metrics.
    """
    print(f"\n{'='*60}")
    print(f"Scraping SALES DATA for: {car_name}")
    print(f"{'='*60}")
    
    urls = generate_sales_data_urls(car_name)
    
    sales_fields = ["monthly_sales"]
    aggregated_sales = {
        "car_name": car_name,
        "sales_source_urls": []
    }
    
    missing_fields = sales_fields.copy()
    
    for idx, url in enumerate(urls):
        if not missing_fields:
            print(f"\n All sales fields populated! Stopping early.")
            break
        
        print(f"\n[Sales URL {idx+1}/{len(urls)}] Analyzing: {url}")
        print(f"   Missing fields: {', '.join(missing_fields)}")
        
        sales_data = extract_sales_data_from_url(url, car_name)
        
        if "error" not in sales_data:
            newly_found = []
            for field in missing_fields[:]:
                value = sales_data.get(field)
                if value and value not in ["Not Available", "N/A", None, ""] and str(value).strip():
                    aggregated_sales[field] = value
                    citation_key = f"{field}_citation"
                    if citation_key in sales_data and sales_data[citation_key]:
                        aggregated_sales[citation_key] = {
                            "source_url": url,
                            "citation_text": sales_data[citation_key]
                        }
                    missing_fields.remove(field)
                    newly_found.append(field)
            
            if newly_found:
                aggregated_sales["sales_source_urls"].append(url)
                print(f"    Found {len(newly_found)} sales metrics: {', '.join(newly_found)}")
        else:
            print(f"    No sales data found")
        
        time.sleep(2)  # Rate limiting
    
    # Fill missing fields
    for field in missing_fields:
        aggregated_sales[field] = "Not Available"
        aggregated_sales[f"{field}_citation"] = {
            "source_url": "N/A",
            "citation_text": "Sales data not available from any source"
        }
    
    populated = len(sales_fields) - len(missing_fields)
    print(f"\n Sales data complete: {populated}/{len(sales_fields)} fields populated")
    
    return aggregated_sales

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
    

def scrape_multiple_cars(car_list: List[str], use_custom_search: bool = True) -> Dict[str, Any]:
    """
    Scrape data for multiple cars.
    
    Args:
        car_list: List of car names to compare
        use_custom_search: If True, use Custom Search API; if False, use legacy Gemini URL parsing
    """
    all_cars = car_list
    
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
    print(f"Output Directory: {folder_name}")
    print(f"Method: {'Custom Search API' if use_custom_search else 'Gemini URL Parsing (Legacy)'}")
    print(f"{'#'*60}\n")
    
    for car in all_cars:
        print(f"\n{'#'*60}")
        print(f"Processing: {car}")
        print(f"{'#'*60}")
        
        
        car_data = scrape_car_data(car, use_custom_search=use_custom_search)
        results["comparison_data"][car] = car_data
        
        populated = sum(1 for field in CAR_SPECS 
                       if car_data.get(field) not in ["Not Available", "N/A", None, ""])
        print(f"\n {car}: {populated}/{len(CAR_SPECS)} fields populated")
        
    
    return results


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



def get_gcs_client():
    """Get GCS client - works both locally and in Cloud Run"""
    from google.cloud import storage
    
    client = storage.Client()
    
    return client


def upload_html_to_gcs(html_content: str, gcs_destination_path: str) -> str:
    """
    Upload HTML content directly to GCS with proper headers for browser viewing.
    
    Args:
        html_content: HTML string content with embedded CSS/JS
        gcs_destination_path: Destination path in GCS (without gs://bucket/)
        
    Returns:
        GCS URI (gs://bucket/path)
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_destination_path)
        
        blob.content_type = "text/html; charset=utf-8"
        blob.cache_control = "public, max-age=3600"  
        
        # Upload HTML content 
        blob.upload_from_string(
            html_content,
            content_type="text/html; charset=utf-8"
        )
        
        # Set additional metadata after upload
        blob.metadata = {
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff"
        }
        blob.patch()
        
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_destination_path}"
        print(f"    Uploaded HTML to GCS: {gcs_uri}")
        
        return gcs_uri
        
    except Exception as e:
        print(f" Failed to upload HTML to GCS: {e}")
        raise


def upload_json_to_gcs(json_content: str, gcs_destination_path: str) -> str:
    """
    Upload JSON content directly to GCS.
    
    Args:
        json_content: JSON string content
        gcs_destination_path: Destination path in GCS (without gs://bucket/)
        
    Returns:
        GCS URI (gs://bucket/path)
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_destination_path)
        
        # Set metadata for JSON
        blob.content_type = "application/json; charset=utf-8"
        blob.cache_control = "public, max-age=3600"
        
        # Upload JSON content directly
        blob.upload_from_string(
            json_content,
            content_type="application/json; charset=utf-8"
        )
        
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_destination_path}"
        print(f"    Uploaded JSON to GCS: {gcs_uri}")
        
        return gcs_uri
        
    except Exception as e:
        print(f" Failed to upload JSON to GCS: {e}")
        raise


def generate_signed_url(gcs_path: str, expiration_minutes: int = 60) -> str:
    """Generate signed URL - works locally and in Cloud Run"""
    
    try:
        
        credentials, project = google.auth.default()
        
        # Create client
        client = storage.Client(credentials=credentials, project=project)
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)
        
        # For Cloud Run, we need to use the service account directly
        # This works with both local service account files and Cloud Run identity
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )
        
        print(f"    Generated signed URL (expires in {expiration_minutes} min)")
        return signed_url
        
    except Exception as e:
        print(f" Failed to generate signed URL: {e}")
        raise

# to locally save the generated file for testing

# def save_chart_html(html_content: str, output_dir: Path) -> str:
#     """Save HTML chart to the output directory and return the file path."""
#     filename = "car_comparison_report.html"
#     filepath = output_dir / filename
    
#     with open(filepath, 'w', encoding='utf-8') as f:
#         f.write(html_content)
    
#     return str(filepath.absolute())

def save_chart_to_gcs(html_content: str, folder_name: str) -> tuple[str, str]:
    """
    Upload HTML report directly to GCS and return GCS URI and browser-viewable signed URL.
    No local file is created. The HTML contains embedded CSS and JavaScript.
    
    Args:
        html_content: Complete HTML string with CSS/JS embedded
        folder_name: Folder name for organization (e.g., "car_comparison_20250124_123456")
        
    Returns:
        Tuple of (gcs_uri, signed_url)
    """
    # Generate unique filename with timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"report_{timestamp}_{unique_id}.html"
    
    print(f"\n Uploading interactive HTML report to Google Cloud Storage...")
    print(f"  Report contains: HTML + CSS + JavaScript + Charts")
    
    # Upload HTML content directly to GCS with proper headers
    gcs_path = f"{GCS_FOLDER_PREFIX}{folder_name}/{filename}"
    gcs_uri = upload_html_to_gcs(html_content, gcs_path)
    
    # Generate signed URL that opens in browser
    signed_url = generate_signed_url(gcs_path)
    
    print(f"  HTML Report ready!")
    print(f"  GCS: {gcs_uri}")
    print(f"  URL: {signed_url[:80]}...")
    print(f"  Click URL to view in browser")
    
    return gcs_uri, signed_url


def save_json_to_gcs(json_data: dict, folder_name: str) -> tuple[str, str]:
    """
    Upload JSON data directly to GCS and return GCS URI and signed URL.
    No local file is created.
    
    Args:
        json_data: Dictionary to convert to JSON
        folder_name: Folder name for organization
        
    Returns:
        Tuple of (gcs_uri, signed_url)
    """
    # Generate unique filename
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"data_{timestamp}_{unique_id}.json"
    
    print(f"\n Uploading JSON data to Google Cloud Storage...")
    
    # Convert dict to JSON string
    json_content = json_module.dumps(json_data, indent=2)
    
    # Upload JSON content directly to GCS
    gcs_path = f"{GCS_FOLDER_PREFIX}{folder_name}/{filename}"
    gcs_uri = upload_json_to_gcs(json_content, gcs_path)
    
    # Generate signed URL
    signed_url = generate_signed_url(gcs_path)
    
    print(f" JSON Data ready!")
    print(f" GCS: {gcs_uri}")
    print(f"      🔗 URL: {signed_url[:80]}...")
    
    return gcs_uri, signed_url

    
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
    import concurrent.futures
    
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
    
    # Process cars
    for car in car_list:
        print(f"\n{'#'*60}")
        print(f"Processing: {car}")
        print(f"{'#'*60}")
        
        # Check if manual specs were provided
        manual_specs = manual_specs_dict.get(car)
        
        if manual_specs and manual_specs.get('left_blank'):
            # User chose to leave blank
            print("→ Using blank specifications (user chose to leave empty)")
            car_data = manual_specs
        else:
            # Normal processing with or without manual specs - PASS use_custom_search flag
            car_data = scrape_car_data(car, manual_specs, use_custom_search=use_custom_search)
        
        if not car_data.get('is_code_car'):
            print(f"\n→ Now fetching sales data for {car}...")
            
            # Use Custom Search for sales if enabled
            if use_custom_search:
                sales_query = f"{car} monthly sales units"
                print(f"   Querying sales via Custom Search: {sales_query}")
                
                # Define async function for sales fetching
                async def fetch_sales():
                    queries = {"monthly_sales": sales_query}
                    results = await call_custom_search_parallel(queries, num_results=5, max_concurrent=1)
                    return results.get("monthly_sales", [])
                
                # Use ThreadPoolExecutor to run async code in a separate thread
                def run_async_task():
                    """Run async function in a new event loop"""
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(fetch_sales())
                    finally:
                        new_loop.close()
                
                # Execute in thread pool
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(run_async_task)
                        sales_results = future.result(timeout=60)  # 60 second timeout
                except Exception as e:
                    print(f"    Error fetching sales data: {e}")
                    sales_results = []
                
                if sales_results:
                    sales_extraction = extract_spec_from_search_results(car, "monthly_sales", sales_results)
                    car_data["monthly_sales"] = sales_extraction["value"]
                    car_data["monthly_sales_citation"] = {
                        "source_url": sales_extraction["source_url"],
                        "citation_text": sales_extraction["citation"]
                    }
                    if sales_extraction["source_url"] not in car_data.get("source_urls", []):
                        car_data["source_urls"].append(sales_extraction["source_url"])
                else:
                    car_data["monthly_sales"] = "Not Available"
                    car_data["monthly_sales_citation"] = {
                        "source_url": "N/A",
                        "citation_text": "No sales data found"
                    }
            
            else:
                # Use legacy scrape_sales_data function
                sales_data = scrape_sales_data(car)
                
                # Merge sales data into car_data
                for key, value in sales_data.items():
                    if key not in ['car_name', 'sales_source_urls']:
                        car_data[key] = value
                
                # Merge source URLs
                if 'sales_source_urls' in sales_data and sales_data['sales_source_urls']:

                    if 'source_urls' not in car_data:
                        car_data['source_urls'] = []
                    
                    car_data['source_urls'].extend(sales_data['sales_source_urls'])
        
        else:
            print(f"\n→ Skipping sales data for code car: {car}")
            car_data["monthly_sales"] = "Not Available"
            car_data["monthly_sales_citation"] = {
                "source_url": "N/A",
                "citation_text": "Code car - sales data not applicable"
            }
        
        results["comparison_data"][car] = car_data
        
        # Show completion status
        populated = sum(1 for field in CAR_SPECS 
                       if car_data.get(field) not in ["Not Available", "N/A", None, ""])
        print(f"\n {car}: {populated}/{len(CAR_SPECS)} specs populated")
        
        
    
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