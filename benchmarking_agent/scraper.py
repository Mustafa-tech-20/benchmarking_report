"""
Car Specifications Scraper using Google Custom Search + Gemini

Enhanced pipeline v3 with IMPROVED ACCURACY:
- Phase 0: Broad comprehensive search (15 results, up from 10)
- Phase 1: Bulk extraction with SMALLER GROUPS (5-8 specs, down from 20-25)
- Phase 2: Targeted search for missing specs (10 results per spec, up from 8)
- Phase 3: Alternative keywords retry
- Full URL citations
- Exponential backoff for API calls
- IMPROVED: Better Gemini prompts with structured output
- IMPROVED: Lower temperature (0.1) for consistency
- IMPROVED: Validation layer for extracted values
"""
import json
import time
import random
import requests
import concurrent.futures
from typing import Dict, Any, List, Callable
from functools import wraps

from vertexai.generative_models import GenerativeModel, GenerationConfig, Tool
try:
    from vertexai.preview import generative_models as grounding
except ImportError:
    try:
        from vertexai.generative_models import grounding
    except ImportError:
        # Fallback: create a simple grounding wrapper
        class grounding:
            @staticmethod
            def GoogleSearchRetrieval(**kwargs):
                return None

from benchmarking_agent.config import GOOGLE_API_KEY, SEARCH_ENGINE_ID, CUSTOM_SEARCH_URL, SEARCH_SITES


# SIMPLIFIED: Per-spec search approach (1 spec = 1 query)
SEARCH_WORKERS = 15  # Parallel searches for 87 specs
GEMINI_WORKERS = 15  # Parallel extractions
SEARCH_RESULTS_PER_SPEC = 10  # Results per spec query
ACCURACY_THRESHOLD = 80  # Trigger retry only if below this
BROAD_SEARCH_RESULTS = 15  # Not used in new simplified approach

# IMPROVED: More conservative retry settings
MAX_RETRIES = 3
BASE_DELAY = 1.5  # Increased from 1.0
MAX_DELAY = 30.0

# IMPROVED: Better generation config for Gemini (consistent extraction)
# Note: Temperature set to 0.3 (not too low to avoid blocking, not too high for consistency)
GENERATION_CONFIG = GenerationConfig(
    temperature=0.3,  # Balanced - low enough for consistency, high enough to avoid blocking
    top_p=0.95,
    top_k=40,
      # Increased to allow full responses for 8 specs
)


def exponential_backoff_retry(max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY):
    """Decorator for exponential backoff retry with jitter."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                        time.sleep(delay)
            # All retries failed
            raise last_exception
        return wrapper
    return decorator


def call_gemini_with_retry(prompt: str, model_name: str = "gemini-2.5-flash", max_retries: int = MAX_RETRIES) -> str:
    """Call Gemini API with exponential backoff retry and improved config."""
    last_error = None
    for attempt in range(max_retries):
        try:
            model = GenerativeModel(model_name)

            # Try with generation config first
            try:
                response = model.generate_content(prompt, generation_config=GENERATION_CONFIG)
                # Check if response has text
                if hasattr(response, 'text') and response.text:
                    return response.text.strip()
                # If no text, try accessing candidates
                if hasattr(response, 'candidates') and response.candidates:
                    if hasattr(response.candidates[0].content, 'parts') and response.candidates[0].content.parts:
                        text = response.candidates[0].content.parts[0].text
                        if text:
                            return text.strip()
            except Exception as config_error:
                # If generation config causes issues, try without it
                if "Cannot get the response text" in str(config_error) or "Cannot get the Candi" in str(config_error):
                    response = model.generate_content(prompt)  # Without config
                    if hasattr(response, 'text') and response.text:
                        return response.text.strip()
                else:
                    raise config_error

            # If we get here, no text was returned
            raise ValueError("Empty response from model")

        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            # Check if it's a retryable error
            if any(x in error_str for x in ["429", "rate", "quota", "resource", "503", "500", "timeout", "empty response"]):
                if attempt < max_retries - 1:
                    delay = min(BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                    time.sleep(delay)
                continue
            else:
                # Non-retryable error, raise immediately
                raise e
    # All retries exhausted
    raise last_error


# 87 specs with targeted search keywords (from car_search.py)
SPEC_QUERIES = {
    # Basic Info
    "price_range": "price ex-showroom on-road cost variants lakh",
    "mileage": "mileage fuel efficiency kmpl ARAI certified real world",
    "user_rating": "user rating owner review score stars out of 5",
    "seating_capacity": "seating capacity seats passengers seater",

    # Engine & Performance
    "performance": "engine power bhp hp horsepower specs kW",
    "torque": "torque Nm engine pulling power peak",
    "transmission": "transmission gearbox manual automatic 6-speed DCT CVT",
    "acceleration": "acceleration 0-100 kmph seconds sprint time",

    # Braking & Safety
    "braking": "braking system disc drum front rear caliper",
    "brakes": "ABS EBD brake assist emergency braking system",
    "brake_performance": "braking distance stopping power test 100-0",
    "vehicle_safety_features": "safety features airbags ADAS NCAP rating ESP",
    "impact": "crash test safety rating NCAP stars adult child",

    # Steering & Handling
    "steering": "steering feel weight electric hydraulic EPS feedback",
    "telescopic_steering": "tilt telescopic steering adjustment column",
    "turning_radius": "turning radius circle meters kerb to kerb",
    "stability": "high speed stability highway cruising 120 kmph",
    "corner_stability": "cornering handling curves grip body roll",
    "straight_ahead_stability": "straight line stability highway tracking",

    # Ride & Suspension
    "ride": "ride quality comfort suspension setup feel",
    "ride_quality": "ride comfort smooth rough roads bumpy surfaces",
    "stiff_on_pot_holes": "pothole absorption suspension stiffness harsh impact",
    "bumps": "bump absorption rough road handling speed breaker",
    "shocks": "suspension setup dampers ride comfort absorbers",

    # NVH (Noise Vibration Harshness)
    "nvh": "NVH noise vibration harshness levels cabin insulation",
    "powertrain_nvh": "engine noise vibration refinement idle clatter",
    "wind_nvh": "wind noise cabin insulation highway speeds sealing",
    "road_nvh": "road noise tyre noise cabin quiet insulation",
    "wind_noise": "wind noise highway speeds aerodynamic 100 120 kmph",
    "tire_noise": "tyre noise road surface cabin rubber pattern",
    "turbo_noise": "turbo whistle sound diesel turbocharger boost",

    # Transmission Feel
    "manual_transmission_performance": "manual gearbox shift quality clutch notchy smooth",
    "automatic_transmission_performance": "automatic gearbox smooth shifts response torque converter",
    "pedal_operation": "clutch pedal feel light heavy travel range",
    "gear_shift": "gear shift quality notchy smooth slick throw",
    "gear_selection": "gear lever throw precision feel slot gate",
    "pedal_travel": "pedal travel stroke accelerator brake clutch",
    "crawl": "low speed crawl traffic driving creep mode",

    # Driving Dynamics
    "driveability": "driveability daily driving city traffic ease",
    "performance_feel": "driving feel sporty responsive quick agile",
    "city_performance": "city driving traffic mileage fuel efficiency urban",
    "highway_performance": "highway driving cruising stability overtaking",
    "off_road": "off-road capability 4x4 terrain modes ground clearance",
    "manoeuvring": "manoeuvring tight spaces parking u-turn ease",

    # Vibration & Feel Issues
    "jerks": "jerky acceleration smooth power delivery judder",
    "pulsation": "brake pulsation vibration pedal judder disc",
    "shakes": "steering shake vibration wheels shimmy",
    "shudder": "shudder vibration acceleration braking clutch",
    "grabby": "brake grabbiness initial bite feel progressive",
    "spongy": "brake pedal spongy firm feel travel",
    "rattle": "rattle squeak creak cabin quality build noise",

    # Interior & Comfort
    "interior": "interior quality materials fit finish plastics leather",
    "climate_control": "AC climate control cooling heating automatic dual zone",
    "seats": "seat comfort cushioning support bolstering contour",
    "seat_cushion": "seat cushion foam density soft firm thigh support",
    "visibility": "visibility windshield pillars blind spots IRVM view",
    "soft_trims": "soft touch materials dashboard quality premium feel",
    "armrest": "armrest center console comfort storage elbow rest",
    "headrest": "headrest comfort adjustable support height angle",
    "egress": "egress exit getting out ease door opening",
    "ingress": "ingress entry getting in ease step height",

    # Features & Tech
    "infotainment_screen": "infotainment touchscreen display size inch resolution",
    "resolution": "screen resolution display quality clarity pixels HD",
    "touch_response": "touchscreen response lag smooth interface speed",
    "apple_carplay": "Apple CarPlay Android Auto wireless wired",
    "digital_display": "digital cluster instrument display TFT screen",
    "button": "physical buttons controls tactile knobs switches",

    # Exterior & Lighting
    "lighting": "headlights LED projector beam pattern throw range",
    "led": "LED lights headlamp tail lamp DRL indicators",
    "drl": "DRL daytime running lights LED signature design",
    "tail_lamp": "tail lamp rear lights LED design signature",
    "alloy_wheel": "alloy wheels size design inch 18 19 diamond cut",

    # Convenience Features
    "sunroof": "sunroof panoramic moonroof glass roof electric",
    "irvm": "IRVM inside rear view mirror auto dimming electro",
    "orvm": "ORVM outside mirror electric folding auto heated",
    "window": "power windows one touch auto up down",
    "wiper_control": "wiper rain sensing automatic intermittent",
    "parking": "parking sensors camera 360 degree rear front",
    "epb": "electronic parking brake EPB auto hold hill",
    "door_effort": "door operation effort quality feel weight thud",

    # Dimensions & Space
    "boot_space": "boot space luggage capacity litres liters trunk",
    "wheelbase": "wheelbase length dimensions mm millimeter",
    "chasis": "chassis frame platform ladder monocoque construction",

    # Other
    "blower_noise": "AC blower noise fan sound cabin loud speed",
    "response": "throttle response accelerator pickup lag turbo",
    "sensitivity": "controls sensitivity steering throttle brake feel",
    "seats_restraint": "seatbelt pretensioner ISOFIX child safety load limiter",
}


# Alternative keywords for Phase 3 retry
ALT_KEYWORDS = {
    # Basic Info
    "price_range": "cost rupees lakh starting price base top variant",
    "mileage": "fuel economy average real world city highway kmpl",
    "user_rating": "owner review feedback satisfaction score rating percentage",
    "seating_capacity": "5 seater passengers cabin space occupants legroom",

    # Engine & Performance
    "performance": "bhp ps horsepower kW engine output power specs",
    "torque": "Nm pulling power diesel petrol engine torque figure",
    "transmission": "gearbox automatic manual 6-speed AT MT DCT",
    "acceleration": "0-100 sprint time seconds quick pickup fast",

    # Braking & Safety
    "braking": "disc drum brake system front rear ventilated",
    "brakes": "ABS EBD brake assist hill hold emergency",
    "brake_performance": "stopping distance 100-0 braking test meters",
    "vehicle_safety_features": "airbags ADAS ESP NCAP rating safety features",
    "impact": "crash test NCAP BNCAP safety rating stars adult child",

    # Steering & Handling
    "steering": "EPS electric power steering feel weight feedback",
    "telescopic_steering": "tilt telescopic steering adjustment column reach height",
    "turning_radius": "turning circle kerb meters minimum radius",
    "stability": "high speed highway 120 kmph stability cruising",
    "corner_stability": "cornering grip body roll handling curves bend",
    "straight_ahead_stability": "straight line tracking highway stability lane",

    # Ride & Suspension
    "ride": "ride quality suspension comfort setup damping",
    "ride_quality": "comfort smooth rough roads potholes absorption",
    "stiff_on_pot_holes": "harsh stiff pothole impact suspension firm",
    "bumps": "speed breaker bump absorption rough road cushioning",
    "shocks": "FSD frequency selective dampers suspension tuning comfort",

    # NVH
    "nvh": "noise vibration harshness cabin insulation refinement quiet",
    "powertrain_nvh": "engine noise vibration diesel clatter refinement idle",
    "wind_nvh": "wind noise highway speeds cabin insulation sealing",
    "road_nvh": "road noise tyre cabin insulation quiet highway",
    "wind_noise": "wind noise 100 120 kmph highway aerodynamic",
    "tire_noise": "tyre noise road surface pattern rubber cabin",
    "turbo_noise": "turbo whistle boost sound diesel turbocharger whine",

    # Transmission Feel
    "manual_transmission_performance": "manual gearbox shift quality clutch notchy smooth throw",
    "automatic_transmission_performance": "AT gearbox smooth shifts response kickdown torque converter",
    "pedal_operation": "clutch pedal feel light heavy effort bite point",
    "gear_shift": "gear shift throw quality notchy smooth slick",
    "gear_selection": "gear lever slot gate feel rubbery precise",
    "pedal_travel": "pedal stroke distance clutch brake accelerator travel",
    "crawl": "low speed traffic creep first gear bumper crawling",

    # Driving Dynamics
    "driveability": "daily driving city traffic ease maneuverability",
    "performance_feel": "driving feel sporty responsive quick agile dynamic",
    "city_performance": "city driving urban mileage traffic fuel efficiency",
    "highway_performance": "highway cruising overtaking 100 120 kmph stability",
    "off_road": "4x4 4WD terrain modes ground clearance off-road capability",
    "manoeuvring": "tight spaces parking u-turn turning ease maneuverability",

    # Vibration & Feel Issues
    "jerks": "smooth power delivery linear turbo lag hesitation jerk",
    "pulsation": "brake pulsation vibration judder warped disc pedal",
    "shakes": "steering vibration shimmy wheel wobble shake speed",
    "shudder": "shudder vibration acceleration braking clutch judder",
    "grabby": "brake initial bite progressive grabby feel confidence",
    "spongy": "brake pedal feel firm soft spongy feedback",
    "rattle": "rattle squeak creak cabin quality build noise plastic",

    # Interior & Comfort
    "interior": "interior quality materials fit finish dashboard plastics",
    "climate_control": "AC automatic dual zone cooling heating rear vents",
    "seats": "seat comfort cushioning support bolstering lumbar thigh",
    "seat_cushion": "seat foam density soft firm thigh support cushion",
    "visibility": "windshield pillars blind spots IRVM forward rear view",
    "soft_trims": "soft touch dashboard materials premium quality feel",
    "armrest": "center armrest console comfort storage elbow support",
    "headrest": "headrest adjustable height angle cushion neck support",
    "egress": "exit getting out door step down ease height",
    "ingress": "entry getting in step height door ease access",

    # Features & Tech
    "infotainment_screen": "touchscreen display size inch resolution infotainment",
    "resolution": "screen display quality pixels clarity HD sharpness",
    "touch_response": "touchscreen response lag smooth interface speed",
    "apple_carplay": "CarPlay Android Auto wireless wired connectivity",
    "digital_display": "digital cluster instrument TFT screen display",
    "button": "physical buttons knobs controls tactile switches",

    # Exterior & Lighting
    "lighting": "headlights LED projector beam throw brightness night",
    "led": "LED headlamp tail lamp DRL indicators lights",
    "drl": "DRL daytime running lights LED signature design",
    "tail_lamp": "tail lamp rear lights LED design brake light",
    "alloy_wheel": "alloy wheels size 18 19 inch design diamond cut",

    # Convenience Features
    "sunroof": "panoramic sunroof moonroof glass roof electric size",
    "irvm": "IRVM inside rear view mirror auto dimming electro",
    "orvm": "ORVM side mirror electric fold auto retract heated",
    "window": "power windows one touch auto up down all",
    "wiper_control": "wiper rain sensing automatic intermittent speed",
    "parking": "parking sensors camera 360 degree rear front assist",
    "epb": "electronic parking brake EPB auto hold hill assist",
    "door_effort": "door closing thud sound quality weight feel slam",

    # Dimensions & Space
    "boot_space": "boot luggage trunk capacity litres liters space",
    "wheelbase": "wheelbase length dimensions mm millimeters size",
    "chasis": "chassis frame ladder monocoque platform construction body",

    # Other
    "blower_noise": "AC blower fan noise cabin loud speed sound",
    "response": "throttle response accelerator pickup lag turbo quick",
    "sensitivity": "controls sensitivity steering throttle brake feel light",
    "seats_restraint": "seatbelt pretensioner ISOFIX child seat load limiter",
}


# The 87 specs list
CAR_SPECS = list(SPEC_QUERIES.keys())


def custom_search(query: str, spec_name: str) -> dict:
    """Execute a single Custom Search API call with exponential backoff."""
    params = {
        "key": GOOGLE_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "q": query,
        "num": SEARCH_RESULTS_PER_SPEC,
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                results = [{
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "domain": item.get("displayLink", ""),
                    "url": item.get("link", ""),
                } for item in items]
                return {"spec": spec_name, "results": results, "query": query}

            elif response.status_code in [429, 500, 503]:
                # Retryable errors
                last_error = f"HTTP {response.status_code}"
                if attempt < MAX_RETRIES - 1:
                    delay = min(BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                    time.sleep(delay)
                continue
            else:
                return {"spec": spec_name, "results": [], "error": f"HTTP {response.status_code}"}

        except requests.exceptions.Timeout:
            last_error = "Timeout"
            if attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                time.sleep(delay)
            continue
        except Exception as e:
            last_error = str(e)
            if attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                time.sleep(delay)
            continue

    return {"spec": spec_name, "results": [], "error": last_error or "Max retries exceeded"}


def extract_spec_value(spec_name: str, search_data: dict, car_name: str) -> dict:
    """Extract spec value using Gemini with full citations."""

    results = search_data.get("results", [])
    if not results:
        return {"spec": spec_name, "value": "Not Available", "citations": []}

    citations = [
        {
            "url": r.get("url", ""),
            "domain": r.get("domain", ""),
            "title": r.get("title", ""),
            "snippet": r.get("snippet", "")[:200] + "..." if len(r.get("snippet", "")) > 200 else r.get("snippet", "")
        }
        for r in results
    ]

    # Combine all snippets for richer context
    context = "\n\n".join([f"[{r.get('domain', '')}] {r.get('title', '')}\n{r.get('snippet', '')}" for r in results])

    # Spec-specific format hints with examples
    format_hints = {
        "price_range": "₹X.XX Lakh onwards OR ₹X-Y Lakh (e.g., ₹11.35-17.19 Lakh)",
        "mileage": "X.X kmpl (e.g., 15.2 kmpl, 12-18 kmpl)",
        "user_rating": "X.X/5 or X stars (e.g., 4.2/5)",
        "seating_capacity": "X Seater (e.g., 5 Seater)",
        "performance": "XXX bhp (e.g., 150 bhp, 130 bhp / 300 Nm)",
        "torque": "XXX Nm (e.g., 300 Nm)",
        "transmission": "Type + speed (e.g., 6-speed Manual, Automatic CVT)",
        "acceleration": "X.X seconds (0-100) (e.g., 10.2 seconds)",
        "turning_radius": "X.X meters (e.g., 5.3 meters)",
        "boot_space": "XXX litres (e.g., 420 litres)",
        "wheelbase": "XXXX mm (e.g., 2750 mm)",
        "nvh": "Description (e.g., well insulated, refined cabin, noticeable engine noise)",
        "ride_quality": "Description (e.g., comfortable, stiff on rough roads, plush ride)",
        "steering": "Type + feel (e.g., electric power steering, light and precise)",
        "braking": "Type (e.g., disc/drum, front disc rear drum, 4-wheel disc)",
    }

    format_hint = format_hints.get(spec_name, "concise value with units if applicable")
    human_name = spec_name.replace('_', ' ').title()

    prompt = f"""Extract "{human_name}" for {car_name} from these search results.

SEARCH RESULTS:
{context}

INSTRUCTIONS:
1. Find information about {human_name} for {car_name}
2. Return ONLY the extracted value
3. Maximum 15 words
4. Include units where applicable
5. Format hint: {format_hint}

EXAMPLES of good responses:
- "₹11.35-17.19 Lakh"
- "15.2 kmpl"
- "4.2/5"
- "6-speed Manual / 6-speed AT"
- "150 bhp / 300 Nm"
- "Well insulated cabin, minimal NVH"
- "Comfortable on highways, stiff on rough roads"

If information is genuinely NOT in the search results, return: "Not found"

VALUE:"""

    try:
        # Use retry logic for Gemini call
        value = call_gemini_with_retry(prompt, "gemini-2.5-flash")

        # Clean up response
        if value.startswith("VALUE:"):
            value = value[6:].strip()
        # Remove markdown formatting
        value = value.replace("**", "").replace("*", "")
        # Take only first line if multiple lines
        if "\n" in value:
            value = value.split("\n")[0].strip()
        # Remove quotes if wrapped
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        # Truncate if too long
        if len(value) > 100 and "Not" not in value:
            value = value[:100] + "..."

        return {"spec": spec_name, "value": value, "citations": citations}
    except Exception as e:
        return {"spec": spec_name, "value": f"Error: {str(e)[:50]}", "citations": citations}


def validate_spec_value(spec_name: str, value: str) -> bool:
    """
    IMPROVED: Validate if extracted value makes sense for the spec type.
    Returns True if valid, False if suspicious/missing.

    This helps catch hallucinated or incorrect extractions.
    """
    if not value or value in ["Not found", "Not Available", "N/A", "Error", "", "—", "-"]:
        return False

    value_lower = value.lower()

    # Spec-specific validation - check if value contains expected keywords/units
    validations = {
        # Numeric with units
        "price_range": ["lakh", "₹", "rs", "crore"],
        "mileage": ["kmpl", "km/l", "mpg", "km/kg"],
        "performance": ["bhp", "hp", "ps", "kw"],
        "torque": ["nm", "kgm"],
        "seating_capacity": ["seater", "seat"],
        "acceleration": ["sec", "second"],
        "turning_radius": ["meter", "m", "feet", "ft"],
        "boot_space": ["litre", "liter", "l"],
        "wheelbase": ["mm", "cm", "meter"],

        # Specific terms
        "transmission": ["manual", "automatic", "amt", "dct", "cvt", "speed"],
        "braking": ["disc", "drum", "brake", "abs", "ebd"],
        "steering": ["power", "steering", "hydraulic", "electric", "light", "heavy"],
    }

    if spec_name in validations:
        keywords = validations[spec_name]
        has_keyword = any(kw in value_lower for kw in keywords)
        return has_keyword

    # For subjective specs, just check it's not too short and contains some content
    if len(value) >= 5 and not value.startswith("Not"):
        return True

    return False


def retry_extract_spec(car_name: str, spec_name: str, search_results: list) -> str:
    """Retry extraction with more aggressive prompt - returns concise value."""
    if not search_results:
        return "Not Available"

    # Build richer context
    context_parts = []
    for r in search_results[:8]:
        domain = r.get('domain', '')
        title = r.get('title', '')
        snippet = r.get('snippet', '')
        if snippet:
            context_parts.append(f"[{domain}] {title}\n{snippet}")

    context = "\n\n".join(context_parts)
    human_name = spec_name.replace('_', ' ').title()

    prompt = f"""Your task: Extract "{human_name}" for {car_name}.

SEARCH DATA:
{context}

EXTRACTION RULES:
1. Find the value for {human_name}
2. Return ONLY the value (max 15 words)
3. Include units where applicable
4. For subjective specs, use brief descriptors
5. If truly not found, return "Not Available"

EXAMPLES:
- price_range: "₹12.5-18.9 Lakh"
- mileage: "16.8 kmpl"
- nvh: "Refined cabin, minimal vibrations"
- ride_quality: "Comfortable, handles bumps well"
- steering: "Light, precise feedback"

VALUE:"""

    try:
        value = call_gemini_with_retry(prompt, "gemini-2.5-flash")
        if value.startswith("VALUE:"):
            value = value[6:].strip()
        value = value.replace("**", "").replace("*", "")
        if "\n" in value:
            value = value.split("\n")[0].strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if len(value) > 100:
            value = value[:100] + "..."
        return value
    except Exception as e:
        return f"Error: {str(e)[:30]}"


def broad_search(car_name: str) -> dict:
    """
    PHASE 0: Run broad comprehensive searches to get rich context.
    Returns combined results from multiple broad queries.
    """
    print(f"\n{'='*60}")
    print(f"PHASE 0: BROAD COMPREHENSIVE SEARCH")
    print(f"{'='*60}\n")

    # Multiple broad queries to get diverse review pages
    base_queries = [
        f"{car_name} full review specifications price mileage features",
        f"{car_name} expert review test drive pros cons verdict",
        f"{car_name} owner review real world experience 2026",
        f"{car_name} variants comparison specifications price list",
        f"{car_name} interior exterior features safety rating",
        f"{car_name} ride handling steering NVH comfort review",
    ]

    # Add site: operators to each query, rotating through sites
    broad_queries = []
    if SEARCH_SITES:
        for i, base_query in enumerate(base_queries):
            site = SEARCH_SITES[i % len(SEARCH_SITES)]
            broad_queries.append(f"{base_query} site:{site}")
    else:
        broad_queries = base_queries

    all_results = []
    domain_counts = {}

    for query in broad_queries:
        print(f"  Broad: {query[:55]}...")
        result = custom_search(query, "broad")
        results = result.get("results", [])
        all_results.extend(results)
        for r in results:
            domain = r.get("domain", "")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        time.sleep(0.3)  # Small delay

    # Deduplicate by URL
    unique_urls = {}
    for r in all_results:
        url = r.get("url", "")
        if url and url not in unique_urls:
            unique_urls[url] = r

    unique_results = list(unique_urls.values())
    print(f"  Broad search: {len(unique_results)} unique URLs from {len(domain_counts)} domains")

    return {
        "results": unique_results,
        "domain_counts": domain_counts
    }


def bulk_extract_specs(car_name: str, search_results: List[dict], specs_to_extract: List[str]) -> dict:
    """
    IMPROVED PHASE 1: Extract multiple specs at once from combined search snippets.

    Key improvements:
    - Better prompt with clearer instructions and structured format
    - More context (25 snippets vs 20)
    - Line-by-line format instead of JSON (easier for model)
    - Better examples for each spec type
    """
    if not search_results:
        return {spec: "Not found" for spec in specs_to_extract}

    # IMPROVED: Use more snippets for richer context
    context_parts = []
    for r in search_results[:25]:  # Increased from 20
        domain = r.get("domain", "")
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        if snippet:
            context_parts.append(f"[{domain}] {title}\n{snippet}")

    context = "\n\n".join(context_parts)

    # IMPROVED: Better format hints with examples
    format_hints = {
        "price_range": "₹X.XX Lakh - ₹Y.YY Lakh (e.g., ₹11.35-17.19 Lakh)",
        "mileage": "X.X kmpl or X-Y kmpl range (e.g., 15.2 kmpl, 12-18 kmpl)",
        "user_rating": "X.X/5 stars (e.g., 4.2/5, 4 stars)",
        "seating_capacity": "X Seater (e.g., 5 Seater, 7 Seater)",
        "performance": "XXX bhp or XXX PS (e.g., 150 bhp, 130 PS)",
        "torque": "XXX Nm or XX kgm (e.g., 300 Nm, 32 kgm)",
        "transmission": "Type with speeds (e.g., 6-speed Manual, 6-speed Automatic, CVT)",
        "acceleration": "X.X seconds 0-100 km/h (e.g., 10.2 sec, 9.5 seconds)",
        "turning_radius": "X.X meters (e.g., 5.3m, 5.75 meters)",
        "boot_space": "XXX litres (e.g., 420 litres, 350L)",
        "wheelbase": "XXXX mm (e.g., 2750 mm, 2700mm)",
        "braking": "Type of brakes (e.g., Disc/Drum, 4-wheel disc, Front disc rear drum)",
        "steering": "Type + feel (e.g., Electric Power Steering - light, Hydraulic - heavy)",
        "nvh": "Brief description (e.g., Well insulated, Refined cabin, Some road noise)",
        "ride_quality": "Brief description (e.g., Comfortable, Stiff on rough roads, Plush)",
        "interior_quality": "Brief description (e.g., Premium materials, Basic plastics, Well finished)",
    }

    # Build spec list with hints
    specs_list_parts = []
    for i, spec in enumerate(specs_to_extract, 1):
        hint = format_hints.get(spec, "concise value")
        human = spec.replace("_", " ").title()
        specs_list_parts.append(f"{i}. {spec}: {human} - Expected format: {hint}")

    specs_list = "\n".join(specs_list_parts)

    # IMPROVED: Better prompt with line-by-line output format (easier than JSON)
    prompt = f"""Extract specifications for the {car_name} from the search results below.

SEARCH RESULTS:
{context}

SPECIFICATIONS TO EXTRACT:
{specs_list}

INSTRUCTIONS:
- Extract ONLY information explicitly stated in the search results
- Return answer in this EXACT format for each spec (one per line):
  spec_name: extracted_value
- Keep values concise (max 15 words)
- Include units where applicable (bhp, Nm, kmpl, Lakh, etc.)
- If a spec is NOT found in the search results, write: spec_name: Not found
- DO NOT make up or infer values
- DO NOT include any explanations or notes

GOOD EXAMPLES:
price_range: ₹11.35-17.19 Lakh
mileage: 15.2 kmpl
performance: 150 bhp
torque: 300 Nm
seating_capacity: 5 Seater
transmission: 6-speed Manual / 6-speed Automatic
nvh: Well insulated cabin, minimal road noise
ride_quality: Comfortable on highways, stiff on rough roads
braking: Front disc, rear drum
steering: Electric power steering, light feel

NOW EXTRACT (one spec per line):"""

    try:
        response = call_gemini_with_retry(prompt, "gemini-2.5-flash")

        # IMPROVED: Parse line-by-line response (more reliable than JSON)
        extracted = {}
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            if ":" in line:
                # Split on first colon only
                parts = line.split(":", 1)
                if len(parts) == 2:
                    spec = parts[0].strip()
                    value = parts[1].strip()

                    # Clean up value
                    value = value.replace("**", "").replace("*", "")
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    if len(value) > 100:
                        value = value[:100] + "..."

                    # Match spec to expected spec names
                    for expected_spec in specs_to_extract:
                        if expected_spec in spec or spec in expected_spec:
                            extracted[expected_spec] = value
                            break

        # Fill in missing specs
        for spec in specs_to_extract:
            if spec not in extracted:
                extracted[spec] = "Not found"

        # Count found specs
        found = sum(1 for v in extracted.values() if v and "Not" not in str(v) and "Error" not in str(v))
        print(f"    → Bulk extracted {found}/{len(specs_to_extract)} specs")

        return extracted

    except Exception as e:
        print(f"  Bulk extraction error: {str(e)[:50]}")
        return {spec: "Not found" for spec in specs_to_extract}


def parallel_search(car_name: str, specs_to_search: List[str] = None) -> dict:
    """Run search queries in parallel."""
    if specs_to_search is None:
        specs_to_search = CAR_SPECS

    print(f"\n{'='*60}")
    print(f"PHASE 2: TARGETED SEARCH ({len(specs_to_search)} queries)")
    print(f"{'='*60}\n")

    all_results = {}

    def search_task(spec_name):
        keywords = SPEC_QUERIES.get(spec_name, spec_name.replace('_', ' '))
        # Rotate through sites to ensure all are queried
        if SEARCH_SITES:
            spec_index = list(CAR_SPECS).index(spec_name) if spec_name in CAR_SPECS else 0
            site = SEARCH_SITES[spec_index % len(SEARCH_SITES)]
            query = f"{car_name} {keywords} site:{site}"
        else:
            query = f"{car_name} {keywords}"
        return custom_search(query, spec_name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        futures = {executor.submit(search_task, spec): spec for spec in specs_to_search}
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            spec_name = futures[future]
            completed += 1
            try:
                result = future.result()
                all_results[spec_name] = result
                if completed % 20 == 0:
                    print(f"  Search: {completed}/{len(futures)}")
            except Exception:
                all_results[spec_name] = {"spec": spec_name, "results": []}

    print(f"  Search complete: {len(all_results)} specs")
    return all_results


def parallel_extract(car_name: str, search_results: dict) -> dict:
    """Run Gemini extractions in parallel."""
    print(f"\n{'='*60}")
    print(f"PHASE 2: PARALLEL EXTRACTION ({len(search_results)} specs)")
    print(f"{'='*60}\n")

    specs = {}
    all_citations = {}

    def extract_task(spec_name, search_data):
        return extract_spec_value(spec_name, search_data, car_name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as executor:
        futures = {executor.submit(extract_task, spec, data): spec for spec, data in search_results.items()}
        completed = 0
        found_count = 0
        for future in concurrent.futures.as_completed(futures):
            spec_name = futures[future]
            completed += 1
            try:
                result = future.result()
                value = result["value"]
                citations = result.get("citations", [])
                specs[spec_name] = value
                if citations:
                    all_citations[spec_name] = {
                        "source_url": citations[0].get("url", "N/A"),
                        "citation_text": citations[0].get("snippet", ""),
                        "all_sources": citations
                    }
                if value and "Not" not in value and "Error" not in value:
                    found_count += 1
                if completed % 20 == 0:
                    print(f"  Extract: {completed}/{len(futures)} ({found_count} found)")
            except Exception:
                specs[spec_name] = "Not Available"

    print(f"  Extraction complete: {found_count}/{len(search_results)} found")
    return {"specs": specs, "citations": all_citations}


def retry_missing_specs(car_name: str, specs: dict, citations: dict, search_results: dict) -> tuple:
    """Phase 3: Retry missing specs with alternative keywords."""
    missing = [k for k, v in specs.items()
               if "Not" in str(v) or "Error" in str(v)]

    retry_specs = [s for s in missing if s in ALT_KEYWORDS]
    if not retry_specs:
        return specs, citations

    print(f"\n{'='*60}")
    print(f"PHASE 3: RETRY ({len(retry_specs)} specs)")
    print(f"{'='*60}\n")

    def retry_task(spec_name):
        alt_keywords = ALT_KEYWORDS[spec_name]
        query = f"{car_name} {alt_keywords}"
        search_result = custom_search(query, spec_name)
        results = search_result.get("results", [])
        if not results:
            original = search_results.get(spec_name, {})
            results = original.get("results", [])
        if not results:
            return spec_name, "Not Available", []
        new_citations = [
            {"url": r.get("url", ""), "domain": r["domain"], "title": r["title"],
             "snippet": r["snippet"][:200] + "..." if len(r["snippet"]) > 200 else r["snippet"]}
            for r in results
        ]
        value = retry_extract_spec(car_name, spec_name, results)
        return spec_name, value, new_citations

    recovered = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as executor:
        futures = {executor.submit(retry_task, spec): spec for spec in retry_specs}
        for future in concurrent.futures.as_completed(futures):
            spec_name = futures[future]
            try:
                spec_name, value, new_citations = future.result()
                if value and "Not" not in value and "Error" not in value:
                    recovered += 1
                    specs[spec_name] = value
                    if new_citations:
                        citations[spec_name] = {
                            "source_url": new_citations[0].get("url", "N/A"),
                            "citation_text": new_citations[0].get("snippet", ""),
                            "retry": True
                        }
            except Exception:
                pass

    print(f"  Recovered: {recovered}/{len(retry_specs)}")
    return specs, citations


def scrape_car_data_with_custom_search(car_name: str) -> Dict[str, Any]:
    """
    SIMPLIFIED scraping function - direct per-spec approach:
    Phase 1: Search + Extract each spec individually (1 spec = 1 query)
    Phase 2: Retry ONLY missing specs with alternative keywords (only if accuracy < 80%)

    NO broad searches, NO bulk extraction - simple and accurate.
    """
    print(f"\n{'#'*60}")
    print(f"SCRAPING: {car_name}")
    print(f"{'#'*60}")

    start_time = time.time()
    car_data = {"car_name": car_name, "source_urls": [], "method": "Direct Per-Spec Search"}
    citations = {}
    specs = {}

    # PHASE 1: Direct per-spec search and extraction (1 spec = 1 query)
    print(f"\n{'='*60}")
    print(f"PHASE 1: PER-SPEC SEARCH & EXTRACT (87 specs)")
    print(f"{'='*60}\n")

    def search_and_extract_spec(spec_name):
        """Search and extract a single spec"""
        keywords = SPEC_QUERIES.get(spec_name, spec_name.replace('_', ' '))
        query = f"{car_name} {keywords}"

        # Search for this specific spec
        search_result = custom_search(query, spec_name)
        results = search_result.get("results", [])

        if not results:
            return spec_name, "Not found", None

        # Extract from search results
        extraction = extract_spec_value(spec_name, {"results": results}, car_name)
        value = extraction.get("value", "Not found")
        cites = extraction.get("citations", [])

        # Build citation
        citation = None
        if cites:
            citation = {
                "source_url": cites[0].get("url", "N/A"),
                "citation_text": cites[0].get("snippet", ""),
                "all_sources": cites
            }

        return spec_name, value, citation

    # Process all 87 specs in parallel
    found_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        futures = {executor.submit(search_and_extract_spec, spec): spec for spec in CAR_SPECS}
        completed = 0

        for future in concurrent.futures.as_completed(futures):
            spec_name = futures[future]
            completed += 1

            try:
                spec_name, value, citation = future.result()
                specs[spec_name] = value

                if citation:
                    citations[spec_name] = citation
                    url = citation.get("source_url")
                    if url and url != "N/A":
                        car_data["source_urls"].append(url)

                if value and "Not" not in value and "Error" not in value:
                    found_count += 1

                if completed % 20 == 0:
                    print(f"  Progress: {completed}/{len(CAR_SPECS)} ({found_count} found)")

            except Exception as e:
                specs[spec_name] = "Not Available"
                print(f"  Error extracting {spec_name}: {str(e)[:50]}")

    # Calculate Phase 1 accuracy
    found_p1 = found_count
    accuracy_p1 = (found_p1 / len(CAR_SPECS) * 100) if CAR_SPECS else 0
    print(f"\n  Phase 1 Complete: {found_p1}/{len(CAR_SPECS)} specs found ({accuracy_p1:.1f}%)")

    # PHASE 2: Retry ALL missing specs using Gemini + Google Search (ONLY if accuracy < 80%)
    if accuracy_p1 < 80:
        # Find ALL specs we didn't get in Phase 1
        missing_specs = [k for k, v in specs.items() if "Not" in str(v) or "Error" in str(v) or not v]

        if missing_specs:
            print(f"\n{'='*60}")
            print(f"PHASE 2: GEMINI + GOOGLE SEARCH RETRY ({len(missing_specs)} specs)")
            print(f"{'='*60}\n")

            # Preferred automotive domains
            preferred_domains = [
                "team-bhp.com", "autocarindia.com", "overdrive.in", "zigwheels.com",
                "carwale.com", "cardekho.com", "autocarpro.in", "motoringworld.in"
            ]

            # Exclude non-automotive domains
            exclude_domains = ["wikipedia.org", "youtube.com", "reddit.com", "facebook.com", "twitter.com"]

            def retry_specs_with_gemini_search(spec_batch):
                """Retry a batch of specs using Gemini + Google Search (like test.py)"""
                try:
                    # Build spec list with hints
                    specs_list = []
                    for spec in spec_batch:
                        human = spec.replace("_", " ").title()
                        # Add format hints for common specs
                        hint = ""
                        if "price" in spec:
                            hint = " (e.g., ₹11.35-17.19 Lakh)"
                        elif "mileage" in spec:
                            hint = " (e.g., 15.2 kmpl)"
                        elif "rating" in spec:
                            hint = " (e.g., 4.2/5)"
                        elif spec in ["performance", "power"]:
                            hint = " (e.g., 150 bhp)"
                        elif "torque" in spec:
                            hint = " (e.g., 300 Nm)"

                        specs_list.append(f'  "{spec}": "{human}{hint}"')

                    specs_json = ",\n".join(specs_list)

                    # Create prompt (similar to test.py approach)
                    prompt = f"""Search for detailed specifications of the {car_name}. Focus on these trusted automotive review sites: {', '.join(preferred_domains)}

Extract these specifications and return in JSON format:

{{
{specs_json}
}}

INSTRUCTIONS:
- Search automotive review sites (prefer team-bhp.com, autocarindia.com, overdrive.in, zigwheels.com)
- Extract EXACT values with units (bhp, Nm, kmpl, Lakh, litres, etc.)
- For subjective specs (ride quality, NVH, steering feel): provide brief descriptions
- Keep values concise (max 15 words per spec)
- If truly not found after searching, use "Not found"

Return ONLY the JSON object with the same keys as shown above:"""

                    # Use Gemini 2.5 Flash with Google Search
                    model = GenerativeModel("gemini-2.5-flash")

                    # Create Google Search tool
                    try:
                        google_search = Tool.from_google_search_retrieval(
                            google_search_retrieval=grounding.GoogleSearchRetrieval(
                                disable_attribution=False
                            )
                        )
                        use_tools = [google_search]
                    except Exception as e:
                        print(f"    Note: Google Search grounding not available ({str(e)[:50]}), using direct generation")
                        use_tools = None

                    # Generate with Google Search grounding
                    response = model.generate_content(
                        prompt,
                        tools=use_tools,
                        generation_config=GenerationConfig(
                            temperature=0.3,
                            max_output_tokens=3000,
                        )
                    )

                    # Parse JSON response
                    text = response.text.strip()

                    # Remove markdown code blocks if present
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0]
                    elif "```" in text:
                        parts = text.split("```")
                        if len(parts) >= 2:
                            text = parts[1]

                    text = text.strip()

                    # Extract JSON object
                    if "{" in text and "}" in text:
                        start = text.index("{")
                        end = text.rindex("}") + 1
                        text = text[start:end]

                    extracted = json.loads(text)

                    # Get grounding metadata for sources
                    sources = []
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'grounding_metadata'):
                            grounding_meta = candidate.grounding_metadata
                            if hasattr(grounding_meta, 'grounding_chunks'):
                                for chunk in grounding_meta.grounding_chunks[:10]:  # First 10 sources
                                    if hasattr(chunk, 'web') and hasattr(chunk.web, 'uri'):
                                        sources.append(chunk.web.uri)

                    return extracted, sources

                except Exception as e:
                    print(f"    Batch error: {str(e)[:100]}")
                    return {}, []

            # Split missing specs into batches of 10 (Gemini can handle this easily)
            batch_size = 10
            spec_batches = []
            for i in range(0, len(missing_specs), batch_size):
                spec_batches.append(missing_specs[i:i+batch_size])

            print(f"  Processing {len(spec_batches)} batches of ~{batch_size} specs each...\n")

            # Process batches in parallel (max 3 at a time to avoid rate limits)
            recovered = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(retry_specs_with_gemini_search, batch): (i, batch)
                          for i, batch in enumerate(spec_batches, 1)}

                for future in concurrent.futures.as_completed(futures):
                    batch_num, batch = futures[future]

                    try:
                        extracted, sources = future.result()
                        batch_found = 0

                        for spec_name in batch:
                            value = extracted.get(spec_name, "")

                            if value and value != "Not found" and "Not" not in value and len(value.strip()) > 0:
                                specs[spec_name] = value
                                recovered += 1
                                batch_found += 1

                                # Create citation
                                citation = {
                                    "source_url": sources[0] if sources else "Google Search (Gemini grounded)",
                                    "citation_text": "Retrieved via Gemini with Google Search grounding",
                                    "gemini_grounded": True,
                                    "all_sources": sources[:5] if sources else []
                                }
                                citations[spec_name] = citation

                                if sources:
                                    car_data["source_urls"].extend(sources[:3])

                        print(f"  Batch {batch_num}/{len(spec_batches)}: Extracted {batch_found}/{len(batch)} specs")

                    except Exception as e:
                        print(f"  Batch {batch_num} failed: {str(e)[:80]}")

            print(f"\n  Phase 2 Complete: Recovered {recovered}/{len(missing_specs)} specs using Gemini + Google Search")
    else:
        print(f"\n  Accuracy >= 80% - skipping Phase 2 retry")

    # Build final car_data
    all_urls = set(car_data.get("source_urls", []))
    for spec_name in CAR_SPECS:
        car_data[spec_name] = specs.get(spec_name, "Not Available")
        if spec_name in citations:
            car_data[f"{spec_name}_citation"] = citations[spec_name]
            url = citations[spec_name].get("source_url", "")
            if url and url != "N/A":
                all_urls.add(url)
        else:
            car_data[f"{spec_name}_citation"] = {"source_url": "N/A", "citation_text": ""}

    car_data["source_urls"] = list(all_urls)

    final_found = sum(1 for s in CAR_SPECS if car_data.get(s) and "Not" not in str(car_data.get(s, "")) and "Error" not in str(car_data.get(s, "")))
    elapsed = time.time() - start_time
    final_accuracy = (final_found / len(CAR_SPECS) * 100) if CAR_SPECS else 0

    print(f"\n{'='*60}")
    print(f"DONE: {final_found}/{len(CAR_SPECS)} specs ({final_accuracy:.1f}%) | {elapsed:.1f}s")
    print(f"{'='*60}\n")

    return car_data


def scrape_car_data_with_pdf_prefill(car_name: str, pdf_specs: Dict[str, str]) -> Dict[str, Any]:
    """
    Scrape car data using PDF-extracted specs as a starting point.
    Only searches for specs NOT found in the PDF.
    Citations for PDF-sourced specs are set to 'PDF uploaded by user'.
    """
    print(f"\n{'#'*60}")
    print(f"SCRAPING (PDF prefill): {car_name}")
    print(f"{'#'*60}")

    start_time = time.time()
    car_data = {"car_name": car_name, "source_urls": [], "method": "Custom Search Pipeline v2 (PDF prefilled)"}
    citations = {}
    specs = {}

    # Pre-fill specs from PDF with "PDF uploaded by user" citation
    pdf_citation = {
        "source_url": "PDF uploaded by user",
        "citation_text": "Extracted from PDF uploaded by user",
        "from_pdf": True
    }
    for spec_name in CAR_SPECS:
        pdf_value = pdf_specs.get(spec_name, "")
        if pdf_value and str(pdf_value).strip() not in ["", "N/A", "Not Available", "Not found", "None"]:
            specs[spec_name] = str(pdf_value).strip()
            citations[spec_name] = pdf_citation

    pdf_filled = sum(1 for s in CAR_SPECS if s in specs)
    missing_specs = [s for s in CAR_SPECS if s not in specs]
    print(f"  PDF pre-filled: {pdf_filled}/{len(CAR_SPECS)} specs")
    print(f"  Searching for:  {len(missing_specs)} missing specs")

    if not missing_specs:
        # All specs found in PDF — no scraping needed
        for spec_name in CAR_SPECS:
            car_data[spec_name] = specs.get(spec_name, "Not Available")
            car_data[f"{spec_name}_citation"] = citations.get(spec_name, {"source_url": "N/A", "citation_text": ""})
        return car_data

    # PHASE 0: Broad search (only needed for missing specs)
    broad_results = broad_search(car_name)
    broad_snippets = broad_results.get("results", [])
    for r in broad_snippets[:20]:
        url = r.get("url", "")
        if url:
            car_data["source_urls"].append(url)

    # PHASE 1: Bulk extraction for missing specs only
    print(f"\n{'='*60}")
    print(f"PHASE 1: BULK EXTRACTION ({len(missing_specs)} missing specs)")
    print(f"{'='*60}\n")

    spec_groups = [
        [s for s in CAR_SPECS[:20] if s in missing_specs],
        [s for s in CAR_SPECS[20:45] if s in missing_specs],
        [s for s in CAR_SPECS[45:70] if s in missing_specs],
        [s for s in CAR_SPECS[70:] if s in missing_specs],
    ]
    spec_groups = [g for g in spec_groups if g]

    for i, group in enumerate(spec_groups):
        print(f"  Extracting group {i+1}/{len(spec_groups)} ({len(group)} specs)...")
        group_specs = bulk_extract_specs(car_name, broad_snippets, group)
        for spec, value in group_specs.items():
            if value and "Not" not in str(value) and "Error" not in str(value):
                specs[spec] = value
                citations[spec] = {
                    "source_url": broad_snippets[0].get("url", "N/A") if broad_snippets else "N/A",
                    "citation_text": broad_snippets[0].get("snippet", "")[:200] if broad_snippets else "",
                    "bulk_extracted": True
                }
        time.sleep(0.5)

    # PHASE 2: Targeted search for still-missing specs
    still_missing = [
        s for s in missing_specs
        if s not in specs or "Not" in str(specs.get(s, "")) or "Error" in str(specs.get(s, "")) or not specs.get(s)
    ]
    if len(still_missing) > 10:
        print(f"\n{'='*60}")
        print(f"PHASE 2: TARGETED SEARCH ({len(still_missing)} specs)")
        print(f"{'='*60}\n")
        search_results = parallel_search(car_name, still_missing)
        extraction = parallel_extract(car_name, search_results)
        for spec, value in extraction["specs"].items():
            if value and "Not" not in str(value) and "Error" not in str(value):
                specs[spec] = value
        for spec, cit in extraction["citations"].items():
            if spec not in citations or not citations[spec].get("from_pdf"):
                citations[spec] = cit

    # PHASE 3: Retry with alternative keywords
    still_missing_2 = [
        s for s in missing_specs
        if "Not" in str(specs.get(s, "Not")) or "Error" in str(specs.get(s, "")) or not specs.get(s)
    ]
    if still_missing_2:
        retry_search = {spec: {"spec": spec, "results": []} for spec in still_missing_2}
        specs, citations = retry_missing_specs(car_name, specs, citations, retry_search)

    # Build final car_data
    all_urls = set(car_data.get("source_urls", []))
    for spec_name in CAR_SPECS:
        car_data[spec_name] = specs.get(spec_name, "Not Available")
        cit = citations.get(spec_name, {"source_url": "N/A", "citation_text": ""})
        car_data[f"{spec_name}_citation"] = cit
        url = cit.get("source_url", "")
        if url and url not in ("N/A", "PDF uploaded by user"):
            all_urls.add(url)

    car_data["source_urls"] = list(all_urls)

    final_found = sum(1 for s in CAR_SPECS if car_data.get(s) and "Not" not in str(car_data.get(s, "")) and "Error" not in str(car_data.get(s, "")))
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"DONE: {final_found}/{len(CAR_SPECS)} specs ({final_found/len(CAR_SPECS)*100:.1f}%) | {elapsed:.1f}s")
    print(f"  PDF contributed: {pdf_filled} specs")
    print(f"{'='*60}\n")

    return car_data


def scrape_car_data(car_name: str, manual_specs: Dict[str, Any] = None, use_custom_search: bool = True, pdf_specs: Dict[str, str] = None) -> Dict[str, Any]:  # noqa: ARG001
    """Main entry point for car data scraping.

    Args:
        car_name: Name of the car to scrape
        manual_specs: Optional manual specs for code cars
        use_custom_search: Kept for backward compatibility (always uses custom search now)
        pdf_specs: Optional specs pre-extracted from a PDF. Only missing specs will be searched.
    """
    _ = use_custom_search  # Always uses custom search in v2

    if manual_specs and manual_specs.get('is_code_car'):
        print(f"  CODE CAR - using manual specs")
        for field in CAR_SPECS:
            if field not in manual_specs or not manual_specs[field]:
                manual_specs[field] = "Not Available"
                manual_specs[f"{field}_citation"] = {"source_url": "Manual", "citation_text": "Skipped"}
        return manual_specs

    if pdf_specs:
        return scrape_car_data_with_pdf_prefill(car_name, pdf_specs)

    return scrape_car_data_with_custom_search(car_name)


# Backward compatibility functions
def get_spec_search_queries(car_name: str) -> Dict[str, str]:
    return {spec: f"{car_name} {keywords}" for spec, keywords in SPEC_QUERIES.items()}


def extract_spec_from_search_results(car_name: str, spec_name: str, search_results: List[Dict[str, str]]) -> Dict[str, Any]:
    result = extract_spec_value(spec_name, {"results": search_results}, car_name)
    citations = result.get("citations", [])
    return {
        "value": result["value"],
        "citation": citations[0].get("snippet", "") if citations else "",
        "source_url": citations[0].get("url", "N/A") if citations else "N/A"
    }


async def call_custom_search_parallel(
    queries: Dict[str, str],
    num_results: int = 5,
    max_concurrent: int = 15
) -> Dict[str, List[Dict[str, str]]]:
    """Async wrapper for backward compatibility.

    Args:
        queries: Dict mapping spec names to search queries
        num_results: Results per query (kept for compatibility)
        max_concurrent: Max concurrent requests (kept for compatibility)
    """
    # These params kept for backward compatibility but not used in v2
    _ = num_results
    _ = max_concurrent

    results = {}
    for spec_name, query in queries.items():
        search_result = custom_search(query, spec_name)
        results[spec_name] = search_result.get("results", [])
    return results
