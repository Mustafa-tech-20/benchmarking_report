import sys
sys.path.append("/app")
from shared_utils import safe_json_parse, clean_json_response

from typing import Dict, Any

import json
import os, json
import vertexai
from vertexai.preview import rag
from vertexai.generative_models import GenerativeModel

# 87 car specifications (matching car_search.py)
CAR_SPECS = [
    # Basic Info
    "price_range",
    "mileage",
    "user_rating",
    "seating_capacity",

    # Engine & Performance
    "performance",
    "torque",
    "transmission",
    "acceleration",

    # Braking & Safety
    "braking",
    "brakes",
    "brake_performance",
    "vehicle_safety_features",
    "impact",

    # Steering & Handling
    "steering",
    "telescopic_steering",
    "turning_radius",
    "stability",
    "corner_stability",
    "straight_ahead_stability",

    # Ride & Suspension
    "ride",
    "ride_quality",
    "stiff_on_pot_holes",
    "bumps",
    "shocks",

    # NVH
    "nvh",
    "powertrain_nvh",
    "wind_nvh",
    "road_nvh",
    "wind_noise",
    "tire_noise",
    "turbo_noise",

    # Transmission Feel
    "manual_transmission_performance",
    "automatic_transmission_performance",
    "pedal_operation",
    "gear_shift",
    "gear_selection",
    "pedal_travel",
    "crawl",

    # Driving Dynamics
    "driveability",
    "performance_feel",
    "city_performance",
    "highway_performance",
    "off_road",
    "manoeuvring",

    # Vibration & Feel Issues
    "jerks",
    "pulsation",
    "shakes",
    "shudder",
    "grabby",
    "spongy",
    "rattle",

    # Interior & Comfort
    "interior",
    "climate_control",
    "seats",
    "seat_cushion",
    "visibility",
    "soft_trims",
    "armrest",
    "headrest",
    "egress",
    "ingress",

    # Features & Tech
    "infotainment_screen",
    "resolution",
    "touch_response",
    "apple_carplay",
    "digital_display",
    "button",

    # Exterior & Lighting
    "lighting",
    "led",
    "drl",
    "tail_lamp",
    "alloy_wheel",

    # Convenience Features
    "sunroof",
    "irvm",
    "orvm",
    "window",
    "wiper_control",
    "parking",
    "epb",
    "door_effort",

    # Dimensions & Space
    "boot_space",
    "wheelbase",
    "chasis",

    # Other
    "blower_noise",
    "response",
    "sensitivity",
    "seats_restraint",
]

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
            spec_data = safe_json_parse(specifications, fallback={})
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
        expected_fields = CAR_SPECS
        
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

        car_data = safe_json_parse(response_text.strip(, fallback={}))
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
        print(f"RAG query failed: {e}")
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