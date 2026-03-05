"""
Feature-specific image extraction using Google CSE with site: filter
Restricts searches to AutoCarIndia.com for reliable, categorized images
"""

import requests
import concurrent.futures
from typing import Dict, List, Tuple
from benchmarking_agent.config import GOOGLE_API_KEY, COMPANY_SEARCH_ID, CUSTOM_SEARCH_URL


def build_autocarindia_url(car_name: str) -> str:
    """
    Build AutoCarIndia URL path for site: filter.

    Examples:
    - "Mahindra Thar" → "autocarindia.com/cars/mahindra/thar"
    - "Hyundai Creta" → "autocarindia.com/cars/hyundai/creta"
    - "Kia Seltos" → "autocarindia.com/cars/kia/seltos"
    """
    parts = car_name.strip().lower().split()
    if len(parts) < 2:
        return "autocarindia.com"

    make = parts[0]
    model = "-".join(parts[1:])

    return f"autocarindia.com/cars/{make}/{model}"


# Feature-specific search queries for each category
# These match how AutoCarIndia organizes their images
FEATURE_QUERIES = {
    "exterior": [
        "headlights",
        "LED DRL",
        "front grille",
        "alloy wheels",
        "tail lamps",
        "side profile",
        "rear view",
        "door handles",
    ],

    "interior": [
        "dashboard",
        "interior seats",
        "infotainment screen",
        "instrument cluster",
        "steering wheel",
        "center console",
        "gear shifter",
        "door pads",
    ],

    "technology": [
        "touchscreen",
        "digital display",
        "infotainment system",
        "Apple CarPlay",
        "360 camera",
        "parking sensors",
        "cruise control",
    ],

    "comfort": [
        "front seats",
        "rear seats",
        "sunroof",
        "AC vents",
        "armrest",
        "boot space",
        "legroom",
    ],

    "safety": [
        "airbags",
        "ABS brakes",
        "parking camera",
        "ADAS",
        "safety rating",
        "crash test",
    ],
}


def search_feature_image(
    car_name: str,
    feature_query: str
) -> Tuple[str, str]:
    """
    Search for a specific feature image using COMPANY_SEARCH_ID.

    Args:
        car_name: Car name (e.g., "Mahindra Thar")
        feature_query: Feature to search for (e.g., "headlights", "dashboard")

    Returns:
        (image_url, caption) tuple
    """
    try:
        # Simple query without site: filter
        # COMPANY_SEARCH_ID should already target automotive websites
        query = f"{car_name} {feature_query}"

        params = {
            "key": GOOGLE_API_KEY,
            "cx": COMPANY_SEARCH_ID,  # Use company search engine
            "q": query,
            "searchType": "image",
            "num": 3,
            "imgSize": "medium",
            "safe": "active",
            "imgType": "photo",
        }

        response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=10)

        if response.status_code == 200:
            items = response.json().get("items", [])

            if items:
                img_url = items[0].get("link", "")
                caption = feature_query.title()
                return img_url, caption

        return None, feature_query.title()

    except Exception as e:
        return None, feature_query.title()


def extract_autocar_images(car_name: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Extract feature-specific images using COMPANY_SEARCH_ID.

    Args:
        car_name: Name of the car (e.g., "Mahindra Thar")

    Returns:
        Dict mapping categories to list of (image_url, caption) tuples
    """
    print(f"\n  Extracting feature images for {car_name}...")
    print(f"    Using COMPANY_SEARCH_ID (automotive websites)")

    results = {
        "hero": [],
        "exterior": [],
        "interior": [],
        "technology": [],
        "comfort": [],
        "safety": []
    }

    # Track used URLs to prevent duplicates
    used_urls = set()

    # Get hero image first (main exterior shot)
    try:
        params = {
            "key": GOOGLE_API_KEY,
            "cx": COMPANY_SEARCH_ID,
            "q": f"{car_name} official exterior",
            "searchType": "image",
            "num": 2,
            "imgSize": "large",
        }
        response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            if items:
                hero_url = items[0].get("link", "")
                if hero_url and hero_url not in used_urls:
                    results["hero"].append((hero_url, car_name))
                    used_urls.add(hero_url)
    except Exception:
        pass

    # Search for each feature in parallel
    search_tasks = []
    for category, features in FEATURE_QUERIES.items():
        for feature in features[:4]:  # Limit to 4 per category to avoid rate limits
            search_tasks.append((category, feature))

    def search_task(task):
        category, feature = task
        url, caption = search_feature_image(car_name, feature)
        return category, url, caption

    # Execute searches in parallel (limit to 6 workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(search_task, task) for task in search_tasks]

        for future in concurrent.futures.as_completed(futures):
            try:
                category, url, caption = future.result()
                # Only add if URL exists and hasn't been used before
                if url and url not in used_urls:
                    results[category].append((url, caption))
                    used_urls.add(url)  # Mark this URL as used
            except Exception:
                pass

    duplicates_skipped = len([f for f in futures]) - sum(len(v) for v in results.values())

    print(f"    Found: Hero={len(results['hero'])}, "
          f"Ext={len(results['exterior'])}, "
          f"Int={len(results['interior'])}, "
          f"Tech={len(results['technology'])}, "
          f"Comfort={len(results['comfort'])}, "
          f"Safety={len(results['safety'])}")
    if duplicates_skipped > 0:
        print(f"    Skipped {duplicates_skipped} duplicate images")

    return results
