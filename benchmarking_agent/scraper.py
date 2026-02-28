"""
Car Specifications Scraper using Google Custom Search + Gemini

Enhanced pipeline with:
- 87 targeted spec queries
- Parallel search and extraction
- Alternative keywords retry when accuracy < 80%
- Full URL citations
- Exponential backoff for API calls
"""
import time
import random
import requests
import concurrent.futures
from typing import Dict, Any, List, Callable
from functools import wraps

from vertexai.generative_models import GenerativeModel

from benchmarking_agent.config import GOOGLE_API_KEY, SEARCH_ENGINE_ID, CUSTOM_SEARCH_URL


# Parallel processing settings
SEARCH_WORKERS = 15
GEMINI_WORKERS = 20
SEARCH_RESULTS_PER_SPEC = 5
ACCURACY_THRESHOLD = 80

# Retry settings
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 30.0  # seconds


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
    """Call Gemini API with exponential backoff retry."""
    last_error = None
    for attempt in range(max_retries):
        try:
            model = GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            # Check if it's a retryable error
            if any(x in error_str for x in ["429", "rate", "quota", "resource", "503", "500", "timeout"]):
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
            "domain": r["domain"],
            "title": r["title"],
            "snippet": r["snippet"][:200] + "..." if len(r["snippet"]) > 200 else r["snippet"]
        }
        for r in results
    ]

    context = "\n".join([f"[{r['domain']}] {r['snippet']}" for r in results])

    # Spec-specific format hints
    format_hints = {
        "price_range": "₹X.XX Lakh onwards OR ₹X-Y Lakh",
        "mileage": "X.X kmpl",
        "user_rating": "X.X/5",
        "seating_capacity": "X Seater",
        "performance": "XXX bhp / XXX Nm",
        "torque": "XXX Nm",
        "transmission": "Manual/Automatic/6-speed AT",
        "acceleration": "X.X seconds (0-100)",
        "turning_radius": "X.X meters",
        "boot_space": "XXX litres",
        "wheelbase": "XXXX mm",
    }

    format_hint = format_hints.get(spec_name, "short value with units")

    prompt = f"""Extract {spec_name.replace('_', ' ')} for {car_name}.

SEARCH RESULTS:
{context}

CRITICAL - RETURN FORMAT:
- Return ONLY the value, NO explanations
- Maximum 10 words
- Format: {format_hint}
- Examples: "₹11.35 Lakh onwards", "15.2 kmpl", "4.5/5", "5 Seater", "150 bhp", "2750 mm"
- If not found, return exactly: "Not found"

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
        # Truncate if too long (more than 50 chars likely means explanation)
        if len(value) > 80 and "Not" not in value:
            # Try to extract just the key value
            value = value[:80] + "..."

        return {"spec": spec_name, "value": value, "citations": citations}
    except Exception as e:
        return {"spec": spec_name, "value": f"Error: {str(e)[:50]}", "citations": citations}


def retry_extract_spec(car_name: str, spec_name: str, search_results: list) -> str:
    """Retry extraction with more aggressive prompt - returns concise value."""
    if not search_results:
        return "Not Available"

    context = "\n".join([f"[{r['domain']}] {r['snippet']}" for r in search_results])

    prompt = f"""Extract {spec_name.replace('_', ' ')} for {car_name}.

SEARCH RESULTS:
{context}

CRITICAL RULES:
- Return ONLY the value (max 10 words)
- NO explanations, NO sentences
- Include units (kmpl, mm, bhp, Nm, etc.)
- Examples: "₹12.5 Lakh", "16.8 kmpl", "4.2/5", "6 Airbags, ABS, ESP"
- If not found: "Not Available"

VALUE:"""

    try:
        # Use retry logic for Gemini call
        value = call_gemini_with_retry(prompt, "gemini-2.5-flash")
        if value.startswith("VALUE:"):
            value = value[6:].strip()
        value = value.replace("**", "").replace("*", "")
        if "\n" in value:
            value = value.split("\n")[0].strip()
        if len(value) > 80:
            value = value[:80] + "..."
        return value
    except Exception as e:
        return f"Error: {str(e)[:30]}"


def parallel_search(car_name: str, specs_to_search: List[str] = None) -> dict:
    """Run search queries in parallel."""
    if specs_to_search is None:
        specs_to_search = CAR_SPECS

    print(f"\n{'='*60}")
    print(f"PHASE 1: PARALLEL SEARCH ({len(specs_to_search)} queries)")
    print(f"{'='*60}\n")

    all_results = {}

    def search_task(spec_name):
        keywords = SPEC_QUERIES.get(spec_name, spec_name.replace('_', ' '))
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
            except Exception as e:
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
    """Main scraping function with 3-phase pipeline."""
    print(f"\n{'#'*60}")
    print(f"SCRAPING: {car_name}")
    print(f"{'#'*60}")

    start_time = time.time()
    car_data = {"car_name": car_name, "source_urls": [], "method": "Custom Search Pipeline"}

    # Phase 1: Search
    search_results = parallel_search(car_name)

    # Phase 2: Extract
    extraction = parallel_extract(car_name, search_results)
    specs = extraction["specs"]
    citations = extraction["citations"]

    # Check accuracy
    total = len(specs)
    found = sum(1 for v in specs.values() if v and "Not" not in str(v) and "Error" not in str(v))
    accuracy = (found / total * 100) if total > 0 else 0

    print(f"\n  Accuracy: {found}/{total} ({accuracy:.1f}%)")

    # Phase 3: Retry if < 80%
    if accuracy < ACCURACY_THRESHOLD:
        print(f"  Below {ACCURACY_THRESHOLD}% - running retry...")
        specs, citations = retry_missing_specs(car_name, specs, citations, search_results)

    # Build final car_data
    all_urls = set()
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

    print(f"\n{'='*60}")
    print(f"DONE: {final_found}/{len(CAR_SPECS)} specs | {elapsed:.1f}s")
    print(f"{'='*60}\n")

    return car_data


def scrape_car_data(car_name: str, manual_specs: Dict[str, Any] = None, use_custom_search: bool = True) -> Dict[str, Any]:
    """Main entry point for car data scraping."""
    if manual_specs and manual_specs.get('is_code_car'):
        print(f"  CODE CAR - using manual specs")
        for field in CAR_SPECS:
            if field not in manual_specs or not manual_specs[field]:
                manual_specs[field] = "Not Available"
                manual_specs[f"{field}_citation"] = {"source_url": "Manual", "citation_text": "Skipped"}
        return manual_specs

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


async def call_custom_search_parallel(queries: Dict[str, str], num_results: int = 5, max_concurrent: int = 15) -> Dict[str, List[Dict[str, str]]]:
    """Async wrapper for backward compatibility."""
    results = {}
    for spec_name, query in queries.items():
        search_result = custom_search(query, spec_name)
        results[spec_name] = search_result.get("results", [])
    return results
