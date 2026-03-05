"""
Async Feature-specific image extraction using Google CSE
with rate limiting and best practices.
"""
import asyncio
import logging
import random
from typing import Dict, List, Tuple

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
# ASYNC IMAGE SEARCH
# ============================================================================

async def async_search_feature_image(
    session: aiohttp.ClientSession,
    car_name: str,
    feature_query: str
) -> Tuple[str, str, str]:
    """
    Search for a specific feature image using async HTTP with retry logic.

    Args:
        session: aiohttp ClientSession
        car_name: Car name (e.g., "Mahindra Thar")
        feature_query: Feature to search for (e.g., "headlights", "dashboard")

    Returns:
        (image_url, caption, status) tuple where status is:
        - "success": Image found
        - "no_results": CSE returned no images
        - "rate_limited": Hit CSE rate limit
        - "error": Other error occurred
    """
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
                        "num": 3,
                        "imgSize": "medium",
                        "safe": "active",
                        "imgType": "photo",
                    }

                    async with session.get(CUSTOM_SEARCH_URL, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            items = data.get("items", [])
                            if items:
                                img_url = items[0].get("link", "")
                                if img_url:
                                    return img_url, feature_query.title(), "success"
                            return None, feature_query.title(), "no_results"

                        elif response.status == 429:
                            # Rate limited - will retry with exponential backoff
                            logger.warning(f"Rate limit hit for {feature_query}")
                            await asyncio.sleep(random.uniform(2, 5))
                            raise Exception("Rate limit (429)")

                        else:
                            return None, feature_query.title(), f"http_{response.status}"

                except aiohttp.ClientError as e:
                    logger.warning(f"Client error for {feature_query}: {e}")
                    raise

                except asyncio.TimeoutError:
                    logger.warning(f"Timeout for {feature_query}")
                    raise

    return None, feature_query.title(), "max_retries_exceeded"


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
                    "q": f"{car_name} front three quarter official press image",
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

        # Execute all searches concurrently
        tasks = [
            async_search_feature_image(http_client.session, car_name, feature)
            for category, feature in search_tasks
        ]

        # Track failure stats
        failure_stats = {
            "duplicates": 0,
            "no_results": 0,
            "rate_limited": 0,
            "errors": 0
        }

        # Process results as they complete
        for i, task in enumerate(asyncio.as_completed(tasks)):
            try:
                url, caption, status = await task
                category, _ = search_tasks[i]

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

            except Exception as e:
                logger.error(f"Image search task failed: {e}")
                failure_stats["errors"] += 1

    # Print summary
    total_found = sum(len(v) for v in results.values())
    total_failed = sum(failure_stats.values())

    logger.info(
        f"Found: Hero={len(results['hero'])}, "
        f"Ext={len(results['exterior'])}, "
        f"Int={len(results['interior'])}, "
        f"Tech={len(results['technology'])}, "
        f"Comfort={len(results['comfort'])}, "
        f"Safety={len(results['safety'])}"
    )

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

        logger.info(f"Skipped {total_failed} images: {', '.join(failure_details)}")

    return results


logger.info("Async images module initialized")
