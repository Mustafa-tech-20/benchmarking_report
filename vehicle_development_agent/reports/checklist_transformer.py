"""
Checklist Transformer - Convert raw spec data to checklist format
Transforms text values into ✓, ✗, numbers, and short text for comparison tables
"""
import re
from typing import Dict, Any, Union


def _xfeat(car_data: Dict[str, Any], feat_name: str):
    """Read a feature fetched by _fetch_binary_feature_comparison (stored as xfeat_ keys)."""
    key = "xfeat_" + feat_name.lower().replace(" ", "_").replace("/", "_").replace(
        "-", "_").replace("(", "").replace(")", "").replace(".", "").replace("&", "_")
    return car_data.get(key)


def extract_number(text: str) -> Union[int, None]:
    """Extract first number from text. Returns None if not found."""
    if not text or text in ["Not Available", "N/A", "Not found", ""]:
        return None
    match = re.search(r'\d+', str(text))
    return int(match.group()) if match else None


def has_feature(text: str, keywords: list = None) -> bool:
    """Check if feature is present in text."""
    if not text or text in ["Not Available", "N/A", "Not found", ""]:
        return False

    text_lower = str(text).lower()

    # If specific keywords provided, check for them
    if keywords:
        return any(kw.lower() in text_lower for kw in keywords)

    # General presence check
    return len(text_lower) > 3


def parse_airbag_types(airbag_breakdown: str, airbag_count: str) -> Dict[str, Any]:
    """
    Parse airbag types from breakdown text.

    Returns:
        {
            "total": 6,
            "knee": True/False,
            "curtain": True/False,
            "side": True/False,
            "front": True/False
        }
    """
    result = {
        "total": extract_number(airbag_count) or 0,
        "knee": False,
        "curtain": False,
        "side": False,
        "front": True if extract_number(airbag_count) else False  # Assume front if any airbags
    }

    if not airbag_breakdown or airbag_breakdown in ["Not Available", "N/A"]:
        return result

    text_lower = airbag_breakdown.lower()

    result["knee"] = "knee" in text_lower
    result["curtain"] = "curtain" in text_lower
    result["side"] = "side" in text_lower or "side airbag" in text_lower

    return result


def parse_seat_features(seat_features: str) -> Dict[str, Any]:
    """
    Parse seat features from detailed text.

    Returns:
        {
            "backrest_split": "60-40" or None,
            "lumbar_support": "2 way" or None,
            "thigh_support": True/False,
            "ventilation": True/False
        }
    """
    result = {
        "backrest_split": None,
        "lumbar_support": None,
        "thigh_support": False,
        "ventilation": False,
        "height_adjust": False
    }

    if not seat_features or seat_features in ["Not Available", "N/A"]:
        return result

    text_lower = seat_features.lower()

    # Extract backrest split ratio
    split_match = re.search(r'(\d+[-:/]\d+)', text_lower)
    if split_match:
        result["backrest_split"] = split_match.group(1).replace('/', '-').replace(':', '-')

    # Extract lumbar support type
    if "lumbar" in text_lower:
        lumbar_match = re.search(r'(\d+)\s*way', text_lower)
        if lumbar_match:
            result["lumbar_support"] = f"{lumbar_match.group(1)} way"
        else:
            result["lumbar_support"] = "Yes"

    # Check for thigh support
    result["thigh_support"] = "thigh" in text_lower and "support" in text_lower

    # Check for ventilation
    result["ventilation"] = "ventilat" in text_lower

    # Check for height adjust
    result["height_adjust"] = "height adjust" in text_lower or "height-adjust" in text_lower

    return result


def parse_rear_seat_features(rear_features: str) -> Dict[str, Any]:
    """
    Parse rear seat features.

    Returns:
        {
            "fold": "60-40" or "flat fold" or None,
            "center_armrest": True/False,
            "recline": True/False
        }
    """
    result = {
        "fold": None,
        "center_armrest": False,
        "recline": False
    }

    if not rear_features or rear_features in ["Not Available", "N/A"]:
        return result

    text_lower = rear_features.lower()

    # Extract fold type
    split_match = re.search(r'(\d+[-:/]\d+)', text_lower)
    if split_match:
        result["fold"] = split_match.group(1).replace('/', '-').replace(':', '-')
    elif "flat" in text_lower and "fold" in text_lower:
        result["fold"] = "Flat fold"
    elif "fold" in text_lower:
        result["fold"] = "Yes"

    # Check for center armrest
    result["center_armrest"] = ("center" in text_lower or "centre" in text_lower) and "armrest" in text_lower

    # Check for recline
    result["recline"] = "recline" in text_lower

    return result


def parse_seatbelt_features(seatbelt_features: str) -> Dict[str, Any]:
    """
    Parse seatbelt features.

    Returns:
        {
            "pretensioner": True/False,
            "load_limiter": True/False,
            "height_adjuster": True/False
        }
    """
    result = {
        "pretensioner": False,
        "load_limiter": False,
        "height_adjuster": False
    }

    if not seatbelt_features or seatbelt_features in ["Not Available", "N/A"]:
        return result

    text_lower = seatbelt_features.lower()

    result["pretensioner"] = "pretensioner" in text_lower or "pre-tensioner" in text_lower
    result["load_limiter"] = "load" in text_lower and "limit" in text_lower
    result["height_adjuster"] = "height" in text_lower and ("adjust" in text_lower or "adjuster" in text_lower)

    return result


def transform_to_checklist(car_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform raw car data into checklist format.

    Args:
        car_data: Raw car specification data

    Returns:
        Dictionary with checklist-formatted data organized by categories
    """
    checklist = {
        "car_name": car_data.get("car_name", "Unknown"),

        # Safety & Airbags
        "safety": {
            "airbag_total": extract_number(car_data.get("airbags", "")),
            "airbag_knee": False,
            "airbag_curtain": False,
            "airbag_side": False,
            "dsc": has_feature(car_data.get("stability", ""), ["dsc", "stability control", "esp"]),
            "abs": has_feature(car_data.get("brakes", ""), ["abs"]) or has_feature(car_data.get("vehicle_safety_features", ""), ["abs"]),
            "adas": has_feature(car_data.get("adas", "")),
            "ncap_rating": car_data.get("ncap_rating", "Not Available"),
            "hill_hold": has_feature(car_data.get("vehicle_safety_features", ""), ["hill hold", "hill start"]),
            "tpms": has_feature(car_data.get("vehicle_safety_features", ""), ["tpms", "tyre pressure"]),
            "isofix": has_feature(car_data.get("vehicle_safety_features", ""), ["isofix"]),
        },

        # Seats & Comfort
        "seats": {
            "material": None,
            "backrest_split": None,
            "lumbar_support": None,
            "ventilation_driver": False,
            "ventilation_codriver": False,
            "seat_height_adjust": False,
            "rear_fold": None,
            "rear_armrest": False,
        },

        # Seatbelts
        "seatbelts": {
            "pretensioner": False,
            "load_limiter": False,
            "height_adjuster": False,
        },

        # Technology & Infotainment
        "technology": {
            "infotainment_size": None,
            "digital_display": has_feature(car_data.get("digital_display", "")),
            "apple_carplay": has_feature(car_data.get("apple_carplay", "")),
            "audio_system": None,
            "cruise_control": has_feature(car_data.get("cruise_control", "")),
            "parking_camera": has_feature(car_data.get("parking_camera", "")),
            "parking_sensors": has_feature(car_data.get("parking_sensors", "")),
            "push_button_start": has_feature(car_data.get("button", ""), ["push button", "keyless"]),
        },

        # Comfort & Convenience
        "comfort": {
            "sunroof": has_feature(car_data.get("sunroof", "")),
            "climate_control": has_feature(car_data.get("climate_control", "")),
            "armrest": has_feature(car_data.get("armrest", "")),
            "headrest": has_feature(car_data.get("headrest", "")),
            "power_windows": has_feature(car_data.get("window", ""), ["power"]),
            "auto_irvm": has_feature(car_data.get("irvm", ""), ["auto"]),
            "power_orvm": has_feature(car_data.get("orvm", ""), ["electric", "power"]),
            "epb": has_feature(car_data.get("epb", ""), ["parking brake", "epb"]),
        },

        # Exterior Features
        "exterior": {
            "led_headlights": has_feature(car_data.get("led", ""), ["led", "projector"]),
            "led_drls": has_feature(car_data.get("drl", ""), ["drl", "led"]),
            "led_tail_lamps": has_feature(car_data.get("tail_lamp", ""), ["led"]),
            "alloy_wheels": has_feature(car_data.get("alloy_wheel", "")),
            "wheel_size": None,
            "tyre_size": car_data.get("tyre_size", "N/A"),
        },

        # Dimensions & Specs
        "dimensions": {
            "wheelbase": car_data.get("wheelbase", "N/A"),
            "ground_clearance": car_data.get("ground_clearance", "N/A"),
            "turning_radius": car_data.get("turning_radius", "N/A"),
            "boot_space": car_data.get("boot_space", "N/A"),
            "fuel_type": car_data.get("fuel_type", "N/A"),
            "engine_displacement": car_data.get("engine_displacement", "N/A"),
        },

        # Boot & Trunk
        "boot_trunk": {
            "trunk_metal_anchor_points":    _xfeat(car_data, "Trunk Metal Anchor Points"),
            "trunk_storage_box":            _xfeat(car_data, "Trunk Storage Box"),
            "trunk_subwoofer":              _xfeat(car_data, "Trunk Subwoofer"),
            "dashcam_provision":            _xfeat(car_data, "Dashcam Provision"),
            "cup_holder_tail_door":         _xfeat(car_data, "Cup Holder at Tail Door"),
            "hooks_tail_door":              _xfeat(car_data, "Hooks at Tail Door"),
            "warning_triangle_tail_door":   _xfeat(car_data, "Warning Triangle at Tail Door"),
            "door_magnetic_strap":          _xfeat(car_data, "Door Magnetic Strap"),
        },

        # Floor Console
        "floor_console": {
            "armrest_sliding":              _xfeat(car_data, "Armrest Sliding"),
            "armrest_soft":                 _xfeat(car_data, "Armrest Soft"),
            "armrest_storage":              _xfeat(car_data, "Armrest Storage"),
            "wireless_charging_front_row":  _xfeat(car_data, "Wireless Charging Front Row"),
            "wireless_charging_count":      _xfeat(car_data, "No of Wireless Charging Pads"),
            "front_cup_holders":            _xfeat(car_data, "Front Cup Holders"),
            "rear_cup_holders":             _xfeat(car_data, "Rear Cup Holders"),
        },

        # Door & Trim
        "door_trim": {
            "front_door_scuff_material":    _xfeat(car_data, "Front Door Scuff Material"),
            "rear_door_scuff_material":     _xfeat(car_data, "Rear Door Scuff Material"),
        },

        # Steering & Voice
        "steering_voice": {
            "voice_recognition_steering":   _xfeat(car_data, "Voice Recognition Steering Wheel"),
            "voice_assistant_type":         _xfeat(car_data, "Voice Assistant Type"),
            "multi_language_voice":         _xfeat(car_data, "Multi-language Voice Commands"),
            "amazon_alexa":                 _xfeat(car_data, "Amazon Alexa Voice Assistant"),
            "active_noise_reduction":       _xfeat(car_data, "Active Noise Reduction"),
            "intelligent_voice_control":    _xfeat(car_data, "Intelligent Voice Control"),
            "intelligent_dodge":            _xfeat(car_data, "Intelligent Dodge"),
            "intelligent_parking_assist":   _xfeat(car_data, "Intelligent Parking Assist"),
        },

        # Seats Extended
        "seats_extended": {
            "codriver_seat_adjustment":     _xfeat(car_data, "Co-Driver Seat Adjustment"),
            "power_seat_controls_location": _xfeat(car_data, "Power Seat Controls Location"),
            "programmable_memory_seat":     _xfeat(car_data, "Programmable Memory Seat"),
            "seatbelt_warning":             _xfeat(car_data, "Seatbelt Warning"),
            "seatbelt_tongue_holder_2nd":   _xfeat(car_data, "Seatbelt Tongue Holder 2nd Row"),
            "crash_sensor":                 _xfeat(car_data, "Crash Sensor"),
        },

        # Technology Extended
        "technology_extended": {
            "infotainment_touch":           _xfeat(car_data, "Infotainment Touch"),
            "display_language":             _xfeat(car_data, "Display Language"),
            "phone_sync_audio":             _xfeat(car_data, "Phone Sync Audio"),
            "bluetooth_hands_free":         _xfeat(car_data, "Bluetooth Hands Free"),
            "am_fm_radio":                  _xfeat(car_data, "AM/FM Radio"),
            "digital_radio_dab":            _xfeat(car_data, "Digital Radio DAB"),
            "wireless_smartphone_integration": _xfeat(car_data, "Wireless Smartphone Integration"),
        },

        # Branded Audio
        "branded_audio": {
            "audio_brand":                  _xfeat(car_data, "Audio Brand"),
            "dolby_atmos":                  _xfeat(car_data, "Dolby Atmos"),
            "speed_sensing_volume":         _xfeat(car_data, "Speed Sensing Volume"),
        },

        # Others
        "others": {
            "transparent_car_bottom_camera": _xfeat(car_data, "Transparent Car Bottom Camera"),
            "car_picnic_table":             _xfeat(car_data, "Car Picnic Table"),
            "safety_belt_holder_2nd_row":   _xfeat(car_data, "Safety Belt Holder 2nd Row"),
            "front_rear_parking_sensor":    _xfeat(car_data, "Front Rear Parking Sensor Radar"),
        },
    }

    # Parse granular features from new specs
    airbag_breakdown = parse_airbag_types(
        car_data.get("airbag_types_breakdown", ""),
        car_data.get("airbags", "")
    )
    checklist["safety"]["airbag_total"] = airbag_breakdown["total"]
    checklist["safety"]["airbag_knee"] = airbag_breakdown["knee"]
    checklist["safety"]["airbag_curtain"] = airbag_breakdown["curtain"]
    checklist["safety"]["airbag_side"] = airbag_breakdown["side"]

    seat_features = parse_seat_features(car_data.get("seat_features_detailed", ""))
    checklist["seats"]["backrest_split"] = seat_features["backrest_split"]
    checklist["seats"]["lumbar_support"] = seat_features["lumbar_support"]
    checklist["seats"]["ventilation_driver"] = seat_features["ventilation"]

    # Seat material
    seat_material = car_data.get("seat_material", "")
    if seat_material and seat_material not in ["Not Available", "N/A"]:
        checklist["seats"]["material"] = seat_material

    # Height adjustable driver seat
    checklist["seats"]["seat_height_adjust"] = has_feature(seat_features.get("height_adjust", "")) or \
                                                has_feature(car_data.get("seat_features_detailed", ""), ["height adjust"])

    # Also check general ventilated_seats field
    if has_feature(car_data.get("ventilated_seats", "")):
        checklist["seats"]["ventilation_driver"] = True
        checklist["seats"]["ventilation_codriver"] = True

    rear_features = parse_rear_seat_features(car_data.get("rear_seat_features", ""))
    checklist["seats"]["rear_fold"] = rear_features["fold"]
    checklist["seats"]["rear_armrest"] = rear_features["center_armrest"]

    seatbelt_features = parse_seatbelt_features(car_data.get("seatbelt_features", ""))
    checklist["seatbelts"].update(seatbelt_features)

    # Technology features
    infotainment_text = car_data.get("infotainment_screen", "")
    if infotainment_text and infotainment_text not in ["Not Available", "N/A"]:
        # Extract screen size (e.g., "17.8 cm" or "10.25 inch")
        size_match = re.search(r'(\d+\.?\d*)\s*(cm|inch|"|in)', infotainment_text.lower())
        if size_match:
            size = size_match.group(1)
            unit = size_match.group(2)
            if unit in ['cm']:
                checklist["technology"]["infotainment_size"] = f"{size} cm"
            else:
                checklist["technology"]["infotainment_size"] = f"{size}\""

    # Audio system
    audio_text = car_data.get("audio_system", "")
    if audio_text and audio_text not in ["Not Available", "N/A"]:
        # Extract brand and speaker count
        if "speaker" in audio_text.lower():
            speaker_match = re.search(r'(\d+)-?speaker', audio_text.lower())
            brand_match = re.search(r'(harman|bose|jbl|sony|alpine|pioneer)', audio_text.lower(), re.IGNORECASE)
            if speaker_match and brand_match:
                checklist["technology"]["audio_system"] = f"{speaker_match.group(1)}sp {brand_match.group(1).title()}"
            elif speaker_match:
                checklist["technology"]["audio_system"] = f"{speaker_match.group(1)} speakers"
            elif brand_match:
                checklist["technology"]["audio_system"] = brand_match.group(1).title()

    # Exterior - Wheel size
    wheel_text = car_data.get("wheel_size", "")
    if wheel_text and wheel_text not in ["Not Available", "N/A"]:
        wheel_match = re.search(r'(\d+)-?inch', wheel_text.lower())
        if wheel_match:
            checklist["exterior"]["wheel_size"] = f"{wheel_match.group(1)}\""

    return checklist


def format_checklist_value(value: Any) -> str:
    """
    Format a value for display in checklist table.

    Args:
        value: Raw value (bool, int, str, None)

    Returns:
        HTML formatted string (✓, ✗, number, or text)
    """
    if value is None or value == "Not Available" or value == "N/A":
        return '<span class="check-no">✗</span>'

    if isinstance(value, bool):
        if value:
            return '<span class="check-yes">✓</span>'
        else:
            return '<span class="check-no">✗</span>'

    if isinstance(value, int):
        return f'<span class="check-number">{value}</span>'

    if isinstance(value, str):
        # Check if it's a "Not Available" variant
        if value.lower() in ["not available", "n/a", "not found", ""]:
            return '<span class="check-no">✗</span>'
        # Short text values (keep as-is)
        if len(value) < 20:
            return f'<span class="check-text">{value}</span>'
        # Long text (truncate)
        return f'<span class="check-text">{value[:17]}...</span>'

    return '<span class="check-no">--</span>'
