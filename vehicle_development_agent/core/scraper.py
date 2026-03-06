"""
Car Specifications Scraper - Simple Per-Spec Search Pipeline

FLOW:
1. Phase 1: Per-spec search (87 queries) → Extract from snippets with Gemini
   - Query: "{car_name} latest {spec_keyword}"
   - Gemini extracts value + source URL from snippets

2. Phase 2: AutoCarIndia fallback for missing specs
   - Build autocarindia.com spec page URL
   - Extract missing specs in batches of 7 (parallel)
"""
import asyncio
import json
import json_repair
import time
import random
import requests
import concurrent.futures
from datetime import datetime
from typing import Dict, Any, List
from functools import wraps

from vertexai.generative_models import GenerativeModel, GenerationConfig

from benchmarking_agent.config import GOOGLE_API_KEY, SEARCH_ENGINE_ID, COMPANY_SEARCH_ID, CUSTOM_SEARCH_URL


# ============================================================================
# CONFIGURATION
# ============================================================================

MAX_RETRIES = 5  # Increased for rate limits
BASE_DELAY = 2.0  # Longer base delay
MAX_DELAY = 30.0

# Parallel workers (reduced to avoid rate limits)
SEARCH_WORKERS = 15  # Reduced from 20
GEMINI_WORKERS = 12  # Reduced from 15

# Dynamic current year (auto-updates, no hardcoding!)
CURRENT_YEAR = datetime.now().year

# Query enhancement strategy
# "latest" is better than year because:
# - Works regardless of model release cycles
# - Search engines understand "latest"
# - Covers cases where current year model isn't released yet
# - Still gets most recent information
QUERY_ENHANCEMENT_MODE = "latest"  # Options: "latest", "year", "both"

# Gemini config
EXTRACTION_CONFIG = GenerationConfig(
    temperature=0.1,
    top_p=0.95,
    response_mime_type="application/json",
)

# Track Gemini model and rate limit failures
_gemini_model = "gemini-2.5-flash"
_rate_limit_count = 0
_RATE_LIMIT_THRESHOLD = 10  # Switch to Pro after 10 rate limits


def reset_gemini_model():
    """Reset to Flash model at the start of each scraping session."""
    global _gemini_model, _rate_limit_count
    _gemini_model = "gemini-2.5-flash"
    _rate_limit_count = 0


# ============================================================================
# 87 CAR SPECIFICATIONS
# ============================================================================

# Top specs to extract from official brand websites
OFFICIAL_SITE_PRIORITY_SPECS = [
    # Top 5 Key Specs
    "price_range", "seating_capacity", "mileage",

    # Performance & Engine
    "acceleration", "torque", "engine_displacement", "fuel_type",

    # Safety
    "airbags", "adas", "ncap_rating", "vehicle_safety_features", "brakes",

    # Dimensions
    "boot_space", "wheelbase", "ground_clearance", "turning_radius",

    # Tech Features
    "infotainment_screen", "digital_display", "apple_carplay",
    "cruise_control", "parking_camera",

    # Exterior
    "tyre_size", "led", "drl",
]  # 25 critical specs

# Official brand website URL patterns
# Format: "brand": ("base_url", "path_pattern")
BRAND_OFFICIAL_URLS = {
    "mahindra": ("https://auto.mahindra.com", "/suv/{model}/"),
    "mahindra_electric": ("https://www.mahindraelectricsuv.com", "/"),
    "tata": ("https://cars.tatamotors.com", "/{model}/ice/specifications.html"),
    "maruti": ("https://www.marutisuzuki.com", "/{model}/specifications"),
    "suzuki": ("https://www.marutisuzuki.com", "/{model}/specifications"),
    "hyundai": ("https://www.hyundai.com", "/in/en/find-a-car/{model}/specification"),
    "toyota": ("https://www.toyota.com", "/{model}/features/"),
    "honda": ("https://www.hondacarindia.com", "/honda-{model}"),
    "kia": ("https://www.kia.com", "/in/our-vehicles/{model}/features.html"),
    "skoda": ("https://www.skoda-auto.com", "/models/{model}"),
    "volkswagen": ("https://www.volkswagen.co.in", "/{model}"),
    "nissan": ("https://www.nissan.in", "/{model}"),
    "renault": ("https://www.renault.co.in", "/{model}"),
    "mg": ("https://www.mgmotor.co.in", "/vehicles/{model}"),
    "bmw": ("https://www.bmw.com", "/models/{model}"),
    "mercedes": ("https://www.mercedes-benz.co.in", "/passengercars/models/{model}/overview.html"),
    "audi": ("https://www.audi.com", "/models/{model}"),
    "porsche": ("https://www.porsche.com", "/international/models/{model}"),
    "lamborghini": ("https://www.lamborghini.com", "/en-en/models/{model}"),
    "ferrari": ("https://www.ferrari.com", "/en-EN/auto/{model}"),
    "aston": ("https://www.astonmartin.com", "/en/models/{model}"),
    "bentley": ("https://www.bentleymotors.com", "/en/models/{model}.html"),
    "rolls": ("https://www.rolls-roycemotorcars.com", "/{model}"),
    "mclaren": ("https://cars.mclaren.com", "/gl_en/{model}"),
    "maserati": ("https://www.maserati.com", "/{model}"),
    "bugatti": ("https://www.bugatti.com", "/en/models/{model}"),
    "jaguar": ("https://www.jaguar.in", "/jaguar-range/{model}/specifications.html"),
    "range": ("https://www.rangerover.com", "/en-in/range-rover/models-and-specifications.html"),
    "rover": ("https://www.rangerover.com", "/en-in/range-rover/models-and-specifications.html"),
    "lexus": ("https://www.lexus.com", "/models/{model}/specifications"),
    "volvo": ("https://www.volvocars.com", "/in/cars/{model}/specifications/"),
    "mini": ("https://www.mini.in", "/en_IN/home/range/{model}/features-functions.html"),
    "tesla": ("https://www.tesla.com", "/{model}"),
    "byd": ("https://www.byd.com", "/en/car/{model}"),
    "vinfast": ("https://vinfastauto.com", "/in_en/{model}/specifications"),
    "geely": ("https://global.geely.com", "/models/{model}/"),
    "chery": ("https://www.cheryinternational.com", "/models/{model}/"),
    "changan": ("https://www.globalchangan.com", "/vehicle/{model}/"),
    "isuzu": ("https://www.isuzu.co.jp", "/museum/vehicle/pickup/{model}/"),
    "subaru": ("https://www.subaru-global.com", "/lineup/{model}/specifications.html"),
    "mazda": ("https://www.mazda.com", "/en/innovation/technology/{model}/"),
    "mitsubishi": ("https://www.mitsubishi-motors.com", "/en/products/{model}/specifications/"),
    "peugeot": ("https://www.peugeot.com", "/en/models/{model}/specifications/"),
    "citroen": ("https://www.citroen.in", "/models/{model}/specifications.html"),
    "jeep": ("https://www.jeep-india.com", "/{model}/specifications.html"),
    "dodge": ("https://www.dodge.com", "/{model}/specs.html"),
    "cadillac": ("https://www.cadillac.com", "/suvs/{model}/specs"),
    "chevrolet": ("https://www.chevrolet.com", "/cars/{model}/specs"),
    "gmc": ("https://www.gmc.com", "/suvs/{model}/specs"),
    "buick": ("https://www.buick.com", "/suvs/{model}/specs"),
    "genesis": ("https://www.genesis.com", "/worldwide/en/models/luxury-sedan-genesis/{model}/specifications.html"),
    "force": ("https://www.forcemotors.com", "/force{model}/specifications"),
}

CAR_SPECS = [
    # Top 5 Key Specs (for main table)
    "price_range", "monthly_sales", "mileage", "user_rating", "seating_capacity",

    # Performance & Driving (from image)
    "performance_feel", "driveability", "acceleration", "torque", "response",
    "city_performance", "highway_performance", "off_road", "crawl",

    # Transmission (from image)
    "manual_transmission_performance", "automatic_transmission_performance",
    "pedal_operation", "gear_shift", "gear_selection", "pedal_travel",

    # Ride & Suspension (from image)
    "ride", "ride_quality", "stiff_on_pot_holes", "bumps", "shocks",

    # NVH & Noise (from image)
    "nvh", "powertrain_nvh", "wind_nvh", "road_nvh",
    "wind_noise", "tire_noise", "turbo_noise", "blower_noise",

    # Vibration & Feel (from image)
    "jerks", "pulsation", "shakes", "shudder", "grabby", "spongy", "rattle",

    # Steering & Handling (from image)
    "steering", "telescopic_steering", "turning_radius", "manoeuvring",
    "stability", "corner_stability", "straight_ahead_stability",

    # Braking (from image)
    "braking", "brakes", "brake_performance", "epb",

    # Safety & Airbags (for checklist + from image)
    "airbags", "airbag_types_breakdown", "vehicle_safety_features",
    "adas", "ncap_rating", "impact", "seats_restraint",

    # Interior & Comfort (from image + checklist)
    "interior", "climate_control", "seats", "seat_cushion", "seat_material",
    "seat_features_detailed", "rear_seat_features", "ventilated_seats",
    "visibility", "soft_trims", "armrest", "headrest", "egress", "ingress",
    "seatbelt_features",

    # Technology & Infotainment (from image + checklist)
    "infotainment_screen", "resolution", "touch_response", "digital_display",
    "apple_carplay", "button", "audio_system", "cruise_control",
    "parking_camera", "parking_sensors",

    # Exterior & Lighting (from image + checklist)
    "led", "drl", "tail_lamp", "alloy_wheel", "tyre_size", "wheel_size",

    # Convenience (from image + checklist)
    "sunroof", "irvm", "orvm", "window", "wiper_control", "parking",
    "door_effort", "sensitivity",

    # Dimensions & Specs (from image + checklist)
    "wheelbase", "ground_clearance", "boot_space", "chasis",
    "fuel_type", "engine_displacement",
]


# Search keywords for each spec (simple, focused)
SPEC_KEYWORDS = {
    "price_range": "price",
    "mileage": "mileage",
    "user_rating": "rating",
    "seating_capacity": "seating capacity",
    "body_type": "body type",
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
    "audio_system": "audio system speakers",
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

    # Checklist Features (Granular extraction)
    "airbag_types_breakdown": "airbag types knee curtain side front rear breakdown",
    "seat_features_detailed": "seat features backrest split ratio recline lumbar support thigh ventilation",
    "rear_seat_features": "rear seat features fold center armrest cup holder recline",
    "seatbelt_features": "seatbelt features pretensioner load limiter height adjuster",
}


# ============================================================================
# UTILITIES
# ============================================================================

def build_enhanced_query(car_name: str, spec_keyword: str, enhance: bool = True) -> str:
    """
    Build search query with smart enhancement for better, more current results.

    Strategy:
    - "latest" mode: "{car_name} latest {spec_keyword}"
      → Best for most cases, always relevant
    - "year" mode: "{CURRENT_YEAR} {car_name} {spec_keyword}"
      → Good when year model definitely exists
    - "both" mode: "{car_name} {CURRENT_YEAR} latest {spec_keyword}"
      → Most comprehensive but longer query

    Args:
        car_name: Name of the car (e.g., "Toyota Camry")
        spec_keyword: Specification keyword (e.g., "price", "mileage")
        enhance: Whether to enhance query (True for specs, False for images)

    Returns:
        Enhanced query string

    Examples:
        >>> build_enhanced_query("Toyota Camry", "price", enhance=True)
        "Toyota Camry latest price"  # if mode="latest"

        >>> build_enhanced_query("Honda Civic", "mileage", enhance=False)
        "Honda Civic mileage"  # no enhancement
    """
    if not enhance:
        return f"{car_name} {spec_keyword}"

    mode = QUERY_ENHANCEMENT_MODE

    if mode == "latest":
        # Recommended: "latest" keyword is understood by search engines
        # and always returns most recent model regardless of release cycle
        return f"{car_name} latest {spec_keyword}"

    elif mode == "year":
        # Use current year - works well mid-year onwards
        return f"{CURRENT_YEAR} {car_name} {spec_keyword}"

    elif mode == "both":
        # Combine both for maximum coverage (longer query)
        return f"{car_name} {CURRENT_YEAR} latest {spec_keyword}"

    else:
        # Fallback to basic query
        return f"{car_name} {spec_keyword}"


def exponential_backoff_retry(max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY):
    """Decorator for exponential backoff retry with rate limit handling."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()

                    # Check for rate limit errors
                    is_rate_limit = any(x in error_str for x in ["429", "rate limit", "quota", "too many requests"])

                    if attempt < max_retries - 1:
                        if is_rate_limit:
                            # Longer delay for rate limits
                            delay = min(base_delay * (3 ** attempt) + random.uniform(2, 5), MAX_DELAY)
                            print(f"      Rate limit hit, waiting {delay:.1f}s before retry...")
                        else:
                            # Normal exponential backoff
                            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)

                        time.sleep(delay)
                    else:
                        # Last attempt failed
                        if is_rate_limit:
                            print(f"      Rate limit exceeded after {max_retries} attempts")
            raise last_exception
        return wrapper
    return decorator


def call_gemini_simple(prompt: str) -> str:
    """
    Simple Gemini call with retry and automatic model fallback.
    Switches from Flash to Pro after repeated rate limits.
    """
    global _gemini_model, _rate_limit_count

    for attempt in range(MAX_RETRIES):
        try:
            # Use current model (Flash or Pro based on rate limit history)
            model = GenerativeModel(_gemini_model)
            response = model.generate_content(
                prompt,
                generation_config=GenerationConfig(temperature=0.1)
            )

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
            error_str = str(e).lower()

            # Check if rate limit error
            is_rate_limit = any(x in error_str for x in [
                "429", "rate limit", "quota", "resource exhausted",
                "too many requests"
            ])

            if is_rate_limit:
                _rate_limit_count += 1

                # Switch to Pro model after threshold
                if (_rate_limit_count >= _RATE_LIMIT_THRESHOLD and
                    _gemini_model == "gemini-2.5-flash"):
                    _gemini_model = "gemini-2.5-pro"
                    print(f"\n  ⚠️  Switching to Gemini Pro after {_rate_limit_count} rate limits")

                # Exponential backoff for rate limits
                if attempt < MAX_RETRIES - 1:
                    delay = min(BASE_DELAY * (3 ** attempt) + random.uniform(2, 5), MAX_DELAY)
                    time.sleep(delay)
                else:
                    # Failed after all retries
                    return ""
            else:
                # Non-rate-limit error - shorter retry
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BASE_DELAY * (2 ** attempt))
                else:
                    return ""

    return ""


# ============================================================================
# PHASE 0: OFFICIAL BRAND SITE EXTRACTION
# ============================================================================

def build_official_brand_url(car_name: str) -> tuple:
    """
    Build official brand website URL dynamically.

    Returns: (url, brand) or (None, None) if brand not found
    """
    parts = car_name.strip().lower().split()
    if not parts:
        return None, None

    brand = parts[0]
    model_parts = parts[1:] if len(parts) > 1 else []

    # Handle special cases
    if brand == "range" or (brand == "land" and model_parts and model_parts[0] == "rover"):
        brand = "rover"
        model_parts = model_parts[1:] if model_parts else []
    elif brand == "aston" and model_parts and model_parts[0] == "martin":
        brand = "aston"
        model_parts = model_parts[1:] if model_parts else []
    elif brand == "rolls" and model_parts and model_parts[0] == "royce":
        brand = "rolls"
        model_parts = model_parts[1:] if model_parts else []

    # Handle Mahindra electric vehicles separately
    if brand == "mahindra" and model_parts:
        model_str = " ".join(model_parts).lower()
        if "ev" in model_str or "electric" in model_str or "xe" in model_str or "xev" in model_str:
            base_url, path_pattern = BRAND_OFFICIAL_URLS.get("mahindra_electric", (None, None))
            if not base_url:
                return None, None
        else:
            base_url, path_pattern = BRAND_OFFICIAL_URLS[brand]
    else:
        # Get URL pattern
        if brand not in BRAND_OFFICIAL_URLS:
            return None, None
        base_url, path_pattern = BRAND_OFFICIAL_URLS[brand]

    # Build model string with brand-specific formatting
    if brand == "mg":
        # MG uses concatenated names: "mg gloster" -> "mggloster"
        model = "mg" + "".join(model_parts) if model_parts else "models"
        model_lower = model.lower()
    else:
        # Most brands use dashes: "model name" -> "model-name"
        model = "-".join(model_parts) if model_parts else "models"
        model_lower = model.lower().replace(" ", "-")

    # Build full URL
    try:
        full_url = base_url + path_pattern.format(model=model_lower)
        return full_url, brand
    except Exception:
        return None, None


def extract_specs_from_official_site(car_name: str, url: str, specs_batch: List[str]) -> Dict[str, str]:
    """
    Extract a batch of specs from official brand URL using Gemini.

    Args:
        car_name: Name of the car
        url: Official brand website URL
        specs_batch: List of spec names to extract (max 10)

    Returns: Dict of {spec_name: value}
    """
    spec_list = "\n".join([f'- {spec}: {spec.replace("_", " ").title()}' for spec in specs_batch])

    prompt = f"""Visit this official car specifications page and extract data for {car_name}:

URL: {url}

Extract these {len(specs_batch)} specifications from the page:
{spec_list}

IMPORTANT:
- Visit the URL and read the official spec sheet/table
- Extract exact values with units (bhp, Nm, mm, litres, kg, kmpl, etc.)
- Look for technical specifications table, features list, or specs section
- If a spec is not on this page, return "Not found"

Return ONLY a JSON object:
{{
    "spec_name": "value with units (concise)",
    ...
}}

Example:
{{
    "price_range": "₹12.5-18.9 Lakh",
    "performance": "175 bhp @ 3500 rpm",
    "torque": "370 Nm",
    "mileage": "15.2 kmpl"
}}

Return ONLY the JSON, no markdown."""

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


def phase0_official_site_extraction(car_name: str) -> Dict[str, Any]:
    """
    Phase 0: Extract top 30 specs from official brand website.

    Extracts in batches of 10 specs (3 Gemini calls total).

    Returns: {specs: {spec_name: value}, citations: {spec_name: {source_url}}}
    """
    print(f"\n{'='*60}")
    print(f"PHASE 0: OFFICIAL BRAND SITE EXTRACTION")
    print(f"{'='*60}\n")

    # Build official URL
    url, brand = build_official_brand_url(car_name)

    if not url:
        print(f"  No official site URL pattern for this brand")
        return {"specs": {}, "citations": {}}

    print(f"  Brand: {brand.upper()}")
    print(f"  URL: {url}")
    print(f"  Extracting {len(OFFICIAL_SITE_PRIORITY_SPECS)} specs in batches of 10...\n")

    specs = {}
    citations = {}

    # Split into batches of 10
    spec_batches = [
        OFFICIAL_SITE_PRIORITY_SPECS[i:i+10]
        for i in range(0, len(OFFICIAL_SITE_PRIORITY_SPECS), 10)
    ]

    for batch_idx, batch in enumerate(spec_batches, 1):
        print(f"    Batch {batch_idx}/{len(spec_batches)}: Extracting {len(batch)} specs...", end=" ")

        try:
            extracted = extract_specs_from_official_site(car_name, url, batch)

            found_count = 0
            for spec_name, value in extracted.items():
                if spec_name in OFFICIAL_SITE_PRIORITY_SPECS and value and "Not found" not in value:
                    specs[spec_name] = value
                    citations[spec_name] = {
                        "source_url": url,
                        "citation_text": f"Official {brand} website",
                        "engine": "OFFICIAL",
                    }
                    found_count += 1

            print(f"✓ {found_count}/{len(batch)}")
            time.sleep(0.5)  # Delay between batches

        except Exception as e:
            print(f"✗ Error: {str(e)[:30]}")

    total_found = len(specs)
    accuracy = (total_found / len(OFFICIAL_SITE_PRIORITY_SPECS) * 100) if OFFICIAL_SITE_PRIORITY_SPECS else 0

    print(f"\n  Phase 0 Complete: {total_found}/{len(OFFICIAL_SITE_PRIORITY_SPECS)} specs ({accuracy:.1f}%)")

    return {"specs": specs, "citations": citations}


# ============================================================================
# PHASE 1: PER-SPEC SEARCH + SNIPPET EXTRACTION
# ============================================================================

@exponential_backoff_retry()
def google_custom_search(query: str, search_engine_id: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Execute Google Custom Search API call with specified search engine."""
    # Small delay to avoid rate limits (distributed across parallel workers)
    time.sleep(random.uniform(0.05, 0.15))

    params = {
        "key": GOOGLE_API_KEY,
        "cx": search_engine_id,
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

    # Handle rate limit responses
    if response.status_code == 429:
        raise Exception("Rate limit exceeded (429)")

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

    prompt = f"""Extract the {human_name} for the LATEST MODEL of {car_name} from these search snippets.

SEARCH RESULTS:
{snippets_text}

Extract the {human_name} value and return a JSON object:
{{
    "value": "the extracted value with units (concise, max 15 words)",
    "source_url": "URL of the result you extracted from"
}}

Rules:
- Extract the MOST RECENT model data available (prefer {CURRENT_YEAR} or latest year mentioned)
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


def phase1_per_spec_search(car_name: str, existing_specs: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Phase 1: For each remaining spec, do one search query and extract from snippets.

    Searches only specs not already found in Phase 0 (official site).

    Returns: {specs: {spec_name: value}, citations: {spec_name: {source_url}}}
    """
    print(f"\n{'='*60}")
    print(f"PHASE 1: PER-SPEC SEARCH + SNIPPET EXTRACTION")
    print(f"{'='*60}\n")

    existing_specs = existing_specs or {}
    specs = {}
    citations = {}

    def search_and_extract(spec_name):
        """Search and extract a single spec."""
        keyword = SPEC_KEYWORDS.get(spec_name, spec_name.replace("_", " "))
        # Use enhanced query with "latest" for most current results
        query = build_enhanced_query(car_name, keyword, enhance=True)

        try:
            # Search with exponential backoff
            search_results = google_custom_search(query, SEARCH_ENGINE_ID, num_results=5)

            # Extract from snippets
            result = extract_spec_from_snippets(car_name, spec_name, search_results)

            return spec_name, result["value"], result["source_url"]

        except Exception as e:
            # Log rate limit errors
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"    Rate limit hit for {spec_name}, will retry...")
            return spec_name, "Not found", "N/A"

    # Find specs not yet found
    remaining_specs = [
        s for s in CAR_SPECS
        if s not in existing_specs or existing_specs.get(s) in ["Not found", "Not Available", ""]
    ]

    print(f"  Searching {len(remaining_specs)} remaining specs with SEARCH_ENGINE_ID...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        futures = {executor.submit(search_and_extract, spec): spec for spec in remaining_specs}

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
                    "citation_text": "From search results",
                    "engine": "SEARCH",
                }

                if value and "Not found" not in value:
                    found += 1

                if completed % 20 == 0:
                    print(f"    Progress: {completed}/{len(remaining_specs)} ({found} found)")

            except Exception:
                specs[spec_name] = "Not found"
                citations[spec_name] = {"source_url": "N/A", "citation_text": "", "engine": "SEARCH"}

    accuracy = (found / len(remaining_specs) * 100) if remaining_specs else 0
    print(f"\n  Phase 1 Complete: {found}/{len(remaining_specs)} specs ({accuracy:.1f}%)")

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
    Phase 2: Extract missing specs from AutoCarIndia in batches of 10 (parallel).
    Gemini fetches the URL itself instead of receiving HTML content.

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
    print(f"  Extracting in batches of 10 (parallel, URL-based)...\n")

    # Split into batches of 10
    batches = [missing_specs[i:i+10] for i in range(0, len(missing_specs), 10)]

    specs = {}
    citations = {}

    def extract_batch_from_url(batch):
        """Extract one batch by letting Gemini visit the URL."""
        json_template = ",\n".join([f'  "{spec}": "value or Not Available"' for spec in batch])

        prompt = f"""Visit this AutoCarIndia specifications page and extract car data for {car_name}:

**URL to visit:** {autocar_url}

**Extract these {len(batch)} specifications:**
{chr(10).join([f"- {spec}" for spec in batch])}

**RULES:**
1. Visit the URL and read the specification table
2. Extract EXACT values with units (e.g., "215/60 R17", "10.5s", "6 Airbags")
3. For descriptive specs, provide brief phrases
4. If not found, use "Not Available"
5. Return ONLY valid JSON

**Return JSON:**
{{
{json_template}
}}"""

        try:
            model = GenerativeModel(_gemini_model)
            config = GenerationConfig(
                temperature=0.1,
                top_p=0.95,
                max_output_tokens=2048,
                response_mime_type="application/json",
            )

            response = model.generate_content(prompt, generation_config=config)
            response_text = response.text

            # Parse JSON
            text = response_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            text = text.strip()

            if "{" in text and "}" in text:
                text = text[text.index("{"):text.rindex("}") + 1]

            return json_repair.loads(text)

        except Exception:
            return {}

    # Process batches in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as executor:
        futures = {executor.submit(extract_batch_from_url, batch): i for i, batch in enumerate(batches, 1)}

        recovered = 0

        for future in concurrent.futures.as_completed(futures):
            batch_num = futures[future]

            try:
                batch_idx = batch_num - 1
                batch = batches[batch_idx]
                extracted = future.result()

                batch_found = 0
                for spec_name in batch:
                    value = extracted.get(spec_name, "Not found")

                    if value and value not in ["Not found", "Not Available", ""]:
                        specs[spec_name] = value
                        citations[spec_name] = {
                            "source_url": autocar_url,
                            "citation_text": "Extracted from AutoCarIndia",
                        }
                        batch_found += 1
                        recovered += 1

                print(f"    Batch {batch_num}/{len(batches)}: {batch_found}/{len(batch)} specs")

            except Exception as e:
                print(f"    Batch {batch_num}/{len(batches)}: Error - {str(e)[:50]}")

    print(f"\n  Phase 2 Complete: Recovered {recovered}/{len(missing_specs)} specs")

    return {"specs": specs, "citations": citations}


# ============================================================================
# MAIN SCRAPING FUNCTION
# ============================================================================

def scrape_car_data_with_custom_search(car_name: str) -> Dict[str, Any]:
    """
    Main scraping function.

    Phase 0: Official brand site extraction (top 30 specs)
    Phase 1: Per-spec search for remaining specs
    Phase 2: AutoCarIndia fallback for missing specs
    """
    # Reset Gemini model to Flash at start of each car
    reset_gemini_model()

    print(f"\n{'#'*60}")
    print(f"SCRAPING: {car_name}")
    print(f"{'#'*60}")

    start_time = time.time()

    # Phase 0: Official brand site extraction
    phase0_result = phase0_official_site_extraction(car_name)
    specs = phase0_result["specs"].copy()
    citations = phase0_result["citations"].copy()

    # Phase 1: Per-spec search for remaining specs
    phase1_result = phase1_per_spec_search(car_name, existing_specs=specs)

    # Merge Phase 1 results
    for spec_name, value in phase1_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase1_result["citations"].items():
        if spec_name not in citations:
            citations[spec_name] = citation

    # Phase 2: AutoCarIndia fallback
    phase2_result = phase2_autocarindia_fallback(car_name, specs)

    # Merge Phase 2 results
    for spec_name, value in phase2_result["specs"].items():
        specs[spec_name] = value

    for spec_name, citation in phase2_result["citations"].items():
        citations[spec_name] = citation

    # Phase 3: Extract feature-specific images from AutoCarIndia
    try:
        from benchmarking_agent.extraction.images import extract_autocar_images
        images = extract_autocar_images(car_name)
    except Exception as e:
        print(f"\n  Warning: Image extraction failed - {str(e)}")
        images = {
            "hero": [],
            "exterior": [],
            "interior": [],
            "technology": [],
            "comfort": [],
            "safety": []
        }

    # Build final car_data
    car_data = {
        "car_name": car_name,
        "method": "Per-Spec Search + AutoCarIndia Fallback",
        "source_urls": [],
        "images": images,  # Add extracted images
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

    # Count by source
    official_count = sum(1 for s in CAR_SPECS if citations.get(s, {}).get("engine") == "OFFICIAL")
    search_count = sum(1 for s in CAR_SPECS if citations.get(s, {}).get("engine") == "SEARCH")
    autocar_count = sum(1 for s in CAR_SPECS if "autocarindia" in str(citations.get(s, {}).get("source_url", "")).lower())

    elapsed = time.time() - start_time
    accuracy = (final_found / len(CAR_SPECS) * 100) if CAR_SPECS else 0

    print(f"\n{'='*60}")
    print(f"COMPLETE: {final_found}/{len(CAR_SPECS)} specs ({accuracy:.1f}%)")
    print(f"Time: {elapsed:.1f}s | Sources: {len(car_data['source_urls'])}")
    print(f"  Official: {official_count} | Search: {search_count} | AutoCar: {autocar_count}")
    print(f"{'='*60}\n")

    return car_data


# ============================================================================
# IMAGE EXTRACTION
# ============================================================================

def extract_car_images(car_name: str) -> Dict[str, List[str]]:
    """
    Extract car images for different sections using Google Custom Search.

    Returns: {
        "hero": [url1, url2],  # Main exterior images
        "exterior": [url1, url2, ...],  # Exterior detail images
        "interior": [url1, url2, ...],  # Interior images
        "technology": [url1, url2, ...],  # Tech feature images
        "comfort": [url1, url2, ...],  # Comfort feature images
        "safety": [url1, url2, ...]  # Safety feature images
    }
    """
    print(f"\n{'='*60}")
    print(f"EXTRACTING IMAGES FOR: {car_name}")
    print(f"{'='*60}\n")

    image_categories = {
        "hero": f"{car_name} official exterior",
        "exterior": f"{car_name} exterior details wheels headlights",
        "interior": f"{car_name} interior dashboard seats",
        "technology": f"{car_name} infotainment screen digital cluster technology",
        "comfort": f"{car_name} comfort features seats sunroof",
        "safety": f"{car_name} safety features airbags ADAS"
    }

    results = {}

    def search_images(category, query):
        """Search for images in a specific category."""
        try:
            # Add searchType=image for Google Image Search
            params = {
                "key": GOOGLE_API_KEY,
                "cx": SEARCH_ENGINE_ID,
                "q": query,
                "searchType": "image",
                "num": 5,
                "imgSize": "large",
                "safe": "active"
            }

            response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=15)

            if response.status_code == 200:
                items = response.json().get("items", [])
                urls = [item.get("link", "") for item in items if item.get("link")]
                print(f"  {category.title()}: Found {len(urls)} images")
                return category, urls[:3]  # Return top 3 images per category

            return category, []

        except Exception as e:
            print(f"  {category.title()}: Error - {str(e)[:50]}")
            return category, []

    # Extract images in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(search_images, cat, query): cat
            for cat, query in image_categories.items()
        }

        for future in concurrent.futures.as_completed(futures):
            try:
                category, urls = future.result()
                results[category] = urls
            except Exception:
                pass

    print(f"\n  Image extraction complete!")
    return results


# ============================================================================
# ENTRY POINT
# ============================================================================

def scrape_car_data(
    car_name: str,
    manual_specs: Dict[str, Any] = None,
    use_custom_search: bool = True,
    pdf_specs: Dict[str, str] = None,
    use_async: bool = True
) -> Dict[str, Any]:
    """
    Main entry point for car data scraping.

    Args:
        car_name: Name of the car to scrape
        manual_specs: Pre-filled specs for code cars
        use_custom_search: Whether to use Custom Search API (legacy parameter)
        pdf_specs: Pre-filled specs from PDF (not implemented yet)
        use_async: Use async scraper for better performance (default: True)

    Returns:
        Dict with car specifications and metadata
    """
    if manual_specs and manual_specs.get('is_code_car'):
        print(f"  CODE CAR - using manual specs")
        for field in CAR_SPECS:
            if field not in manual_specs or not manual_specs[field]:
                manual_specs[field] = "Not Available"
                manual_specs[f"{field}_citation"] = {"source_url": "Manual", "citation_text": ""}
        return manual_specs

    if pdf_specs:
        print(f"  PDF prefill not implemented in this version")

    # Use async scraper if enabled
    if use_async:
        try:
            # Run async scraper in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(async_scrape_car_data(car_name))
            finally:
                loop.close()
        except Exception as e:
            print(f"Async scraping failed: {e}")
            print("Falling back to sync scraper...")

    # Fallback to sync scraper
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
    """
    Execute multiple Custom Search queries in parallel using the async scraper.
    This is the async implementation with proper rate limiting.
    """
    try:
        from benchmarking_agent.core.async_scraper import async_call_custom_search_parallel
        return await async_call_custom_search_parallel(queries, num_results, max_concurrent)
    except Exception as e:
        print(f"Async search failed, falling back to sync: {e}")
        return {}


# ============================================================================
# ASYNC SCRAPING - HIGH-PERFORMANCE MODE
# ============================================================================

async def async_scrape_car_data(car_name: str) -> Dict[str, Any]:
    """
    Async version of scrape_car_data using the high-performance async scraper.

    Benefits:
    - Concurrent API calls with rate limiting
    - Token bucket algorithm for smooth request distribution
    - Exponential backoff with tenacity
    - Circuit breaker pattern for fault tolerance
    - Connection pooling for better performance

    Args:
        car_name: Name of the car to scrape

    Returns:
        Dict with car specifications and metadata
    """
    try:
        from benchmarking_agent.core.async_scraper import (
            async_phase1_per_spec_search,
            gemini_api
        )
        from benchmarking_agent.extraction.async_images import async_extract_autocar_images
    except ImportError as e:
        print(f"Async modules not available: {e}")
        print("Falling back to sync scraper...")
        return scrape_car_data_with_custom_search(car_name)

    # Reset Gemini rate limit counter
    gemini_api.reset_rate_limit_count()

    print(f"\n{'#'*60}")
    print(f"ASYNC SCRAPING: {car_name}")
    print(f"{'#'*60}")

    start_time = time.time()

    # Phase 0: Official brand site extraction (still sync - Gemini SDK limitation)
    phase0_result = phase0_official_site_extraction(car_name)
    specs = phase0_result["specs"].copy()
    citations = phase0_result["citations"].copy()

    # Phase 1: Async per-spec search for remaining specs
    phase1_result = await async_phase1_per_spec_search(car_name, existing_specs=specs)

    # Merge Phase 1 results
    for spec_name, value in phase1_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase1_result["citations"].items():
        if spec_name not in citations:
            citations[spec_name] = citation

    # Phase 2: AutoCarIndia fallback (still sync for now)
    phase2_result = phase2_autocarindia_fallback(car_name, specs)

    # Merge Phase 2 results
    for spec_name, value in phase2_result["specs"].items():
        specs[spec_name] = value

    for spec_name, citation in phase2_result["citations"].items():
        citations[spec_name] = citation

    # Phase 3: Async image extraction
    try:
        images = await async_extract_autocar_images(car_name)
    except Exception as e:
        print(f"\n  Warning: Async image extraction failed - {str(e)}")
        images = {
            "hero": [],
            "exterior": [],
            "interior": [],
            "technology": [],
            "comfort": [],
            "safety": []
        }

    # Build final car_data
    car_data = {
        "car_name": car_name,
        "method": "Async Per-Spec Search + AutoCarIndia Fallback",
        "source_urls": [],
        "images": images,
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

    # Count by source
    official_count = sum(1 for s in CAR_SPECS if citations.get(s, {}).get("engine") == "OFFICIAL")
    search_count = sum(1 for s in CAR_SPECS if citations.get(s, {}).get("engine") in ["SEARCH", "SEARCH_ASYNC"])
    autocar_count = sum(1 for s in CAR_SPECS if "autocarindia" in str(citations.get(s, {}).get("source_url", "")).lower())

    elapsed = time.time() - start_time
    accuracy = (final_found / len(CAR_SPECS) * 100) if CAR_SPECS else 0

    print(f"\n{'='*60}")
    print(f"ASYNC COMPLETE: {final_found}/{len(CAR_SPECS)} specs ({accuracy:.1f}%)")
    print(f"Time: {elapsed:.1f}s | Sources: {len(car_data['source_urls'])}")
    print(f"  Official: {official_count} | Search: {search_count} | AutoCar: {autocar_count}")
    print(f"{'='*60}\n")

    return car_data
