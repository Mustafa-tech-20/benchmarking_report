"""
Async Feature-specific image extraction using Google CSE
with rate limiting and best practices.
Includes intelligent image-feature relevance verification.
"""
import asyncio
import logging
import random
import re
from typing import Dict, List, Tuple, Optional

import aiohttp

from benchmarking_agent.config import (
    GOOGLE_API_KEY,
    COMPANY_SEARCH_ID,
    CUSTOM_SEARCH_URL
)
from benchmarking_agent.core.async_utils import (
    AsyncHTTPClient,
    custom_search_limiter,
    async_retry,
    logger
)
from benchmarking_agent.extraction.images import FEATURE_QUERIES


# ============================================================================
# IMAGE RELEVANCE VERIFICATION
# ============================================================================

def calculate_relevance_score(image_item: dict, feature_query: str) -> float:
    """
    Calculate how relevant an image is to the requested feature.

    Checks:
    - Image title contains feature keywords
    - Image snippet/description contains feature keywords
    - Context (page title) contains feature keywords

    Args:
        image_item: Image result from Google CSE
        feature_query: The feature we're looking for (e.g., "headlights")

    Returns:
        Relevance score (0.0 to 1.0), higher is better
    """
    score = 0.0
    feature_keywords = feature_query.lower().split()

    # Get image metadata
    title = image_item.get("title", "").lower()
    snippet = image_item.get("snippet", "").lower()

    # Image-specific metadata
    image_meta = image_item.get("image", {})
    context_link = image_meta.get("contextLink", "").lower()

    # Score based on title (most important - 40%)
    if any(keyword in title for keyword in feature_keywords):
        score += 0.4
    elif any(re.search(rf'\b{keyword}\b', title) for keyword in feature_keywords):
        score += 0.3

    # Score based on snippet (30%)
    if any(keyword in snippet for keyword in feature_keywords):
        score += 0.3
    elif any(re.search(rf'\b{keyword}\b', snippet) for keyword in feature_keywords):
        score += 0.2

    # Score based on context/URL (20%)
    if any(keyword in context_link for keyword in feature_keywords):
        score += 0.2
    elif any(re.search(rf'\b{keyword}\b', context_link) for keyword in feature_keywords):
        score += 0.1

    # Bonus: exact phrase match (10%)
    if feature_query.lower() in title or feature_query.lower() in snippet:
        score += 0.1

    return min(score, 1.0)  # Cap at 1.0


def select_best_image(items: List[dict], feature_query: str) -> Optional[Tuple[str, float]]:
    """
    Select the highest scoring image from search results.
    ALWAYS returns the best available image, even if score is low.

    Args:
        items: List of image results from Google CSE
        feature_query: The feature we're looking for

    Returns:
        (image_url, relevance_score) or None if no images at all
    """
    best_image = None
    best_score = -1.0  # Start with -1 to accept any score >= 0

    for item in items:
        img_url = item.get("link", "")
        if not img_url:
            continue

        score = calculate_relevance_score(item, feature_query)

        if score > best_score:
            best_score = score
            best_image = img_url

    if best_image:
        return best_image, best_score

    return None  # Only if no images at all


# ============================================================================
# ASYNC IMAGE SEARCH
# ============================================================================

async def async_search_feature_image(
    session: aiohttp.ClientSession,
    car_name: str,
    feature_query: str,
    confidence_threshold: float = 0.5
) -> Tuple[str, str, str, float]:
    """
    Search for a specific feature image with intelligent relevance scoring.
    ALWAYS returns the best available image, never skips.

    Args:
        session: aiohttp ClientSession
        car_name: Car name (e.g., "Mahindra Thar")
        feature_query: Feature to search for (e.g., "headlights", "dashboard")
        confidence_threshold: Score above this = high confidence (for logging only)

    Returns:
        (image_url, caption, status, relevance_score) tuple where status is:
        - "high_confidence": Relevance >= threshold (good match)
        - "best_available": Relevance < threshold but best we have
        - "no_results": No images returned by CSE at all
        - "rate_limited": Hit CSE rate limit
        - "error": Other error occurred
    """
    # Build specific query - don't use "latest" for images
    query = f"{car_name} {feature_query}"

    # Apply rate limiting
    async with custom_search_limiter.acquire():
        # Retry logic
        async for attempt in async_retry(
            max_attempts=3,
            min_wait=1.0,
            max_wait=10.0,
            exceptions=(aiohttp.ClientError, asyncio.TimeoutError)
        ):
            with attempt:
                try:
                    params = {
                        "key": GOOGLE_API_KEY,
                        "cx": COMPANY_SEARCH_ID,
                        "q": query,
                        "searchType": "image",
                        "num": 5,  # Get more results for better selection
                        "imgSize": "medium",
                        "safe": "active",
                        "imgType": "photo",
                    }

                    async with session.get(CUSTOM_SEARCH_URL, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            items = data.get("items", [])

                            if not items:
                                return None, feature_query.title(), "no_results", 0.0

                            # Always select best image, regardless of score
                            result = select_best_image(items, feature_query)

                            if result:
                                img_url, score = result

                                # Status based on confidence level
                                status = "high_confidence" if score >= confidence_threshold else "best_available"

                                logger.debug(
                                    f"Selected image for '{feature_query}': "
                                    f"score={score:.2f}, status={status}"
                                )
                                return img_url, feature_query.title(), status, score
                            else:
                                # This should rarely happen (only if no valid URLs)
                                return None, feature_query.title(), "no_results", 0.0

                        elif response.status == 429:
                            # Rate limited - will retry with exponential backoff
                            logger.warning(f"Rate limit hit for {feature_query}")
                            await asyncio.sleep(random.uniform(2, 5))
                            raise Exception("Rate limit (429)")

                        else:
                            return None, feature_query.title(), f"http_{response.status}", 0.0

                except aiohttp.ClientError as e:
                    logger.warning(f"Client error for {feature_query}: {e}")
                    raise

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout for {feature_query}")
                    raise

    return None, feature_query.title(), "max_retries_exceeded", 0.0


# ============================================================================
# ASYNC IMAGE EXTRACTION
# ============================================================================

async def async_extract_autocar_images(car_name: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Extract feature-specific images using async HTTP with rate limiting.

    Args:
        car_name: Name of the car (e.g., "Mahindra Thar")

    Returns:
        Dict mapping categories to list of (image_url, caption) tuples
    """
    logger.info(f"Extracting feature images for {car_name} (async)...")

    results = {
        "hero": [],
        "exterior": [],
        "interior": [],
        "technology": [],
        "comfort": [],
        "safety": []
    }

    used_urls = set()

    async with AsyncHTTPClient() as http_client:
        # Get hero image first
        try:
            async with custom_search_limiter.acquire():
                params = {
                    "key": GOOGLE_API_KEY,
                    "cx": COMPANY_SEARCH_ID,
                    "q": f"{car_name} official exterior",
                    "searchType": "image",
                    "num": 2,
                    "imgSize": "large",
                }

                async with http_client.session.get(CUSTOM_SEARCH_URL, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("items", [])
                        if items:
                            hero_url = items[0].get("link", "")
                            if hero_url and hero_url not in used_urls:
                                results["hero"].append((hero_url, car_name))
                                used_urls.add(hero_url)
        except Exception as e:
            logger.warning(f"Hero image fetch failed: {e}")

        # Search for each feature in parallel
        search_tasks = []
        for category, features in FEATURE_QUERIES.items():
            for feature in features[:4]:  # Limit to 4 per category
                search_tasks.append((category, feature))

        # Execute all searches concurrently with confidence threshold
        tasks = [
            async_search_feature_image(http_client.session, car_name, feature, confidence_threshold=0.5)
            for category, feature in search_tasks
        ]

        # Track stats by confidence level
        stats = {
            "high_confidence": 0,      # Score >= 0.5
            "best_available": 0,       # Score < 0.5 but used anyway
            "duplicates": 0,
            "no_results": 0,
            "rate_limited": 0,
            "errors": 0
        }
        relevance_scores = []

        # Process results as they complete
        completed_tasks = []
        for task in asyncio.as_completed(tasks):
            try:
                url, caption, status, relevance = await task
                completed_tasks.append((url, caption, status, relevance))
            except Exception as e:
                logger.error(f"Image search task failed: {e}")
                stats["errors"] += 1
                completed_tasks.append((None, None, "error", 0.0))

        # Match results back to categories
        for i, (url, caption, status, relevance) in enumerate(completed_tasks):
            if i >= len(search_tasks):
                break

            category, _ = search_tasks[i]

            if url and url not in used_urls:
                # Always add the image
                results[category].append((url, caption))
                used_urls.add(url)
                relevance_scores.append(relevance)

                # Track confidence level
                if status == "high_confidence":
                    stats["high_confidence"] += 1
                elif status == "best_available":
                    stats["best_available"] += 1

            elif url and url in used_urls:
                stats["duplicates"] += 1
            elif status == "no_results":
                stats["no_results"] += 1
            elif status == "rate_limited":
                stats["rate_limited"] += 1
            else:
                stats["errors"] += 1

    # Print summary with confidence stats
    total_found = sum(len(v) for v in results.values())
    total_skipped = stats["duplicates"] + stats["no_results"] + stats["rate_limited"] + stats["errors"]
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

    logger.info(
        f"Found: Hero={len(results['hero'])}, "
        f"Ext={len(results['exterior'])}, "
        f"Int={len(results['interior'])}, "
        f"Tech={len(results['technology'])}, "
        f"Comfort={len(results['comfort'])}, "
        f"Safety={len(results['safety'])}"
    )

    if relevance_scores:
        logger.info(
            f"Confidence: {stats['high_confidence']} high (≥0.5), "
            f"{stats['best_available']} acceptable (<0.5)"
        )
        logger.info(
            f"Relevance scores: avg={avg_relevance:.2f}, "
            f"min={min(relevance_scores):.2f}, "
            f"max={max(relevance_scores):.2f}"
        )

    if total_skipped > 0:
        skip_details = []
        if stats["no_results"] > 0:
            skip_details.append(f"{stats['no_results']} no results")
        if stats["duplicates"] > 0:
            skip_details.append(f"{stats['duplicates']} duplicates")
        if stats["rate_limited"] > 0:
            skip_details.append(f"{stats['rate_limited']} rate limited")
        if stats["errors"] > 0:
            skip_details.append(f"{stats['errors']} errors")

        logger.info(f"Skipped {total_skipped} searches: {', '.join(skip_details)}")

    return results


logger.info("Async images module initialized")
