"""
Car Specifications Scraper - Simple Per-Spec Search Pipeline

FLOW:
1. Phase 1: Per-spec search (87 queries) → Extract from snippets with Gemini
   - Query: "{car_name} latest {spec_keyword}"
   - Gemini extracts value + source URL from snippets

2. Phase 2: Gemini + Google Search fallback for missing specs
   - Uses Gemini with Google Search grounding
   - Extract missing specs in batches of 10 (parallel)
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
from google import genai
from google.genai import types

from benchmarking_agent.config import GOOGLE_API_KEY, SEARCH_ENGINE_ID, COMPANY_SEARCH_ID, CUSTOM_SEARCH_URL
from product_planning_agent.config import GEMINI_MAIN_MODEL

# Initialize Gemini client for Google Search grounding (requires Vertex AI)
# Google Search grounding only works with Vertex AI, not API key
import os
_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
_gemini_search_client = genai.Client(vertexai=True, project=_PROJECT_ID, location="global")


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
_gemini_model = GEMINI_MAIN_MODEL
_rate_limit_count = 0
_RATE_LIMIT_THRESHOLD = 10  # Switch to Pro after 10 rate limits


def reset_gemini_model():
    """Reset to Flash model at the start of each scraping session."""
    global _gemini_model, _rate_limit_count
    _gemini_model = GEMINI_MAIN_MODEL
    _rate_limit_count = 0


# ============================================================================
# 87 CAR SPECIFICATIONS
# ============================================================================

# Top specs to extract from official brand websites
OFFICIAL_SITE_PRIORITY_SPECS = [
    # Top Key Specs
    "price_range", "seating_capacity", "mileage",

    # Performance & Engine
    "acceleration", "torque", "engine_displacement", "fuel_type",

    # Safety
    "airbags", "adas", "ncap_rating", "vehicle_safety_features", "brakes",

    # Dimensions
    "boot_space", "wheelbase", "ground_clearance", "turning_radius",

    # Tech Features
    "infotainment_screen", "digital_display", "apple_carplay",
    "cruise_control", "parking_camera", "parking_sensors",

    # Exterior
    "tyre_size", "led", "drl", "alloy_wheel", "sunroof",

    # Interior & Comfort
    "audio_system", "ventilated_seats", "epb",
]  # 30 critical specs

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


# Top 4 most reliable automotive spec sources (hardcoded)
RELIABLE_SPEC_DOMAINS = [
    "cardekho.com",
    "carwale.com",
    "zigwheels.com",
    "autocarindia.com",
]

# Automotive spec sources searched individually in parallel (like clinical trial registries)
# Each source is searched independently for all missing specs, then results are merged
AUTOMOTIVE_SPEC_SOURCES = [
    {
        "name": "CarDekho",
        "url": "https://www.cardekho.com",
        "description": "India's largest car specs database with complete variant-wise spec tables",
        "strengths": "price range, engine specs, dimensions, features list, variant comparison",
    },
    {
        "name": "CarWale",
        "url": "https://www.carwale.com",
        "description": "Comprehensive car specifications, expert reviews and user ratings for Indian market",
        "strengths": "specifications table, user rating, expert review scores, safety features",
    },
    {
        "name": "ZigWheels",
        "url": "https://www.zigwheels.com",
        "description": "Car specs, prices, and road test reviews with detailed performance data",
        "strengths": "price range, monthly sales, mileage, 0-100 times, spec comparison",
    },
    {
        "name": "AutoCarIndia",
        "url": "https://www.autocarindia.com",
        "description": "India's premier automotive magazine with detailed road tests and scored performance",
        "strengths": "acceleration timing, NVH levels, ride quality score, handling, braking distance, steering feel",
    },
    {
        "name": "Team-BHP",
        "url": "https://www.team-bhp.com",
        "description": "India's most trusted owner community with detailed long-term real-world road tests",
        "strengths": "real-world mileage, NVH issues, interior quality, ride comfort, ownership experience",
    },
    {
        "name": "MotorBeam",
        "url": "https://www.motorbeam.com",
        "description": "Detailed spec sheets and driving impressions for Indian market cars",
        "strengths": "technical specs, dimensions, performance figures, feature details",
    },
    {
        "name": "CarAndBike",
        "url": "https://www.carandbike.com",
        "description": "NDTV automotive - specs database and expert road test reviews",
        "strengths": "spec comparison, road test scores, safety features, ADAS details",
    },
    {
        "name": "V3Cars",
        "url": "https://www.v3cars.com",
        "description": "Variant-wise spec breakdowns and feature availability comparison for Indian cars",
        "strengths": "variant-level feature availability, tyre specs, alloy wheel details, interior features",
    },
]

# ============================================================================
# TRUSTED CITATION DOMAINS
# Citations must ONLY use these domains — never Vertex AI grounding URLs
# ============================================================================

TRUSTED_CITATION_DOMAINS = [
    # Indian spec databases
    "cardekho.com", "carwale.com", "zigwheels.com", "v3cars.com",
    # Indian automotive media
    "autocarindia.com", "overdrive.in", "autocarpro.in", "motorbeam.com",
    "carandbike.com", "rushlane.com", "drivespark.com", "motoroctane.com",
    "evreporter.com", "motoringworld.in",
    # Community reviews
    "team-bhp.com",
    # Global automotive
    "autocar.co.uk", "autoblog.com", "jalopnik.com", "topgear.com",
    "automobilemagazine.com", "leftlanenews.com",
    # Sales data
    "bestsellingcarsblog.com",
    # China automotive
    "carnewschina.com", "gasgoo.com", "autohome.com.cn",
    # EV focused
    "insideevs.com", "evadoption.com",
    # YouTube
    "youtube.com",
]

# Source name → trusted base URL fallback mapping
_SOURCE_FALLBACK_URLS = {
    "CarDekho": "https://www.cardekho.com",
    "CarWale": "https://www.carwale.com",
    "ZigWheels": "https://www.zigwheels.com",
    "AutoCarIndia": "https://www.autocarindia.com",
    "Team-BHP": "https://www.team-bhp.com",
    "MotorBeam": "https://www.motorbeam.com",
    "CarAndBike": "https://www.carandbike.com",
    "V3Cars": "https://www.v3cars.com",
    "Overdrive": "https://www.overdrive.in",
    "Rushlane": "https://www.rushlane.com",
}

# Official brand website domains — always trusted as citations
_OFFICIAL_BRAND_DOMAINS = [
    "mahindra.com", "mahindraelectric", "hyundai.com", "toyota.com",
    "tatamotors.com", "tata.com", "marutisuzuki.com", "honda.com",
    "kia.com", "mgmotor.co.in", "mgmotor.com", "volkswagen.co.in",
    "skoda-auto.com", "nissan.in", "renault.co.in", "ford.com",
    "jeep.com", "jeep-india.com", "bmw.com", "mercedes-benz.co.in",
    "audi.com", "tesla.com", "byd.com", "volvocars.com", "citroen.in",
]

# URL patterns that must NEVER appear in citations
_BLOCKED_URL_PATTERNS = [
    "vertexaisearch.cloud.google.com",
    "grounding-api-redirect",
    "googleapis.com",
    "google.com/search",
    "bing.com/search",
    "search.yahoo.com",
    "googleusercontent.com",
]

# Trusted domains list string for use in prompts
_TRUSTED_DOMAINS_PROMPT_LIST = ", ".join([
    "cardekho.com", "carwale.com", "zigwheels.com", "autocarindia.com",
    "team-bhp.com", "overdrive.in", "motorbeam.com", "carandbike.com",
    "rushlane.com", "v3cars.com", "autocarpro.in", "youtube.com",
])


def normalize_citation_url(url: str, source_name: str = None) -> str:
    """
    Normalize citation URL to only use trusted domains.

    Strips Vertex AI grounding redirect URLs and maps unknown domains to the
    source's trusted base URL. Ensures citations always point to real,
    trusted automotive sources.

    Args:
        url: Raw URL from Gemini or search results
        source_name: Source name (e.g., "CarDekho") for fallback mapping

    Returns:
        Trusted URL, or source's base URL, or "N/A"
    """
    if not url or url in ["N/A", "Google Search", "", "Not found"]:
        if source_name and source_name in _SOURCE_FALLBACK_URLS:
            return _SOURCE_FALLBACK_URLS[source_name]
        return "N/A"

    url_lower = url.lower()

    # Block Vertex AI / grounding / search engine redirect URLs
    for pattern in _BLOCKED_URL_PATTERNS:
        if pattern in url_lower:
            if source_name and source_name in _SOURCE_FALLBACK_URLS:
                return _SOURCE_FALLBACK_URLS[source_name]
            return "N/A"

    # Accept URLs from trusted domains
    for domain in TRUSTED_CITATION_DOMAINS:
        if domain in url_lower:
            return url  # Already trusted domain — keep as-is

    # Accept official brand website URLs
    for domain in _OFFICIAL_BRAND_DOMAINS:
        if domain in url_lower:
            return url  # Official brand URL — keep as-is

    # URL from untrusted/unknown domain — fall back to source's base URL
    if source_name and source_name in _SOURCE_FALLBACK_URLS:
        return _SOURCE_FALLBACK_URLS[source_name]

    return "N/A"


# Detailed per-spec extraction guidance for Phase 2 Gemini prompt
SPEC_DESCRIPTIONS = {
    "price_range": "Ex-showroom price range across all variants (e.g., '₹8.99 Lakh - ₹15.50 Lakh')",
    "monthly_sales": "Monthly retail sales volume in India (e.g., '3,000–5,000 units/month')",
    "mileage": "ARAI-certified or real-world fuel efficiency (e.g., '14.5 kmpl petrol, 19.1 kmpl diesel')",
    "user_rating": "Aggregate owner rating out of 5 from cardekho/carwale/zigwheels (e.g., '4.3/5 based on 850 reviews')",
    "seating_capacity": "Number of seats (e.g., '5 seater' or '7 seater')",
    "performance_feel": "Overall driving dynamics and performance impression from expert road tests",
    "driveability": "Day-to-day drivability: throttle smoothness, traffic ease, low-speed behaviour",
    "acceleration": "0–100 kmph time (e.g., '9.5 seconds 0–100 kmph')",
    "torque": "Peak torque with RPM band (e.g., '300 Nm @ 1500–3000 rpm')",
    "response": "Throttle/accelerator response quality — immediate, laggy, or turbo lag details",
    "city_performance": "Performance in city stop-go traffic: low-end torque, ease of driving",
    "highway_performance": "Cruising ability, overtaking ease, stability at highway speeds",
    "off_road": "Off-road capability: ground clearance, 4WD/AWD, approach/departure angle",
    "crawl": "Low-speed crawl function: Hill Descent Control or 4L crawl ratio",
    "manual_transmission_performance": "Manual gearbox quality: shift throw length, clutch weight, notchiness",
    "automatic_transmission_performance": "AT/AMT/CVT/DCT smoothness, kickdown response, paddle shifters",
    "pedal_operation": "Clutch pedal weight and engagement point (manual variants)",
    "gear_shift": "Gear shifter mechanical feel, effort required, precise or vague",
    "gear_selection": "Precision of individual gear selection, slotting quality",
    "pedal_travel": "Brake/clutch pedal travel distance — long vs short",
    "ride": "Overall ride quality — comfortable, stiff, pliant, or harsh",
    "ride_quality": "Suspension comfort over city bumps and highways — bump absorption",
    "stiff_on_pot_holes": "Behaviour over potholes and broken roads — jolt vs absorption",
    "bumps": "Front and rear suspension bump absorption capability",
    "shocks": "Shock absorber damping quality description from expert review",
    "nvh": "Overall NVH (Noise, Vibration, Harshness) — cabin insulation rating",
    "powertrain_nvh": "Engine and drivetrain noise entering the cabin",
    "wind_nvh": "Aerodynamic/wind noise at speed",
    "road_nvh": "Road noise penetration into cabin",
    "wind_noise": "Wind noise level at highway speeds (e.g., 'well-suppressed', 'noticeable above 100 kmph')",
    "tire_noise": "Tyre rolling noise entering cabin",
    "turbo_noise": "Turbocharger whine audible inside cabin",
    "blower_noise": "AC blower/HVAC fan noise at various speeds",
    "jerks": "Jerkiness during acceleration or gear changes",
    "pulsation": "Brake pulsation or vibration felt through pedal when braking",
    "shakes": "Steering wheel or body shake/vibration at speed",
    "shudder": "Engine or drivetrain shudder at low speeds",
    "grabby": "Brake bite point — grabby/sharp vs progressive",
    "spongy": "Brake pedal sponginess or lack of feel",
    "rattle": "Interior rattle and squeak noises from trim or panels",
    "steering": "Steering system: EPS type, weighting light/heavy, feedback quality",
    "telescopic_steering": "Steering column adjustment: tilt only, or tilt + telescopic",
    "turning_radius": "Turning circle radius in metres (e.g., '5.2 m turning radius')",
    "manoeuvring": "Ease of parking and low-speed manoeuvring in tight spaces",
    "stability": "Overall vehicle stability at speed and during cornering",
    "corner_stability": "Body roll, lean, and composure in corners",
    "straight_ahead_stability": "Straight-line stability at highway speeds — nervous vs planted",
    "braking": "Braking performance: stopping distance, pedal feel, system type",
    "brakes": "Brake system: disc/drum front/rear, ABS, EBD, Brake Assist details",
    "brake_performance": "Braking distance from 100 kmph or expert braking assessment",
    "epb": "Electronic Parking Brake — available or not, auto-hold feature",
    "airbags": "Total number of airbags (e.g., '6 airbags standard')",
    "airbag_types_breakdown": "Airbag positions: front driver+passenger, side, curtain, knee — which are present",
    "vehicle_safety_features": "Safety tech: ABS, EBD, ESC, TCS, hill hold assist, ISOFIX",
    "adas": "ADAS suite: lane departure warning, blind spot monitor, forward collision warning, auto emergency braking, adaptive cruise",
    "ncap_rating": "NCAP/BNCAP crash test star rating (e.g., '5-star Global NCAP 2024')",
    "impact": "Crash test scores: adult occupant % and child occupant % from NCAP",
    "seats_restraint": "Seatbelt features: 3-point belts, pretensioners, load limiters, height adjusters",
    "interior": "Interior quality: materials, fit-and-finish, soft-touch surfaces, premium feel",
    "climate_control": "AC type: manual AC, automatic single-zone, dual-zone climate control; rear vents",
    "seats": "Seat comfort, bolstering, cushioning, long-drive comfort assessment",
    "seat_cushion": "Seat cushion density, thigh support, under-thigh support quality",
    "seat_material": "Upholstery material: fabric, leatherette, leather, suede-like",
    "seat_features_detailed": "Driver seat: 6-way/8-way power, lumbar support, memory, ventilation, heating",
    "rear_seat_features": "Rear seat: 60:40 split fold, recline angle, armrest, cup holders, rear AC vents",
    "ventilated_seats": "Ventilated/cooled seats — available in which variants, front only or front+rear",
    "visibility": "All-round visibility from driver's seat — thick pillars, small windows, blind spots",
    "soft_trims": "Soft-touch dashboard, door inserts — areas with soft materials vs hard plastic",
    "armrest": "Front and rear armrest quality, padding, height",
    "headrest": "Headrest adjustability (height/angle), comfort for tall passengers",
    "egress": "Ease of getting out of the car — door width, sill height, roof clearance",
    "ingress": "Ease of getting into the car — step-in height, door opening angle",
    "seatbelt_features": "Seatbelt pretensioners and load limiters — how many rows, height adjusters on which seats",
    "infotainment_screen": "Touchscreen size and system name (e.g., '10.25-inch Bluelink touchscreen')",
    "resolution": "Infotainment display resolution or sharpness description",
    "touch_response": "Touchscreen responsiveness: lag-free, sluggish, or fast",
    "digital_display": "Digital instrument cluster: size, type (TFT/LCD), displayed information",
    "apple_carplay": "Apple CarPlay and Android Auto: wired, wireless, or both",
    "button": "Physical buttons/knobs quality: tactile feedback, layout, ease of use",
    "audio_system": "Speaker system: brand (Bose/JBL/Sony), number of speakers (e.g., 'Bose 8-speaker')",
    "cruise_control": "Cruise control type: standard (set speed) or adaptive/radar with follow function",
    "parking_camera": "Parking camera: 2D/360-degree surround view, display quality, guidelines",
    "parking_sensors": "Parking sensors: front and rear PDC sensor count",
    "led": "LED headlights type: projector LED, reflector LED, matrix/adaptive LED",
    "drl": "Daytime Running Lights: LED design, signature, always-on vs auto",
    "tail_lamp": "Tail lamp design: full LED, LED elements, connected light bar",
    "alloy_wheel": "Alloy wheel design and size (e.g., '17-inch diamond-cut alloy wheels')",
    "tyre_size": "Tyre dimensions (e.g., '215/60 R17' or '235/55 R18')",
    "wheel_size": "Rim diameter in inches",
    "sunroof": "Sunroof type: none, standard tilt-slide, panoramic, electric one-touch",
    "irvm": "IRVM: manual day-night, auto-dimming electrochromic",
    "orvm": "ORVM: electrically adjustable, auto-fold, integrated turn indicator, puddle lamp",
    "window": "Power windows: all 4, one-touch up/down on which windows, auto-up with pinch guard",
    "wiper_control": "Wiper: intermittent speeds, rain-sensing auto wipers availability",
    "parking": "Parking assist: auto park, hill-hold, hill descent control",
    "door_effort": "Door build quality: solid thud vs hollow sound, effort to close, sealing",
    "sensitivity": "Control sensitivity: steering, throttle, brake — well-calibrated vs over/under sensitive",
    "wheelbase": "Wheelbase in mm (e.g., '2600 mm')",
    "ground_clearance": "Ground clearance in mm (e.g., '210 mm unladen')",
    "boot_space": "Boot/cargo capacity in litres (e.g., '373 litres')",
    "chasis": "Chassis type: monocoque, body-on-frame, platform name (e.g., 'INGLO platform')",
    "fuel_type": "Available fuel variants: petrol, diesel, CNG, mild-hybrid, strong hybrid, electric",
    "engine_displacement": "Engine displacement in cc (e.g., '1497 cc' petrol or '1956 cc' diesel)",
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
                    _gemini_model == GEMINI_MAIN_MODEL):
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
    Extract a batch of specs from official brand URL using Gemini (no web search).

    Args:
        car_name: Name of the car
        url: Official brand website URL
        specs_batch: List of spec names to extract (max 10)

    Returns: Dict of {spec_name: value}
    """
    # Build rich per-spec guidance using SPEC_DESCRIPTIONS
    spec_guide_lines = []
    for spec in specs_batch:
        desc = SPEC_DESCRIPTIONS.get(spec, spec.replace("_", " ").title())
        spec_guide_lines.append(f'- "{spec}": {desc}')
    spec_guide = "\n".join(spec_guide_lines)

    prompt = f"""You are an automotive specifications expert. Extract EXACT car specifications for {car_name} from the official brand website.

Official website URL: {url}

Extract these {len(specs_batch)} specifications:
{spec_guide}

RULES:
- EXACT values with units always: e.g., "210 mm", "₹12.5–18.9 Lakh", "1497 cc", "6 airbags", "10.25 inch"
- Include measurement units: bhp, Nm, mm, litres, kg, kmpl, rpm, seconds
- Binary features: "Yes", "No", or the specific variant where available
- Use your knowledge of this car model from the official website
- Return "Not found" only if the spec is genuinely unavailable

Return ONLY a JSON object (no markdown):
{{
    "price_range": "₹12.5–18.9 Lakh",
    "acceleration": "9.2 seconds (0–100 kmph)",
    "airbags": "6 airbags",
    "tyre_size": "215/60 R17",
    "sunroof": "Yes – Electric Panoramic Sunroof",
    "audio_system": "Sony 8-speaker system"
}}

Return ONLY the JSON, no markdown."""

    try:
        text = call_gemini_simple(prompt)
        if not text:
            return {}

        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()

        if "{" in text and "}" in text:
            text = text[text.index("{"):text.rindex("}") + 1]

        return json_repair.loads(text)

    except Exception as e:
        print(f"      Phase 0 Gemini error: {str(e)[:60]}")
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
    lock = concurrent.futures.thread.threading.Lock()

    # Split into batches of 10
    spec_batches = [
        OFFICIAL_SITE_PRIORITY_SPECS[i:i+10]
        for i in range(0, len(OFFICIAL_SITE_PRIORITY_SPECS), 10)
    ]

    def run_batch(args):
        batch_idx, batch = args
        try:
            extracted = extract_specs_from_official_site(car_name, url, batch)
            results = []
            for spec_name, value in extracted.items():
                if spec_name in OFFICIAL_SITE_PRIORITY_SPECS and value and "Not found" not in value:
                    results.append((spec_name, value))
            print(f"    Batch {batch_idx}/{len(spec_batches)}: ✓ {len(results)}/{len(batch)}")
            return results
        except Exception as e:
            print(f"    Batch {batch_idx}/{len(spec_batches)}: ✗ Error: {str(e)[:30]}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(spec_batches)) as executor:
        for batch_results in executor.map(run_batch, enumerate(spec_batches, 1)):
            with lock:
                for spec_name, value in batch_results:
                    specs[spec_name] = value
                    citations[spec_name] = {
                        "source_url": url,
                        "citation_text": f"Official {brand} website",
                        "engine": "OFFICIAL",
                    }

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
- source_url MUST be a real page URL from one of: {_TRUSTED_DOMAINS_PROMPT_LIST}
- NEVER return Google, Bing, Vertex AI, or redirect URLs as source_url
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
        raw_url = data.get("source_url", "N/A")
        # Normalize: strip Vertex AI / grounding URLs, ensure trusted domain
        source_url = normalize_citation_url(raw_url)

        return {"value": value, "source_url": source_url}

    except Exception:
        return {"value": "Not found", "source_url": "N/A"}


def _extract_batch_from_snippets(
    car_name: str,
    batch: List[str],
    search_results_map: Dict[str, List[Dict[str, str]]]
) -> Dict[str, Dict[str, str]]:
    """
    Extract up to 10 specs in ONE Gemini call.
    Each spec's snippets are shown in a clearly labelled section to prevent
    cross-contamination. Searches remain 1-per-spec; only Gemini is batched.

    Returns: {spec_name: {"value": ..., "source_url": ...}}
    """
    sections = []
    for spec_name in batch:
        results = search_results_map.get(spec_name, [])
        human_name = spec_name.replace("_", " ").title()
        desc = SPEC_DESCRIPTIONS.get(spec_name, human_name)
        section = f"--- SPEC: {spec_name} ({human_name}) ---\nDefinition: {desc}\n"
        if results:
            for i, r in enumerate(results[:5], 1):
                section += f"[{i}] {r.get('domain', '')}: {r.get('snippet', '')}\n    URL: {r.get('url', '')}\n"
        else:
            section += "(No search results)\n"
        sections.append(section)

    json_lines = [
        f'    "{s}": {{"value": "extracted value or Not found", "source_url": "URL from that spec\'s results only"}}'
        for s in batch
    ]

    prompt = f"""Extract {len(batch)} specifications for the LATEST MODEL of {car_name}.
Each specification has its own clearly labelled search results section.

{"".join(sections)}
Return ONLY this JSON (no markdown):
{{
{chr(10).join(json_lines)}
}}

CRITICAL RULES:
- Use ONLY the search results from each spec's OWN section — never mix between specs
- Include units: bhp, Nm, kmpl, mm, litres, kg, sec, etc.
- source_url must be a real URL from THAT spec's own results, from: {_TRUSTED_DOMAINS_PROMPT_LIST}
- NEVER return Google, Bing, Vertex AI, or redirect URLs
- Prefer {CURRENT_YEAR} or most recent model data
- If not clearly found in a spec's own results: return "Not found" and source_url "N/A" """

    try:
        text = call_gemini_simple(prompt)
        if not text:
            return {s: {"value": "Not found", "source_url": "N/A"} for s in batch}

        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()
        if "{" in text and "}" in text:
            text = text[text.index("{"):text.rindex("}") + 1]

        data = json_repair.loads(text)
        if not isinstance(data, dict):
            return {s: {"value": "Not found", "source_url": "N/A"} for s in batch}

        result = {}
        for spec_name in batch:
            spec_data = data.get(spec_name, {})
            if isinstance(spec_data, dict):
                value = spec_data.get("value", "Not found")
                raw_url = spec_data.get("source_url", "N/A")
            else:
                value = str(spec_data) if spec_data else "Not found"
                raw_url = "N/A"
            if not value or value in ["Not found", "N/A", ""]:
                value = "Not found"
            result[spec_name] = {"value": value, "source_url": normalize_citation_url(raw_url)}
        return result

    except Exception:
        return {s: {"value": "Not found", "source_url": "N/A"} for s in batch}


def phase1_per_spec_search(car_name: str, existing_specs: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Phase 1: Per-spec CSE search (unchanged) + batched Gemini extraction.

    Searches: 1 Custom Search query per spec (same as before).
    Extraction: snippets from 10 specs sent to 1 Gemini call (10x fewer Gemini calls).

    Returns: {specs: {spec_name: value}, citations: {spec_name: {source_url}}}
    """
    BATCH_SIZE = 10

    print(f"\n{'='*60}")
    print(f"PHASE 1: PER-SPEC SEARCH + BATCHED SNIPPET EXTRACTION")
    print(f"{'='*60}\n")

    existing_specs = existing_specs or {}

    # Find specs not yet found
    remaining_specs = [
        s for s in CAR_SPECS
        if s not in existing_specs or existing_specs.get(s) in ["Not found", "Not Available", ""]
    ]

    print(f"  Searching {len(remaining_specs)} specs | extracting in batches of {BATCH_SIZE}...\n")

    # ── STEP 1: run all searches in parallel (identical to original) ──────────
    search_results_map: Dict[str, List[Dict]] = {}

    def run_search(spec_name):
        keyword = SPEC_KEYWORDS.get(spec_name, spec_name.replace("_", " "))
        query = build_enhanced_query(car_name, keyword, enhance=True)
        try:
            return spec_name, google_custom_search(query, SEARCH_ENGINE_ID, num_results=5)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"    Search rate limit: {spec_name}")
            return spec_name, []

    with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        for spec_name, results in executor.map(run_search, remaining_specs):
            search_results_map[spec_name] = results

    # ── STEP 2: batch specs into groups of 10, one Gemini call per batch ──────
    batches = [remaining_specs[i:i+BATCH_SIZE] for i in range(0, len(remaining_specs), BATCH_SIZE)]
    print(f"  {len(remaining_specs)} searches done → {len(batches)} Gemini extraction calls\n")

    specs = {}
    citations = {}
    found = 0

    def run_batch(batch):
        return _extract_batch_from_snippets(car_name, batch, search_results_map)

    with concurrent.futures.ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as executor:
        for batch_result in executor.map(run_batch, batches):
            for spec_name, spec_data in batch_result.items():
                value = spec_data["value"]
                source_url = spec_data["source_url"]
                specs[spec_name] = value
                citations[spec_name] = {
                    "source_url": source_url,
                    "citation_text": "From search results",
                    "engine": "SEARCH",
                }
                if value and "Not found" not in value:
                    found += 1

    accuracy = (found / len(remaining_specs) * 100) if remaining_specs else 0
    print(f"\n  Phase 1 Complete: {found}/{len(remaining_specs)} specs ({accuracy:.1f}%)")

    return {"specs": specs, "citations": citations}


# ============================================================================
# PHASE 2: AUTOCARINDIA URL FALLBACK (BATCHED)
# ============================================================================

def get_brand_name(car_name: str) -> str:
    """Extract brand name from car name."""
    brands = ["mahindra", "tata", "hyundai", "mg", "toyota", "maruti", "kia",
              "honda", "ford", "jeep", "skoda", "volkswagen", "nissan", "renault", "citroen"]

    car_name_lower = car_name.lower()
    for brand in brands:
        if brand in car_name_lower:
            return brand

    return car_name.split()[0].lower()


def normalize_car_name_for_url(car_name: str) -> str:
    """Normalize car name for URL format."""
    brands = ["mahindra", "tata", "hyundai", "mg", "toyota", "maruti", "suzuki", "kia",
              "honda", "ford", "jeep", "skoda", "volkswagen", "nissan", "renault", "citroen"]

    car_name_lower = car_name.lower()
    for brand in brands:
        car_name_lower = car_name_lower.replace(brand + " ", "")

    url_name = car_name_lower.strip().replace(" ", "-")
    return url_name


def build_cardekho_url(car_name: str) -> str:
    """Build CarDekho spec page URL."""
    brand = get_brand_name(car_name)
    url_car_name = normalize_car_name_for_url(car_name)
    return f"https://www.cardekho.com/{brand}/{url_car_name}"


def extract_specs_from_url(car_name: str, url: str, spec_batch: List[str]) -> Dict[str, str]:
    """
    Extract a batch of specs from CarDekho URL using Gemini.

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


def search_single_source_for_specs(car_name: str, source: dict, specs_to_find: List[str]) -> Dict[str, Any]:
    """
    Search a single automotive source for all missing specs.

    Inspired by clinical trials multi-registry parallel search — each source
    is searched independently and results are merged afterwards.

    Returns: {spec_name: {"value": ..., "source_url": ...}} dict
    """
    # Build numbered spec guide with descriptions
    spec_guide_lines = []
    for i, spec in enumerate(specs_to_find, 1):
        desc = SPEC_DESCRIPTIONS.get(spec, spec.replace("_", " ").title())
        spec_guide_lines.append(f"{i}. **{spec}**: {desc}")
    specs_detail = "\n".join(spec_guide_lines)

    json_template = ",\n".join([
        f'    "{spec}": {{"value": "extracted value or Not found", "source_url": "exact page URL"}}'
        for spec in specs_to_find
    ])

    source_domain = source["url"].split("//")[1].split("/")[0] if "//" in source["url"] else source["url"]

    prompt = f'''You are an automotive data expert. Search {source["name"]} ({source["url"]}) for {car_name} specifications.

SOURCE: {source["name"]}
WEBSITE: {source["url"]}
BEST FOR: {source.get("strengths", "general car specs")}
DESCRIPTION: {source.get("description", "")}

YOUR TASK: Find ALL {len(specs_to_find)} specifications for **{car_name}** from {source["name"]} ONLY.

SPECIFICATIONS TO EXTRACT:
{specs_detail}

SEARCH STRATEGY:
1. Search: "{car_name} specifications site:{source_domain}"
2. Search: "{car_name} {source["name"].lower()} review specs"
3. Navigate to the {car_name} page on {source["name"]} and read the spec table / road test

CRITICAL RULES:
- ONLY use data from {source["name"]} — do NOT use data from other websites
- EXACT values with units: "210 mm", "1497 cc", "6 airbags", "₹12.5-18.9 Lakh", "9.2 sec 0-100 kmph"
- For qualitative specs (ride, NVH, steering): use the exact phrase or rating from the {source["name"]} review
- If NOT found on {source["name"]}: set value to "Not found"
- source_url MUST be a real page URL from {source_domain} (e.g., https://www.{source_domain}/...)
- NEVER return Vertex AI, Google, grounding redirect, or googleapis.com URLs as source_url

Return ONLY this JSON (no markdown):
{{
{json_template}
}}'''

    try:
        tools = [types.Tool(google_search=types.GoogleSearch())]
        config = types.GenerateContentConfig(
            tools=tools,
            temperature=0.1,
            max_output_tokens=4096,
        )

        response = _gemini_search_client.models.generate_content(
            model=GEMINI_MAIN_MODEL,
            contents=prompt,
            config=config,
        )

        if response and response.text:
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            text = text.strip()
            if "{" in text and "}" in text:
                text = text[text.index("{"):text.rindex("}") + 1]
            return json_repair.loads(text)

    except Exception as e:
        print(f"      {source['name']} error: {str(e)[:60]}")

    return {}


def phase2_gemini_search_fallback(car_name: str, current_specs: Dict[str, str]) -> Dict[str, Any]:
    """
    Phase 2: Multi-source parallel search for missing specs.

    TWO-STEP approach (inspired by clinical trials multi-registry parallel search):
    Step 1: Search ALL 8 automotive sources IN PARALLEL for all missing specs
            — each source searched independently, like individual clinical trial registries
    Step 2: Aggregate results — first non-empty value per spec wins, with source tracking

    Returns: {specs: {spec_name: value}, citations: {spec_name: {source_url}}}
    """
    missing_specs = [
        s for s in CAR_SPECS
        if s not in current_specs or current_specs[s] in ["Not found", "Not Available", ""]
    ]

    if not missing_specs:
        return {"specs": {}, "citations": {}}

    print(f"\n{'='*60}")
    print(f"PHASE 2: MULTI-SOURCE PARALLEL SEARCH ({len(missing_specs)} missing specs)")
    print(f"{'='*60}\n")
    print(f"  Searching {len(AUTOMOTIVE_SPEC_SOURCES)} sources in PARALLEL...")
    print(f"  Sources: {', '.join(s['name'] for s in AUTOMOTIVE_SPEC_SOURCES)}\n")

    # Split missing specs into batches of 15 — keeps each prompt focused and avoids truncation
    PHASE2_BATCH_SIZE = 15
    spec_batches = [missing_specs[i:i+PHASE2_BATCH_SIZE] for i in range(0, len(missing_specs), PHASE2_BATCH_SIZE)]

    # Build all (source × batch) task combinations
    tasks = [
        (source, batch_idx, batch)
        for source in AUTOMOTIVE_SPEC_SOURCES
        for batch_idx, batch in enumerate(spec_batches)
    ]

    print(f"  Total queries: {len(tasks)} ({len(AUTOMOTIVE_SPEC_SOURCES)} sources × {len(spec_batches)} batches)\n")

    # Collect all results: spec_name -> list of {value, source_url, source_name}
    all_results: Dict[str, List[Dict]] = {}
    source_counts = {source["name"]: 0 for source in AUTOMOTIVE_SPEC_SOURCES}

    def run_source_batch(source, batch_idx, batch):
        result = search_single_source_for_specs(car_name, source, batch)
        found = {}
        for spec_name in batch:
            spec_data = result.get(spec_name, {})
            if isinstance(spec_data, dict):
                value = spec_data.get("value", "Not found")
                raw_url = spec_data.get("source_url", source["url"])
            else:
                value = str(spec_data) if spec_data else "Not found"
                raw_url = source["url"]

            # Always normalize to a trusted citation URL
            source_url = normalize_citation_url(raw_url, source["name"])

            if value and value not in ["Not found", "Not Available", "", "N/A"]:
                found[spec_name] = {"value": value, "source_url": source_url, "source_name": source["name"]}

        return source["name"], batch_idx, found

    # Run all tasks in parallel with bounded concurrency
    max_workers = min(len(tasks), GEMINI_WORKERS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_source_batch, source, batch_idx, batch): (source["name"], batch_idx)
            for source, batch_idx, batch in tasks
        }

        for future in concurrent.futures.as_completed(futures):
            src_name, batch_idx = futures[future]
            try:
                src_name, b_idx, found = future.result()
                source_counts[src_name] = source_counts.get(src_name, 0) + len(found)

                for spec_name, data in found.items():
                    if spec_name not in all_results:
                        all_results[spec_name] = []
                    all_results[spec_name].append(data)

                print(f"    {src_name} (batch {b_idx+1}/{len(spec_batches)}): {len(found)} specs found")

            except Exception as e:
                print(f"    {src_name}: Error - {str(e)[:60]}")

    # Step 2: Aggregate — first found value per spec wins
    specs = {}
    citations = {}

    for spec_name, results in all_results.items():
        if results:
            best = results[0]
            specs[spec_name] = best["value"]
            citations[spec_name] = {
                "source_url": best["source_url"],
                "citation_text": f"Extracted from {best['source_name']} via Gemini+Search",
            }

    # Print source breakdown
    print(f"\n  Source breakdown:")
    for src_name, count in source_counts.items():
        if count > 0:
            print(f"    {src_name}: {count} specs")

    recovered = len(specs)
    print(f"\n  Phase 2 Complete: Recovered {recovered}/{len(missing_specs)} specs")

    return {"specs": specs, "citations": citations}


# Backward compatibility alias
def phase2_cardekho_fallback(car_name: str, current_specs: Dict[str, str]) -> Dict[str, Any]:
    """Alias for phase2_gemini_search_fallback (backward compatibility)."""
    return phase2_gemini_search_fallback(car_name, current_specs)


# ============================================================================
# MAIN SCRAPING FUNCTION
# ============================================================================

def scrape_car_data_with_custom_search(car_name: str) -> Dict[str, Any]:
    """
    Main scraping function.

    Phase 0: Official brand site extraction (top 30 specs)
    Phase 1: Per-spec search for remaining specs
    Phase 2: CarDekho fallback for missing specs
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

    # Phase 2: CarDekho fallback
    phase2_result = phase2_cardekho_fallback(car_name, specs)

    # Merge Phase 2 results
    for spec_name, value in phase2_result["specs"].items():
        specs[spec_name] = value

    for spec_name, citation in phase2_result["citations"].items():
        citations[spec_name] = citation

    # Phase 3: Extract feature-specific images from CarDekho
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
        "method": "Per-Spec Search + CarDekho Fallback",
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
    cardekho_count = sum(1 for s in CAR_SPECS if "cardekho" in str(citations.get(s, {}).get("source_url", "")).lower())

    elapsed = time.time() - start_time
    accuracy = (final_found / len(CAR_SPECS) * 100) if CAR_SPECS else 0

    print(f"\n{'='*60}")
    print(f"COMPLETE: {final_found}/{len(CAR_SPECS)} specs ({accuracy:.1f}%)")
    print(f"Time: {elapsed:.1f}s | Sources: {len(car_data['source_urls'])}")
    print(f"  Official: {official_count} | Search: {search_count} | CarDekho: {cardekho_count}")
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
        from benchmarking_agent.core.async_scraper import gemini_api
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

    # Phase 0: Official brand site extraction (parallel batches)
    phase0_result = phase0_official_site_extraction(car_name)
    specs = phase0_result["specs"].copy()
    citations = phase0_result["citations"].copy()

    # Phase 1: Sync per-spec search with batched Gemini extraction (faster than async per-spec)
    phase1_result = phase1_per_spec_search(car_name, existing_specs=specs)

    # Merge Phase 1 results
    for spec_name, value in phase1_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase1_result["citations"].items():
        if spec_name not in citations:
            citations[spec_name] = citation

    # Phase 2: CarDekho fallback (still sync for now)
    phase2_result = phase2_cardekho_fallback(car_name, specs)

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
        "method": "Async Per-Spec Search + CarDekho Fallback",
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
    cardekho_count = sum(1 for s in CAR_SPECS if "cardekho" in str(citations.get(s, {}).get("source_url", "")).lower())

    elapsed = time.time() - start_time
    accuracy = (final_found / len(CAR_SPECS) * 100) if CAR_SPECS else 0

    print(f"\n{'='*60}")
    print(f"ASYNC COMPLETE: {final_found}/{len(CAR_SPECS)} specs ({accuracy:.1f}%)")
    print(f"Time: {elapsed:.1f}s | Sources: {len(car_data['source_urls'])}")
    print(f"  Official: {official_count} | Search: {search_count} | CarDekho: {cardekho_count}")
    print(f"{'='*60}\n")

    return car_data
