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
        "steering wheel image",
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


def calculate_image_relevance_score(item: dict, car_name: str, feature_query: str) -> float:
    """
    Calculate relevance score for an image result.

    Args:
        item: Search result item from API
        car_name: Car name (e.g., "Mahindra Thar")
        feature_query: Feature being searched (e.g., "dashboard")

    Returns:
        Float score (0.0 to 1.0, higher is better)
    """
    score = 0.0

    # Extract text fields
    title = item.get("title", "").lower()
    snippet = item.get("snippet", "").lower()
    link = item.get("link", "").lower()
    display_link = item.get("displayLink", "").lower()

    # Combine all text for matching
    combined_text = f"{title} {snippet} {link} {display_link}"

    # Extract feature keywords (split on spaces, take important words)
    feature_keywords = [w.lower() for w in feature_query.split() if len(w) > 3]
    car_keywords = [w.lower() for w in car_name.split() if len(w) > 3]

    # Score based on feature keyword matches
    feature_matches = sum(1 for keyword in feature_keywords if keyword in combined_text)
    if feature_matches > 0:
        score += 0.5 * (feature_matches / len(feature_keywords))

    # Score based on car name matches
    car_matches = sum(1 for keyword in car_keywords if keyword in combined_text)
    if car_matches > 0:
        score += 0.3 * (car_matches / len(car_keywords))

    # Bonus for preferred domains
    preferred_domains = ["autocarindia", "cardekho", "carwale", "zigwheels", "overdrive"]
    if any(domain in display_link for domain in preferred_domains):
        score += 0.2

    # PENALTY: If only car name present but NO feature keywords (generic car image)
    has_car_keywords = any(keyword in combined_text for keyword in car_keywords)
    has_feature_keywords = any(keyword in combined_text for keyword in feature_keywords)

    if has_car_keywords and not has_feature_keywords:
        score = 0.01  # Heavy penalty for generic car images

    return min(score, 1.0)  # Cap at 1.0


def search_feature_image(
    car_name: str,
    feature_query: str,
    max_retries: int = 3
) -> Tuple[str, str, str]:
    """
    Search for a specific feature image using COMPANY_SEARCH_ID with retry logic.
    Uses scoring to select the best match and skips invalid URLs.

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
                "num": 10,  # Get more results for scoring
                "imgSize": "medium",
                "safe": "active",
                "imgType": "photo",
            }

            response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=10)

            if response.status_code == 200:
                items = response.json().get("items", [])
                if not items:
                    return None, feature_query.title(), "no_results"

                # Score all items and filter valid URLs
                scored_items = []

                for item in items:
                    img_url = item.get("link", "")

                    # SKIP x-raw-image URLs completely
                    if "x-raw-image" in img_url:
                        continue

                    # Validate URL
                    if not img_url.startswith(('http://', 'https://')):
                        # Try thumbnail as fallback (but skip if it's encrypted/blurry)
                        image_meta = item.get("image", {})
                        thumb_url = image_meta.get("thumbnailLink", "")

                        # Skip encrypted thumbnail URLs (they're blurry)
                        if thumb_url and "encrypted-tbn" not in thumb_url:
                            img_url = thumb_url
                        else:
                            # Try original image context
                            img_url = image_meta.get("contextLink", "")

                    # Only consider valid HTTP/HTTPS URLs
                    if img_url and img_url.startswith(('http://', 'https://')):
                        # Skip encrypted thumbnails
                        if "encrypted-tbn" in img_url:
                            continue

                        score = calculate_image_relevance_score(item, car_name, feature_query)
                        scored_items.append((score, img_url, item))

                # Sort by score (highest first)
                scored_items.sort(key=lambda x: x[0], reverse=True)

                # Always return the best scoring image, even if score is low
                # Better to show something relevant than nothing at all
                if scored_items:
                    best_score, best_url, best_item = scored_items[0]
                    # No minimum threshold - if we have ANY valid image, use the best one
                    return best_url, feature_query.title(), "success"

                # No valid results found (all were invalid URLs)
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
            "q": f"{car_name} official exterior",
            "searchType": "image",
            "num": 10,  # Get more results for better selection
            "imgSize": "large",
        }
        response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            if items:
                # Score all hero images to find the best match
                scored_heroes = []
                fallback_url = None  # Track first valid URL as fallback

                for item in items:
                    hero_url = item.get("link", "")

                    # Skip x-raw-image URLs
                    if "x-raw-image" in hero_url:
                        continue

                    # Skip encrypted thumbnails (blurry)
                    if "encrypted-tbn" in hero_url:
                        continue

                    # Validate URL
                    if not hero_url.startswith(('http://', 'https://')):
                        image_meta = item.get("image", {})
                        hero_url = image_meta.get("contextLink", "")  # Use context, not thumbnail

                    if hero_url and hero_url.startswith(('http://', 'https://')) and hero_url not in used_urls:
                        # Store first valid URL as fallback
                        if fallback_url is None:
                            fallback_url = hero_url

                        # Validate car name match in URL and metadata
                        title = item.get("title", "").lower()
                        snippet = item.get("snippet", "").lower()
                        link = hero_url.lower()
                        display_link = item.get("displayLink", "").lower()

                        combined_text = f"{title} {snippet} {link} {display_link}"
                        car_keywords = [w.lower() for w in car_name.split() if len(w) > 3]

                        # Check if car name is present
                        car_matches = sum(1 for keyword in car_keywords if keyword in combined_text)

                        # Penalty for other car brand names in the URL/title
                        other_brands = ["kia", "tata", "maruti", "mahindra", "toyota", "honda", "ford", "volkswagen", "skoda", "nissan", "renault"]
                        # Remove the current car's brand from penalty list
                        current_brand = car_name.split()[0].lower()
                        other_brands = [b for b in other_brands if b != current_brand]

                        has_other_brand = any(brand in combined_text for brand in other_brands)

                        # Add all valid images with scores (even 0.0)
                        score = 0.0
                        if car_matches > 0 and not has_other_brand:
                            score = car_matches / len(car_keywords)
                            # Bonus for official domains
                            if any(domain in display_link for domain in ["hyundai.com", "mahindra.com", "kia.com", "autocarindia", "cardekho"]):
                                score += 0.3
                        scored_heroes.append((score, hero_url))

                # Sort by score and take the best (always return highest score, even if 0.0)
                if scored_heroes:
                    scored_heroes.sort(key=lambda x: x[0], reverse=True)
                    best_score, best_hero_url = scored_heroes[0]
                    results["hero"].append((best_hero_url, car_name))
                    used_urls.add(best_hero_url)
                elif fallback_url:
                    # If all were filtered, use fallback
                    results["hero"].append((fallback_url, car_name))
                    used_urls.add(fallback_url)
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
