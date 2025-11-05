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

from datetime import timedelta
from google.cloud import storage
from google.auth import compute_engine
from google.auth.transport import requests as auth_requests



import google.auth
from google.adk.agents import Agent
from google.cloud import storage
from google.oauth2 import service_account
from datetime import timedelta 
from vertexai.generative_models import GenerativeModel, Part

load_dotenv()


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-south1")
vertexai.init(project=PROJECT_ID, location=LOCATION)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
SEARCH_ENGINE_ID = "a7aa909fb90a24678" 
CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GCS_FOLDER_PREFIX = "car-comparisons/"
SIGNED_URL_EXPIRATION_HOURS = 168  # URLs expire after 6 days


# Car specifications to scrape 
CAR_SPECS = [
    # Original 19 specs
    "price_range",
    "mileage",
    "user_rating",
    "seating_capacity",
    "braking",
    "steering",
    "climate_control",
    "battery",
    "transmission",
    "brakes",
    "wheels",
    "performance",
    "body",
    "vehicle_safety_features",
    "lighting",
    "audio_system",
    "off_road",
    "interior",
    "seat",
    # NEW: 72 Additional specs
    "ride",
    "performance_feel",
    "driveability",
    "manual_transmission_performance",
    "pedal_operation",
    "automatic_transmission_performance",
    "powertrain_nvh",
    "wind_nvh",
    "road_nvh",
    "visibility",
    "seats_restraint",
    "impact",
    "seat_cushion",
    "turning_radius",
    "epb",
    "brake_performance",
    "stiff_on_pot_holes",
    "bumps",
    "jerks",
    "pulsation",
    "stability",
    "shakes",
    "shudder",
    "shocks",
    "grabby",
    "spongy",
    "telescopic_steering",
    "torque",
    "nvh",
    "wind_noise",
    "tire_noise",
    "crawl",
    "gear_shift",
    "pedal_travel",
    "gear_selection",
    "turbo_noise",
    "resolution",
    "touch_response",
    "button",
    "apple_carplay",
    "digital_display",
    "blower_noise",
    "soft_trims",
    "armrest",
    "sunroof",
    "irvm",
    "orvm",
    "window",
    "alloy_wheel",
    "tail_lamp",
    "boot_space",
    "led",
    "drl",
    "ride_quality",
    "infotainment_screen",
    "chasis",
    "straight_ahead_stability",
    "wheelbase",
    "egress",
    "ingress",
    "corner_stability",
    "parking",
    "manoeuvring",
    "city_performance",
    "highway_performance",
    "wiper_control",
    "sensitivity",
    "rattle",
    "headrest",
    "acceleration",
    "response",
    "door_effort",
    "review_ride_handling",      
    "review_steering",            
    "review_braking",             
    "review_performance",         
    "review_4x4_operation",      
    "review_nvh",                 
    "review_gsq"                  
]


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
        
        # NEW: 72 Additional spec queries
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
                    print(f"   ✗ API error {response.status} for query '{query[:50]}...'")
                    return []
        
        except asyncio.TimeoutError:
            print(f"   ⚠ Timeout for query '{query[:50]}...' (attempt {attempt + 1}/{retry_count})")
            if attempt < retry_count - 1:
                await asyncio.sleep(1)
                continue
            return []
        
        except Exception as e:
            print(f"   ✗ Error for query '{query[:50]}...': {e}")
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
                print(f"   ✓ Found YouTube video: {url}")
                return url
        
        print(f"   ✗ No YouTube video found")
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
        print(f"   ✗ Gemini extraction error: {e}")
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
    
    print(f"   ✓ CardDekho URL: {cardekho_url}")
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
        print(f"   ✓ Extracted {populated}/{len(CAR_SPECS)} fields from CardDekho")
        
        # Check threshold
        if populated >= THRESHOLD:
            elapsed = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"✓ SUCCESS! {populated}/{len(CAR_SPECS)} fields populated")
            print(f"✓ Threshold met ({THRESHOLD}+), stopping early")
            print(f"✓ Completed in {elapsed:.2f} seconds")
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
        print(f"   ✗ CardDekho scraping failed: {url_data.get('error', 'Unknown error')}")
    
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
                
    #             print(f"   ✓ Found {newly_found} additional fields from YouTube")
                
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
    #                 print(f"✓ SUCCESS! {populated}/{len(CAR_SPECS)} fields populated")
    #                 print(f"✓ Threshold met after YouTube analysis")
    #                 print(f"✓ Completed in {elapsed:.2f} seconds")
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
        
        print(f"   ✓ API calls completed")
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
        
        print(f"   ✓ Parallel Gemini extraction completed")
    
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
    print(f"✓ Scraping completed: {final_populated}/{len(CAR_SPECS)} fields")
    print(f"✓ Time taken: {elapsed_time:.2f} seconds")
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
        
        print(f"   ✓ Gemini extracted {valid_fields} valid fields")
        return car_data
        
    except json.JSONDecodeError as e:
        print(f"   JSON parsing error: {e}")
        print(f"  Raw response: {response.text[:300]}...")
        return {
            "car_name": car_name,
            "error": "Failed to parse Gemini response as JSON"
        }
    except Exception as e:
        print(f"  ✗Gemini URL analysis failed: {e}")
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
        
        print(f"   ✓ Extracted {valid_fields} valid fields from YouTube video")
        return car_data
        
    except Exception as e:
        print(f"   ✗ YouTube video analysis failed: {e}")
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
    
    # Define all specs with user-friendly prompts - UPDATE THIS LIST
    spec_prompts = [
        # Original 19 specs
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
        
        # NEW: 72 Additional specs
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
            print(f"   ✓ Saved")
        else:
            manual_specs[field] = None  # Mark as not provided
            print(f"   - Skipped (will attempt web scraping)")
    
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
        print(f"   ✗ Sales data extraction failed: {e}")
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
            print(f"\n✓ All sales fields populated! Stopping early.")
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
                print(f"   ✓ Found {len(newly_found)} sales metrics: {', '.join(newly_found)}")
        else:
            print(f"   ✗ No sales data found")
        
        time.sleep(2)  # Rate limiting
    
    # Fill missing fields
    for field in missing_fields:
        aggregated_sales[field] = "Not Available"
        aggregated_sales[f"{field}_citation"] = {
            "source_url": "N/A",
            "citation_text": "Sales data not available from any source"
        }
    
    populated = len(sales_fields) - len(missing_fields)
    print(f"\n✓ Sales data complete: {populated}/{len(sales_fields)} fields populated")
    
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
        print(f"✓ CODE CAR detected with manual specs - SKIPPING web scraping")
        manually_provided = sum(1 for k, v in manual_specs.items() 
                               if v and not k.endswith('_citation') 
                               and k not in ['car_name', 'is_code_car', 'manual_entry', 'source_urls', 'left_blank'])
        
        print(f"✓ Using {manually_provided}/19 manually entered fields")
        
        # Fill any missing fields with "Not Available"
        for field in CAR_SPECS:
            if field not in manual_specs or not manual_specs[field]:
                manual_specs[field] = "Not Available"
                manual_specs[f"{field}_citation"] = {
                    "source_url": "Manual User Input",
                    "citation_text": "User skipped this specification during manual entry"
                }
        
        print(f"✓ CODE CAR processing complete: {manually_provided} provided, {19-manually_provided} marked as N/A")
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
        print(f"\n✓ {car}: {populated}/{len(CAR_SPECS)} fields populated")
        
    
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


def _generate_citations_html(comparison_data: Dict[str, Any]) -> str:
    """Generate HTML for citations section."""
    citations_html = ""
    
    for car_name, car_data in comparison_data.items():
        if "error" in car_data:
            continue
            
        citations_html += f"""
        <div class="citation-card animate-on-scroll">
            <h3 class="citation-car-name">{car_data.get('car_name', car_name).upper()}</h3>
            <div class="citation-items">
        """
        
        # Get all citation fields
        citation_fields = [
            # Original 19 specs
            ("price_range", "Price Range"),
            ("mileage", "Mileage"),
            ("user_rating", "User Rating"),
            ("seating_capacity", "Seating Capacity"),
            ("braking", "Braking"),
            ("steering", "Steering"),
            ("climate_control", "Climate Control"),
            ("battery", "Battery"),
            ("transmission", "Transmission"),
            ("brakes", "Brakes"),
            ("wheels", "Wheels"),
            ("performance", "Performance"),
            ("body", "Body Type"),
            ("vehicle_safety_features", "Vehicle Safety Features"),
            ("lighting", "Lighting"),
            ("audio_system", "Audio System"),
            ("off_road", "Off-Road"),
            ("interior", "Interior"),
            ("seat", "Seat"),
            ("monthly_sales", "Monthly Sales"),
            
            # NEW: 72 Additional specs
            ("ride", "Ride"),
            ("performance_feel", "Performance Feel"),
            ("driveability", "Driveability"),
            ("manual_transmission_performance", "Manual Transmission Performance"),
            ("pedal_operation", "Pedal Operation"),
            ("automatic_transmission_performance", "Automatic Transmission Performance"),
            ("powertrain_nvh", "Powertrain NVH"),
            ("wind_nvh", "Wind NVH"),
            ("road_nvh", "Road NVH"),
            ("visibility", "Visibility"),
            ("seats_restraint", "Seats Restraint"),
            ("impact", "Impact"),
            ("seat_cushion", "Seat Cushion"),
            ("turning_radius", "Turning Radius"),
            ("epb", "Electronic Parking Brake"),
            ("brake_performance", "Brake Performance"),
            ("stiff_on_pot_holes", "Stiff on Pot Holes"),
            ("bumps", "Bumps"),
            ("jerks", "Jerks"),
            ("pulsation", "Pulsation"),
            ("stability", "Stability"),
            ("shakes", "Shakes"),
            ("shudder", "Shudder"),
            ("shocks", "Shocks"),
            ("grabby", "Grabby"),
            ("spongy", "Spongy"),
            ("telescopic_steering", "Telescopic Steering"),
            ("torque", "Torque"),
            ("nvh", "NVH"),
            ("wind_noise", "Wind Noise"),
            ("tire_noise", "Tire Noise"),
            ("crawl", "Crawl"),
            ("gear_shift", "Gear Shift"),
            ("pedal_travel", "Pedal Travel"),
            ("gear_selection", "Gear Selection"),
            ("turbo_noise", "Turbo Noise"),
            ("resolution", "Resolution"),
            ("touch_response", "Touch Response"),
            ("button", "Button"),
            ("apple_carplay", "Apple CarPlay"),
            ("digital_display", "Digital Display"),
            ("blower_noise", "Blower Noise"),
            ("soft_trims", "Soft Trims"),
            ("armrest", "Armrest"),
            ("sunroof", "Sunroof"),
            ("irvm", "IRVM"),
            ("orvm", "ORVM"),
            ("window", "Window"),
            ("alloy_wheel", "Alloy Wheel"),
            ("tail_lamp", "Tail Lamp"),
            ("boot_space", "Boot Space"),
            ("led", "LED"),
            ("drl", "DRL"),
            ("ride_quality", "Ride Quality"),
            ("infotainment_screen", "Infotainment Screen"),
            ("chasis", "Chassis"),
            ("straight_ahead_stability", "Straight Ahead Stability"),
            ("wheelbase", "Wheelbase"),
            ("egress", "Egress"),
            ("ingress", "Ingress"),
            ("corner_stability", "Corner Stability"),
            ("parking", "Parking"),
            ("manoeuvring", "Manoeuvring"),
            ("city_performance", "City Performance"),
            ("highway_performance", "Highway Performance"),
            ("wiper_control", "Wiper Control"),
            ("sensitivity", "Sensitivity"),
            ("rattle", "Rattle"),
            ("headrest", "Headrest"),
            ("acceleration", "Acceleration"),
            ("response", "Response"),
            ("door_effort", "Door Effort"),
            ("review_ride_handling", "Review: Ride & Handling"),
    ("review_steering", "Review: Steering"),
    ("review_braking", "Review: Braking"),
    ("review_performance", "Review: Performance"),
    ("review_4x4_operation", "Review: 4x4 Operation"),
    ("review_nvh", "Review: NVH"),
    ("review_gsq", "Review: GSQ")
        ]
        
        for field, field_display in citation_fields:
            citation_key = f"{field}_citation"
            if citation_key in car_data and car_data[citation_key]:
                citation = car_data[citation_key]
                
                if isinstance(citation, dict):
                    source_url = citation.get('source_url', 'Unknown')
                    citation_text = citation.get('citation_text', 'No citation available')
                else:
                    source_url = car_data.get('source_urls', ['Unknown'])[0] if 'source_urls' in car_data else 'Unknown'
                    citation_text = citation
                
                # Update display for RAG sources
                if "RAG Corpus" in str(source_url):
                    source_url = "RAG Engine"
                    citation_text = f"Retrieved from RAG Engine: {citation_text}"
                
                citations_html += f"""
                <div class="citation-item">
                    <div class="citation-field-name">{field_display}</div>
                    <div class="citation-text">&nbsp;</div>
                    <a href="{source_url}" target="_blank" class="citation-link">
                        {source_url}
                    </a>
                </div>
                """
        
        citations_html += """
            </div>
        </div>
        """
    
    return citations_html



def _generate_consolidated_review_html(comparison_data: Dict[str, Any]) -> str:
    """
    Generate consolidated review summary table from scraped review data.
    Now uses the actual review fields fetched from CardDekho and Custom Search.
    Includes expandable "Read more" feature for long reviews (>50 words or >300 chars).
    """
    
    # Extract car names from comparison data
    car_names = list(comparison_data.keys())
    
    # Define review categories mapped to the NEW review fields
    review_categories = [
        ("Ride & Handling", "review_ride_handling"),
        ("Steering", "review_steering"),
        ("Braking", "review_braking"),
        ("Performance & Drivability", "review_performance"),
        ("4x4 Operation", "review_4x4_operation"),
        ("NVH", "review_nvh"),
        ("GSQ", "review_gsq")
    ]
    
    # Helper function to count words
    def count_words(text: str) -> int:
        return len(str(text).split())
    
    # Helper function to count characters
    def count_chars(text: str) -> int:
        return len(str(text))
    
    WORD_THRESHOLD = 50  
    CHAR_THRESHOLD = 200  
    
    
    num_cars = len(car_names)
    category_width = 20  # 20% for category column
    car_column_width = (100 - category_width) / num_cars

    review_html = f"""
    <div class="review-table-container animate-on-scroll">
        <table class="review-table">
            <thead>
                <tr>
                    <th style="width: {category_width}%;">Category</th>
    """

    # Add column headers for each car with equal widths
    for car_name in car_names:
        review_html += f'<th style="width: {car_column_width}%;">{car_name.upper()}</th>'
    
    review_html += """
                </tr>
            </thead>
            <tbody>
    """
    
    # Add rows for each review category
    for category_name, field_key in review_categories:
        review_html += f"""
            <tr>
                <td class="review-category">{category_name}:</td>
        """
        
        for car_name in car_names:
            car_data = comparison_data[car_name]
            
            # Get the review field value
            field_value = car_data.get(field_key, "Not Available")
            
            if field_value and field_value != "Not Available":
                display_value = str(field_value)
                word_count = count_words(display_value)
                char_count = count_chars(display_value)
                
                review_html += "<td>"
                
                # Apply expandable content if text is long (>50 words OR >300 chars)
                if word_count > WORD_THRESHOLD or char_count > CHAR_THRESHOLD:
                    review_html += f'<div class="expandable-content">{display_value}</div>'
                    review_html += '<button onclick="toggleExpand(this)" class="read-more-btn">Read more</button>'
                else:
                    review_html += display_value
                
                review_html += "</td>"
            else:
                review_html += '<td style="color: #6c757d; font-style: italic;">Review not available</td>'
        
        review_html += '</tr>\n'
    
    review_html += """
            </tbody>
        </table>
    </div>
    """
    
    return review_html


def create_comparison_chart_html(comparison_data: Dict[str, Any], summary: str) -> str:
    """
    Create interactive HTML report with enhanced design featuring grouped specifications.
    Specifications are grouped into collapsible accordions for better readability.
    Optimized for PDF printing with proper page breaks and layout.
    
    Features:
    - Grouped specification table with accordion functionality
    - Sticky header with smooth-scrolling navigation
    - Professional section headers with icons
    - Alternating color charts (dark blue and Mahindra red)
    - Scroll animations for all components
    - PDF-optimized printing (2 charts per page, landscape table)
    
    Args:
        comparison_data: Dictionary containing car comparison data
        summary: Text summary of the comparison
        
    Returns:
        Complete HTML string ready to be saved as a file
    """
    
    # Helper function for summary formatting
    def format_summary(summary_text: str) -> str:
        """Format summary with bold text preserved and clean bullet points"""
        processed_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', summary_text)
        processed_text = processed_text.replace('\n', '<br>').replace('*','•')
        return processed_text

    # Data Extraction
    cars, prices, mileages, ratings, seating ,sales_volumes = [], [], [], [], [],[]
    for car_name, car_data in comparison_data.items():
        if "error" not in car_data or car_data.get("price_range") != "Not Available":
            cars.append(car_data.get("car_name", car_name))
            try:
                price_str = car_data.get("price_range", "0")
                price_str = price_str.replace('₹', '').replace('Rs.', '').replace('Rs', '').replace('Lakh', '').replace('lakh', '').strip()                

                if '-' in price_str or ' to ' in price_str:
                    
                    parts = price_str.replace(' to ', '-').split('-')

                    if len(parts) >= 2:
                        # Extract min and max values
                        min_price = ''.join(c for c in parts[0].strip() if c.isdigit() or c == '.')
                        max_price = ''.join(c for c in parts[1].strip().split()[0] if c.isdigit() or c == '.')
                        
                        if min_price and max_price:
                            # Calculate average (middle value)
                            avg_price = (float(min_price) + float(max_price)) / 2
                            prices.append(avg_price)
                        elif min_price:
                            prices.append(float(min_price))
                        else:
                            prices.append(0)
                    
                    else:
                        price_clean = ''.join(c for c in parts[0] if c.isdigit() or c == '.')
                        prices.append(float(price_clean) if price_clean else 0)
                
                else:
                    # Single value (no range)
                    price_part = price_str.split('onwards')[0].strip()
                    price_clean = ''.join(c for c in price_part if c.isdigit() or c == '.')
                    prices.append(float(price_clean) if price_clean else 0)
            
            except: 
                prices.append(0)
            
            try:
                mileage_str = car_data.get("mileage", "0")
                # Skip if it's EV range (contains 'km/charge' or 'charge')
                if 'charge' in mileage_str.lower() or 'range' in mileage_str.lower():
                    mileages.append(0)
                
                else:
                    # Remove 'kmpl' and clean
                    mileage_str = mileage_str.replace('kmpl', '').strip()
                    
                    # Check if it's a range (contains '-' or 'to')
                    if ' to ' in mileage_str or '-' in mileage_str:
                        parts = mileage_str.replace(' to ', '-').split('-')
                        
                        if len(parts) >= 2:
                            min_mileage = ''.join(c for c in parts[0].strip() if c.isdigit() or c == '.')
                            max_mileage = ''.join(c for c in parts[1].strip() if c.isdigit() or c == '.')
                            
                            if min_mileage and max_mileage:
                                avg_mileage = (float(min_mileage) + float(max_mileage)) / 2
                                if avg_mileage > 50:
                                    avg_mileage = 0
                                mileages.append(avg_mileage)
                            elif min_mileage:
                                mileages.append(float(min_mileage) if float(min_mileage) <= 50 else 0)
                            else:
                                mileages.append(0)
                        
                        else:
                            mileage_clean = ''.join(c for c in parts[0] if c.isdigit() or c == '.')
                            mileage_value = float(mileage_clean) if mileage_clean else 0
                            mileages.append(mileage_value if mileage_value <= 50 else 0)
                    
                    else:
                        # Single value
                        mileage_clean = ''.join(c for c in mileage_str if c.isdigit() or c == '.')
                        mileage_value = float(mileage_clean) if mileage_clean else 0
                        mileages.append(mileage_value if mileage_value <= 50 else 0)
            
            except: 
                mileages.append(0)
            
            
            try:
                rating_str = car_data.get("user_rating", "0")
                rating_part = rating_str.split('/')[0].split('out')[0].strip()
                rating_clean = ''.join(c for c in rating_part if c.isdigit() or c == '.')
                ratings.append(float(rating_clean) if rating_clean else 0)
            except: ratings.append(0)
            
            try:
                seating_str = car_data.get("seating_capacity", "0")
                first_part = seating_str.split('-')[0].split('to')[0].split('and')[0].strip()
                seating_clean = ''.join(filter(str.isdigit, first_part.split()[0]))
                seating.append(int(seating_clean) if seating_clean else 0)
            except: seating.append(0)
            
            try:
                sales_str = car_data.get("monthly_sales", "0")
                sales_str = sales_str.lower().replace('units', '').replace('approximately', '').replace('around', '').replace('between', '')
                if ' to ' in sales_str or '-' in sales_str or ' and ' in sales_str:
                    parts = sales_str.replace(' to ', '|').replace('-', '|').replace(' and ', '|').split('|')
                    sales_str = parts[0].strip()
                sales_str = sales_str.replace(',', '')
                sales_clean = ''.join(filter(str.isdigit, sales_str))
                sales_value = int(sales_clean) if sales_clean else 0

                if sales_value > 50000: sales_value = 0
                sales_volumes.append(sales_value)
            
            except Exception as e:
                sales_volumes.append(0)

    formatted_summary = format_summary(summary)
    citations_html = _generate_citations_html(comparison_data)
    

    def count_words(text: str) -> int:
        return len(str(text).split())
    
    WORD_THRESHOLD = 12

    # Build table with grouped accordion structure
    features_table = "<table><thead><tr><th>Specification</th>"
    for car_name in cars:
        features_table += f"<th>{car_name.upper()}</th>"
    features_table += "</tr></thead><tbody id=\"specifications-tbody\">"

    spec_groups = {
    "Key Specifications": {
        "": [  # Empty string means no accordion, direct rows
            ("Price Range", "price_range"),
            ("Monthly Sales", "monthly_sales"),
            ("Mileage", "mileage"),
            ("User Rating", "user_rating"),
            ("Seating Capacity", "seating_capacity"),
        ]
    },
    "Specifications": {
        "Engine & Transmission": [
            ("Performance", "performance"),
            ("Acceleration", "acceleration"),
            ("Torque", "torque"),
            ("Driveability", "driveability"),
            ("Response", "response"),
            ("Transmission", "transmission"),
            ("Manual Transmission Performance", "manual_transmission_performance"),
            ("Automatic Transmission Performance", "automatic_transmission_performance"),
            ("Gear Shift", "gear_shift"),
            ("Gear Selection", "gear_selection"),
            ("Pedal Operation", "pedal_operation"),
            ("Pedal Travel", "pedal_travel"),
            ("Turbo Noise", "turbo_noise"),
            ("Powertrain NVH", "powertrain_nvh"),
            ("Crawl", "crawl"),
            ("Performance Feel", "performance_feel"),
            ("City Performance", "city_performance"),
            ("Highway Performance", "highway_performance"),
        ],
        "Dimensions & Weight": [
            ("Turning Radius", "turning_radius"),
            ("Body Type", "body"),
            ("Wheelbase", "wheelbase"),
            ("Chassis", "chasis"),
        ],
        "Capacity & Space": [
            ("Boot Space", "boot_space"),
            ("Egress", "egress"),
            ("Ingress", "ingress"),
        ],
        "Suspensions, Brakes, Steering & Tyres": [
            ("Ride", "ride"),
            ("Ride Quality", "ride_quality"),
            ("Stiff on Pot Holes", "stiff_on_pot_holes"),
            ("Bumps", "bumps"),
            ("Jerks", "jerks"),
            ("Shocks", "shocks"),
            ("Stability", "stability"),
            ("Straight Ahead Stability", "straight_ahead_stability"),
            ("Corner Stability", "corner_stability"),
            ("Shakes", "shakes"),
            ("Shudder", "shudder"),
            ("Pulsation", "pulsation"),
            ("Braking", "braking"),
            ("Brake Performance", "brake_performance"),
            ("Brakes", "brakes"),
            ("Electronic Parking Brake", "epb"),
            ("Grabby", "grabby"),
            ("Spongy", "spongy"),
            ("Steering", "steering"),
            ("Telescopic Steering", "telescopic_steering"),
            ("Sensitivity", "sensitivity"),
            ("Wheels", "wheels"),
            ("Alloy Wheel", "alloy_wheel"),
        ],
        "NVH (Noise, Vibration, Harshness)": [
            ("NVH", "nvh"),
            ("Wind NVH", "wind_nvh"),
            ("Road NVH", "road_nvh"),
            ("Wind Noise", "wind_noise"),
            ("Tire Noise", "tire_noise"),
            ("Blower Noise", "blower_noise"),
            ("Rattle", "rattle"),
        ],
        "Parking & Manoeuvring": [
            ("Parking", "parking"),
            ("Manoeuvring", "manoeuvring"),
        ],
        "Electric Motor & Battery": [
            ("Battery", "battery"),
        ],
    },
    "Features": {
        "Exterior": [
            ("Sunroof", "sunroof"),
            ("Lighting", "lighting"),
            ("LED", "led"),
            ("DRL", "drl"),
            ("Tail Lamp", "tail_lamp"),
            ("ORVM", "orvm"),
            ("Window", "window"),
            ("Door Effort", "door_effort"),
        ],
        "Safety & Impact": [
            ("Vehicle Safety Features", "vehicle_safety_features"),
            ("Impact", "impact"),
            ("Seats Restraint", "seats_restraint"),
            ("Seat Cushion", "seat_cushion"),
            ("Headrest", "headrest"),
        ],
        "Comfort & Convenience": [
            ("Interior", "interior"),
            ("Seat", "seat"),
            ("Soft Trims", "soft_trims"),
            ("Armrest", "armrest"),
            ("IRVM", "irvm"),
            ("Climate Control", "climate_control"),
        ],
        "Infotainment & Connectivity": [
            ("Infotainment Screen", "infotainment_screen"),
            ("Resolution", "resolution"),
            ("Touch Response", "touch_response"),
            ("Audio System", "audio_system"),
            ("Button", "button"),
            ("Apple CarPlay", "apple_carplay"),
            ("Digital Display", "digital_display"),
        ],
        "Visibility & Controls": [
            ("Visibility", "visibility"),
            ("Wiper Control", "wiper_control"),
        ],
        "Off-Road": [
            ("Off-Road", "off_road"),
        ],
    }
}

    # REPLACEMENT FOR THE TABLE GENERATION LOOP
    for main_group_title, sub_groups in spec_groups.items():
    # Add a non-collapsible main heading for the entire section
        features_table += f"""
        <tr class="main-group-header">
            <td>{main_group_title}</td>
        """

        # Add empty cells for car columns
        for _ in cars:
            features_table += "<td></td>"

        features_table += "</tr>\n"
        
        for group_name, specifications in sub_groups.items():
            # Check if any car has a value for any spec in this sub-group
            group_has_data = any(
                comparison_data[car_name].get(key) not in [None, 'N/A', '']
                for _, key in specifications
                for car_name in cars
            )
            if not group_has_data:
                continue  # Skip rendering empty accordion groups

            # Special handling for Key Specifications (no accordion)
            if main_group_title == "Key Specifications":
                # Render specs directly without accordion header
                for label, key in specifications:
                    features_table += f"<tr class='spec-row'><td>{label}</td>"

                    for car_name, car_data in comparison_data.items():
                        
                        if "error" not in car_data or car_data.get("price_range") != "Not Available":
                            value = car_data.get(key, 'N/A')
                            display_value = ", ".join(value) if isinstance(value, list) else str(value or 'N/A')
                            word_count = count_words(display_value)
                            
                            features_table += "<td>"
                            
                            if word_count > WORD_THRESHOLD:
                                features_table += f'<div class="expandable-content">{display_value}</div>'
                                features_table += '<button onclick="toggleExpand(this)" class="read-more-btn">Read more</button>'
                            
                            else:
                                features_table += display_value
                            features_table += "</td>"
                    features_table += "</tr>"
            
            else:
                # Regular accordion rendering for other groups
                features_table += f"""
                    <tr class="accordion-header" onclick="toggleAccordion(this)">
                    <td class="accordion-title-cell">
                        {group_name}
                    </td>
                """

                # Add empty cells for car columns (except the last one)
                for i in range(len(cars)):

                    if i == len(cars) - 1:
                        # Last column gets the arrow icon
                        features_table += """
                    <td class='accordion-empty-cell accordion-icon-cell'>
                        <span class="accordion-icon"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z"/></svg></span>
                    </td>
                """
                    
                    else:
                        features_table += "<td class='accordion-empty-cell'></td>\n"

                features_table += "</tr>\n"
                
                for label, key in specifications:
                    features_table += f"<tr class='spec-row hidden-spec'><td>{label}</td>"
                    
                    for car_name, car_data in comparison_data.items():
                        
                        if "error" not in car_data or car_data.get("price_range") != "Not Available":
                            value = car_data.get(key, 'N/A')
                            display_value = ", ".join(value) if isinstance(value, list) else str(value or 'N/A')
                            word_count = count_words(display_value)
                            
                            features_table += "<td>"
                            if word_count > WORD_THRESHOLD:
                                features_table += f'<div class="expandable-content">{display_value}</div>'
                                features_table += '<button onclick="toggleExpand(this)" class="read-more-btn">Read more</button>'
                            else:
                                features_table += display_value
                            features_table += "</td>"
                    features_table += "</tr>"

    features_table += "</tbody></table>"

    # The rest of the HTML template 
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>Car Comparison Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{ font-family: 'Poppins', sans-serif; background: #f8f9fa; color: #212529; }}
        .container {{ max-width: 100%; margin: 0 auto; background: white; overflow: hidden; }}
        .site-header {{ display: flex; justify-content: space-between; align-items: center; padding: 16px 40px; background: #fff; border-bottom: 1px solid #e9ecef; width: 100%; position: sticky; top: 0; z-index: 1000; }}
        .logo {{ height: 22px; width: auto; }}
        .header-actions {{ display: flex; align-items: center; gap: 30px; }}
        .main-nav {{ display: flex; gap: 25px; }}
        .main-nav a {{ text-decoration: none; color: #212529; font-size: 14px; font-weight: 500; transition: color 0.2s ease-in-out; }}
        .main-nav a:hover {{ color: #dd032b; }}
        .main-group-header td {{
            font-size: 22px;
            font-weight: 700;
            color: #1c2a39;
            padding-top: 40px !important;
            padding-bottom: 10px !important;
            border-bottom: none !important;
            background: #fff;
            text-align: left;
        }}

        .main-group-header td:not(:first-child) {{
            background: #fff;
        }}
        #comparison-section, #analytics-section, #summary-section {{ scroll-margin-top: 90px; }}
        .print-btn {{ background: transparent; color: #333; padding: 8px 12px; border: 1px solid #ced4da; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s ease; display: flex; align-items: center; gap: 8px; }}
        .print-btn:hover {{ color: #dd032b; border-color: #dd032b; background-color: #fff5f7; }}
        .content {{ padding: 50px 60px; }}
        .section-header {{ display: flex; align-items: center; gap: 15px; margin-bottom: 25px; }}
        .section-header .icon-wrapper {{ flex-shrink: 0; width: 50px; height: 50px; border-radius: 50%; background-color: white; border: 1px solid #fccad4; display: flex; align-items: center; justify-content: center; }}
        .section-header .icon-wrapper svg {{ width: 24px; height: 24px; stroke: #dd032b; stroke-width: 2; }}
        .section-header h2 {{ font-size: 24px; font-weight: 600; color: #1c2a39; }}
        .summary, .chart-container {{ background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); border: 1px solid #e9ecef; }}
        .summary p {{ line-height: 1.8; font-size: 14px; color: #495057; }}
        .summary strong {{ font-weight: 600; color: #212529; }}
        .charts-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 25px; margin-bottom: 40px; }}
        .chart-container h3 {{ color: #212529; margin-bottom: 20px; text-align: center; font-size: 16px; font-weight: 600; }}
        .chart-container:nth-child(2) {{ page-break-after: always; }}
        .chart-container {{ page-break-inside: avoid; }}
        .chart-container canvas {{
            max-width: 100% !important;
            height: auto !important;
            display: block;
        }}

        .charts-grid {{
            width: 100%;
            overflow: hidden;
        }}

        .chart-container {{
            width: 100%;
            overflow: hidden;
            position: relative;
        }}
        
        /* Sales Chart Container Fix */
        .chart-container:has(#salesChart) {{
            position: relative;
            height: 450px;
        }}

        .chart-container:has(#salesChart) canvas {{
            position: absolute;
            left: 0;
            top: 0;
            width: 100% !important;
            height: 100% !important;
        }}
        
        .table-container {{ overflow-x: auto; margin-top: 24px; border-radius: 12px; background: white; border: 1px solid #e9ecef; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05); position: relative; }}
        .table-filter-wrapper {{ padding: 20px 20px 0 20px; background: #f8f9fa; border-bottom: 1px solid #e9ecef; position: sticky; top: 0; left: 0; z-index: 10; width: 100%; }}
        .filter-input-group {{ position: relative; display: flex; align-items: center; margin-bottom: 12px; }}
        .filter-icon {{ position: absolute; left: 16px; width: 18px; height: 18px; stroke: #6c757d; pointer-events: none; }}
        .filter-input {{ width: 100%; padding: 12px 45px 12px 45px; border: 2px solid #e9ecef; border-radius: 8px; font-size: 14px; font-family: 'Poppins', sans-serif; transition: all 0.2s ease; background: white; }}
        .filter-input:focus {{ outline: none; border-color: #e9ecef; box-shadow: 0 0 0 3px rgba(221, 3, 43, 0.1); }}
        .filter-clear-btn {{ position: absolute; right: 12px; width: 28px; height: 28px; border: none; background: #e9ecef; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s ease; padding: 0; }}
        .filter-clear-btn:hover {{ background: #dd032b; }}
        .filter-clear-btn:hover svg {{ stroke: white; }}
        .filter-clear-btn svg {{ width: 14px; height: 14px; stroke: #6c757d; transition: stroke 0.2s ease; }}
        .filter-results-info {{ font-size: 13px; color: #6c757d; padding: 0 4px 12px 4px; font-weight: 500; }}
        .filter-results-info.no-results {{ color: #dd032b; }}
        table {{ font-size: 13px; width: 100%; border-collapse: collapse; color: #212529; }}
        table th, table td {{ padding: 16px 14px; border-bottom: 1px solid #e9ecef; }}
        table th {{ background: #ffffff !important; color: #212529 !important; text-align: center; font-weight: 600; border-bottom: 2px solid #dee2e6; }}
        table th:first-child {{ text-align: left; }}
        tbody td {{ text-align: center; vertical-align: middle; }}
        tbody td:first-child {{ font-weight: 600; text-align: left; vertical-align: top; }}
        .read-more-btn {{ background: none; border: none; color: black; text-decoration: underline; cursor: pointer; padding: 4px 0; font-size: 12px; font-weight: 600; }}
        .expandable-content {{ display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; transition: -webkit-line-clamp 0.3s ease; }}
        .expandable-content.expanded {{ -webkit-line-clamp: 50; }}
        .accordion-header {{ background: #f8f9fa; cursor: pointer; transition: background 0.2s ease; user-select: none; }}
        .accordion-header:hover {{ background: #e9ecef; }}
        .accordion-header td {{ padding: 12px 14px !important; font-weight: 700; color: #1c2a39; border-bottom: 2px solid #dee2e6 !important; }}
        .accordion-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 24px; 
            font-weight: 300; 
            line-height: 1; 
            transition: transform 0.3s ease; 
        }}
        .accordion-header.active .accordion-icon {{ transform: rotate(180deg); }}
        .accordion-icon-cell {{
            text-align: right !important;
            vertical-align: middle !important;
        }}
        .hidden-spec {{ display: none; }}
        .spec-row td {{ background: #fff; }}
        .animate-on-scroll {{ opacity: 0; transform: translateY(30px); transition: opacity 0.6s ease-out, transform 0.6s ease-out; }}
        .animate-on-scroll.is-visible {{ opacity: 1; transform: translateY(0); }}
        #salesChart {{ min-height: 400px !important; }}
        .chart-container:has(#salesChart) {{ grid-column: 1 / -1; page-break-before: always; }}
        .footer {{ background: #dd032b; padding: 20px 60px; display: flex; align-items: center; justify-content: center; gap: 12px; border-top: none; }}
        .footer .logo {{ height: 24px; width: auto; }}
        .footer span {{ color: white; font-size: 13px; font-weight: 400; }}
        /* Consolidated Review Table Styles */
.review-table-container {{
    background: white;
    padding: 30px;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
    border: 1px solid #e9ecef;
    overflow-x: auto;
    margin-top: 30px;
}}

.review-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    table-layout: fixed;
}}

.review-table th {{
    background: #2E3B4E !important;
    color: white !important;
    padding: 16px 14px;
    text-align: center;
    font-weight: 600;
    border: 1px solid #dee2e6;
    font-size: 14px;
}}

.review-table th:first-child {{
    background: #dd032b !important;
    text-align: left;
}}

.review-table td {{
    padding: 16px 14px;
    border: 1px solid #dee2e6;
    vertical-align: top;
    text-align: left;
    line-height: 1.8;
}}

.review-table td:first-child {{
    font-weight: 700;
    background: #f8f9fa;
    color: #1c2a39;
    font-size: 13px;
}}

.review-table .review-negative {{
    color: #000000;
    font-weight: 600;
}}
.review-table .review-category {{
    font-weight: 700;
    color: #212529;
}}
.review-table .expandable-content {{
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    overflow: hidden;
    transition: -webkit-line-clamp 0.3s ease;
    text-overflow: ellipsis; /* Ensure ellipsis is shown */
}}
.review-table .expandable-content.expanded {{
    -webkit-line-clamp: 50;
}}

.review-table .read-more-btn {{
    background: none;
    border: none;
    color: black;
    text-decoration: underline;
    cursor: pointer;
    padding: 4px 0;
    font-size: 12px;
    font-weight: 600;
    margin-top: 4px;
}}

.review-table .read-more-btn:hover {{
    color: #dd032b;
}}

        
        /* Citations Section Styles */
        .citations-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
        }}
        
        .citation-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #e9ecef;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        }}
        
        .citation-car-name {{
            font-size: 20px;
            font-weight: 700;
            color: #212529;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #212529;
        }}
        
        .citation-items {{
            display: flex;
            flex-direction: column;
            gap: 15px;
            max-height: 600px;
            overflow-y: auto;
        }}
        
        .citation-item {{
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 3px solid #dd032b;
        }}
        
        .citation-field-name {{
            font-size: 12px;
            font-weight: 600;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        
        .citation-link {{
            font-size: 12px;
            color: #212529;
            text-decoration: none;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            transition: color 0.2s ease;
        }}
        
        .citation-link:hover {{
            color: #dd032b;
            text-decoration: underline;
        }}
        
       
      @media print {{
    #citations-section, #citations-toggle, .site-header, .print-btn, .main-nav, .table-filter-wrapper, .read-more-btn {{ display: none !important; }}
    
    @page {{ 
        size: A4 landscape; 
        margin: 10mm; 
    }}
    
    * {{
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
        color-adjust: exact !important;
    }}
    
    /* BASE FONT RESET */
    html {{
        font-size: 10px !important;
    }}
    
    body {{
        font-size: 10px !important;
        line-height: 1.4 !important;
        font-family: 'Poppins', Arial, sans-serif !important;
    }}
    
    .animate-on-scroll {{ opacity: 1 !important; transform: none !important; }}
    .filtered-row {{ display: table-row !important; }}
    .expandable-content {{ display: block !important; -webkit-line-clamp: unset !important; overflow: visible !important; }}
    
    .container {{ max-width: 100%; background: white; box-shadow: none; }}
    .content {{ padding: 15px 8px; page-break-inside: avoid; }}
    
    .section-header {{ margin-bottom: 12px; page-break-after: avoid; }}
    .section-header h2 {{ font-size: 16px !important; line-height: 1.3 !important; }}
    .section-header .icon-wrapper {{ display: none; }}
    
    /* OPTIMIZED TABLE STYLES */
    .table-container {{ 
        overflow: visible !important; 
        border-radius: 0; 
        box-shadow: none; 
        page-break-inside: auto; 
        margin-top: 8px; 
        width: 100%;
    }}
    
    table {{ 
        font-size: 10px !important; 
        line-height: 1.4 !important;
        width: 100% !important; 
        page-break-inside: auto; 
        border-collapse: collapse !important;
        table-layout: fixed !important;
    }}
    
    table th, table td {{ 
        padding: 8px 6px !important; 
        border: 1px solid #333 !important; 
        font-size: 10px !important;
        line-height: 1.4 !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        word-break: break-word !important;
        vertical-align: top !important;
        hyphens: auto !important;
        -webkit-hyphens: auto !important;
        -ms-hyphens: auto !important;
    }}
    
    table th {{ 
        background: #e9ecef !important; 
        color: #000 !important; 
        font-size: 11px !important; 
        font-weight: 700 !important;
        text-align: center !important;
        line-height: 1.3 !important;
        padding: 10px 6px !important;
    }}
    
    table th:first-child {{ 
        background: #6c757d !important; 
        color: white !important;
        text-align: left !important;
        width: 180px !important;
        min-width: 180px !important;
        max-width: 180px !important;
        font-size: 11px !important;
    }}
    
    table tr {{ 
        page-break-inside: avoid !important;
    }}
    
    tbody td {{ 
        font-size: 10px !important;
        line-height: 1.4 !important;
        padding: 8px 6px !important;
    }}
    
    tbody td:first-child {{ 
        font-weight: 700; 
        font-size: 10px !important;
        background: #f8f9fa !important;
        text-align: left !important;
        width: 180px !important;
        min-width: 180px !important;
        max-width: 180px !important;
        line-height: 1.3 !important;
    }}
    
    tbody td:not(:first-child) {{
        text-align: center !important;
        font-size: 10px !important;
        font-weight: 400 !important;
    }}
    
    /* Long text handling */
    tbody td {{
        white-space: normal !important;
        overflow: visible !important;
    }}
    
    /* Hide empty cells/rows */
    tbody tr:has(td:nth-child(2):empty):has(td:nth-child(3):empty):not(.spec-row) {{
        display: none !important;
    }}
    
    /* Accordion Headers */
    .accordion-header {{ 
        display: table-row !important; 
        background: #dee2e6 !important; 
        page-break-after: avoid !important;
    }}
    
    .accordion-header td {{ 
        font-size: 11px !important; 
        font-weight: 700 !important;
        padding: 10px 6px !important;
        border: 1px solid #333 !important;
        line-height: 1.3 !important;
    }}
    
    .accordion-header td:not(:first-child):empty {{
        display: none !important;
    }}
    
    .accordion-icon {{ display: none !important; }}
    
    .accordion-title-cell {{
        padding: 10px 6px !important;
        font-weight: 700;
        font-size: 11px !important;
        color: #000 !important;
        border: 1px solid #333 !important;
        background: #dee2e6 !important;
        text-align: left !important;
        line-height: 1.3 !important;
    }}

    .accordion-empty-cell {{
        background: #dee2e6 !important;
        border: 1px solid #333 !important;
        padding: 10px 6px !important;
    }}

    /* Main Group Headers */
    .main-group-header td {{
        font-size: 12px !important;
        font-weight: 700 !important;
        line-height: 1.3 !important;
        color: #000 !important;
        padding: 12px 6px !important;
        background: #f8f9fa !important;
        border: 1px solid #333 !important;
        text-align: left !important;
    }}

    .spec-row td {{
        background: #fff !important;
    }}
    
    .hidden-spec {{ display: table-row !important; }}
    
    /* Review Table */
    .review-table-container {{
        page-break-inside: avoid !important;
        padding: 12px !important;
        margin-top: 15px;
        box-shadow: none !important;
        border-radius: 0;
        overflow: visible !important;
    }}
    
    .review-table {{
        font-size: 10px !important;
        line-height: 1.4 !important;
        page-break-inside: avoid !important;
        table-layout: fixed !important;
        width: 100% !important;
        border-collapse: collapse !important;
    }}

    .review-table th, .review-table td {{
        padding: 8px 6px !important;
        font-size: 10px !important;
        line-height: 1.4 !important;
        border: 1px solid #333 !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
        word-break: break-word !important;
        vertical-align: top !important;
        hyphens: auto !important;
        -webkit-hyphens: auto !important;
        -ms-hyphens: auto !important;
        white-space: normal !important;
        overflow: visible !important;
    }}

    .review-table th {{
        background: #e9ecef !important;
        color: #000 !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        text-align: center !important;
        line-height: 1.3 !important;
        padding: 10px 6px !important;
    }}
    
    .review-table th:first-child {{
        background: #adb5bd !important;
        color: #000 !important;
        text-align: left !important;
        width: 180px !important;
        min-width: 180px !important;
        max-width: 180px !important;
        font-size: 11px !important;
    }}
    
    .review-table td:first-child {{
        font-size: 11px !important;
        background: #f8f9fa !important;
        width: 180px !important;
        min-width: 180px !important;
        max-width: 180px !important;
        font-weight: 700 !important;
        text-align: left !important;
        line-height: 1.3 !important;
    }}
    
    .review-table td:not(:first-child) {{
        text-align: left !important;
        font-size: 10px !important;
        font-weight: 400 !important;
        line-height: 1.4 !important;
    }}
    
    .review-table tr {{
        page-break-inside: avoid !important;
    }}
    
    .review-table .review-category {{
        font-weight: 700 !important;
        color: #000 !important;
    }}
    
    /* Hide Read More buttons in print */
    .review-table .read-more-btn {{
        display: none !important;
    }}
    
    /* Expand all content in print */
    .review-table .expandable-content {{
        display: block !important;
        -webkit-line-clamp: unset !important;
        overflow: visible !important;
    }}
    
    .review-table .expandable-content.expanded {{
        -webkit-line-clamp: unset !important;
    }}
    
    /* Charts */
    .charts-grid {{ 
        display: grid !important; 
        grid-template-columns: repeat(2, 1fr) !important; 
        gap: 12px !important; 
        margin-bottom: 0 !important; 
        page-break-inside: avoid; 
    }}
    
    .chart-container {{ 
        padding: 12px !important; 
        border: 1px solid #333 !important; 
        border-radius: 6px; 
        box-shadow: none !important; 
        page-break-inside: avoid !important; 
        break-inside: avoid !important; 
        margin-bottom: 8px; 
    }}
    
    .chart-container h3 {{ 
        font-size: 13px !important; 
        line-height: 1.3 !important;
        margin-bottom: 8px !important; 
    }}
    
    .chart-container:nth-child(2) {{ 
        page-break-after: always !important; 
        break-after: page !important; 
    }}
    
    canvas {{ 
        max-width: 100% !important; 
        height: auto !important; 
    }}
    
    /* Summary */
    .summary {{ 
        padding: 12px !important; 
        border: 1px solid #333 !important; 
        border-radius: 6px; 
        box-shadow: none !important; 
        page-break-inside: avoid; 
        font-size: 11px !important; 
        line-height: 1.5 !important;
    }}
    
    .summary p {{ 
        font-size: 11px !important; 
        line-height: 1.5 !important; 
    }}
    
    /* Footer */
    .footer {{ 
        page-break-before: avoid; 
        padding: 12px 15px !important; 
        margin-top: 15px; 
    }}
    
    .footer span {{ 
        font-size: 10px !important; 
    }}
    
    .footer .logo {{ 
        height: 18px !important; 
    }}
    
    h2, h3 {{ 
        page-break-after: avoid; 
        orphans: 3; 
        widows: 3; 
    }}
    
    /* Typography consistency */
    p, span, div, li {{
        font-size: 10px !important;
        line-height: 1.4 !important;
    }}
    
    strong, b {{
        font-weight: 700 !important;
    }}
}}
        /* Tablet Styles (1024px and below) */
        @media (max-width: 1024px) {{ 
            .charts-grid {{ 
                grid-template-columns: 1fr; 
            }} 
            
            .citations-grid {{
                grid-template-columns: 1fr;
            }}
            
            .main-nav {{ 
                gap: 15px; 
            }} 
            
            .main-nav a {{
                font-size: 13px;
            }}
            
            .content {{ 
                padding: 30px 40px; 
            }} 
            
            .site-header {{
                padding: 16px 30px;
            }}
            
            .footer {{
                padding: 20px 40px;
            }}
            
            table {{
                font-size: 12px;
            }}
            
            table th, table td {{
                padding: 12px 10px;
            }}
            
            .section-header h2 {{
                font-size: 22px;
            }}
            
            .chart-container {{
                padding: 25px;
            }}
            
            .chart-container h3 {{
                font-size: 15px;
            }}
        }}
        
        /* Mobile Styles (768px and below) */
        @media (max-width: 768px) {{ 
            .site-header {{ 
                padding: 12px 20px;
                flex-wrap: wrap;
                gap: 12px;
            }} 
            
            .logo {{
                height: 18px;
            }}
            .review-table {{
        font-size: 11px;
    }}
    
    .review-table th, .review-table td {{
        padding: 10px 8px;
    }}
            .header-actions {{
                width: 100%;
                justify-content: space-between;
                gap: 15px;
            }}
            
            .main-nav {{
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
            }}
            
            .main-nav a {{
                font-size: 12px;
                padding: 4px 8px;
            }}
            
            .print-btn {{
                font-size: 11px;
                padding: 6px 10px;
                gap: 4px;
            }}
            
            .content {{ 
                padding: 20px 15px; 
            }} 
            
            .section-header {{
                gap: 10px;
                margin-bottom: 20px;
            }}
            
            .section-header .icon-wrapper {{
                width: 40px;
                height: 40px;
            }}
            
            .section-header .icon-wrapper svg {{
                width: 20px;
                height: 20px;
            }}
            
            .section-header h2 {{ 
                font-size: 18px; 
            }} 
            
             .main-group-header td {{
                font-size: 16px !important;
                padding: 20px 8px 8px 8px !important;
                text-align: left !important;
                font-weight: 700 !important;
            }}
            
            .summary, .chart-container {{
                padding: 20px 15px;
                border-radius: 12px;
            }}
            
            .summary p {{
                font-size: 13px;
                line-height: 1.6;
            }}
            
            .charts-grid {{
                gap: 20px;
                margin-bottom: 30px;
            }}
            
            .chart-container {{
                padding: 15px 10px !important;
                width: 100%;
                overflow-x: hidden;
            }}
            
            .chart-container canvas {{
                width: 100% !important;
                max-width: 100% !important;
                height: auto !important;
            }}
            
            .charts-grid {{
                padding: 0;
                margin-bottom: 20px;
                width: 100%;
            }}
            
            /* Sales Chart Mobile Fix */
            .chart-container:has(#salesChart) {{
                padding: 10px 5px !important;
                height: 400px;
            }}
            
            #salesChart {{
                height: 100% !important;
                min-height: unset !important;
            }}
            
            .table-container {{
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                margin-top: 20px;
                border-radius: 8px;
                position: relative;
            }}
            
            .table-filter-wrapper {{
                padding: 15px 15px 0 15px;
            }}
            .spec-row td {{
        font-size: 11px !important;
        background: #fff !important;
    }}
    
    .spec-row td:first-child {{
        font-size: 11px !important;
        background: #f8f9fa !important;
        font-weight: 600 !important;
        text-align: left !important;
    }}
            .filter-input {{
                padding: 10px 40px 10px 40px;
                font-size: 13px;
            }}
            
            .filter-icon {{
                left: 12px;
                width: 16px;
                height: 16px;
            }}
            
            .filter-clear-btn {{
                right: 10px;
                width: 24px;
                height: 24px;
            }}
            
            .filter-results-info {{
                font-size: 12px;
            }}
            
             table {{
                font-size: 11px !important;
                min-width: 100% !important;
                table-layout: auto !important;
                width: 100% !important;
            }}
            
             table th, table td {{
                padding: 10px 8px !important;
                font-size: 11px !important;
                line-height: 1.5 !important;
                word-wrap: break-word !important;
                overflow-wrap: break-word !important;
                white-space: normal !important;
            }}
            
            .accordion-header td {{
                padding: 10px 8px !important;
                font-size: 13px;
            }}
            
            .accordion-icon {{
                font-size: 18px !important;
                display: inline-flex !important;
            }}
            
             table th:first-child,
            table td:first-child,
            tbody td:first-child {{
                font-size: 11px !important;
                font-weight: 600 !important;
                text-align: left !important;
                padding: 10px 8px !important;
                min-width: 140px !important;
                max-width: 140px !important;
                width: 140px !important;
                position: sticky !important;
                left: 0 !important;
                background: #f8f9fa !important;
                z-index: 2 !important;
            }}
             tbody td:not(:first-child) {{
        text-align: center !important;
        font-size: 11px !important;
        font-weight: 400 !important;
        vertical-align: middle !important;
        padding: 10px 8px !important;
    }}
            
            .expandable-content {{
        font-size: 11px !important;
        -webkit-line-clamp: 2 !important;
        line-height: 1.5 !important;
    }}
            
            .read-more-btn {{
        font-size: 10px !important;
        padding: 2px 0 !important;
        margin-top: 4px !important;
    }}
            .footer {{
                padding: 15px 20px;
                flex-direction: column;
                gap: 8px;
            }}
            
            .footer .logo {{
                height: 20px;
            }}
            
            .footer span {{
                font-size: 11px;
                text-align: center;
            }}
            
            .citations-grid {{
                grid-template-columns: 1fr;
                gap: 20px;
            }}
            
            .citation-card {{
                padding: 20px 15px;
            }}
            
            .citation-car-name {{
                font-size: 18px;
                margin-bottom: 15px;
            }}
            
            .citation-items {{
                gap: 12px;
                max-height: 500px;
            }}
            
            .citation-item {{
                padding: 10px;
            }}
            
            .citation-field-name {{
                font-size: 11px;
            }}
            
             .citation-link {{
        font-size: 11px;
        line-height: 1.5;
        padding: 4px 0;
        word-break: break-all; /* Ensure URLs break */
        max-width: 100%;
    }}
           .review-table {{
        font-size: 11px !important;
        table-layout: auto !important;
    }}
    
    review-table th, .review-table td {{
        padding: 10px 8px !important;
        font-size: 11px !important;
        text-align: left !important;
    }}
    
    .review-table-container {{
        padding: 20px 15px;
        margin-top: 20px;
    }}
    
    .review-table .read-more-btn {{
        font-size: 11px;
    }}
    .review-table td:first-child {{
        font-size: 11px !important;
        min-width: 120px !important;
        max-width: 120px !important;
        position: sticky !important;
        left: 0 !important;
        background: #f8f9fa !important;
        z-index: 2 !important;
    }}
    .review-table .expandable-content {{
        -webkit-line-clamp: 2;
    }}
        }}
        
        /* Small Mobile Styles (480px and below) */
        @media (max-width: 430px) {{
            .site-header {{
                padding: 10px 15px;
            }}
            
            .logo {{
                height: 16px;
            }}
            
            .header-actions {{
                flex-direction: column;
                gap: 10px;
            }}
            
            .main-nav {{
                width: 100%;
            }}
            
            .main-nav a {{
                font-size: 11px;
                padding: 3px 6px;
            }}
            
            .print-btn {{
                font-size: 10px;
                padding: 5px 8px;
                width: 100%;
                justify-content: center;
            }}
            
            .content {{
                padding: 15px 10px;
            }}
            
            .section-header h2 {{
                font-size: 16px;
            }}
            
            .section-header .icon-wrapper {{
                width: 35px;
                height: 35px;
            }}
            
            .section-header .icon-wrapper svg {{
                width: 18px;
                height: 18px;
            }}
            
            .main-group-header td {{
                font-size: 16px;
            }}
            
            .summary {{
                padding: 15px 10px;
            }}
            
            .summary p {{
                font-size: 12px;
            }}
            
            .chart-container {{
                padding: 10px 5px !important;
            }}
            
            .chart-container h3 {{
                font-size: 12px;
                margin-bottom: 10px;
            }}
            
            /* Sales Chart Small Mobile Fix */
            .chart-container:has(#salesChart) {{
                padding: 8px 3px !important;
                height: 350px;
            }}
    
            table {{
        font-size: 10px !important;
    }}
            
             table th, table td {{
        font-size: 10px !important;
        padding: 8px 5px !important;
    }}
            table td:first-child,
    tbody td:first-child {{
        font-size: 10px !important;
        min-width: 105px !important;
        max-width: 105px !important;
        width: 105px !important;
    }}
    tbody td:not(:first-child) {{
        font-size: 10px !important;
        text-align: center !important;
    }}
    
            .accordion-header td {{
        font-size: 10px !important;
        padding: 8px 5px !important;
    }}
    .main-group-header td {{
        font-size: 13px !important;
    }}
            
            .filter-input {{
                padding: 8px 35px 8px 35px;
                font-size: 12px;
            }}
            
            .citation-card {{
                padding: 15px 10px;
            }}
            
            .citation-car-name {{
                font-size: 16px;
            }}
            
            .citation-items {{
                max-height: 400px;
            }}

    
    .citation-link {{
        font-size: 10px;
        line-height: 1.6;
        padding: 5px 0;
        word-break: break-all;
        max-width: 100%;
    }}
            .footer {{
                padding: 12px 15px;
            }}
            
            .footer span {{
                font-size: 10px;
            }}
            
            canvas {{
                max-height: 250px !important;
            }}
            .review-table {{
        font-size: 10px;
    }}
    
    .review-table th, .review-table td {{
        padding: 8px 6px;
    }}
    
    .review-table-container {{
        padding: 15px 10px;
    }}
        }}

        /* Extra Small Mobile - 375px specific fix */
        @media (max-width: 375px) {{
            .site-header {{
                padding: 8px 12px;
                flex-direction: column;
                gap: 8px;
                align-items: stretch;
            }}
            
            .logo {{
                height: 16px;
                align-self: flex-start;
            }}
            
            .header-actions {{
                width: 100%;
                flex-direction: column;
                gap: 8px;
            }}
            
            .main-nav {{
                width: 100%;
                flex-wrap: nowrap;
                justify-content: space-between;
                gap: 5px;
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                padding: 4px 0;
            }}
            
            .main-nav a {{
                font-size: 10px;
                padding: 4px 6px;
                white-space: nowrap;
                flex-shrink: 0;
            }}
            
            .print-btn {{
                font-size: 11px;
                padding: 6px 10px;
                width: 100%;
                justify-content: center;
            }}
            
            .content {{
                padding: 12px 8px;
            }}
            
            .section-header h2 {{
                font-size: 14px;
            }}
            
            .section-header .icon-wrapper {{
                width: 32px;
                height: 32px;
            }}
            
            .section-header .icon-wrapper svg {{
                width: 16px;
                height: 16px;
            }}
            
            /* Sales Chart Extra Small Fix */
            .chart-container:has(#salesChart) {{
                height: 380px;
            }}
 
    
    .citation-link {{
        font-size: 10px; /* Don't go smaller than 10px */
        line-height: 1.6;
        padding: 5px 0;
        word-break: break-all;
        max-width: 100%;
    }}
        }}
    </style>
</head>
<body>
    <header class="site-header">
        <a href="#"><img src="https://www.mahindra.com//sites/default/files/2025-07/mahindra-red-logo.webp" alt="Logo" class="logo"></a>
        <div class="header-actions">
            <nav class="main-nav">
                <a href="#comparison-section">Comparison</a>
                <a href="#analytics-section">Analytics</a>
                <a href="#review-section">Reviews</a>
                <a href="#summary-section">Summary</a>
                <a href="#" id="citations-toggle" onclick="toggleCitations(event)">Citations</a>
            </nav>
            <button class="print-btn" onclick="printReport()">Save as PDF</button>
        </div>
    </header>
    <div class="container">
        <div class="content">
            <div class="section-header"><div class="icon-wrapper"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M18 18h-2c-1.1 0-2-.9-2-2v-3c0-1.1.9-2 2-2h2c1.1 0 2 .9 2 2v3c0 1.1-.9 2-2 2zM6 18H4c-1.1 0-2-.9-2-2v-3c0-1.1.9-2 2-2h2c1.1 0 2 .9 2 2v3c0 1.1-.9 2-2 2zM17 11V9c0-1.1-.9-2-2-2h-2V5c0-1.1-.9-2-2-2h-2c-1.1 0-2 .9-2 2v2H5c-1.1 0-2 .9-2 2v2h18v-2c0-1.1-.9-2-2-2h-2z"/></svg></div><h2 id="comparison-section">Detailed Specifications</h2></div>
            <div class="table-container animate-on-scroll">
                <div class="table-filter-wrapper">
                    <div class="filter-input-group">
                        <svg class="filter-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>
                        <input type="text" id="specFilter" class="filter-input" placeholder="Search specifications (e.g., mileage, safety, transmission)..." onkeyup="filterSpecs()"/>
                        <button class="filter-clear-btn" onclick="clearFilter()" id="clearFilterBtn" style="display: none;"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
                    </div><div class="filter-results-info" id="filterResults"></div>
                </div>{features_table}
            </div>
        </div>
        <div class="content">
            <div class="section-header"><div class="icon-wrapper"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h3v9H3zM9 8h3v13H9zM15 4h3v17h-3zM21 20h-3"/></svg></div><h2 id="analytics-section">Visual Analytics</h2></div>
            <div class="charts-grid">
                <div class="chart-container animate-on-scroll"><h3>Price Comparison (₹ Lakhs)</h3><canvas id="priceChart"></canvas></div><div class="chart-container animate-on-scroll"><h3>Mileage Comparison (kmpl)</h3><canvas id="mileageChart"></canvas></div>
                <div class="chart-container animate-on-scroll"><h3>User Ratings (out of 5)</h3><canvas id="ratingChart"></canvas></div><div class="chart-container animate-on-scroll"><h3>Seating Capacity</h3><canvas id="seatingChart"></canvas></div>
<h5>Sales Performance (Volume vs Price)</h5><div class="chart-container animate-on-scroll"><canvas id="salesChart"></canvas></div>            </div>
        </div>
         <div class="content">
            <div class="section-header">
                <div class="icon-wrapper">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                        <path d="M9 12h6m-6 4h6"/>
                    </svg>
                </div>
                <h2 id="review-section">Consolidated Review Summary</h2>
            </div>
            {_generate_consolidated_review_html(comparison_data)}
        </div>
        <div class="content">
            <div class="section-header"><div class="icon-wrapper"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg></div><h2 id="summary-section">Analysis Summary</h2></div>
            <div class="summary animate-on-scroll"><p>{formatted_summary}</p></div>
        </div>
        <div class="content" id="citations-section" style="display: none;"><div class="section-header"><div class="icon-wrapper"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><line x1="10" y1="9" x2="8" y2="9"></line></svg></div><h2>Data Source Citations</h2></div><div class="citations-grid">{citations_html}</div></div>
    </div>
    <footer class="footer"><span>Copyright© 2025 Mahindra&Mahindra Ltd. All Rights Reserved.</span></footer>
    <script>
            function toggleAccordion(headerRow) {{
    headerRow.classList.toggle('active');
    let currentRow = headerRow.nextElementSibling;
    
    while (currentRow && currentRow.classList.contains('spec-row')) {{
        if (document.getElementById('specFilter').value.trim() === '') {{
            // Toggle display without changing any styles
            if (headerRow.classList.contains('active')) {{
                currentRow.style.display = 'table-row';
            }} else {{
                currentRow.style.display = 'none';
            }}
        }}
        currentRow = currentRow.nextElementSibling;
    }}
}}
            function expandAllAccordions() {{ document.querySelectorAll('.accordion-header:not(.active)').forEach(header => {{ header.classList.add('active'); let currentRow = header.nextElementSibling; while (currentRow && currentRow.classList.contains('spec-row')) {{ currentRow.style.display = 'table-row'; currentRow = currentRow.nextElementSibling; }} }}); }}
        function collapseAllAccordions() {{ document.querySelectorAll('.accordion-header.active').forEach(header => {{ header.classList.remove('active'); let currentRow = header.nextElementSibling; while (currentRow && currentRow.classList.contains('spec-row')) {{ currentRow.style.display = 'none'; currentRow = currentRow.nextElementSibling; }} }}); }}
        function filterSpecs() {{ const input = document.getElementById('specFilter'); const filter = input.value.toLowerCase().trim(); const tbody = document.getElementById('specifications-tbody'); const resultsInfo = document.getElementById('filterResults'); document.getElementById('clearFilterBtn').style.display = filter ? 'flex' : 'none'; if (filter) {{ expandAllAccordions(); }} else {{ collapseAllAccordions(); }} let visibleSpecCount = 0; const specRows = tbody.querySelectorAll('.spec-row'); specRows.forEach(row => {{ const specName = row.cells[0].textContent.toLowerCase(); if (filter && specName.includes(filter)) {{ row.style.display = 'table-row'; visibleSpecCount++; }} else if (filter) {{ row.style.display = 'none'; }} else {{ let prevSibling = row.previousElementSibling; let isUnderAccordion = false; while (prevSibling) {{ if (prevSibling.classList.contains('accordion-header')) {{ isUnderAccordion = true; break; }} if (prevSibling.classList.contains('main-group-header')) {{ break; }} prevSibling = prevSibling.previousElementSibling; }} row.style.display = isUnderAccordion ? 'none' : 'table-row'; }} }}); tbody.querySelectorAll('.accordion-header').forEach(header => {{ if (filter) {{ let hasVisibleChild = false; let currentRow = header.nextElementSibling; while (currentRow && currentRow.classList.contains('spec-row')) {{ if (currentRow.style.display !== 'none') {{ hasVisibleChild = true; break; }} currentRow = currentRow.nextElementSibling; }} header.style.display = hasVisibleChild ? 'table-row' : 'none'; }} else {{ header.style.display = 'table-row'; }} }}); tbody.querySelectorAll('.main-group-header').forEach(mainHeader => {{ if (filter) {{ mainHeader.style.display = 'none'; }} else {{ mainHeader.style.display = 'table-row'; }} }}); if (filter) {{ resultsInfo.textContent = visibleSpecCount === 0 ? 'No specifications match your search' : `Showing ${{visibleSpecCount}} matching specifications`; resultsInfo.classList.toggle('no-results', visibleSpecCount === 0); }} else {{ resultsInfo.textContent = ''; resultsInfo.classList.remove('no-results'); }} }}
        function clearFilter() {{ const input = document.getElementById('specFilter'); input.value = ''; filterSpecs(); input.focus(); }}
        function printReport() {{ window.print(); }}
        function toggleExpand(button) {{ const content = button.previousElementSibling; content.classList.toggle('expanded'); button.textContent = content.classList.contains('expanded') ? 'Read less' : 'Read more'; }}
        function toggleCitations(event) {{ event.preventDefault(); const citationsSection = document.getElementById('citations-section'); const mainContent = document.querySelectorAll('.content:not(#citations-section)'); const toggleButton = document.getElementById('citations-toggle'); const navLinks = document.querySelectorAll('.main-nav a:not(#citations-toggle)'); if (citationsSection.style.display === 'none') {{ citationsSection.style.display = 'block'; mainContent.forEach(section => {{ section.style.display = 'none'; }}); navLinks.forEach(link => {{ link.style.display = 'none'; }}); toggleButton.textContent = 'Go Back'; }} else {{ citationsSection.style.display = 'none'; mainContent.forEach(section => {{ section.style.display = 'block'; }}); navLinks.forEach(link => {{ link.style.display = 'block'; }}); toggleButton.textContent = 'Citations'; }} window.scrollTo({{ top: 0, behavior: 'smooth' }}); }}
        
        const carLabels = {json.dumps(cars)}; 
        const priceData = {json.dumps(prices)}; 
        const mileageData = {json.dumps(mileages)}; 
        const ratingData = {json.dumps(ratings)}; 
        const seatingData = {json.dumps(seating)}; 
        const salesVolumes = {json.dumps(sales_volumes)};
        const primaryColor = '#2E3B4E', secondaryColor = '#dd032b';
        const isMobile = window.innerWidth < 768;
        
        new Chart(document.getElementById('priceChart'), {{ type: 'bar', data: {{ labels: carLabels, datasets: [{{ data: priceData, backgroundColor: (ctx) => ctx.dataIndex % 2 === 0 ? primaryColor : secondaryColor }}] }}, options: {{ plugins: {{ legend: {{ display: false }} }} }} }});        
        new Chart(document.getElementById('mileageChart'), {{ type: 'bar', data: {{ labels: carLabels, datasets: [{{ data: mileageData, backgroundColor: (ctx) => ctx.dataIndex % 2 === 0 ? primaryColor : secondaryColor }}] }}, options: {{ plugins: {{ legend: {{ display: false }} }} }} }});
        new Chart(document.getElementById('ratingChart'), {{ type: 'bar', data: {{ labels: carLabels, datasets: [{{ data: ratingData, backgroundColor: (ctx) => ctx.dataIndex % 2 === 0 ? primaryColor : secondaryColor }}] }}, options: {{ scales: {{ y: {{ max: 5 }} }}, plugins: {{ legend: {{ display: false }} }} }} }});
        new Chart(document.getElementById('seatingChart'), {{ type: 'bar', data: {{ labels: carLabels, datasets: [{{ data: seatingData, backgroundColor: (ctx) => ctx.dataIndex % 2 === 0 ? primaryColor : secondaryColor }}] }}, options: {{ plugins: {{ legend: {{ display: false }} }} }} }});
        
        new Chart(document.getElementById('salesChart'), {{ 
            type: 'bar', 
            data: {{ 
                labels: carLabels, 
                datasets: [{{ 
                    label: 'Sales Volume (Units/Month)', 
                    data: salesVolumes, 
                    backgroundColor: primaryColor, 
                    xAxisID: 'x' 
                }}, {{ 
                    label: 'Price (₹ Lakhs)', 
                    data: priceData, 
                    backgroundColor: secondaryColor, 
                    xAxisID: 'x1' 
                }}] 
            }}, 
            options: {{ 
                maintainAspectRatio: false,
                indexAxis: 'y', 
                scales: {{ 
                    y: {{ 
                        position: 'left',
                        ticks: {{
                            font: {{ size: isMobile ? 9 : 12 }},
                            autoSkip: false,
                            maxRotation: 0,
                            minRotation: 0
                        }}
                    }},
                    x: {{ 
                        display: true,
                        type: 'linear', 
                        position: 'bottom', 
                        title: {{ 
                            display: !isMobile,
                            text: 'Sales Volume (Units/Month)',
                            font: {{ size: isMobile ? 9 : 12 }}
                        }}, 
                        ticks: {{ 
                            display: true,
                            font: {{ size: isMobile ? 7 : 11 }},
                            callback: function(value) {{ 
                                if (isMobile) {{
                                    return value >= 1000 ? (value/1000).toFixed(0) + 'k' : value;
                                }}
                                return value.toLocaleString() + ' units'; 
                            }}
                        }},
                        grid: {{
                            display: true,
                            color: isMobile ? '#f0f0f0' : '#e9ecef'
                        }}
                    }},
                    x1: {{ 
                        display: true,
                        type: 'linear', 
                        position: 'top', 
                        title: {{ 
                            display: !isMobile,
                            text: 'Price (₹ Lakhs)', 
                            color: '#6c757d',
                            font: {{ size: isMobile ? 9 : 12 }}
                        }}, 
                        grid: {{ 
                            drawOnChartArea: false,
                            display: false
                        }}, 
                        ticks: {{ 
                            display: true,
                            color: '#6c757d',
                            font: {{ size: isMobile ? 7 : 11 }},
                            callback: function(value) {{ return '₹' + value.toFixed(1) + 'L'; }}
                        }} 
                    }}
                }}, 
                plugins: {{ 
    legend: {{
        display: false
    }},
    tooltip: {{ 
        enabled: true,
        callbacks: {{ 
            label: function(context) {{ 
                let label = context.dataset.label || ''; 
                if (label) {{ label += ': '; }} 
                if (context.dataset.label.includes('Price')) {{ 
                    label += '₹' + context.parsed.x.toFixed(2) + ' Lakhs'; 
                }} else {{ 
                    label += context.parsed.x.toLocaleString() + ' units'; 
                }} 
                return label; 
            }} 
        }} 
    }} 
}}
            }} 
        }});
        
        document.addEventListener('DOMContentLoaded', () => {{ const observer = new IntersectionObserver((entries) => {{ entries.forEach(entry => {{ if (entry.isIntersecting) {{ entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }} }}); }}, {{ threshold: 0.1 }}); document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el)); }});
    </script>
</body></html>"""
    return html

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
        
        # Set metadata for proper browser rendering
        blob.content_type = "text/html; charset=utf-8"
        blob.cache_control = "public, max-age=3600"  
        
        # Upload HTML content 
        blob.upload_from_string(
            html_content,
            content_type="text/html; charset=utf-8"
        )
        
        # Set additional metadata after upload
        blob.metadata = {
            "Content-Disposition": "inline",  # Display in browser, don't download
            "X-Content-Type-Options": "nosniff"
        }
        blob.patch()
        
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_destination_path}"
        print(f"   ✓ Uploaded HTML to GCS: {gcs_uri}")
        
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
        print(f"   ✓ Uploaded JSON to GCS: {gcs_uri}")
        
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
        
        print(f"   ✓ Generated signed URL (expires in {expiration_minutes} min)")
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

def is_code_car(car_name: str) -> bool:
    """Check if a car name is a code/custom car."""
    car_name_upper = car_name.strip().upper()
    return (car_name.startswith("CODE:") or 
            car_name.startswith("code:") or
            (car_name_upper == car_name and len(car_name.split()) <= 2))

def create_blank_specs_for_code_car(car_name: str) -> Dict[str, Any]:
    """Create a blank spec structure for a code car - all fields marked as Not Available."""
    blank_specs = {
        "car_name": car_name,
        "is_code_car": True,
        "manual_entry": True,
        "left_blank": True,
        "source_urls": ["User chose to leave blank"]
    }
    
    for field in CAR_SPECS:
        blank_specs[field] = "Not Available"
        blank_specs[f"{field}_citation"] = {
            "source_url": "User Input",
            "citation_text": "User chose to leave this specification blank"
        }
    
    return blank_specs

def add_code_car_specs_tool(
    car_name: str,
    # Original 19 specs
    price_range: str,
    mileage: str,
    user_rating: str,
    seating_capacity: str,
    braking: str,
    steering: str,
    climate_control: str,
    battery: str,
    transmission: str,
    brakes: str,
    wheels: str,
    performance: str,
    body: str,
    vehicle_safety_features: str,
    lighting: str,
    audio_system: str,
    off_road: str,
    interior: str,
    seat: str,
    # NEW: 72 Additional specs
    ride: str,
    performance_feel: str,
    driveability: str,
    manual_transmission_performance: str,
    pedal_operation: str,
    automatic_transmission_performance: str,
    powertrain_nvh: str,
    wind_nvh: str,
    road_nvh: str,
    visibility: str,
    seats_restraint: str,
    impact: str,
    seat_cushion: str,
    turning_radius: str,
    epb: str,
    brake_performance: str,
    stiff_on_pot_holes: str,
    bumps: str,
    jerks: str,
    pulsation: str,
    stability: str,
    shakes: str,
    shudder: str,
    shocks: str,
    grabby: str,
    spongy: str,
    telescopic_steering: str,
    torque: str,
    nvh: str,
    wind_noise: str,
    tire_noise: str,
    crawl: str,
    gear_shift: str,
    pedal_travel: str,
    gear_selection: str,
    turbo_noise: str,
    resolution: str,
    touch_response: str,
    button: str,
    apple_carplay: str,
    digital_display: str,
    blower_noise: str,
    soft_trims: str,
    armrest: str,
    sunroof: str,
    irvm: str,
    orvm: str,
    window: str,
    alloy_wheel: str,
    tail_lamp: str,
    boot_space: str,
    led: str,
    drl: str,
    ride_quality: str,
    infotainment_screen: str,
    chasis: str,
    straight_ahead_stability: str,
    wheelbase: str,
    egress: str,
    ingress: str,
    corner_stability: str,
    parking: str,
    manoeuvring: str,
    city_performance: str,
    highway_performance: str,
    wiper_control: str,
    sensitivity: str,
    rattle: str,
    headrest: str,
    acceleration: str,
    response: str,
    door_effort: str
) -> str:
    """
    Collect manual specifications for a code car (91 total specs).
    ADK will automatically prompt for EACH parameter before executing this function.
    
    IMPORTANT: To skip a field, user should type 'skip' or 'n/a'
    
    Args:
        car_name: Name of the code car
        
        # Original 19 specs
        price_range: Price Range (e.g., ₹13.66 Lakh onwards, or 'skip')
        mileage: Mileage (e.g., 16.5 kmpl, or 'skip')
        user_rating: User Rating (e.g., 4.5/5, or 'skip')
        seating_capacity: Seating Capacity (e.g., 7 Seater, or 'skip')
        braking: Braking System (e.g., ABS with EBD, or 'skip')
        steering: Steering Type (e.g., Electric Power Steering, or 'skip')
        climate_control: Climate Control (e.g., Dual Zone Automatic, or 'skip')
        battery: Battery (e.g., 50 kWh, or 'skip' for non-EVs)
        transmission: Transmission (e.g., Manual & Automatic, or 'skip')
        brakes: Brakes (e.g., Front Disc/Rear Drum, or 'skip')
        wheels: Wheels (e.g., 18-inch alloy wheels, or 'skip')
        performance: Performance (e.g., 0-100 in 10.5s, or 'skip')
        body: Body Type (e.g., SUV, Monocoque, or 'skip')
        vehicle_safety_features: Safety Features (e.g., 6 Airbags, ESP, or 'skip')
        lighting: Lighting (e.g., LED Headlamps with DRLs, or 'skip')
        audio_system: Audio System (e.g., 9-inch touchscreen, or 'skip')
        off_road: Off-Road Features (e.g., 4x4, Hill Descent, or 'skip')
        interior: Interior Features (e.g., Leather seats, or 'skip')
        seat: Seat Details (e.g., Ventilated leather seats, or 'skip')
        
        # NEW: 72 Additional specs
        ride: Ride quality/comfort (or 'skip')
        performance_feel: Performance feel/driving experience (or 'skip')
        driveability: Driveability/ease of driving (or 'skip')
        manual_transmission_performance: Manual transmission performance (or 'skip')
        pedal_operation: Pedal operation (clutch/brake/accelerator) (or 'skip')
        automatic_transmission_performance: Automatic transmission performance (or 'skip')
        powertrain_nvh: Powertrain NVH (noise/vibration/harshness) (or 'skip')
        wind_nvh: Wind NVH (or 'skip')
        road_nvh: Road NVH (or 'skip')
        visibility: Visibility/sight lines (or 'skip')
        seats_restraint: Seats restraint/safety (or 'skip')
        impact: Impact safety/crash test ratings (or 'skip')
        seat_cushion: Seat cushion comfort (or 'skip')
        turning_radius: Turning radius (or 'skip')
        epb: Electronic parking brake (EPB) (or 'skip')
        brake_performance: Brake performance/stopping distance (or 'skip')
        stiff_on_pot_holes: Stiffness on pot holes (or 'skip')
        bumps: Bumps handling (or 'skip')
        jerks: Jerks in transmission/drivetrain (or 'skip')
        pulsation: Pulsation/vibration (or 'skip')
        stability: Stability at high speed/cornering (or 'skip')
        shakes: Shakes/vibration (or 'skip')
        shudder: Shudder/vibration (or 'skip')
        shocks: Shocks/suspension quality (or 'skip')
        grabby: Grabby brakes/clutch (or 'skip')
        spongy: Spongy brakes/pedal feel (or 'skip')
        telescopic_steering: Telescopic steering adjustment (or 'skip')
        torque: Torque/power output (or 'skip')
        nvh: Overall NVH (noise/vibration/harshness) (or 'skip')
        wind_noise: Wind noise in cabin (or 'skip')
        tire_noise: Tire/road noise (or 'skip')
        crawl: Crawl/low speed control (or 'skip')
        gear_shift: Gear shift quality (or 'skip')
        pedal_travel: Pedal travel distance (or 'skip')
        gear_selection: Gear selection ease (or 'skip')
        turbo_noise: Turbo noise/sound (or 'skip')
        resolution: Display resolution (or 'skip')
        touch_response: Touch response of infotainment (or 'skip')
        button: Button controls quality (or 'skip')
        apple_carplay: Apple CarPlay support (or 'skip')
        digital_display: Digital display/instrument cluster (or 'skip')
        blower_noise: Blower noise from AC (or 'skip')
        soft_trims: Soft trims/interior quality (or 'skip')
        armrest: Armrest comfort (or 'skip')
        sunroof: Sunroof/panoramic sunroof (or 'skip')
        irvm: IRVM (Interior Rear View Mirror) (or 'skip')
        orvm: ORVM (Outside Rear View Mirror) (or 'skip')
        window: Window quality/power windows (or 'skip')
        alloy_wheel: Alloy wheel design/size (or 'skip')
        tail_lamp: Tail lamp design/LED (or 'skip')
        boot_space: Boot space/luggage capacity (or 'skip')
        led: LED lights (or 'skip')
        drl: DRL (Daytime Running Lights) (or 'skip')
        ride_quality: Overall ride quality (or 'skip')
        infotainment_screen: Infotainment screen size/touchscreen (or 'skip')
        chasis: Chassis/platform construction (or 'skip')
        straight_ahead_stability: Straight ahead stability on highway (or 'skip')
        wheelbase: Wheelbase dimensions (or 'skip')
        egress: Egress/ease of getting out (or 'skip')
        ingress: Ingress/ease of getting in (or 'skip')
        corner_stability: Corner stability/handling (or 'skip')
        parking: Parking ease/sensors/camera (or 'skip')
        manoeuvring: Manoeuvring in city (or 'skip')
        city_performance: City performance/urban driving (or 'skip')
        highway_performance: Highway performance/cruising (or 'skip')
        wiper_control: Wiper control/operation (or 'skip')
        sensitivity: Sensitivity of controls (or 'skip')
        rattle: Rattle/interior build quality (or 'skip')
        headrest: Headrest comfort/adjustment (or 'skip')
        acceleration: Acceleration/0-100 performance (or 'skip')
        response: Response (throttle/steering) (or 'skip')
        door_effort: Door effort/opening-closing ease (or 'skip')
        
    Returns:
        JSON confirmation that specs were saved
    """
    manual_specs = {
        "car_name": car_name,
        "is_code_car": True,
        "manual_entry": True,
        "source_urls": ["Manual User Input"]
    }
    
    # Collect all provided specs, treating 'skip', 'n/a', empty strings as None
    spec_params = {
        "price_range": price_range,
        "mileage": mileage,
        "user_rating": user_rating,
        "seating_capacity": seating_capacity,
        "braking": braking,
        "steering": steering,
        "climate_control": climate_control,
        "battery": battery,
        "transmission": transmission,
        "brakes": brakes,
        "wheels": wheels,
        "performance": performance,
        "body": body,
        "vehicle_safety_features": vehicle_safety_features,
        "lighting": lighting,
        "audio_system": audio_system,
        "off_road": off_road,
        "interior": interior,
        "seat": seat,
        "ride": ride,
        "performance_feel": performance_feel,
        "driveability": driveability,
        "manual_transmission_performance": manual_transmission_performance,
        "pedal_operation": pedal_operation,
        "automatic_transmission_performance": automatic_transmission_performance,
        "powertrain_nvh": powertrain_nvh,
        "wind_nvh": wind_nvh,
        "road_nvh": road_nvh,
        "visibility": visibility,
        "seats_restraint": seats_restraint,
        "impact": impact,
        "seat_cushion": seat_cushion,
        "turning_radius": turning_radius,
        "epb": epb,
        "brake_performance": brake_performance,
        "stiff_on_pot_holes": stiff_on_pot_holes,
        "bumps": bumps,
        "jerks": jerks,
        "pulsation": pulsation,
        "stability": stability,
        "shakes": shakes,
        "shudder": shudder,
        "shocks": shocks,
        "grabby": grabby,
        "spongy": spongy,
        "telescopic_steering": telescopic_steering,
        "torque": torque,
        "nvh": nvh,
        "wind_noise": wind_noise,
        "tire_noise": tire_noise,
        "crawl": crawl,
        "gear_shift": gear_shift,
        "pedal_travel": pedal_travel,
        "gear_selection": gear_selection,
        "turbo_noise": turbo_noise,
        "resolution": resolution,
        "touch_response": touch_response,
        "button": button,
        "apple_carplay": apple_carplay,
        "digital_display": digital_display,
        "blower_noise": blower_noise,
        "soft_trims": soft_trims,
        "armrest": armrest,
        "sunroof": sunroof,
        "irvm": irvm,
        "orvm": orvm,
        "window": window,
        "alloy_wheel": alloy_wheel,
        "tail_lamp": tail_lamp,
        "boot_space": boot_space,
        "led": led,
        "drl": drl,
        "ride_quality": ride_quality,
        "infotainment_screen": infotainment_screen,
        "chasis": chasis,
        "straight_ahead_stability": straight_ahead_stability,
        "wheelbase": wheelbase,
        "egress": egress,
        "ingress": ingress,
        "corner_stability": corner_stability,
        "parking": parking,
        "manoeuvring": manoeuvring,
        "city_performance": city_performance,
        "highway_performance": highway_performance,
        "wiper_control": wiper_control,
        "sensitivity": sensitivity,
        "rattle": rattle,
        "headrest": headrest,
        "acceleration": acceleration,
        "response": response,
        "door_effort": door_effort
    }
    
    specs_provided = 0
    for field, value in spec_params.items():
        # Treat 'skip', 'n/a', 'none', empty strings, or whitespace as blank
        if value and value.strip() and value.strip().lower() not in ['skip', 'n/a', 'none', 'na', '']:
            manual_specs[field] = value.strip()
            manual_specs[f"{field}_citation"] = {
                "source_url": "Manual User Input",
                "citation_text": f"Manually entered by user: '{value.strip()}'"
            }
            specs_provided += 1
        else:
            manual_specs[field] = None
    
    # Store in global state for the comparison tool to use
    if not hasattr(add_code_car_specs_tool, 'collected_specs'):
        add_code_car_specs_tool.collected_specs = {}
    
    add_code_car_specs_tool.collected_specs[car_name] = manual_specs
    
    return json.dumps({
        "status": "success",
        "message": f"Successfully saved {specs_provided}/91 specifications for '{car_name}'",
        "car_name": car_name,
        "specs_provided": specs_provided,
        "specs_missing": 91 - specs_provided,
        "next_step": "Now call 'scrape_cars_tool' with all car names to generate the comparison report"
    }, indent=2)

def add_code_car_specs_bulk_tool(
    car_name: str,
    specifications: str
) -> str:
    """
    Collect ALL specifications for a code car at once using JSON or structured format.
    This is faster than the one-by-one method.
    
    Args:
        car_name: Name of the code car
        specifications: ALL specifications in JSON format. Example:
            {
                "price_range": "₹15 Lakh",
                "mileage": "18 kmpl",
                "user_rating": "skip",
                "seating_capacity": "5 Seater",
                "braking": "ABS with EBD",
                "steering": "Electric Power Steering",
                "climate_control": "Dual Zone",
                "battery": "N/A",
                "transmission": "Manual & Automatic",
                "brakes": "Disc/Drum",
                "wheels": "18-inch alloy",
                "performance": "0-100 in 9s",
                "body": "SUV",
                "vehicle_safety_features": "6 Airbags, ESP",
                "lighting": "LED Headlamps",
                "audio_system": "9-inch touchscreen",
                "off_road": "4x4",
                "interior": "Leather seats",
                "seat": "Ventilated front seats",
                "ride": "Comfortable",
                "performance_feel": "Sporty",
                ... (add all 91 specs as needed)
            }
            
            Use "skip", "n/a", or empty string "" for fields you want to leave blank.
        
    Returns:
        JSON confirmation that specs were saved
    """
    try:
        # Try to parse as JSON first
        try:
            spec_data = json.loads(specifications)
        except json.JSONDecodeError:
            # If not valid JSON, try to parse as key-value pairs
            spec_data = {}
            for line in specifications.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    spec_data[key.strip()] = value.strip()
        
        manual_specs = {
            "car_name": car_name,
            "is_code_car": True,
            "manual_entry": True,
            "source_urls": ["Manual User Input - Bulk Entry"]
        }
        
        # Map of expected fields - UPDATE THIS LIST
        expected_fields = [
            # Original 19 specs
            "price_range", "mileage", "user_rating", "seating_capacity",
            "braking", "steering", "climate_control", "battery",
            "transmission", "brakes", "wheels", "performance",
            "body", "vehicle_safety_features", "lighting",
            "audio_system", "off_road", "interior", "seat",
            # NEW: 72 Additional specs
            "ride", "performance_feel", "driveability", "manual_transmission_performance",
            "pedal_operation", "automatic_transmission_performance", "powertrain_nvh",
            "wind_nvh", "road_nvh", "visibility", "seats_restraint", "impact",
            "seat_cushion", "turning_radius", "epb", "brake_performance",
            "stiff_on_pot_holes", "bumps", "jerks", "pulsation", "stability",
            "shakes", "shudder", "shocks", "grabby", "spongy", "telescopic_steering",
            "torque", "nvh", "wind_noise", "tire_noise", "crawl", "gear_shift",
            "pedal_travel", "gear_selection", "turbo_noise", "resolution",
            "touch_response", "button", "apple_carplay", "digital_display",
            "blower_noise", "soft_trims", "armrest", "sunroof", "irvm", "orvm",
            "window", "alloy_wheel", "tail_lamp", "boot_space", "led", "drl",
            "ride_quality", "infotainment_screen", "chasis", "straight_ahead_stability",
            "wheelbase", "egress", "ingress", "corner_stability", "parking",
            "manoeuvring", "city_performance", "highway_performance", "wiper_control",
            "sensitivity", "rattle", "headrest", "acceleration", "response", "door_effort"
        ]
        
        specs_provided = 0
        for field in expected_fields:
            value = spec_data.get(field, "")
            
            # Treat 'skip', 'n/a', 'none', empty strings as blank
            if value and str(value).strip() and str(value).strip().lower() not in ['skip', 'n/a', 'none', 'na', '']:
                manual_specs[field] = str(value).strip()
                manual_specs[f"{field}_citation"] = {
                    "source_url": "Manual User Input",
                    "citation_text": f"Manually entered by user (bulk): '{str(value).strip()}'"
                }
                specs_provided += 1
            else:
                manual_specs[field] = None
        
        # Store in global state
        if not hasattr(add_code_car_specs_tool, 'collected_specs'):
            add_code_car_specs_tool.collected_specs = {}
        
        add_code_car_specs_tool.collected_specs[car_name] = manual_specs
        
        return json.dumps({
            "status": "success",
            "message": f"Successfully saved {specs_provided}/91 specifications for '{car_name}' using bulk entry",
            "car_name": car_name,
            "specs_provided": specs_provided,
            "specs_missing": 91 - specs_provided,
            "entry_method": "bulk",
            "next_step": "Now call 'scrape_cars_tool' with all car names to generate the comparison report"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to parse specifications: {str(e)}",
            "hint": "Please provide specifications in valid JSON format or as key:value pairs"
        }, indent=2)

def query_rag_for_code_car_specs(car_name: str, rag_corpus: str) -> Dict[str, Any]:
    """
    Query Vertex RAG corpus for full car specifications (91 fields) with citations.
    Each field will have:
      - field value: exact text from corpus or "Not Available"
      - field_citation: exact text snippet or "N/A"
    """
    print(f"\n{'='*60}")
    print(f"Querying RAG corpus for: {car_name}")
    print(f"{'='*60}")

    try:
        import os, json
        import vertexai
        from vertexai.preview import rag
        from vertexai.generative_models import GenerativeModel

        # Initialize VertexAI at RAG corpus region
        rag_location = "asia-south1"
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        vertexai.init(project=project_id, location=rag_location)
        print("   Querying RAG corpus...")

        rag_query = f"""
        Find all available detailed specifications for the car: {car_name}.
        Include specifications from all categories — mechanical, performance, comfort, safety, design, technology, and pricing.
        """

        rag_response = rag.retrieval_query(
            rag_resources=[rag.RagResource(rag_corpus=rag_corpus)],
            text=rag_query,
            similarity_top_k=20,
        )

        rag_context = ""
        if hasattr(rag_response, "contexts") and rag_response.contexts:
            for context in rag_response.contexts.contexts:
                if hasattr(context, "text"):
                    rag_context += context.text + "\n\n"

        print(f"   ✓ Retrieved {len(rag_context)} characters from RAG corpus")

        # Switch back to main location for Gemini call
        original_location = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-south1")
        vertexai.init(project=project_id, location=original_location)

        model = GenerativeModel("gemini-2.5-flash")

        extraction_prompt = f"""
        Based on the following RAG corpus data about {car_name}, extract all 91 specifications.

        Extract ONLY the field values, do NOT include citation fields.

        RAG CORPUS DATA:
        {rag_context}

        Return strictly valid JSON with this structure (values only, no citations):
        {{
            "price_range": "₹24 Lakh - ₹23 Lakh",
            "mileage": "XX km/l",
            "user_rating": "X.X / 5",
            "seating_capacity": "X-seater",
            "braking": "Disc/Drum",
            "steering": "Power-assisted",
            "climate_control": "Automatic climate control",
            "battery": "Lithium-ion XX kWh",
            "transmission": "6-speed automatic/manual",
            "brakes": "ABS with EBD",
            "wheels": "Alloy XX-inch",
            "performance": "XX hp @ XXXX rpm",
            "body": "SUV/Crossover",
            "vehicle_safety_features": "Airbags, ABS, ESP, Hill Assist",
            "lighting": "LED projector headlamps",
            "audio_system": "Touchscreen infotainment with Bluetooth",
            "off_road": "AWD with terrain modes",
            "interior": "Premium leather upholstery",
            "seat": "Ventilated front seats",
            "ride": "Comfortable and smooth",
            "performance_feel": "Responsive and sporty",
            "driveability": "Easy to drive in city",
            "manual_transmission_performance": "Smooth gear shifts",
            "pedal_operation": "Light clutch operation",
            "automatic_transmission_performance": "Seamless gear changes",
            "powertrain_nvh": "Well-insulated engine noise",
            "wind_nvh": "Minimal wind noise",
            "road_nvh": "Good cabin insulation",
            "visibility": "Excellent all-round visibility",
            "seats_restraint": "3-point seatbelts all rows",
            "impact": "5-star safety rating",
            "seat_cushion": "Comfortable cushioning",
            "turning_radius": "5.5 meters",
            "epb": "Electronic parking brake available",
            "brake_performance": "Strong braking power",
            "stiff_on_pot_holes": "Absorbs bumps well",
            "bumps": "Handles rough roads",
            "jerks": "No jerks in acceleration",
            "pulsation": "Smooth without vibration",
            "stability": "Stable at high speeds",
            "shakes": "No steering shake",
            "shudder": "No engine shudder",
            "shocks": "Good shock absorption",
            "grabby": "Progressive brake feel",
            "spongy": "Firm brake pedal",
            "telescopic_steering": "Tilt and telescopic steering",
            "torque": "XXX Nm @ XXXX rpm",
            "nvh": "Well-refined cabin",
            "wind_noise": "Minimal at highway speeds",
            "tire_noise": "Low tire noise",
            "crawl": "Good low-speed control",
            "gear_shift": "Smooth gear shifts",
            "pedal_travel": "Optimal pedal travel",
            "gear_selection": "Easy gear selection",
            "turbo_noise": "Muted turbo sound",
            "resolution": "10.25-inch HD display",
            "touch_response": "Quick touch response",
            "button": "Physical buttons available",
            "apple_carplay": "Wireless Apple CarPlay",
            "digital_display": "12.3-inch digital cluster",
            "blower_noise": "Quiet AC operation",
            "soft_trims": "Soft-touch dashboard",
            "armrest": "Comfortable front armrest",
            "sunroof": "Panoramic sunroof",
            "irvm": "Auto-dimming IRVM",
            "orvm": "Power-adjustable ORVMs",
            "window": "One-touch power windows",
            "alloy_wheel": "18-inch diamond-cut alloys",
            "tail_lamp": "LED tail lamps",
            "boot_space": "XXX liters",
            "led": "Full LED lighting",
            "drl": "LED DRLs",
            "ride_quality": "Comfortable ride",
            "infotainment_screen": "10.25-inch touchscreen",
            "chasis": "Monocoque construction",
            "straight_ahead_stability": "Excellent highway stability",
            "wheelbase": "XXXX mm",
            "egress": "Easy to get out",
            "ingress": "Easy to get in",
            "corner_stability": "Confident cornering",
            "parking": "360-degree camera",
            "manoeuvring": "Easy to maneuver",
            "city_performance": "Good city drivability",
            "highway_performance": "Stable highway cruiser",
            "wiper_control": "Rain-sensing wipers",
            "sensitivity": "Responsive controls",
            "rattle": "No interior rattles",
            "headrest": "Adjustable headrests",
            "acceleration": "0-100 km/h in X.X sec",
            "response": "Quick throttle response",
            "door_effort": "Easy door operation",
            "review_ride_handling": "Expert review of ride quality",
            "review_steering": "Expert review of steering",
            "review_braking": "Expert review of braking",
            "review_performance": "Expert review of performance",
            "review_4x4_operation": "Expert review of 4x4",
            "review_nvh": "Expert review of NVH",
            "review_gsq": "Expert review of gear shift"
        }}

        RULES:
        - Extract actual values from the RAG corpus
        - If not found in corpus, use "Not Available"
        - Output valid JSON only, no markdown or commentary
        - Do NOT include _citation fields
        """

        response = model.generate_content(extraction_prompt)
        response_text = response.text.strip()

        # Clean up JSON fences
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        car_data = json.loads(response_text.strip())
        car_data["source"] = "RAG Corpus"
        car_data["is_code_car"] = True
        car_data["source_urls"] = [f"RAG Corpus: {rag_corpus}"]

        for field in CAR_SPECS:
            if field in car_data:
                car_data[f"{field}_citation"] = {
                    "source_url": f"RAG Corpus: {rag_corpus}",
                    "citation_text": "Retrieved from RAG Engine"
                }
        
        valid_fields = sum(
            1 for k, v in car_data.items()
            if not k.endswith("_citation") and v not in ["Not Available", "N/A", None, ""]
        )


        print(f"   ✓ RAG extraction complete: {valid_fields}/91 fields found")
        return car_data

    except Exception as e:
        print(f"   ✗ RAG query failed: {e}")
        import traceback; traceback.print_exc()
        try:
            vertexai.init(
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "asia-south1")
            )
        except:
            pass

        return {
            "car_name": car_name,
            "error": f"Failed to query RAG corpus: {str(e)}",
            "is_code_car": True
        }
    
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
                    print(f"✓ Created blank spec structure for '{car}'")
            
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
                        print(f"✓ Retrieved specs from RAG for '{car}'")
                    else:
                        print(f"✗ RAG query failed for '{car}', will use blank specs")
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
                    print(f"   ✗ Error fetching sales data: {e}")
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
        print(f"\n✓ {car}: {populated}/{len(CAR_SPECS)} specs populated")
        
        
    
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

---

WORKFLOW

 1. When user requests a car comparison:
- Check if any car names are **CODE CARS** — meaning:
  - They start with **'CODE:'** (e.g., CODE:PROTO1)
  - OR are written in **ALL CAPS** (e.g., XYZ123, ABC456)


 2. If CODE CARS are detected:
- Call 'scrape_cars_tool' FIRST to identify the code cars.
- If the response status is "awaiting_code_car_specs", ask the user:

> "Is this a **released car** or an **internal product**?"

---

##### If user says **RELEASED CAR / NOT INTERNAL / PUBLIC**:
- Treat it as a normal car.
- Call `scrape_cars_tool` with `use_custom_search=True` to fetch data via Google Custom Search API.
- Proceed with standard web scraping workflow.

---

##### If user says **INTERNAL PRODUCT / PROTOTYPE / CODE CAR**:
Ask how they want to provide specifications:

> "Would you like to manually specify specifications for the code car(s)?"

Provide **three options**:

1. **MANUAL ENTRY** (ONE-BY-ONE or BULK)
2. **RAG CORPUS** (Vertex RAG query)
3. **BLANK** (Leave all fields empty)

---

#####  If user says **YES / MANUAL**:
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

#####  If user says **RAG / GCS / CORPUS / VERTEX RAG / RAG CORPUS**:
- Call 'scrape_cars_tool' with user_decision="rag"
- System queries Vertex RAG corpus for specifications
- Proceeds automatically after RAG query

---

#####  If user says **BLANK / EMPTY / LEAVE**:
- The agent marks all fields as "Not Available".  
- No manual entry or web scraping is done.  
- Call `scrape_cars_tool` again with `user_decision="blank"`.

---

#### 3. If **NO CODE CARS detected**:
- Directly call:
  scrape_cars_tool(car_names=[...], use_custom_search=True)
- The tool uses Custom Search API to fetch real car data and generates the comparison report.

---

### **TOOLS AVAILABLE**
- add_code_car_specs_tool: Interactive, one-by-one entry for all 91 specifications.
- add_code_car_specs_bulk_tool: Bulk JSON entry (all specs at once).
- scrape_cars_tool: Main comparison and report generation tool (uses Custom Search API by default).

---

### **IMPORTANT LOGIC RULES**
- Always call **`scrape_cars_tool` FIRST** to detect code cars.
- Only call **manual tools** (`add_code_car_specs_tool` / `add_code_car_specs_bulk_tool`) if the user confirms manual entry.
- After manual entry, always call `scrape_cars_tool` again to generate the final report.
- All 91 specifications are optional — user may skip any.
- Custom Search API is used by default for better accuracy and citations.

---


ALL REPORTS ARE BROWSER-VIEWABLE:
- HTML reports contain embedded CSS and JavaScript
- Reports open directly in browser via signed URLs
- No downloads required - click URL to view instantly

### **98 SPECIFICATIONS TRACKED**

**Original Core Specs (19):**
Price Range, Mileage, User Rating, Seating Capacity, Braking, Steering, 
Climate Control, Battery, Transmission, Brakes, Wheels, Performance, Body Type, 
Vehicle Safety Features, Lighting, Audio System, Off-Road, Interior, Seat, Monthly Sales

**Advanced Performance & Feel (72):**
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

### **OUTPUT FORMAT - CRITICAL**

After comparison completes, present the results like this:

---
 **Car Comparison Complete!**

 **Compared**: [Car1], [Car2], [Car3]
 **Time**: 45.2 seconds

---

**VIEW REPORT IN BROWSER**
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