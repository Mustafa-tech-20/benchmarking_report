"""Car Specifications Search using Google Custom Search + Gemini

Individual query per spec with parallel batching for:
- Search API calls (parallel)
- Gemini extraction calls (parallel)
"""
import os
import requests
import json
import concurrent.futures
from dotenv import load_dotenv
from time import sleep

load_dotenv()

# Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/mustafa.mohammed/Documents/Mahindra-CloudRun/service.json"

from google import genai
from google.genai.types import GenerateContentConfig

# Initialize Gemini client
client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
MODEL_ID = "gemini-2.5-flash"

# Parallel settings
SEARCH_WORKERS = 10  # Concurrent search API calls
GEMINI_WORKERS = 15  # Concurrent Gemini calls
SEARCH_RESULTS_PER_SPEC = 5  # Results per search query

# Each spec with its best search keywords
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

    # AC & Blower
    "blower_noise": "AC blower noise fan sound cabin loud speed",

    # Response & Sensitivity
    "response": "throttle response accelerator pickup lag turbo",
    "sensitivity": "controls sensitivity steering throttle brake feel",

    # Safety Restraints
    "seats_restraint": "seatbelt pretensioner ISOFIX child safety load limiter",
}


def custom_search(query: str, spec_name: str) -> dict:
    """Search for a single spec."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "q": query,
        "num": SEARCH_RESULTS_PER_SPEC,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 429:  # Rate limit
            sleep(1)
            response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return {"spec": spec_name, "results": [], "error": f"HTTP {response.status_code}"}

        data = response.json()
        items = data.get("items", [])

        results = [{
            "title": item.get("title", ""),
            "snippet": item.get("snippet", ""),
            "domain": item.get("displayLink", ""),
            "url": item.get("link", ""),  # Full URL to the page
            "formatted_url": item.get("formattedUrl", ""),  # Human-readable URL
        } for item in items]

        return {"spec": spec_name, "results": results, "query": query}

    except Exception as e:
        return {"spec": spec_name, "results": [], "error": str(e)}


def extract_spec_value(spec_name: str, search_data: dict, car_name: str) -> dict:
    """Extract spec value using Gemini."""

    results = search_data.get("results", [])
    if not results:
        return {
            "spec": spec_name,
            "value": "N/A - No search results",
            "citations": []
        }

    # Build citations list with full URL
    citations = [
        {
            "url": r.get("url", ""),
            "domain": r["domain"],
            "title": r["title"],
            "snippet": r["snippet"][:200] + "..." if len(r["snippet"]) > 200 else r["snippet"]
        }
        for r in results
    ]

    # Build context from search results
    context = "\n".join([
        f"[{r['domain']}] {r['snippet']}"
        for r in results
    ])

    prompt = f"""Extract the {spec_name.replace('_', ' ')} for {car_name}.

SEARCH RESULTS:
{context}

INSTRUCTIONS:
- Return ONLY the specific value, measurement, or description
- Include units where applicable (kmpl, mm, Nm, bhp, etc.)
- For ratings, include scale (e.g., "4.5/5 stars")
- For features, list what's included
- For subjective specs, quote expert opinions briefly
- If the information is NOT in the search results, return exactly: "Not found"

VALUE:"""

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.1),
        )
        value = response.text.strip()

        # Clean up response
        if value.startswith("VALUE:"):
            value = value[6:].strip()

        return {
            "spec": spec_name,
            "value": value,
            "citations": citations
        }

    except Exception as e:
        return {
            "spec": spec_name,
            "value": f"Error: {str(e)[:50]}",
            "citations": citations
        }


def parallel_search(car_name: str) -> dict:
    """Run all search queries in parallel."""

    print(f"\n{'='*70}")
    print(f"PHASE 1: PARALLEL SEARCH ({len(SPEC_QUERIES)} queries)")
    print(f"Workers: {SEARCH_WORKERS} | Results per query: {SEARCH_RESULTS_PER_SPEC}")
    print(f"{'='*70}\n")

    all_results = {}
    domains_used = set()
    completed = 0

    def search_task(spec_name, keywords):
        query = f"{car_name} {keywords}"
        return custom_search(query, spec_name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        futures = {
            executor.submit(search_task, spec, keywords): spec
            for spec, keywords in SPEC_QUERIES.items()
        }

        for future in concurrent.futures.as_completed(futures):
            spec_name = futures[future]
            completed += 1

            try:
                result = future.result()
                all_results[spec_name] = result

                if result.get("results"):
                    domains = [r["domain"] for r in result["results"]]
                    domains_used.update(domains)
                    status = f"✓ {len(result['results'])} ({domains[0][:20]})"
                else:
                    status = f"○ {result.get('error', 'No results')}"

                print(f"  [{completed:2}/{len(SPEC_QUERIES)}] {spec_name}: {status}")

            except Exception as e:
                print(f"  [{completed:2}/{len(SPEC_QUERIES)}] {spec_name}: ✗ {e}")
                all_results[spec_name] = {"spec": spec_name, "results": []}

    print(f"\n  Domains found: {len(domains_used)}")
    print(f"  {', '.join(sorted(domains_used)[:8])}...")
    return all_results


# Alternative keywords for retry (different angle for each spec)
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

    # AC & Blower
    "blower_noise": "AC blower fan noise cabin loud speed sound",

    # Response & Sensitivity
    "response": "throttle response accelerator pickup lag turbo quick",
    "sensitivity": "controls sensitivity steering throttle brake feel light",

    # Safety Restraints
    "seats_restraint": "seatbelt pretensioner ISOFIX child seat load limiter safety",
}


def retry_extract_spec(car_name: str, spec_name: str, search_results: list) -> str:
    """Retry extraction with more aggressive prompt."""

    if not search_results:
        return "N/A - No data available"

    # Build fuller context
    context = "\n\n".join([
        f"SOURCE: {r['domain']}\nTITLE: {r['title']}\nCONTENT: {r['snippet']}"
        for r in search_results
    ])

    prompt = f"""You are extracting car specifications. Find ANY information about {spec_name.replace('_', ' ')} for {car_name}.

SEARCH RESULTS:
{context}

IMPORTANT INSTRUCTIONS:
1. Look for ANY mention related to {spec_name.replace('_', ' ')}
2. Include direct quotes if available
3. Include measurements, ratings, or descriptions
4. If multiple sources mention it, combine the information
5. Even partial information is valuable - extract it
6. Only say "Not available" if there is absolutely NO relevant information

{spec_name.replace('_', ' ').upper()} for {car_name}:"""

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=GenerateContentConfig(temperature=0.2),
        )
        value = response.text.strip()
        return value
    except Exception as e:
        return f"Error: {str(e)[:30]}"


def parallel_extract(car_name: str, search_results: dict) -> dict:
    """Run all Gemini extractions in parallel."""

    print(f"\n{'='*70}")
    print(f"PHASE 2: PARALLEL GEMINI EXTRACTION ({len(search_results)} calls)")
    print(f"Workers: {GEMINI_WORKERS}")
    print(f"{'='*70}\n")

    specs = {
        "car_name": car_name,
        "specifications": {},
        "all_citations": []
    }
    completed = 0
    found_count = 0
    all_domains = set()

    def extract_task(spec_name, search_data):
        return extract_spec_value(spec_name, search_data, car_name)

    with concurrent.futures.ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as executor:
        futures = {
            executor.submit(extract_task, spec, data): spec
            for spec, data in search_results.items()
        }

        for future in concurrent.futures.as_completed(futures):
            spec_name = futures[future]
            completed += 1

            try:
                result = future.result()
                value = result["value"]
                citations = result.get("citations", [])

                # Store spec with its citations
                specs["specifications"][spec_name] = {
                    "value": value,
                    "citations": citations
                }

                # Track all domains
                for c in citations:
                    all_domains.add(c["domain"])

                is_found = value and "N/A" not in value and "Not found" not in value and "Error" not in value
                if is_found:
                    found_count += 1
                    display = value[:45] + "..." if len(value) > 45 else value
                    print(f"  [{completed:2}/{len(search_results)}] {spec_name}: ✓ {display}")
                else:
                    print(f"  [{completed:2}/{len(search_results)}] {spec_name}: ○ {value[:30]}")

            except Exception as e:
                print(f"  [{completed:2}/{len(search_results)}] {spec_name}: ✗ {e}")
                specs["specifications"][spec_name] = {
                    "value": f"Error: {e}",
                    "citations": []
                }

    # Add summary of all unique domains used
    specs["all_citations"] = sorted(list(all_domains))

    print(f"\n  Extracted: {found_count}/{len(search_results)} specs")
    print(f"  Unique sources: {len(all_domains)} domains")
    return specs


def retry_missing_specs(car_name: str, specs: dict, search_results: dict) -> dict:
    """Phase 3: Retry missing specs with alternative keywords and aggressive extraction."""

    spec_data = specs.get("specifications", {})

    # Find missing specs
    missing = [k for k, v in spec_data.items()
               if "N/A" in str(v.get("value", ""))
               or "Not found" in str(v.get("value", ""))
               or "Not available" in str(v.get("value", ""))
               or "Error" in str(v.get("value", ""))]

    if not missing:
        print("\n✓ No missing specs to retry!")
        return specs

    # Filter to only those with alternative keywords defined
    retry_specs = [s for s in missing if s in ALT_KEYWORDS]

    if not retry_specs:
        print(f"\n⚠ {len(missing)} missing specs but no alternative keywords defined")
        return specs

    print(f"\n{'='*70}")
    print(f"PHASE 3: RETRY MISSING SPECS ({len(retry_specs)} specs)")
    print(f"{'='*70}\n")

    recovered = 0
    completed = 0

    def retry_task(spec_name):
        """Search with alternative keywords and extract with aggressive prompt."""
        alt_keywords = ALT_KEYWORDS[spec_name]
        query = f"{car_name} {alt_keywords}"

        # New search with alternative keywords
        search_result = custom_search(query, spec_name)
        results = search_result.get("results", [])

        if not results:
            # Fall back to original search results if retry search found nothing
            original = search_results.get(spec_name, {})
            results = original.get("results", [])

        if not results:
            return spec_name, "N/A - No data after retry", []

        # Build citations with full URL
        citations = [
            {
                "url": r.get("url", ""),
                "domain": r["domain"],
                "title": r["title"],
                "snippet": r["snippet"][:200] + "..." if len(r["snippet"]) > 200 else r["snippet"]
            }
            for r in results
        ]

        # Extract with aggressive prompt
        value = retry_extract_spec(car_name, spec_name, results)

        return spec_name, value, citations

    with concurrent.futures.ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as executor:
        futures = {
            executor.submit(retry_task, spec): spec
            for spec in retry_specs
        }

        for future in concurrent.futures.as_completed(futures):
            spec_name = futures[future]
            completed += 1

            try:
                spec_name, value, citations = future.result()

                is_found = (value
                            and "N/A" not in value
                            and "Not found" not in value
                            and "Not available" not in value
                            and "Error" not in value)

                if is_found:
                    recovered += 1
                    # Update the spec
                    specs["specifications"][spec_name] = {
                        "value": value,
                        "citations": citations,
                        "retry": True  # Mark as recovered via retry
                    }
                    display = value[:45] + "..." if len(value) > 45 else value
                    print(f"  [{completed:2}/{len(retry_specs)}] {spec_name}: ✓ RECOVERED - {display}")
                else:
                    print(f"  [{completed:2}/{len(retry_specs)}] {spec_name}: ○ Still missing - {value[:30]}")

            except Exception as e:
                print(f"  [{completed:2}/{len(retry_specs)}] {spec_name}: ✗ {e}")

    print(f"\n  Recovered: {recovered}/{len(retry_specs)} specs")
    return specs


def main():
    """Main function with full parallel processing."""

    print("\n" + "="*70)
    print("CAR SPECIFICATIONS EXTRACTOR")
    print("Individual queries + Parallel execution")
    print("="*70)
    print(f"Search Engine: {SEARCH_ENGINE_ID}")
    print(f"Total Specs: {len(SPEC_QUERIES)}")
    print(f"Search Workers: {SEARCH_WORKERS} | Gemini Workers: {GEMINI_WORKERS}")

    if not GOOGLE_API_KEY or not SEARCH_ENGINE_ID:
        print("\n❌ Error: API keys not found in .env")
        return

    try:
        car_name = "Mahindra Thar Roxx 2024"

        # Phase 1: Parallel search (all 87 queries)
        search_results = parallel_search(car_name)

        # Phase 2: Parallel Gemini extraction (all 87 calls)
        specs = parallel_extract(car_name, search_results)

        # Calculate initial accuracy
        spec_data = specs.get("specifications", {})
        total = len(spec_data)
        found = sum(1 for _, v in spec_data.items()
                    if v.get("value")
                    and "N/A" not in str(v.get("value", ""))
                    and "Not found" not in str(v.get("value", ""))
                    and "Not available" not in str(v.get("value", ""))
                    and "Error" not in str(v.get("value", "")))

        accuracy = (found / total * 100) if total > 0 else 0

        print(f"\n{'='*70}")
        print(f"PHASE 2 ACCURACY: {found}/{total} ({accuracy:.1f}%)")
        print(f"{'='*70}")

        # Phase 3: Only run if accuracy < 80%
        if accuracy < 80:
            print(f"\n⚠ Accuracy below 80% - Running Phase 3 retry with alternative keywords...")
            specs = retry_missing_specs(car_name, specs, search_results)
        else:
            print(f"\n✓ Accuracy >= 80% - Skipping Phase 3 retry")

        # Count final results (recalculate after potential Phase 3)
        spec_data = specs.get("specifications", {})
        total = len(spec_data)
        found = sum(1 for _, v in spec_data.items()
                    if v.get("value")
                    and "N/A" not in str(v.get("value", ""))
                    and "Not found" not in str(v.get("value", ""))
                    and "Not available" not in str(v.get("value", ""))
                    and "Error" not in str(v.get("value", "")))

        total_citations = sum(len(v.get("citations", [])) for v in spec_data.values())

        print(f"\n{'='*70}")
        print(f"FINAL RESULTS")
        print(f"{'='*70}")
        print(f"  Specs extracted: {found}/{total}")
        print(f"  Total citations: {total_citations}")
        print(f"  Unique domains: {len(specs.get('all_citations', []))}")
        print(f"{'='*70}\n")

        output = json.dumps(specs, indent=2, ensure_ascii=False)
        print(output)

        with open("car_specs_output.json", "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n✓ Saved to car_specs_output.json")

        # List missing specs
        missing = [k for k, v in spec_data.items()
                   if "N/A" in str(v.get("value", ""))
                   or "Not found" in str(v.get("value", ""))
                   or "Not available" in str(v.get("value", ""))
                   or "Error" in str(v.get("value", ""))]
        if missing:
            print(f"\n⚠ Missing specs ({len(missing)}):")
            print(f"  {', '.join(missing)}")

        print(f"\n{'='*70}")
        print("DONE")
        print(f"{'='*70}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
