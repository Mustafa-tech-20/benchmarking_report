"""
Async Car Specifications Scraper with Rate Limiting and Best Practices

Features:
- Async HTTP requests with aiohttp
- Token bucket rate limiting
- Exponential backoff with tenacity
- Circuit breaker pattern
- Connection pooling
- Proper error handling and logging
- Smart query enhancement with "latest" keyword
"""
import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import json_repair
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential_jitter
from vertexai.generative_models import GenerativeModel, GenerationConfig

from benchmarking_agent.config import (
    GOOGLE_API_KEY,
    SEARCH_ENGINE_ID,
    COMPANY_SEARCH_ID,
    CUSTOM_SEARCH_URL,
    GEMINI_MAIN_MODEL,
    GEMINI_LITE_MODEL,
)
from benchmarking_agent.async_config import rate_limit_config
from benchmarking_agent.core.async_utils import (
    AsyncHTTPClient,
    async_retry,
    custom_search_limiter,
    gemini_flash_limiter,
    gemini_pro_limiter,
    custom_search_circuit_breaker,
    gemini_circuit_breaker,
    logger,
)

# Import only what we actually use from scraper
from benchmarking_agent.core.scraper import (
    CAR_SPECS,
    SPEC_KEYWORDS,
    CURRENT_YEAR,
    QUERY_ENHANCEMENT_MODE,
    build_enhanced_query,
)


# ============================================================================
# GEMINI API - ASYNC VERSION
# ============================================================================

class GeminiAPI:
    """Async wrapper for Gemini API with rate limiting and fallback."""

    def __init__(self):
        self.current_model = GEMINI_MAIN_MODEL
        self.rate_limit_count = 0
        self.rate_limit_threshold = 10
        self.flash_lock = asyncio.Lock()
        self.pro_lock = asyncio.Lock()

    async def generate_content(
        self,
        prompt: str,
        use_flash: bool = True,
        response_mime_type: Optional[str] = None
    ) -> str:
        """
        Generate content using Gemini with automatic rate limiting and fallback.

        Args:
            prompt: The prompt to send to Gemini
            use_flash: Whether to use Flash model (falls back to Pro on rate limits)
            response_mime_type: Optional MIME type for response (e.g., "application/json")

        Returns:
            Generated text response
        """
        # Choose rate limiter and model based on current state
        if use_flash and self.rate_limit_count < self.rate_limit_threshold:
            limiter = gemini_flash_limiter
            model_name = GEMINI_MAIN_MODEL
            lock = self.flash_lock
        else:
            limiter = gemini_pro_limiter
            model_name = "gemini-2.5-pro"
            lock = self.pro_lock
            if use_flash:
                logger.warning(f"Switching to Gemini Pro after {self.rate_limit_count} rate limits")

        # Rate limiting
        async with limiter.acquire():
            async with lock:
                # Use circuit breaker
                try:
                    return await gemini_circuit_breaker.call(
                        self._call_gemini_api,
                        prompt,
                        model_name,
                        response_mime_type
                    )
                except Exception as e:
                    error_str = str(e).lower()
                    if any(x in error_str for x in ["429", "rate limit", "quota", "resource exhausted"]):
                        self.rate_limit_count += 1
                        logger.warning(f"Rate limit hit (count: {self.rate_limit_count})")
                    raise

    async def _call_gemini_api(
        self,
        prompt: str,
        model_name: str,
        response_mime_type: Optional[str] = None
    ) -> str:
        """Internal method to call Gemini API."""
        # This is a synchronous call wrapped in asyncio
        # Gemini SDK doesn't support async yet, so we run in executor
        loop = asyncio.get_event_loop()

        def _sync_call():
            try:
                config_kwargs = {"temperature": 0.1, "top_p": 0.95}
                if response_mime_type:
                    config_kwargs["response_mime_type"] = response_mime_type

                config = GenerationConfig(**config_kwargs)
                model = GenerativeModel(model_name)
                response = model.generate_content(prompt, generation_config=config)

                if hasattr(response, 'text') and response.text:
                    return response.text.strip()

                if hasattr(response, 'candidates') and response.candidates:
                    text = ""
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "text") and part.text:
                            text += part.text
                    if text:
                        return text.strip()

                return ""
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                raise

        return await loop.run_in_executor(None, _sync_call)

    def reset_rate_limit_count(self):
        """Reset rate limit counter (call at start of new scraping session)."""
        self.rate_limit_count = 0
        self.current_model = GEMINI_MAIN_MODEL
        logger.info(f"Gemini rate limit counter reset - using {GEMINI_MAIN_MODEL}")


# Global Gemini API instance
gemini_api = GeminiAPI()


# ============================================================================
# GOOGLE CUSTOM SEARCH - ASYNC VERSION
# ============================================================================

async def async_google_custom_search(
    session: aiohttp.ClientSession,
    query: str,
    search_engine_id: str,
    num_results: int = 5
) -> List[Dict[str, str]]:
    """
    Execute Google Custom Search API call with rate limiting and retry logic.

    Args:
        session: aiohttp ClientSession
        query: Search query
        search_engine_id: Google Custom Search Engine ID
        num_results: Number of results to return

    Returns:
        List of search results with url, title, snippet, domain
    """
    params = {
        "key": GOOGLE_API_KEY,
        "cx": search_engine_id,
        "q": query,
        "num": min(num_results, 10),
    }

    # Apply rate limiting
    async with custom_search_limiter.acquire():
        # Apply retry logic with exponential backoff
        async for attempt in async_retry(
            max_attempts=rate_limit_config.max_retries,
            min_wait=rate_limit_config.base_delay,
            max_wait=rate_limit_config.max_delay,
            exceptions=(aiohttp.ClientError, asyncio.TimeoutError)
        ):
            with attempt:
                try:
                    # Use circuit breaker
                    return await custom_search_circuit_breaker.call(
                        _execute_search,
                        session,
                        params
                    )
                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in error_str or "rate limit" in error_str:
                        logger.warning(f"Rate limit hit for query: {query[:50]}...")
                        # Add extra delay for rate limits
                        await asyncio.sleep(random.uniform(2, 5))
                    raise


async def _execute_search(
    session: aiohttp.ClientSession,
    params: Dict[str, Any]
) -> List[Dict[str, str]]:
    """Execute the actual search request."""
    async with session.get(CUSTOM_SEARCH_URL, params=params) as response:
        if response.status == 200:
            data = await response.json()
            return [
                {
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "domain": item.get("displayLink", ""),
                }
                for item in data.get("items", [])
            ]
        elif response.status == 429:
            raise Exception(f"Rate limit exceeded (429)")
        else:
            logger.warning(f"Search API returned status {response.status}")
            return []


# ============================================================================
# SPEC EXTRACTION - ASYNC VERSION
# ============================================================================

async def async_extract_spec_from_snippets(
    car_name: str,
    spec_name: str,
    search_results: List[Dict[str, str]]
) -> Dict[str, str]:
    """
    Extract spec value from search result snippets using Gemini.

    Args:
        car_name: Name of the car
        spec_name: Specification name
        search_results: List of search results

    Returns:
        Dict with 'value' and 'source_url'
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
- If not found, return: {{"value": "Not found", "source_url": "N/A"}}

Return ONLY the JSON object."""

    try:
        response_text = await gemini_api.generate_content(
            prompt,
            use_flash=True,
            response_mime_type="application/json"
        )

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
        return {
            "value": data.get("value", "Not found"),
            "source_url": data.get("source_url", "N/A")
        }

    except Exception as e:
        logger.error(f"Error extracting spec {spec_name}: {e}")
        return {"value": "Not found", "source_url": "N/A"}


# ============================================================================
# PHASE 1: PER-SPEC SEARCH - ASYNC VERSION
# ============================================================================

async def async_phase1_per_spec_search(
    car_name: str,
    existing_specs: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Phase 1: For each remaining spec, do one search query and extract from snippets.
    Fully async with proper rate limiting and concurrent execution.

    Args:
        car_name: Name of the car
        existing_specs: Specs already found in Phase 0

    Returns:
        Dict with 'specs' and 'citations'
    """
    logger.info("="*60)
    logger.info("PHASE 1: ASYNC PER-SPEC SEARCH + SNIPPET EXTRACTION")
    logger.info("="*60)

    existing_specs = existing_specs or {}
    specs = {}
    citations = {}

    # Find specs not yet found
    remaining_specs = [
        s for s in CAR_SPECS
        if s not in existing_specs or existing_specs.get(s) in ["Not found", "Not Available", ""]
    ]

    logger.info(f"Searching {len(remaining_specs)} remaining specs async...")

    async with AsyncHTTPClient(
        max_connections=rate_limit_config.max_connections,
        max_connections_per_host=rate_limit_config.max_connections_per_host,
        timeout=rate_limit_config.connection_timeout
    ) as http_client:

        async def search_and_extract_spec(spec_name: str) -> Tuple[str, str, str]:
            """Search and extract a single spec."""
            keyword = SPEC_KEYWORDS.get(spec_name, spec_name.replace("_", " "))
            # Use enhanced query with "latest" for most current results
            query = build_enhanced_query(car_name, keyword, enhance=True)

            try:
                # Search with rate limiting
                search_results = await async_google_custom_search(
                    http_client.session,
                    query,
                    SEARCH_ENGINE_ID,
                    num_results=5
                )

                # Extract from snippets
                result = await async_extract_spec_from_snippets(
                    car_name,
                    spec_name,
                    search_results
                )

                return spec_name, result["value"], result["source_url"]

            except Exception as e:
                logger.error(f"Error processing {spec_name}: {e}")
                return spec_name, "Not found", "N/A"

        # Execute all searches concurrently with rate limiting
        tasks = [search_and_extract_spec(spec) for spec in remaining_specs]

        # Gather results with progress tracking
        results = []
        completed = 0
        found = 0

        for coro in asyncio.as_completed(tasks):
            try:
                spec_name, value, source_url = await coro
                results.append((spec_name, value, source_url))

                specs[spec_name] = value
                citations[spec_name] = {
                    "source_url": source_url,
                    "citation_text": "From search results",
                    "engine": "SEARCH_ASYNC",
                }

                if value and "Not found" not in value:
                    found += 1

                completed += 1
                if completed % 20 == 0:
                    logger.info(f"Progress: {completed}/{len(remaining_specs)} ({found} found)")

            except Exception as e:
                logger.error(f"Task failed: {e}")

    accuracy = (found / len(remaining_specs) * 100) if remaining_specs else 0
    logger.info(f"Phase 1 Complete: {found}/{len(remaining_specs)} specs ({accuracy:.1f}%)")

    # Print rate limiter stats
    search_stats = custom_search_limiter.get_stats()
    gemini_stats = gemini_flash_limiter.get_stats()
    logger.info(f"Custom Search: {search_stats['total_calls']} calls, "
                f"{search_stats['calls_per_second']:.2f} req/s")
    logger.info(f"Gemini Flash: {gemini_stats['total_calls']} calls, "
                f"{gemini_stats['calls_per_second']:.2f} req/s")

    return {"specs": specs, "citations": citations}


# ============================================================================
# CALL_CUSTOM_SEARCH_PARALLEL - ASYNC VERSION
# ============================================================================

async def async_call_custom_search_parallel(
    queries: Dict[str, str],
    num_results: int = 5,
    max_concurrent: int = 10,
    use_company_search: bool = False
) -> Dict[str, List[Dict[str, str]]]:
    """
    Execute multiple Custom Search queries in parallel with rate limiting.

    Args:
        queries: Dict mapping query names to query strings
        num_results: Number of results per query
        max_concurrent: Maximum concurrent requests (overrides default limiter)
        use_company_search: Use COMPANY_SEARCH_ID instead of SEARCH_ENGINE_ID

    Returns:
        Dict mapping query names to list of search results
    """
    search_engine_id = COMPANY_SEARCH_ID if use_company_search else SEARCH_ENGINE_ID
    results = {}

    async with AsyncHTTPClient() as http_client:

        async def execute_query(query_name: str, query_string: str):
            try:
                search_results = await async_google_custom_search(
                    http_client.session,
                    query_string,
                    search_engine_id,
                    num_results
                )
                return query_name, search_results
            except Exception as e:
                logger.error(f"Query '{query_name}' failed: {e}")
                return query_name, []

        # Execute all queries concurrently
        tasks = [execute_query(name, query) for name, query in queries.items()]
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for result in completed_results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
            else:
                query_name, search_results = result
                results[query_name] = search_results

    return results


# ============================================================================
# EXTRACT_SPEC_FROM_SEARCH_RESULTS - ASYNC VERSION
# ============================================================================

async def async_extract_spec_from_search_results(
    car_name: str,
    spec_name: str,
    search_results: List[Dict[str, str]]
) -> Dict[str, str]:
    """
    Extract a specific spec value from search results using Gemini.

    Returns:
        Dict with 'value', 'source_url', 'citation'
    """
    result = await async_extract_spec_from_snippets(car_name, spec_name, search_results)

    return {
        "value": result["value"],
        "source_url": result["source_url"],
        "citation": f"Extracted from {result['source_url']}" if result['source_url'] != "N/A" else "Not found"
    }


logger.info("Async scraper module initialized")
