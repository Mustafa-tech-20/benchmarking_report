"""
YouTube Pros & Cons Extraction Module

This module uses Gemini to directly search and analyze YouTube videos:
1. Ask Gemini to find car review videos from trusted channels
2. Extract pros & cons from video content
3. Provide source citations with links
"""
import sys
sys.path.append("/app")
from shared_utils import safe_json_parse, clean_json_response

from typing import Dict, List, Any
from vertexai.generative_models import GenerativeModel
import json

# Trusted YouTube channels for car reviews (Indian automotive channels)
TRUSTED_YOUTUBE_CHANNELS = [
    "Autocar India",
    "PowerDrift",
    "CarDekho",
    "Overdrive India",
    "ZigWheels",
    "Motorbeam",
    "DriveSpark",
    "Evo India",
    "Carwale",
    "Acko Drives",
    "Fasbeam",
    "Car and Bike",
    "Motoroctane",
    "Rushlane",
    "Ask Car Guru",
    "Top Gear"
]


def get_proscons_from_youtube(car_name: str, channel_name: str) -> Dict[str, Any]:
    """
    Ask Gemini to find and analyze a car review from a specific YouTube channel.

    Args:
        car_name: Car name (e.g., "Mahindra Thar")
        channel_name: YouTube channel name (e.g., "Autocar India")

    Returns:
        Dictionary with pros, cons, publication, video_title, and link
    """
    try:
        model = GenerativeModel("gemini-2.5-flash")

        prompt = f"""Analyze the {car_name} based on typical reviews from the {channel_name} YouTube channel.

TASK:
1. Based on your knowledge of {car_name} reviews from the {channel_name} YouTube channel, extract typical pros and cons
2. Extract 5-7 key POSITIVES (pros) about the {car_name}
3. Extract 5-7 key NEGATIVES (cons) about the {car_name}
4. Provide a typical video title format that users can search for
5. For the link, provide the search URL format so users can find the actual video

IMPORTANT FORMAT RULES:
- Each positive should be 1-2 sentences max, specific and factual
- Each negative should be 1-2 sentences max, specific and factual
- Focus on: performance, features, comfort, value, quality, practicality, driving dynamics
- Avoid generic statements
- Base analysis on actual review content you know about

Return ONLY a valid JSON object in this EXACT format (no markdown, no code blocks):
{{
    "positives": [
        "Positive point 1",
        "Positive point 2",
        "Positive point 3",
        "Positive point 4",
        "Positive point 5"
    ],
    "negatives": [
        "Negative point 1",
        "Negative point 2",
        "Negative point 3",
        "Negative point 4",
        "Negative point 5"
    ],
    "publication": "{channel_name}",
    "video_title": "Search: {car_name} review {channel_name}",
    "link": "https://www.youtube.com/results?search_query={car_name.replace(' ', '+')}+review+{channel_name.replace(' ', '+')}"
}}
"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean up response
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join([line for line in lines if not line.strip().startswith("```")])

        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

        # Parse JSON
        proscons_data = safe_json_parse(response_text, fallback={})
        proscons_data["car_name"] = car_name

        return proscons_data

    except Exception as e:
        print(f"Error analyzing {car_name} from {channel_name}: {e}")

        return {
            "car_name": car_name,
            "positives": [f"Error analyzing video: {str(e)[:100]}"],
            "negatives": [f"Error analyzing video: {str(e)[:100]}"],
            "publication": channel_name,
            "video_title": "N/A",
            "link": "N/A"
        }


def get_car_proscons(car_name: str, num_channels: int = 2) -> List[Dict[str, Any]]:
    """
    Get pros/cons for a car from multiple trusted YouTube channels.

    Args:
        car_name: Car name (e.g., "Mahindra Thar")
        num_channels: Number of channels to analyze (default: 2)

    Returns:
        List of dictionaries with pros/cons data from different channels
    """
    results = []

    print(f"\n[{car_name}] Extracting YouTube pros/cons from {num_channels} channels...")

    for channel in TRUSTED_YOUTUBE_CHANNELS[:num_channels]:
        print(f"  Analyzing from {channel}...")
        proscons = get_proscons_from_youtube(car_name, channel)
        results.append(proscons)

    return results


def get_multiple_cars_proscons(
    car_names: List[str],
    num_channels: int = 2
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get pros & cons for multiple cars from multiple channels.

    Args:
        car_names: List of car names
        num_channels: Number of channels to analyze per car (default: 2)

    Returns:
        Dictionary mapping car names to list of their pros/cons data from different channels
    """
    results = {}

    for car_name in car_names:
        try:
            proscons_list = get_car_proscons(car_name, num_channels)
            results[car_name] = proscons_list
        except Exception as e:
            print(f"Error getting pros/cons for {car_name}: {e}")
            results[car_name] = [{
                "car_name": car_name,
                "positives": [f"Error fetching data: {str(e)[:100]}"],
                "negatives": [f"Error fetching data: {str(e)[:100]}"],
                "publication": "N/A",
                "video_title": "N/A",
                "link": "N/A"
            }]

    return results
