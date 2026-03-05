"""
Car Specifications Scraper - Simple Per-Spec Search Pipeline

FLOW:
1. Phase 1: Per-spec search (87 queries) → Extract from snippets with Gemini
   - Query: "{car_name} {spec_keyword}"
   - Gemini extracts value + source URL from snippets

2. Phase 2: AutoCarIndia fallback for missing specs
   - Build autocarindia.com spec page URL
   - Extract missing specs in batches of 7 (parallel)
"""
import json
import json_repair
import time
import random
import requests
import concurrent.futures
from typing import Dict, Any, List
from functools import wraps

from vertexai.generative_models import GenerativeModel, GenerationConfig

from benchmarking_agent.config import GOOGLE_API_KEY, SEARCH_ENGINE_ID, CUSTOM_SEARCH_URL


# ============================================================================
# CONFIGURATION
# ============================================================================

MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 20.0

# Parallel workers
SEARCH_WORKERS = 20
GEMINI_WORKERS = 15

# Gemini config
EXTRACTION_CONFIG = GenerationConfig(
    temperature=0.1,
    top_p=0.95,
    response_mime_type="application/json",
)


# ============================================================================
# 87 CAR SPECIFICATIONS
# ============================================================================

CAR_SPECS = [
    # Basic Info
    "price_range", "mileage", "user_rating", "seating_capacity",

    # Engine & Performance
    "performance", "torque", "transmission", "acceleration",
    "engine_displacement", "fuel_type", "number_of_gears", "drive_type",

    # Braking & Safety
    "braking", "brakes", "brake_performance", "vehicle_safety_features",
    "impact", "airbags", "adas", "ncap_rating",

    # Steering & Handling
    "steering", "telescopic_steering", "turning_radius",
    "stability", "corner_stability", "straight_ahead_stability",

    # Ride & Suspension
    "ride", "ride_quality", "stiff_on_pot_holes", "bumps", "shocks",
    "suspension_front", "suspension_rear",

    # NVH
    "nvh", "powertrain_nvh", "wind_nvh", "road_nvh",
    "wind_noise", "tire_noise", "turbo_noise",

    # Transmission Feel
    "manual_transmission_performance", "automatic_transmission_performance",
    "pedal_operation", "gear_shift", "gear_selection", "pedal_travel", "crawl",

    # Driving Dynamics
    "driveability", "performance_feel", "city_performance",
    "highway_performance", "off_road", "manoeuvring",

    # Vibration Issues
    "jerks", "pulsation", "shakes", "shudder",
    "grabby", "spongy", "rattle",

    # Interior & Comfort
    "interior", "climate_control", "seats", "seat_cushion",
    "seat_material", "ventilated_seats", "visibility", "soft_trims",
    "armrest", "headrest", "egress", "ingress",

    # Features & Tech
    "infotainment_screen", "resolution", "touch_response", "apple_carplay",
    "digital_display", "button", "cruise_control", "parking_sensors", "parking_camera",

    # Exterior & Lighting
    "lighting", "led", "drl", "tail_lamp",
    "alloy_wheel", "tyre_size", "wheel_size",

    # Convenience Features
    "sunroof", "irvm", "orvm", "window",
    "wiper_control", "parking", "epb", "door_effort",

    # Dimensions & Space
    "boot_space", "wheelbase", "chasis",
    "ground_clearance", "fuel_tank", "kerb_weight",

    # Other
    "blower_noise", "response", "sensitivity", "seats_restraint",
]


# Search keywords for each spec (simple, focused)
SPEC_KEYWORDS = {
    "price_range": "price",
    "mileage": "mileage",
    "user_rating": "rating",
    "seating_capacity": "seating capacity",
    "performance": "power bhp",
    "torque": "torque",
    "transmission": "transmission",
    "acceleration": "0-100 kmph",
    "engine_displacement": "engine cc",
    "fuel_type": "fuel type",
    "number_of_gears": "gears",
    "drive_type": "drive type",
    "braking": "brakes",
    "brakes": "ABS EBD",
    "brake_performance": "braking distance",
    "vehicle_safety_features": "safety features",
    "impact": "NCAP rating",
    "airbags": "airbags",
    "adas": "ADAS",
    "ncap_rating": "safety rating",
    "steering": "steering",
    "telescopic_steering": "steering adjustment",
    "turning_radius": "turning radius",
    "stability": "stability",
    "corner_stability": "cornering",
    "straight_ahead_stability": "straight line stability",
    "ride": "ride quality",
    "ride_quality": "ride comfort",
    "stiff_on_pot_holes": "pothole ride",
    "bumps": "bump absorption",
    "shocks": "suspension",
    "suspension_front": "front suspension",
    "suspension_rear": "rear suspension",
    "nvh": "NVH noise",
    "powertrain_nvh": "engine noise",
    "wind_nvh": "wind noise",
    "road_nvh": "road noise",
    "wind_noise": "wind noise highway",
    "tire_noise": "tyre noise",
    "turbo_noise": "turbo noise",
    "manual_transmission_performance": "manual gearbox",
    "automatic_transmission_performance": "automatic gearbox",
    "pedal_operation": "clutch pedal",
    "gear_shift": "gear shift",
    "gear_selection": "gear lever",
    "pedal_travel": "pedal travel",
    "crawl": "low speed crawl",
    "driveability": "driveability",
    "performance_feel": "driving feel",
    "city_performance": "city driving",
    "highway_performance": "highway performance",
    "off_road": "off-road",
    "manoeuvring": "parking manoeuvre",
    "jerks": "jerky acceleration",
    "pulsation": "brake pulsation",
    "shakes": "steering shake",
    "shudder": "shudder",
    "grabby": "brake grab",
    "spongy": "brake spongy",
    "rattle": "rattle",
    "interior": "interior quality",
    "climate_control": "climate control AC",
    "seats": "seat comfort",
    "seat_cushion": "seat cushion",
    "seat_material": "seat material",
    "ventilated_seats": "ventilated seats",
    "visibility": "visibility",
    "soft_trims": "soft touch dashboard",
    "armrest": "armrest",
    "headrest": "headrest",
    "egress": "getting out",
    "ingress": "getting in",
    "infotainment_screen": "infotainment screen",
    "resolution": "screen resolution",
    "touch_response": "touchscreen response",
    "apple_carplay": "CarPlay Android Auto",
    "digital_display": "digital cluster",
    "button": "buttons controls",
    "cruise_control": "cruise control",
    "parking_sensors": "parking sensors",
    "parking_camera": "parking camera",
    "lighting": "headlights",
    "led": "LED lights",
    "drl": "DRL",
    "tail_lamp": "tail lamp",
    "alloy_wheel": "alloy wheels",
    "tyre_size": "tyre size",
    "wheel_size": "wheel size",
    "sunroof": "sunroof",
    "irvm": "IRVM mirror",
    "orvm": "ORVM mirror",
    "window": "power windows",
    "wiper_control": "wipers",
    "parking": "parking assist",
    "epb": "parking brake",
    "door_effort": "door quality",
    "boot_space": "boot space",
    "wheelbase": "wheelbase",
    "chasis": "chassis",
    "ground_clearance": "ground clearance",
    "fuel_tank": "fuel tank",
    "kerb_weight": "kerb weight",
    "blower_noise": "AC blower noise",
    "response": "throttle response",
    "sensitivity": "control sensitivity",
    "seats_restraint": "seatbelt",
}


# ============================================================================
# UTILITIES
# ============================================================================

def exponential_backoff_retry(max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY):
    """Decorator for exponential backoff retry."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


def call_gemini_simple(prompt: str) -> str:
    """Simple Gemini call with retry."""
    for attempt in range(MAX_RETRIES):
        try:
            model = GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt, generation_config=GenerationConfig(temperature=0.1))

            if hasattr(response, 'text') and response.text:
                return response.text.strip()

            if hasattr(response, 'candidates') and response.candidates:
                text = ""
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        text += part.text
                if text:
                    return text.strip()

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(BASE_DELAY * (2 ** attempt))
            else:
                return ""
    return ""


# ============================================================================
# PHASE 1: PER-SPEC SEARCH + SNIPPET EXTRACTION
# ============================================================================

@exponential_backoff_retry()
def google_custom_search(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Execute Google Custom Search API call."""
    params = {
        "key": GOOGLE_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "q": query,
        "num": min(num_results, 10),
    }

    response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=15)

    if response.status_code == 200:
        return [{
            "url": item.get("link", ""),
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "domain": item.get("displayLink", ""),
        } for item in response.json().get("items", [])]

    return []


def extract_spec_from_snippets(car_name: str, spec_name: str, search_results: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Extract spec value from search result snippets using Gemini.

    Returns: {value: str, source_url: str}
    """
    if not search_results:
        return {"value": "Not found", "source_url": "N/A"}

    # Build context from snippets
    snippets_text = ""
    for i, result in enumerate(search_results[:5], 1):
        snippets_text += f"[{i}] {result['domain']}: {result['snippet']}\n"
        snippets_text += f"    URL: {result['url']}\n\n"

    human_name = spec_name.replace("_", " ").title()

    prompt = f"""Extract the {human_name} for {car_name} from these search snippets.

SEARCH RESULTS:
{snippets_text}

Extract the {human_name} value and return a JSON object:
{{
    "value": "the extracted value with units (concise, max 15 words)",
    "source_url": "URL of the result you extracted from"
}}

Rules:
- Extract ONLY if explicitly stated in snippets
- Include units (bhp, Nm, kmpl, mm, litres, etc.)
- For subjective specs, use brief phrase (3-5 words)
- If not found, return: {{"value": "Not found", "source_url": "N/A"}}

Return ONLY the JSON object."""

    try:
        response_text = call_gemini_simple(prompt)

        if not response_text:
            return {"value": "Not found", "source_url": "N/A"}

        # Parse JSON
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()

        if "{" in text and "}" in text:
            text = text[text.index("{"):text.rindex("}") + 1]

        data = json_repair.loads(text)

        value = data.get("value", "Not found")
        source_url = data.get("source_url", "N/A")

        return {"value": value, "source_url": source_url}

    except Exception:
        return {"value": "Not found", "source_url": "N/A"}


def phase1_per_spec_search(car_name: str) -> Dict[str, Any]:
    """
    Phase 1: For each spec, do one search query and extract from snippets.

    Returns: {specs: {spec_name: value}, citations: {spec_name: {source_url}}}
    """
    print(f"\n{'='*60}")
    print(f"PHASE 1: PER-SPEC SEARCH + SNIPPET EXTRACTION")
    print(f"{'='*60}\n")
    print(f"  Searching and extracting {len(CAR_SPECS)} specs...")

    specs = {}
    citations = {}

    def search_and_extract(spec_name):
        """Search and extract a single spec."""
        keyword = SPEC_KEYWORDS.get(spec_name, spec_name.replace("_", " "))
        query = f"{car_name} {keyword}"

        try:
            # Search
            search_results = google_custom_search(query, num_results=5)

            # Extract from snippets
            result = extract_spec_from_snippets(car_name, spec_name, search_results)

            return spec_name, result["value"], result["source_url"]

        except Exception:
            return spec_name, "Not found", "N/A"

    # Process all specs in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        futures = {executor.submit(search_and_extract, spec): spec for spec in CAR_SPECS}

        completed = 0
        found = 0

        for future in concurrent.futures.as_completed(futures):
            spec_name = futures[future]
            completed += 1

            try:
                spec_name, value, source_url = future.result()

                specs[spec_name] = value
                citations[spec_name] = {
                    "source_url": source_url,
                    "citation_text": f"Extracted from search results",
                }

                if value and "Not found" not in value:
                    found += 1

                if completed % 20 == 0:
                    print(f"    Progress: {completed}/{len(CAR_SPECS)} ({found} found)")

            except Exception:
                specs[spec_name] = "Not found"
                citations[spec_name] = {"source_url": "N/A", "citation_text": ""}

    accuracy = (found / len(CAR_SPECS) * 100) if CAR_SPECS else 0
    print(f"\n  Phase 1 Complete: {found}/{len(CAR_SPECS)} specs ({accuracy:.1f}%)")

    return {"specs": specs, "citations": citations}


# ============================================================================
# PHASE 2: AUTOCARINDIA URL FALLBACK (BATCHED)
# ============================================================================

def build_autocarindia_url(car_name: str) -> str:
    """Build AutoCarIndia spec page URL."""
    parts = car_name.strip().lower().split()
    make = parts[0] if parts else ""
    model = "-".join(parts[1:]) if len(parts) > 1 else ""

    return f"https://www.autocarindia.com/cars/{make}/{model}/specifications"


def extract_specs_from_url(car_name: str, url: str, spec_batch: List[str]) -> Dict[str, str]:
    """
    Extract a batch of specs from AutoCarIndia URL using Gemini.

    Returns: {spec_name: value}
    """
    # Build spec list
    spec_list = "\n".join([f'- {spec}: {spec.replace("_", " ").title()}' for spec in spec_batch])

    prompt = f"""Go to this URL and extract specifications for {car_name}:

URL: {url}

Extract these {len(spec_batch)} specifications:
{spec_list}

Return a JSON object with spec names as keys and values as strings:
{{
    "spec_name": "value with units (concise)",
    ...
}}

Rules:
- Visit the URL and read the spec table
- Extract exact values with units
- For subjective specs, provide brief phrase
- If not found on page, set to "Not found"

Return ONLY the JSON object."""

    try:
        response_text = call_gemini_simple(prompt)

        if not response_text:
            return {}

        # Parse JSON
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()

        if "{" in text and "}" in text:
            text = text[text.index("{"):text.rindex("}") + 1]

        data = json_repair.loads(text)

        return data

    except Exception:
        return {}


def phase2_autocarindia_fallback(car_name: str, current_specs: Dict[str, str]) -> Dict[str, Any]:
    """
    Phase 2: Extract missing specs from AutoCarIndia URL in batches of 7 (parallel).

    Returns: {specs: {spec_name: value}, citations: {spec_name: {source_url}}}
    """
    # Find missing specs
    missing_specs = [
        s for s in CAR_SPECS
        if s not in current_specs or current_specs[s] in ["Not found", "Not Available", ""]
    ]

    if not missing_specs:
        return {"specs": {}, "citations": {}}

    print(f"\n{'='*60}")
    print(f"PHASE 2: AUTOCARINDIA FALLBACK ({len(missing_specs)} missing specs)")
    print(f"{'='*60}\n")

    autocar_url = build_autocarindia_url(car_name)
    print(f"  URL: {autocar_url}")
    print(f"  Extracting in batches of 7 (parallel)...\n")

    # Split into batches of 7
    batches = [missing_specs[i:i+7] for i in range(0, len(missing_specs), 7)]

    specs = {}
    citations = {}

    def extract_batch(batch):
        """Extract one batch."""
        extracted = extract_specs_from_url(car_name, autocar_url, batch)
        return batch, extracted

    # Process batches in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as executor:
        futures = {executor.submit(extract_batch, batch): i for i, batch in enumerate(batches, 1)}

        recovered = 0

        for future in concurrent.futures.as_completed(futures):
            batch_num = futures[future]

            try:
                batch, extracted = future.result()

                batch_found = 0
                for spec_name in batch:
                    value = extracted.get(spec_name, "Not found")

                    if value and "Not found" not in value:
                        specs[spec_name] = value
                        citations[spec_name] = {
                            "source_url": autocar_url,
                            "citation_text": "Extracted from AutoCarIndia",
                        }
                        batch_found += 1
                        recovered += 1

                print(f"    Batch {batch_num}/{len(batches)}: {batch_found}/{len(batch)} specs")

            except Exception:
                print(f"    Batch {batch_num}/{len(batches)}: Error")

    print(f"\n  Phase 2 Complete: Recovered {recovered}/{len(missing_specs)} specs")

    return {"specs": specs, "citations": citations}


# ============================================================================
# MAIN SCRAPING FUNCTION
# ============================================================================

def scrape_car_data_with_custom_search(car_name: str) -> Dict[str, Any]:
    """
    Main scraping function.

    Phase 1: Per-spec search + snippet extraction
    Phase 2: AutoCarIndia fallback for missing specs
    """
    print(f"\n{'#'*60}")
    print(f"SCRAPING: {car_name}")
    print(f"{'#'*60}")

    start_time = time.time()

    # Phase 1: Per-spec search
    phase1_result = phase1_per_spec_search(car_name)
    specs = phase1_result["specs"].copy()
    citations = phase1_result["citations"].copy()

    # Phase 2: AutoCarIndia fallback
    phase2_result = phase2_autocarindia_fallback(car_name, specs)

    # Merge Phase 2 results
    for spec_name, value in phase2_result["specs"].items():
        specs[spec_name] = value

    for spec_name, citation in phase2_result["citations"].items():
        citations[spec_name] = citation

    # Build final car_data
    car_data = {
        "car_name": car_name,
        "method": "Per-Spec Search + AutoCarIndia Fallback",
        "source_urls": [],
    }

    # Collect source URLs
    source_urls = set()
    for citation in citations.values():
        url = citation.get("source_url", "")
        if url and url != "N/A":
            source_urls.add(url)

    car_data["source_urls"] = list(source_urls)

    # Add all specs
    for spec_name in CAR_SPECS:
        value = specs.get(spec_name, "Not Available")
        if not value or value in ["Not found", ""]:
            value = "Not Available"

        car_data[spec_name] = value
        car_data[f"{spec_name}_citation"] = citations.get(
            spec_name,
            {"source_url": "N/A", "citation_text": ""}
        )

    # Final stats
    final_found = sum(
        1 for s in CAR_SPECS
        if car_data.get(s) and car_data[s] not in ["Not Available", "Not found", ""]
    )
    elapsed = time.time() - start_time
    accuracy = (final_found / len(CAR_SPECS) * 100) if CAR_SPECS else 0

    print(f"\n{'='*60}")
    print(f"COMPLETE: {final_found}/{len(CAR_SPECS)} specs ({accuracy:.1f}%)")
    print(f"Time: {elapsed:.1f}s | Sources: {len(car_data['source_urls'])}")
    print(f"{'='*60}\n")

    return car_data


# ============================================================================
# ENTRY POINT
# ============================================================================

def scrape_car_data(car_name: str, manual_specs: Dict[str, Any] = None, use_custom_search: bool = True, pdf_specs: Dict[str, str] = None) -> Dict[str, Any]:
    """Main entry point."""

    if manual_specs and manual_specs.get('is_code_car'):
        print(f"  CODE CAR - using manual specs")
        for field in CAR_SPECS:
            if field not in manual_specs or not manual_specs[field]:
                manual_specs[field] = "Not Available"
                manual_specs[f"{field}_citation"] = {"source_url": "Manual", "citation_text": ""}
        return manual_specs

    if pdf_specs:
        print(f"  PDF prefill not implemented in this version")

    return scrape_car_data_with_custom_search(car_name)


# Backward compatibility
def get_spec_search_queries(car_name: str) -> Dict[str, str]:
    return {spec: f"{car_name} {SPEC_KEYWORDS.get(spec, spec)}" for spec in CAR_SPECS}

def extract_spec_from_search_results(car_name: str, spec_name: str, search_results: List[Dict[str, str]]) -> Dict[str, Any]:
    result = extract_spec_from_snippets(car_name, spec_name, search_results)
    return {
        "value": result.get("value", "Not Available"),
        "citation": "",
        "source_url": result.get("source_url", "N/A")
    }

async def call_custom_search_parallel(queries: Dict[str, str], num_results: int = 5, max_concurrent: int = 15) -> Dict[str, List[Dict[str, str]]]:
    return {}
