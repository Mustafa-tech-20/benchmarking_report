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
        "front headlights close up",
        "LED DRL daytime running lights",
        "front grille close up",
        "alloy wheels rim design",
        "rear tail lamps close up",
        "side profile exterior",
        "rear exterior view",
        "door handles exterior detail",
    ],

    "interior": [
        "dashboard steering wheel view",
        "front seats interior",
        "infotainment touchscreen display",
        "speedometer instrument cluster display",
        "steering wheel controls",
        "center console interior",
        "gear",
        "door panel interior trim",
    ],

    "technology": [
        "infotainment touchscreen system",
        "digital instrument cluster display",
        "infotainment UI screen",
        "Apple CarPlay infotainment",
        "360 degree camera display",
        "parking sensors display",
        "cruise control steering controls",
    ],

    "comfort": [
        "front seats comfort interior",
        "rear seats interior",
        "sunroof interior view",
        "rear AC vents interior",
        "center armrest interior",
        "boot space trunk open",
        "rear legroom interior",
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
    feature_query: str,
    max_retries: int = 3
) -> Tuple[str, str, str]:
    """
    Search for a specific feature image using COMPANY_SEARCH_ID with retry logic.

    Args:
        car_name: Car name (e.g., "Mahindra Thar")
        feature_query: Feature to search for (e.g., "headlights", "dashboard")
        max_retries: Maximum number of retry attempts

    Returns:
        (image_url, caption, status) tuple where status is:
        - "success": Image found
        - "no_results": CSE returned no images
        - "rate_limited": Hit CSE rate limit
        - "error": Other error occurred
    """
    import time
    import random

    query = f"{car_name} {feature_query}"

    for attempt in range(max_retries):
        try:
            params = {
                "key": GOOGLE_API_KEY,
                "cx": COMPANY_SEARCH_ID,
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
                    if img_url:
                        return img_url, feature_query.title(), "success"

                # No results found
                return None, feature_query.title(), "no_results"

            elif response.status_code == 429:
                # Rate limited - retry with exponential backoff
                if attempt < max_retries - 1:
                    delay = min(5 * (2 ** attempt) + random.uniform(1, 3), 30)
                    time.sleep(delay)
                    continue
                else:
                    return None, feature_query.title(), "rate_limited"

            else:
                # Other HTTP error
                return None, feature_query.title(), f"http_{response.status_code}"

        except requests.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None, feature_query.title(), "timeout"

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None, feature_query.title(), f"error"

    return None, feature_query.title(), "max_retries_exceeded"


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
            "q": f"{car_name} front three quarter official press image",
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
        url, caption, status = search_feature_image(car_name, feature)
        return category, url, caption, status

    # Track failure reasons
    failure_stats = {
        "duplicates": 0,
        "no_results": 0,
        "rate_limited": 0,
        "errors": 0
    }

    # Execute searches in parallel (limit to 6 workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(search_task, task) for task in search_tasks]

        for future in concurrent.futures.as_completed(futures):
            try:
                category, url, caption, status = future.result()

                if url and url not in used_urls:
                    results[category].append((url, caption))
                    used_urls.add(url)
                elif url and url in used_urls:
                    failure_stats["duplicates"] += 1
                elif status == "no_results":
                    failure_stats["no_results"] += 1
                elif status == "rate_limited":
                    failure_stats["rate_limited"] += 1
                else:
                    failure_stats["errors"] += 1

            except Exception:
                failure_stats["errors"] += 1

    total_found = sum(len(v) for v in results.values())
    total_failed = sum(failure_stats.values())

    print(f"    Found: Hero={len(results['hero'])}, "
          f"Ext={len(results['exterior'])}, "
          f"Int={len(results['interior'])}, "
          f"Tech={len(results['technology'])}, "
          f"Comfort={len(results['comfort'])}, "
          f"Safety={len(results['safety'])}")

    if total_failed > 0:
        failure_details = []
        if failure_stats["rate_limited"] > 0:
            failure_details.append(f"{failure_stats['rate_limited']} rate limited")
        if failure_stats["no_results"] > 0:
            failure_details.append(f"{failure_stats['no_results']} no results")
        if failure_stats["duplicates"] > 0:
            failure_details.append(f"{failure_stats['duplicates']} duplicates")
        if failure_stats["errors"] > 0:
            failure_details.append(f"{failure_stats['errors']} errors")

        print(f"    Skipped {total_failed} images: {', '.join(failure_details)}")

    return results
