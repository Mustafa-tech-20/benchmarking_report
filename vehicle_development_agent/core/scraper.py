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
from vehicle_development_agent.config import GEMINI_MAIN_MODEL

# Initialize Gemini client for Google Search grounding (requires Vertex AI)
# Google Search grounding requires us-central1 location
import os
_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
_GROUNDING_LOCATION = "us-central1"  # Required for Google Search grounding
_gemini_search_client = genai.Client(vertexai=True, project=_PROJECT_ID, location=_GROUNDING_LOCATION)


# ============================================================================
# CONFIGURATION
# ============================================================================

MAX_RETRIES = 5  # Increased for rate limits
BASE_DELAY = 2.0  # Longer base delay
MAX_DELAY = 30.0

# Parallel workers (reduced to avoid rate limits)
SEARCH_WORKERS = 6   # Reduced for ~255 specs to avoid rate limits
GEMINI_WORKERS = 12  # Keep higher for Gemini (not hitting rate limits)

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
    "jetour": ("https://jetourglobal.com", "/{model}/"),
}

CAR_SPECS = [
    # ===== Top 5 Key Specs (for main table/charts) =====
    "price_range", "monthly_sales", "mileage", "user_rating", "seating_capacity",

    # ===== Professional Reviews / Functional Evaluation Specs =====
    # Performance & Driving
    "performance_feel", "driveability", "acceleration", "torque", "response",
    "city_performance", "highway_performance", "off_road", "crawl",
    # Transmission
    "manual_transmission_performance", "automatic_transmission_performance",
    "gear_selection",
    # Ride & Suspension
    "ride", "ride_quality", "stiff_on_pot_holes", "bumps", "shocks",
    # NVH & Noise
    "nvh", "powertrain_nvh", "wind_nvh", "road_nvh",
    "wind_noise", "tire_noise", "turbo_noise", "blower_noise",
    # Vibration & Feel
    "jerks", "pulsation", "shakes", "shudder", "grabby", "spongy", "rattle",
    # Steering & Handling
    "steering", "telescopic_steering", "turning_radius", "manoeuvring",
    "stability", "corner_stability", "straight_ahead_stability",
    # Braking
    "braking", "brakes", "brake_performance", "epb",
    # Safety
    "airbags", "airbag_types_breakdown", "vehicle_safety_features",
    "adas", "ncap_rating", "impact", "seats_restraint",
    # Interior & Comfort
    "interior", "climate_control", "seats", "seat_cushion", "seat_material",
    "seat_features_detailed", "rear_seat_features", "ventilated_seats",
    "visibility", "soft_trims", "armrest", "headrest", "egress",
    "seatbelt_features",
    # Technology & Infotainment
    "infotainment_screen", "resolution", "touch_response", "digital_display",
    "apple_carplay", "button", "audio_system", "cruise_control",
    "parking_camera", "parking_sensors",
    # Exterior & Lighting
    "led", "drl", "tail_lamp", "alloy_wheel", "tyre_size", "wheel_size",
    # Convenience
    "sunroof", "irvm", "orvm", "window", "wiper_control", "parking",
    "door_effort", "sensitivity",
    # Dimensions
    "wheelbase", "ground_clearance", "boot_space", "chasis",
    "fuel_type", "engine_displacement",

    # ===== IMAGE 1: Technical Specifications =====
    "engine", "max_power_kw", "fuel_tank_capacity", "transmission", "drive",
    "drive_mode", "top_speed", "length", "width", "height", "wheel_track",
    "kerb_weight", "front_brakes", "rear_brakes", "front_suspension",
    "rear_suspension", "front_tyre_size", "rear_tyre_size", "spare_tyres",

    # Exterior Features (from Images 2-3)
    "full_led", "wheel_arch_claddings", "front_bumper_grille", "antenna_type",
    "foot_step", "console_switches", "upholstery", "ip_dashboard", "glove_box",
    "sunvisor_driver", "sunvisor_co_driver", "grab_handle_driver",
    "grab_handle_co_driver", "grab_handle_2nd_row", "panoramic_sunroof",
    "roller_blind_sunblind", "luggage_rack", "front_wiper", "defogging",
    "rain_sensing_wipers", "rear_wiper", "door_front", "door_rear",
    "tailgate_type", "power_tailgate",

    # Interior Features (from Images 4-5)
    "steering_wheel", "bonnet_gas_strut", "bottle_holder", "door_arm_rest",
    "boot_organizer", "boot_lamp", "power_window_all_doors",
    "power_window_driver_door", "window_one_key_lift", "window_anti_clamping",
    "multilayer_silencing_glass", "front_windshield_mute_glass",
    "steering_column", "floor_console_armrest",
    "cup_holders", "wireless_charging", "no_of_wireless_charging",
    "door_inner_scuff_front", "door_inner_scuff_rear", "voice_recognition_steering",

    # Safety Features (from Image 6)
    "seat_ventilation_driver", "seat_ventilation_front_passenger",
    "driver_seat_belt", "front_passenger_seat_belt",
    "seat_belt_2nd_row", "child_anchor", "child_lock", "seat_belt_reminder",
    "seat_belt_holder_2nd_row", "crash_sensors",

    # Technology Features (from Image 8)
    "smartphone_connectivity", "bluetooth", "am_fm_radio", "digital_radio",
    "connected_drive_wireless", "no_of_speakers",
    "audio_brand", "dolby_atmos", "audio_adjustable",

    # Lighting Features (from Image 9)
    "headlamp", "high_beam", "low_beam", "auto_high_beam", "headlamp_leveling",
    "projector_led", "front_fog_lamp", "welcome_lighting", "ambient_lighting",
    "cabin_lamps", "high_mounted_stop_lamp", "hazard_lamp",

    # Locking Features (from Image 9)
    "central_locking", "door_lock", "speed_sensing_door_lock", "panic_alarm",
    "remote_lock_unlock", "digital_key_plus", "over_speeding_bell",

    # ADAS Features (from Image 10)
    "active_cruise_control", "lane_departure_warning", "automatic_emergency_braking",
    "lane_keep_assist", "blind_spot_detection", "blind_spot_collision_warning",
    "forward_collision_warning", "rear_collision_warning", "door_open_alert",
    "high_beam_assist", "traffic_sign_recognition", "rear_cross_traffic_alert",
    "traffic_jam_alert", "safe_exit_braking", "surround_view_monitor", "smart_pilot_assist",

    # Climate Features (from Image 11)
    "auto_defogging", "no_of_zone_climate", "rear_vent_ac", "active_carbon_filter",
    "temp_diff_control", "bottle_opener",

    # Capabilities Features (from Image 11)
    "terrain_modes", "crawl_smart", "off_road_info_display",
    "central_differential", "wading_sensing_system",
    "electronic_gear_shift", "electric_driveline_disconnect", "tpms",
    "hhc_uphill_start_assist", "engine_electronic_security",

    # Power Outlet / Charging Points (from Image 11)
    "usb_type_c_front_row", "usb_type_c_front_row_count", "usb_type_c_rear_row",
    "socket_12v",

    # Brakes Detailed (from Image 11)
    "auto_hold", "rollover_mitigation", "rmi_anti_rollover", "vdc_vehicle_dynamic",
    "csc_corner_stability", "avh_auto_vehicle_hold", "hac_hill_ascend",
    "hba_hydraulic_brake", "dbc_downhill_brake", "ebp_electronic_brake_prefill",
    "bdw_brake_disc_wiping", "edtc_engine_drag_torque", "tcs_traction_control",
    "ebd_electronic_brake", "abs_antilock", "dst_dynamic_steering",
    "eba_brake_assist", "cbc_cornering_brake", "hdc_hill_descent",

    # Others (from Image 11)
    "active_noise_reduction", "intelligent_voice_control", "transparent_car_bottom",
    "car_picnic_table", "trunk_subwoofer", "dashcam_provision",
    "cup_holder_tail_door", "warning_triangle_tail_door",
    "door_magnetic_strap",
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
    "gear_selection": "gear lever",
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

    # Technical Specifications (from Image 1)
    "engine": "engine name type",
    "max_power_kw": "max power kW kilowatt",
    "fuel_tank_capacity": "fuel tank capacity litres",
    "transmission": "transmission type manual automatic CVT DCT",
    "drive": "drive type FWD RWD AWD 4WD",
    "drive_mode": "drive modes eco sport normal",
    "top_speed": "top speed kmph",
    "length": "length mm dimensions",
    "width": "width mm dimensions",
    "height": "height mm dimensions",
    "wheel_track": "wheel track front rear",
    "front_brakes": "front brakes disc drum ventilated",
    "rear_brakes": "rear brakes disc drum",
    "front_suspension": "front suspension MacPherson strut",
    "rear_suspension": "rear suspension multi-link torsion beam",
    "front_tyre_size": "front tyre size",
    "rear_tyre_size": "rear tyre size",
    "spare_tyres": "spare tyre type full size temporary",

    # Exterior Features (from Images 2-3)
    "full_led": "full LED headlamps",
    "wheel_arch_claddings": "wheel arch claddings",
    "front_bumper_grille": "front bumper grille design",
    "antenna_type": "antenna type shark fin",
    "foot_step": "foot step side step",
    "console_switches": "console switches controls",
    "upholstery": "upholstery material leather fabric",
    "ip_dashboard": "instrument panel dashboard",
    "glove_box": "glove box cooled illuminated",
    "sunvisor_driver": "sun visor driver vanity mirror",
    "sunvisor_co_driver": "sun visor co-driver passenger",
    "grab_handle_driver": "grab handle driver",
    "grab_handle_co_driver": "grab handle co-driver",
    "grab_handle_2nd_row": "grab handle 2nd row rear",
    "panoramic_sunroof": "panoramic sunroof",
    "roller_blind_sunblind": "roller blind sunblind sunshade",
    "luggage_rack": "luggage rack roof rails",
    "front_wiper": "front wiper",
    "defogging": "defogging defogger",
    "rain_sensing_wipers": "rain sensing wipers automatic",
    "rear_wiper": "rear wiper washer",
    "door_front": "front door",
    "door_rear": "rear door",
    "tailgate_type": "tailgate type",
    "power_tailgate": "power tailgate electric boot",

    # Interior Features (from Images 4-5)
    "steering_wheel": "steering wheel leather wrapped",
    "bonnet_gas_strut": "bonnet gas strut hood lifter",
    "bottle_holder": "bottle holder door pocket",
    "door_arm_rest": "door arm rest",
    "boot_organizer": "boot organizer cargo net",
    "boot_lamp": "boot lamp trunk light",
    "power_window_all_doors": "power window all doors",
    "power_window_driver_door": "power window driver door auto",
    "window_one_key_lift": "window one touch up down",
    "window_anti_clamping": "window anti-pinch anti-clamping",
    "multilayer_silencing_glass": "multilayer silencing glass acoustic",
    "front_windshield_mute_glass": "front windshield acoustic glass",
    "steering_column": "steering column tilt telescopic",
    "floor_console_armrest": "floor console armrest storage",
    "cup_holders": "cup holders number",
    "wireless_charging": "wireless charging pad",
    "no_of_wireless_charging": "number of wireless charging pads",
    "door_inner_scuff_front": "front door scuff plate",
    "door_inner_scuff_rear": "rear door scuff plate",
    "voice_recognition_steering": "voice recognition steering wheel button",

    # Safety Features (from Image 6)
    "seat_ventilation_driver": "driver seat ventilation cooling",
    "seat_ventilation_front_passenger": "front passenger seat ventilation",
    "driver_seat_belt": "driver seat belt pretensioner",
    "front_passenger_seat_belt": "front passenger seat belt",
    "seat_belt_2nd_row": "2nd row seat belt rear",
    "child_anchor": "child anchor ISOFIX",
    "child_lock": "child lock rear door",
    "seat_belt_reminder": "seat belt reminder buzzer warning",
    "seat_belt_holder_2nd_row": "seat belt holder 2nd row",
    "crash_sensors": "crash sensors impact detection",

    # Technology Features (from Image 8)
    "smartphone_connectivity": "smartphone connectivity mirroring",
    "bluetooth": "bluetooth connectivity",
    "am_fm_radio": "AM FM radio",
    "digital_radio": "digital radio DAB",
    "connected_drive_wireless": "connected drive wireless OTA",
    "no_of_speakers": "number of speakers",
    "audio_brand": "audio brand harman bose JBL",
    "dolby_atmos": "Dolby Atmos sound",
    "audio_adjustable": "audio adjustable equalizer",

    # Lighting Features (from Image 9)
    "headlamp": "headlamp type LED halogen",
    "high_beam": "high beam",
    "low_beam": "low beam",
    "auto_high_beam": "auto high beam assist",
    "headlamp_leveling": "headlamp leveling auto manual",
    "projector_led": "projector LED headlamps",
    "front_fog_lamp": "front fog lamp LED",
    "welcome_lighting": "welcome lighting puddle lamps",
    "ambient_lighting": "ambient lighting interior",
    "cabin_lamps": "cabin lamps interior lights",
    "high_mounted_stop_lamp": "high mounted stop lamp HMSL",
    "hazard_lamp": "hazard lamp warning lights",

    # Locking Features (from Image 9)
    "central_locking": "central locking",
    "door_lock": "door lock power",
    "speed_sensing_door_lock": "speed sensing door lock auto",
    "panic_alarm": "panic alarm",
    "remote_lock_unlock": "remote lock unlock key fob",
    "digital_key_plus": "digital key smartphone",
    "over_speeding_bell": "over speeding bell alert warning",

    # ADAS Features (from Image 10)
    "active_cruise_control": "active cruise control ACC adaptive",
    "lane_departure_warning": "lane departure warning LDW",
    "automatic_emergency_braking": "automatic emergency braking AEB",
    "lane_keep_assist": "lane keep assist LKA",
    "blind_spot_detection": "blind spot detection BSD",
    "blind_spot_collision_warning": "blind spot collision warning",
    "forward_collision_warning": "forward collision warning FCW",
    "rear_collision_warning": "rear collision warning",
    "door_open_alert": "door open alert warning",
    "high_beam_assist": "high beam assist automatic",
    "traffic_sign_recognition": "traffic sign recognition TSR",
    "rear_cross_traffic_alert": "rear cross traffic alert RCTA",
    "traffic_jam_alert": "traffic jam alert assist",
    "safe_exit_braking": "safe exit braking warning",
    "surround_view_monitor": "surround view monitor 360 camera",
    "smart_pilot_assist": "smart pilot assist autonomous",

    # Climate Features (from Image 11)
    "auto_defogging": "auto defogging automatic defog",
    "no_of_zone_climate": "climate zone dual triple automatic",
    "rear_vent_ac": "rear AC vent air conditioning",
    "active_carbon_filter": "active carbon filter air purifier",
    "temp_diff_control": "temperature differential control",
    "bottle_opener": "bottle opener",

    # Capabilities Features (from Image 11)
    "terrain_modes": "terrain modes off-road sand mud snow",
    "crawl_smart": "crawl smart low speed control",
    "off_road_info_display": "off-road information display",
    "central_differential": "central differential lock",
    "wading_sensing_system": "wading sensing system water depth",
    "electronic_gear_shift": "electronic gear shift dial rotary",
    "electric_driveline_disconnect": "electric driveline disconnect front axle",
    "tpms": "TPMS tyre pressure monitoring",
    "hhc_uphill_start_assist": "HHC uphill start assist hill hold",
    "engine_electronic_security": "engine electronic security immobilizer",

    # Power Outlet / Charging Points (from Image 11)
    "usb_type_c_front_row": "USB Type-C front row",
    "usb_type_c_front_row_count": "number USB Type-C front",
    "usb_type_c_rear_row": "USB Type-C rear row",
    "socket_12v": "12V socket power outlet",

    # Brakes Detailed (from Image 11)
    "auto_hold": "auto hold brake",
    "rollover_mitigation": "rollover mitigation",
    "rmi_anti_rollover": "RMI anti-rollover control",
    "vdc_vehicle_dynamic": "VDC vehicle dynamic control",
    "csc_corner_stability": "CSC corner stability control",
    "avh_auto_vehicle_hold": "AVH automatic vehicle hold",
    "hac_hill_ascend": "HAC hill ascend control",
    "hba_hydraulic_brake": "HBA hydraulic brake assist",
    "dbc_downhill_brake": "DBC downhill brake control",
    "ebp_electronic_brake_prefill": "EBP electronic brake pre-fill",
    "bdw_brake_disc_wiping": "BDW brake disc wiping",
    "edtc_engine_drag_torque": "EDTC engine drag torque control",
    "tcs_traction_control": "TCS traction control system",
    "ebd_electronic_brake": "EBD electronic brake force distribution",
    "abs_antilock": "ABS antilock braking system",
    "dst_dynamic_steering": "DST dynamic steering torque",
    "eba_brake_assist": "EBA emergency brake assist",
    "cbc_cornering_brake": "CBC cornering brake control",
    "hdc_hill_descent": "HDC hill descent control",

    # Others (from Image 11)
    "active_noise_reduction": "active noise reduction cancellation ANC",
    "intelligent_voice_control": "intelligent voice control assistant",
    "transparent_car_bottom": "transparent car bottom camera view",
    "car_picnic_table": "car picnic table",
    "trunk_subwoofer": "trunk subwoofer bass",
    "dashcam_provision": "dashcam provision",
    "cup_holder_tail_door": "cup holder tail door tailgate",
    "warning_triangle_tail_door": "warning triangle tail door",
    "door_magnetic_strap": "door magnetic strap holder",
}

# ============================================================================
# SPEC GROUPS - Group related specs to reduce Custom Search API calls
# Each group uses ONE search query to extract MULTIPLE specs
# Only for newly added specs (IMAGE 1-11 specs)
# ============================================================================
SPEC_GROUPS = {
    "sunvisor": {"query": "sun visor driver passenger vanity mirror illuminated", "specs": ["sunvisor_driver", "sunvisor_co_driver"]},
    "grab_handle": {"query": "grab handle driver passenger rear 2nd row", "specs": ["grab_handle_driver", "grab_handle_co_driver", "grab_handle_2nd_row"]},
    "sunroof_features": {"query": "panoramic sunroof roller blind sunshade", "specs": ["panoramic_sunroof", "roller_blind_sunblind"]},
    "wipers": {"query": "wiper front rear rain sensing automatic defogger", "specs": ["front_wiper", "defogging", "rain_sensing_wipers", "rear_wiper"]},
    "doors": {"query": "front door rear door features", "specs": ["door_front", "door_rear"]},
    "tailgate": {"query": "tailgate power electric boot type", "specs": ["tailgate_type", "power_tailgate"]},
    "power_windows": {"query": "power window all doors one touch auto up down anti-pinch", "specs": ["power_window_all_doors", "power_window_driver_door", "window_one_key_lift", "window_anti_clamping"]},
    "acoustic_glass": {"query": "acoustic glass multilayer silencing windshield", "specs": ["multilayer_silencing_glass", "front_windshield_mute_glass"]},
    "steering_column": {"query": "steering column tilt telescopic adjustment", "specs": ["steering_column"]},
    "wireless_charging": {"query": "wireless charging pad number of chargers", "specs": ["wireless_charging", "no_of_wireless_charging"]},
    "door_scuff": {"query": "door scuff plate front rear illuminated", "specs": ["door_inner_scuff_front", "door_inner_scuff_rear"]},
    "seat_ventilation": {"query": "seat ventilation cooling driver front passenger", "specs": ["seat_ventilation_driver", "seat_ventilation_front_passenger"]},
    "seat_belts": {"query": "seat belt driver passenger rear 2nd row reminder pretensioner holder", "specs": ["driver_seat_belt", "front_passenger_seat_belt", "seat_belt_2nd_row", "seat_belt_reminder", "seat_belt_holder_2nd_row"]},
    "radio": {"query": "radio AM FM digital DAB", "specs": ["am_fm_radio", "digital_radio"]},
    "audio_system": {"query": "audio speakers Dolby brand harman bose JBL", "specs": ["no_of_speakers", "audio_brand", "dolby_atmos", "audio_adjustable"]},
    "headlamps": {"query": "headlamp LED projector high beam low beam auto leveling", "specs": ["headlamp", "high_beam", "low_beam", "auto_high_beam", "headlamp_leveling", "projector_led"]},
    "interior_lighting": {"query": "ambient lighting welcome puddle cabin lamps interior", "specs": ["welcome_lighting", "ambient_lighting", "cabin_lamps", "high_mounted_stop_lamp"]},
    "locking": {"query": "central locking door lock speed sensing remote digital key", "specs": ["central_locking", "door_lock", "speed_sensing_door_lock", "remote_lock_unlock", "digital_key_plus"]},
    "adas_collision": {"query": "collision warning forward rear blind spot automatic emergency braking AEB", "specs": ["forward_collision_warning", "rear_collision_warning", "blind_spot_collision_warning", "automatic_emergency_braking"]},
    "adas_lane": {"query": "lane departure warning keep assist LDW LKA", "specs": ["lane_departure_warning", "lane_keep_assist"]},
    "adas_alerts": {"query": "door open alert traffic sign recognition jam alert safe exit", "specs": ["door_open_alert", "traffic_sign_recognition", "traffic_jam_alert", "safe_exit_braking"]},
    "adas_advanced": {"query": "surround view 360 camera smart pilot assist rear cross traffic blind spot detection", "specs": ["surround_view_monitor", "smart_pilot_assist", "rear_cross_traffic_alert", "blind_spot_detection"]},
    "climate": {"query": "climate zone dual automatic AC rear vent defogging carbon filter", "specs": ["auto_defogging", "no_of_zone_climate", "rear_vent_ac", "active_carbon_filter", "temp_diff_control"]},
    "terrain_capabilities": {"query": "terrain modes off-road crawl smart display", "specs": ["terrain_modes", "crawl_smart", "off_road_info_display"]},
    "differential": {"query": "differential central lock", "specs": ["central_differential"]},
    "offroad_tech": {"query": "wading sensing water depth electronic gear shift driveline disconnect", "specs": ["wading_sensing_system", "electronic_gear_shift", "electric_driveline_disconnect"]},
    "usb_ports": {"query": "USB Type-C port front rear 12V socket power outlet", "specs": ["usb_type_c_front_row", "usb_type_c_front_row_count", "usb_type_c_rear_row", "socket_12v"]},
    "brake_assist": {"query": "auto hold brake assist AVH HBA EBA emergency", "specs": ["auto_hold", "avh_auto_vehicle_hold", "hba_hydraulic_brake", "eba_brake_assist"]},
    "brake_stability": {"query": "rollover mitigation VDC vehicle dynamic CSC corner stability RMI", "specs": ["rollover_mitigation", "rmi_anti_rollover", "vdc_vehicle_dynamic", "csc_corner_stability"]},
    "hill_control": {"query": "hill ascend descent control HAC HDC HHC uphill start DBC", "specs": ["hac_hill_ascend", "dbc_downhill_brake", "hdc_hill_descent", "hhc_uphill_start_assist"]},
    "brake_tech": {"query": "ABS EBD TCS traction control brake disc wiping EDTC CBC cornering DST", "specs": ["ebp_electronic_brake_prefill", "bdw_brake_disc_wiping", "edtc_engine_drag_torque", "tcs_traction_control", "ebd_electronic_brake", "abs_antilock", "cbc_cornering_brake", "dst_dynamic_steering"]},
    "boot_features": {"query": "boot organizer cargo net lamp trunk light", "specs": ["boot_organizer", "boot_lamp"]},
    "door_trim": {"query": "bottle holder door pocket arm rest", "specs": ["bottle_holder", "door_arm_rest"]},
    "tail_door_accessories": {"query": "tail door cup holder warning triangle cargo", "specs": ["cup_holder_tail_door", "warning_triangle_tail_door"]},
    "misc_features": {"query": "active noise reduction voice control transparent car bottom", "specs": ["active_noise_reduction", "intelligent_voice_control", "transparent_car_bottom"]},
    "misc_accessories": {"query": "picnic table trunk subwoofer dashcam provision door magnetic strap", "specs": ["car_picnic_table", "trunk_subwoofer", "dashcam_provision", "door_magnetic_strap"]},
    "exterior_body": {"query": "wheel arch claddings front bumper grille foot step side", "specs": ["wheel_arch_claddings", "front_bumper_grille", "foot_step"]},
    "floor_console": {"query": "floor console armrest cup holders storage", "specs": ["floor_console_armrest", "cup_holders"]},
    "child_safety": {"query": "child anchor ISOFIX lock rear door", "specs": ["child_anchor", "child_lock"]},
    "connectivity": {"query": "smartphone connectivity bluetooth mirroring connected drive wireless OTA", "specs": ["smartphone_connectivity", "bluetooth", "connected_drive_wireless"]},
    "security": {"query": "panic alarm engine immobilizer electronic security", "specs": ["panic_alarm", "engine_electronic_security"]},
    "cruise_speed": {"query": "cruise control ACC adaptive active over speeding bell alert TPMS", "specs": ["active_cruise_control", "over_speeding_bell", "tpms"]},
}

# Create reverse mapping: spec -> group name
SPEC_TO_GROUP = {}
for group_name, group_data in SPEC_GROUPS.items():
    for spec in group_data["specs"]:
        SPEC_TO_GROUP[spec] = group_name


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
    "gear_selection": "Precision of individual gear selection, slotting quality",
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


def call_gemini_simple(prompt: str, timeout: int = 40) -> str:
    """
    Simple Gemini call with retry, timeout, and automatic model fallback.
    Switches from Flash to Pro after repeated rate limits.

    Args:
        prompt: The prompt to send to Gemini
        timeout: Maximum seconds to wait for API response (default 60s)
    """
    global _gemini_model, _rate_limit_count

    def _make_api_call():
        """Inner function for API call - can be timed out."""
        model = GenerativeModel(_gemini_model)
        return model.generate_content(
            prompt,
            generation_config=GenerationConfig(temperature=0.1)
        )

    for attempt in range(MAX_RETRIES):
        try:
            # Use ThreadPoolExecutor to enforce timeout on API call
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_make_api_call)
                try:
                    response = future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    print(f"      API call timeout after {timeout}s, attempt {attempt + 1}/{MAX_RETRIES}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(BASE_DELAY)
                        continue
                    return ""

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
    Phase 1: Optimized search with GROUPED specs to reduce API calls.

    - Grouped specs (newly added): ONE search per group extracts multiple specs
    - Ungrouped specs (original): ONE search per spec

    Returns: {specs: {spec_name: value}, citations: {spec_name: {source_url}}}
    """
    BATCH_SIZE = 10
    SEARCH_CHUNK_SIZE = 30
    GEMINI_CHUNK_SIZE = 8
    CHUNK_DELAY = 1.5

    print(f"\n{'='*60}")
    print(f"PHASE 1: GROUPED SEARCH + BATCHED EXTRACTION")
    print(f"{'='*60}\n")

    existing_specs = existing_specs or {}

    remaining_specs = [
        s for s in CAR_SPECS
        if s not in existing_specs or existing_specs.get(s) in ["Not found", "Not Available", ""]
    ]

    # Separate grouped vs ungrouped specs
    grouped_specs = []
    ungrouped_specs = []
    groups_to_search = set()

    for spec in remaining_specs:
        if spec in SPEC_TO_GROUP:
            grouped_specs.append(spec)
            groups_to_search.add(SPEC_TO_GROUP[spec])
        else:
            ungrouped_specs.append(spec)

    print(f"  Total remaining: {len(remaining_specs)} specs")
    print(f"  - Grouped specs: {len(grouped_specs)} (in {len(groups_to_search)} groups)")
    print(f"  - Ungrouped specs: {len(ungrouped_specs)} (individual searches)")
    print(f"  Total searches: {len(groups_to_search) + len(ungrouped_specs)} (reduced from {len(remaining_specs)})\n")

    search_results_map: Dict[str, List[Dict]] = {}

    # STEP 1a: Search for GROUPED specs
    def run_group_search(group_name):
        group_data = SPEC_GROUPS[group_name]
        query = build_enhanced_query(car_name, group_data["query"], enhance=True)
        try:
            results = google_custom_search(query, SEARCH_ENGINE_ID, num_results=5)
            return group_name, results
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"    Search rate limit: group {group_name}")
            return group_name, []

    group_list = list(groups_to_search)
    group_chunks = [group_list[i:i+SEARCH_CHUNK_SIZE] for i in range(0, len(group_list), SEARCH_CHUNK_SIZE)]

    for chunk_idx, chunk in enumerate(group_chunks):
        if chunk_idx > 0:
            time.sleep(CHUNK_DELAY)

        with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
            for group_name, results in executor.map(run_group_search, chunk):
                for spec in SPEC_GROUPS[group_name]["specs"]:
                    if spec in remaining_specs:
                        search_results_map[spec] = results

        print(f"    Group search chunk {chunk_idx+1}/{len(group_chunks)} done ({len(chunk)} groups)")

    # STEP 1b: Search for UNGROUPED specs
    def run_single_search(spec_name):
        keyword = SPEC_KEYWORDS.get(spec_name, spec_name.replace("_", " "))
        query = build_enhanced_query(car_name, keyword, enhance=True)
        try:
            return spec_name, google_custom_search(query, SEARCH_ENGINE_ID, num_results=5)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"    Search rate limit: {spec_name}")
            return spec_name, []

    ungrouped_chunks = [ungrouped_specs[i:i+SEARCH_CHUNK_SIZE] for i in range(0, len(ungrouped_specs), SEARCH_CHUNK_SIZE)]

    for chunk_idx, chunk in enumerate(ungrouped_chunks):
        if chunk_idx > 0 or group_chunks:
            time.sleep(CHUNK_DELAY)

        with concurrent.futures.ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
            for spec_name, results in executor.map(run_single_search, chunk):
                search_results_map[spec_name] = results

        print(f"    Ungrouped search chunk {chunk_idx+1}/{len(ungrouped_chunks)} done ({len(chunk)} specs)")

    # STEP 2: Batch Gemini extraction
    batches = [remaining_specs[i:i+BATCH_SIZE] for i in range(0, len(remaining_specs), BATCH_SIZE)]
    print(f"\n  {len(groups_to_search) + len(ungrouped_specs)} searches done → {len(batches)} Gemini calls")

    specs = {}
    citations = {}
    found = 0

    def run_batch(batch):
        return _extract_batch_from_snippets(car_name, batch, search_results_map)

    batch_chunks = [batches[i:i+GEMINI_CHUNK_SIZE] for i in range(0, len(batches), GEMINI_CHUNK_SIZE)]

    for chunk_idx, batch_chunk in enumerate(batch_chunks):
        if chunk_idx > 0:
            time.sleep(CHUNK_DELAY)

        with concurrent.futures.ThreadPoolExecutor(max_workers=GEMINI_WORKERS) as executor:
            for batch_result in executor.map(run_batch, batch_chunk):
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

        print(f"    Gemini chunk {chunk_idx+1}/{len(batch_chunks)} done")

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
    Phase 2: Extract missing specs by giving Gemini the direct CardDekho URL.
    Batches of 10 specs are fired in parallel — no Google Search grounding.

    Returns: {specs: {spec_name: value}, citations: {spec_name: {source_url}}}
    """
    missing_specs = [
        s for s in CAR_SPECS
        if s not in current_specs or current_specs[s] in ["Not found", "Not Available", ""]
    ]

    if not missing_specs:
        return {"specs": {}, "citations": {}}

    cardekho_url = build_cardekho_url(car_name)

    print(f"\n{'='*60}")
    print(f"PHASE 2: CARDEKHO URL EXTRACTION ({len(missing_specs)} missing specs)")
    print(f"  URL: {cardekho_url}")
    print(f"{'='*60}\n")

    PHASE2_BATCH_SIZE = 10
    MAX_PARALLEL_BATCHES = 3  # Limit parallel execution to prevent hangs
    spec_batches = [missing_specs[i:i + PHASE2_BATCH_SIZE] for i in range(0, len(missing_specs), PHASE2_BATCH_SIZE)]
    print(f"  {len(spec_batches)} batches of up to {PHASE2_BATCH_SIZE} specs")
    print(f"  Processing {MAX_PARALLEL_BATCHES} batches at a time\n")

    import threading
    specs: Dict[str, str] = {}
    citations: Dict[str, Dict] = {}
    lock = threading.Lock()

    def _call_batch(batch: List[str]) -> Dict[str, Any]:
        spec_guide_lines = []
        json_lines = []
        for spec in batch:
            desc = SPEC_DESCRIPTIONS.get(spec, spec.replace("_", " ").title())
            spec_guide_lines.append(f"- **{spec}**: {desc}")
            json_lines.append(f'  "{spec}": {{"value": "...", "source_url": "{cardekho_url}"}}')

        prompt = f"""Visit the following CarDekho page and extract the listed specifications for {car_name}.

URL: {cardekho_url}

SPECIFICATIONS TO EXTRACT:
{chr(10).join(spec_guide_lines)}

RULES:
- Navigate to the URL above and read the spec table
- Include units where applicable: bhp, Nm, kmpl, mm, litres, kg, sec
- If a spec is not present on the page, set value to "Not found"
- source_url must always be: {cardekho_url}

Return ONLY this JSON (no markdown):
{{
{chr(10).join(json_lines)}
}}"""
        try:
            raw = call_gemini_simple(prompt)
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            text = text.strip()
            if "{" in text and "}" in text:
                text = text[text.index("{"):text.rindex("}") + 1]
            return json_repair.loads(text)
        except Exception as e:
            print(f"  Batch error ({batch[0]}…): {e}")
            return {}

    # Process batches in groups of MAX_PARALLEL_BATCHES to prevent hangs
    BATCH_TIMEOUT = 120  # 2 minutes timeout per batch

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_BATCHES) as executor:
        future_to_batch = {executor.submit(_call_batch, batch): batch for batch in spec_batches}

        # Process completed futures without global timeout to prevent hangs
        try:
            for future in concurrent.futures.as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    result = future.result(timeout=BATCH_TIMEOUT)
                    found_count = 0
                    for spec_name in batch:
                        spec_data = result.get(spec_name, {})
                        value = spec_data.get("value", "Not found") if isinstance(spec_data, dict) else str(spec_data or "Not found")
                        if value and value not in ["Not found", "Not Available", "", "N/A"]:
                            with lock:
                                specs[spec_name] = value
                                citations[spec_name] = {
                                    "source_url": cardekho_url,
                                    "citation_text": "Extracted from CarDekho via Gemini",
                                }
                            found_count += 1
                    print(f"  Batch ({batch[0]}…): {found_count}/{len(batch)} found")
                except concurrent.futures.TimeoutError:
                    print(f"  Batch ({batch[0]}…): TIMEOUT after {BATCH_TIMEOUT}s - skipping")
                except Exception as e:
                    print(f"  Batch ({batch[0]}…): Error - {e}")
        except KeyboardInterrupt:
            print(f"\n  Phase 2 interrupted by user")
            executor.shutdown(wait=False)

    print(f"\n  Phase 2 Complete: Recovered {len(specs)}/{len(missing_specs)} specs")
    return {"specs": specs, "citations": citations}


# Backward compatibility alias
def phase2_cardekho_fallback(car_name: str, current_specs: Dict[str, str]) -> Dict[str, Any]:
    """Alias for phase2_gemini_search_fallback."""
    return phase2_gemini_search_fallback(car_name, current_specs)


# ============================================================================
# ENGINE VARIANTS EXTRACTION
# ============================================================================

def fetch_engine_variants(car_name: str) -> List[Dict[str, str]]:
    """
    Fetch all engine variants for a car using Gemini with Google Search grounding.

    Returns a list of dicts, each containing:
    - engine: Engine name (e.g., "TGDI mStallion", "CRDI mHawk")
    - engine_displacement: Engine CC (e.g., "2.0L [1997cc]")
    - max_power_kw: Power output (e.g., "130kW @ 5000 RPM")
    - torque: Torque (e.g., "380Nm @ 1750-3000 RPM")
    - transmission: Transmission type (e.g., "6AT | 6MT")
    - drive: Drive type (e.g., "RWD", "AWD")
    - kerb_weight: Weight (e.g., "1970 kg")
    - steering: Steering type (e.g., "Electric power steering")
    """
    print(f"\n  Fetching engine variants for {car_name}...")

    prompt = f"""Search for all engine/powertrain variants available for the {car_name} car.

For each engine variant found, extract:
1. engine: The engine name/type (e.g., "2.0L TGDI mStallion Petrol", "2.2L CRDI mHawk Diesel", "1.5TD+7DCT")
2. engine_displacement: Engine capacity in CC or liters (e.g., "1997cc", "2.0L [1997cc]")
3. max_power_kw: Maximum power in kW or bhp with RPM (e.g., "130kW @ 5000 RPM", "170bhp @ 3750 RPM")
4. torque: Maximum torque in Nm with RPM range (e.g., "380Nm @ 1750-3000 RPM")
5. transmission: Available transmissions for this engine (e.g., "6AT | 6MT", "7DCT")
6. drive: Drive type (e.g., "RWD", "FWD", "AWD", "4WD")
7. kerb_weight: Kerb weight in kg (e.g., "1970 kg")
8. steering: Steering type (e.g., "Electric power steering with Tilt")

Return JSON array with each engine variant as an object. Example:
[
  {{
    "engine": "2.0L TGDI mStallion Petrol",
    "engine_displacement": "2.0L [1997cc]",
    "max_power_kw": "130kW @ 5000 RPM",
    "torque": "380Nm @ 1750-3000 RPM",
    "transmission": "6AT | 6MT",
    "drive": "RWD",
    "kerb_weight": "1970 kg",
    "steering": "Electric power steering"
  }},
  {{
    "engine": "2.2L CRDI mHawk Diesel",
    "engine_displacement": "2.2L [2184cc]",
    "max_power_kw": "128.6kW @ 3750 RPM",
    "torque": "400Nm @ 1750-2750 RPM",
    "transmission": "6AT | 6MT",
    "drive": "RWD | AWD",
    "kerb_weight": "2050 kg",
    "steering": "Electric power steering"
  }}
]

If only one engine variant exists, return array with single object.
Return ONLY valid JSON array, no markdown or explanation."""

    try:
        response = _gemini_search_client.models.generate_content(
            model=GEMINI_MAIN_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_modalities=["TEXT"],
                temperature=0.1,
            )
        )

        if response and response.text:
            text = response.text.strip()
            # Clean up markdown if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            variants = json_repair.loads(text)
            if isinstance(variants, list) and len(variants) > 0:
                print(f"    Found {len(variants)} engine variant(s)")
                return variants
    except Exception as e:
        print(f"    Warning: Engine variants fetch failed - {str(e)}")

    # Return empty list if failed
    return []


# ============================================================================
# MAIN SCRAPING FUNCTION
# ============================================================================

def scrape_car_data_with_custom_search(car_name: str) -> Dict[str, Any]:
    """
    Main scraping function.

    Phase 0: Official brand site extraction (top 30 specs)
    Phase 1: AutoCar/CarDekho fallback (better spec coverage)
    Phase 2: CSE grouped search for missing specs
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

    # Phase 1: AutoCar/CarDekho fallback (better spec coverage)
    phase1_result = phase2_cardekho_fallback(car_name, specs)

    # Merge Phase 1 results
    for spec_name, value in phase1_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase1_result["citations"].items():
        if spec_name not in citations:
            citations[spec_name] = citation

    # Phase 2: CSE grouped search (only for missing specs)
    phase2_result = phase1_per_spec_search(car_name, existing_specs=specs)

    # Merge Phase 2 results (only missing specs)
    for spec_name, value in phase2_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase2_result["citations"].items():
        if spec_name not in citations:
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

    # Phase 4: Fetch engine variants
    engine_variants = fetch_engine_variants(car_name)

    # Build final car_data
    car_data = {
        "car_name": car_name,
        "method": "Per-Spec Search + CarDekho Fallback",
        "source_urls": [],
        "images": images,  # Add extracted images
        "engine_variants": engine_variants,  # Add engine variants
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

    # Phase 1: AutoCar/CarDekho fallback (better spec coverage)
    phase1_result = phase2_cardekho_fallback(car_name, specs)

    # Merge Phase 1 results
    for spec_name, value in phase1_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase1_result["citations"].items():
        if spec_name not in citations:
            citations[spec_name] = citation

    # Phase 2: CSE grouped search (only for missing specs after fallback)
    phase2_result = phase1_per_spec_search(car_name, existing_specs=specs)

    # Merge Phase 2 results (only missing specs)
    for spec_name, value in phase2_result["specs"].items():
        if spec_name not in specs or specs.get(spec_name) in ["Not found", "Not Available", ""]:
            specs[spec_name] = value

    for spec_name, citation in phase2_result["citations"].items():
        if spec_name not in citations:
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

    # Phase 4: Fetch engine variants
    engine_variants = fetch_engine_variants(car_name)

    # Build final car_data
    car_data = {
        "car_name": car_name,
        "method": "Async Per-Spec Search + CarDekho Fallback",
        "source_urls": [],
        "images": images,
        "engine_variants": engine_variants,  # Add engine variants
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


# ============================================================================
# MULTI-CAR PARALLEL PROCESSING
# ============================================================================

def scrape_cars_parallel(cars: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Scrape multiple cars in parallel using API-interleaved processing.

    This function maximizes throughput by interleaving different API types:
    - When Gemini is rate-limited, Custom Search tasks are processed
    - When Custom Search is rate-limited, Gemini tasks are processed

    Expected performance:
    - 2 cars: ~2-3 minutes (down from 7-10 minutes sequential)
    - 10 cars: ~8-12 minutes (down from 35-50 minutes sequential)

    Args:
        cars: List of car dicts, e.g., [{"brand": "Mahindra", "model": "XUV700"}, ...]

    Returns:
        {
            "results": {car_id: car_data, ...},
            "total_time": float,
            "metrics": metrics_dict
        }
    """
    from vehicle_development_agent.async_config import interleaved_config

    if not interleaved_config.enabled:
        # Fallback to sequential processing
        print("Interleaved processing disabled, using sequential mode...")
        results = {}
        start_time = time.time()
        for car in cars:
            car_name = f"{car.get('brand', '')} {car.get('model', '')}".strip()
            car_id = f"{car.get('brand', '').lower()}_{car.get('model', '').lower()}".replace(" ", "_")
            results[car_id] = scrape_car_data(car_name)
        return {
            "results": results,
            "total_time": time.time() - start_time,
            "metrics": {},
        }

    # Use interleaved parallel processor
    from vehicle_development_agent.core.interleaved_processor import scrape_cars_parallel_sync
    return scrape_cars_parallel_sync(cars)


async def async_scrape_cars_parallel(cars: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Async version of scrape_cars_parallel.

    For use from async code.
    """
    from vehicle_development_agent.async_config import interleaved_config

    if not interleaved_config.enabled:
        # Fallback to sequential processing
        results = {}
        start_time = time.time()
        for car in cars:
            car_name = f"{car.get('brand', '')} {car.get('model', '')}".strip()
            car_id = f"{car.get('brand', '').lower()}_{car.get('model', '').lower()}".replace(" ", "_")
            results[car_id] = await async_scrape_car_data(car_name)
        return {
            "results": results,
            "total_time": time.time() - start_time,
            "metrics": {},
        }

    # Use interleaved parallel processor
    from vehicle_development_agent.core.interleaved_processor import scrape_cars_parallel as async_scrape_parallel
    return await async_scrape_parallel(cars)
