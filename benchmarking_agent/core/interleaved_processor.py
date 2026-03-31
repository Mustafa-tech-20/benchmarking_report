"""
Interleaved Car Processor

Implements API-type interleaved parallel processing for multiple cars.
When one car is blocked on Gemini API, another car processes Custom Search
queries (and vice versa), maximizing throughput without exceeding rate limits.
"""
import asyncio
import logging
import time
import random
import json
import json_repair
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google import genai
from google.genai import types

from benchmarking_agent.config import GOOGLE_API_KEY, SEARCH_ENGINE_ID, CUSTOM_SEARCH_URL, GEMINI_MAIN_MODEL
from benchmarking_agent.async_config import rate_limit_config, interleaved_config
from benchmarking_agent.core.resource_scheduler import (
    ResourceScheduler, ResourceType, CarTask, get_scheduler, reset_scheduler
)
from benchmarking_agent.core.scraper_metrics import (
    ScraperMetrics, CarMetrics, get_metrics, reset_metrics
)
from benchmarking_agent.core.scraper import (
    CAR_SPECS, SPEC_KEYWORDS, SPEC_DESCRIPTIONS, CURRENT_YEAR,
    OFFICIAL_SITE_PRIORITY_SPECS, TRUSTED_CITATION_DOMAINS,
    build_enhanced_query, build_official_brand_url, build_cardekho_url,
    normalize_citation_url, _TRUSTED_DOMAINS_PROMPT_LIST,
    EXTRACTION_CONFIG,
)

logger = logging.getLogger(__name__)

# Initialize Gemini client for async operations
import os
_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
_gemini_search_client = genai.Client(vertexai=True, project=_PROJECT_ID, location="global")

# Shared thread pool executors - sized for typical 2-6 car comparisons
_http_executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="http_worker")
_gemini_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="gemini_worker")


# ============================================================================
# CAR RESULT ACCUMULATOR
# ============================================================================

@dataclass
class CarResult:
    """Accumulates results for a single car."""
    car_id: str
    car_name: str
    specs: Dict[str, str] = field(default_factory=dict)
    citations: Dict[str, Dict[str, str]] = field(default_factory=dict)
    images: Dict[str, List[str]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def add_specs(self, new_specs: Dict[str, str], source: str, source_url: str) -> int:
        """Add specs to result, returns count of new specs added."""
        async with self._lock:
            added = 0
            for spec_name, value in new_specs.items():
                # Only add if not already found
                if (spec_name not in self.specs or
                    self.specs.get(spec_name) in ["Not found", "Not Available", ""]):
                    if value and value not in ["Not found", "Not Available", ""]:
                        self.specs[spec_name] = value
                        self.citations[spec_name] = {
                            "source_url": source_url,
                            "citation_text": source,
                            "engine": source,
                        }
                        added += 1
            return added

    def get_missing_specs(self) -> List[str]:
        """Get list of specs not yet found."""
        return [
            s for s in CAR_SPECS
            if s not in self.specs or self.specs.get(s) in ["Not found", "Not Available", ""]
        ]

    def get_found_count(self) -> int:
        """Get count of found specs."""
        return sum(
            1 for s in CAR_SPECS
            if s in self.specs and self.specs[s] not in ["Not found", "Not Available", ""]
        )

    def to_car_data(self) -> Dict[str, Any]:
        """Convert to final car_data format."""
        car_data = {
            "car_name": self.car_name,
            "method": "Interleaved Parallel Processing",
            "source_urls": [],
            "images": self.images,
        }

        # Collect source URLs
        source_urls = set()
        for citation in self.citations.values():
            url = citation.get("source_url", "")
            if url and url != "N/A":
                source_urls.add(url)
        car_data["source_urls"] = list(source_urls)

        # Add all specs
        for spec_name in CAR_SPECS:
            value = self.specs.get(spec_name, "Not Available")
            if not value or value in ["Not found", ""]:
                value = "Not Available"
            car_data[spec_name] = value
            car_data[f"{spec_name}_citation"] = self.citations.get(
                spec_name,
                {"source_url": "N/A", "citation_text": ""}
            )

        return car_data


# ============================================================================
# ASYNC API WRAPPERS
# ============================================================================

async def async_google_search(query: str, search_engine_id: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Async wrapper for Google Custom Search API using dedicated thread pool."""
    loop = asyncio.get_event_loop()

    def _search():
        time.sleep(random.uniform(0.02, 0.08))  # Reduced delay for faster throughput
        params = {
            "key": GOOGLE_API_KEY,
            "cx": search_engine_id,
            "q": query,
            "num": min(num_results, 10),
        }
        try:
            response = requests.get(CUSTOM_SEARCH_URL, params=params, timeout=15)
            if response.status_code == 200:
                return [{
                    "url": item.get("link", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "domain": item.get("displayLink", ""),
                } for item in response.json().get("items", [])]
            if response.status_code == 429:
                logger.warning(f"Rate limit hit for search: {query[:50]}")
                time.sleep(1)  # Brief backoff
                return []
            return []
        except requests.exceptions.Timeout:
            logger.warning(f"Search timeout: {query[:50]}")
            return []
        except Exception as e:
            logger.warning(f"Search error: {e}")
            return []

    return await loop.run_in_executor(_http_executor, _search)


async def async_gemini_call(prompt: str, timeout: int = 45) -> str:
    """Async wrapper for Gemini API call using dedicated thread pool."""
    loop = asyncio.get_event_loop()

    def _call():
        try:
            model = GenerativeModel(GEMINI_MAIN_MODEL)
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
                return text.strip()
            return ""
        except Exception as e:
            logger.warning(f"Gemini call error: {e}")
            return ""

    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_gemini_executor, _call),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning("Gemini call timeout")
        return ""
    except Exception as e:
        logger.warning(f"Gemini call failed: {e}")
        return ""


# ============================================================================
# TASK EXECUTORS
# ============================================================================

async def execute_search_task(task: CarTask) -> Dict[str, List[Dict]]:
    """
    Execute a search task - searches for multiple specs.

    Returns: {spec_name: [search_results]}
    """
    results = {}

    for spec_name in task.spec_batch:
        keyword = SPEC_KEYWORDS.get(spec_name, spec_name.replace("_", " "))
        query = build_enhanced_query(task.car_name, keyword, enhance=True)

        try:
            search_results = await async_google_search(query, SEARCH_ENGINE_ID, num_results=5)
            results[spec_name] = search_results
        except Exception as e:
            logger.debug(f"Search failed for {spec_name}: {e}")
            results[spec_name] = []

    return results


async def execute_extraction_task(
    task: CarTask,
    search_results_map: Dict[str, List[Dict]]
) -> Dict[str, Dict[str, str]]:
    """
    Execute a Gemini extraction task - extracts specs from search snippets.

    Returns: {spec_name: {"value": ..., "source_url": ...}}
    """
    # Build sections for each spec
    sections = []
    for spec_name in task.spec_batch:
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
        for s in task.spec_batch
    ]

    prompt = f"""Extract {len(task.spec_batch)} specifications for the LATEST MODEL of {task.car_name}.
Each specification has its own clearly labelled search results section.

{"".join(sections)}
Return ONLY this JSON (no markdown):
{{
{chr(10).join(json_lines)}
}}

CRITICAL RULES:
- Use ONLY the search results from each spec's OWN section - never mix between specs
- Include units: bhp, Nm, kmpl, mm, litres, kg, sec, etc.
- source_url must be a real URL from THAT spec's own results, from: {_TRUSTED_DOMAINS_PROMPT_LIST}
- NEVER return Google, Bing, Vertex AI, or redirect URLs
- Prefer {CURRENT_YEAR} or most recent model data
- If not clearly found in a spec's own results: return "Not found" and source_url "N/A" """

    try:
        text = await async_gemini_call(prompt)
        if not text:
            return {s: {"value": "Not found", "source_url": "N/A"} for s in task.spec_batch}

        # Parse JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()
        if "{" in text and "}" in text:
            text = text[text.index("{"):text.rindex("}") + 1]

        data = json_repair.loads(text)
        if not isinstance(data, dict):
            return {s: {"value": "Not found", "source_url": "N/A"} for s in task.spec_batch}

        result = {}
        for spec_name in task.spec_batch:
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

    except Exception as e:
        logger.debug(f"Extraction failed: {e}")
        return {s: {"value": "Not found", "source_url": "N/A"} for s in task.spec_batch}


async def execute_official_site_task(task: CarTask) -> Dict[str, str]:
    """
    Execute official site extraction task.

    Returns: {spec_name: value}
    """
    url = task.context.get("url", "")
    if not url:
        return {}

    spec_guide_lines = []
    for spec in task.spec_batch:
        desc = SPEC_DESCRIPTIONS.get(spec, spec.replace("_", " ").title())
        spec_guide_lines.append(f'- "{spec}": {desc}')
    spec_guide = "\n".join(spec_guide_lines)

    prompt = f"""You are an automotive specifications expert. Extract EXACT car specifications for {task.car_name} from the official brand website.

Official website URL: {url}

Extract these {len(task.spec_batch)} specifications:
{spec_guide}

RULES:
- EXACT values with units always: e.g., "210 mm", "12.5-18.9 Lakh", "1497 cc", "6 airbags", "10.25 inch"
- Include measurement units: bhp, Nm, mm, litres, kg, kmpl, rpm, seconds
- Binary features: "Yes", "No", or the specific variant where available
- Use your knowledge of this car model from the official website
- Return "Not found" only if the spec is genuinely unavailable

Return ONLY a JSON object (no markdown):
{{
    "price_range": "12.5-18.9 Lakh",
    "acceleration": "9.2 seconds (0-100 kmph)",
    "airbags": "6 airbags",
    "tyre_size": "215/60 R17",
    "sunroof": "Yes - Electric Panoramic Sunroof",
    "audio_system": "Sony 8-speaker system"
}}

Return ONLY the JSON, no markdown."""

    try:
        text = await async_gemini_call(prompt)
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
        logger.debug(f"Official site extraction failed: {e}")
        return {}


async def execute_cardekho_fallback_task(task: CarTask) -> Dict[str, Dict[str, str]]:
    """
    Execute CarDekho fallback extraction task.

    Returns: {spec_name: {"value": ..., "source_url": ...}}
    """
    cardekho_url = task.context.get("url", build_cardekho_url(task.car_name))

    spec_guide_lines = []
    json_lines = []
    for spec in task.spec_batch:
        desc = SPEC_DESCRIPTIONS.get(spec, spec.replace("_", " ").title())
        spec_guide_lines.append(f"- **{spec}**: {desc}")
        json_lines.append(f'  "{spec}": {{"value": "...", "source_url": "{cardekho_url}"}}')

    prompt = f"""Visit the following CarDekho page and extract the listed specifications for {task.car_name}.

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
        text = await async_gemini_call(prompt)
        if not text:
            return {s: {"value": "Not found", "source_url": "N/A"} for s in task.spec_batch}

        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        text = text.strip()
        if "{" in text and "}" in text:
            text = text[text.index("{"):text.rindex("}") + 1]

        data = json_repair.loads(text)
        result = {}
        for spec_name in task.spec_batch:
            spec_data = data.get(spec_name, {})
            if isinstance(spec_data, dict):
                value = spec_data.get("value", "Not found")
                source_url = spec_data.get("source_url", cardekho_url)
            else:
                value = str(spec_data) if spec_data else "Not found"
                source_url = cardekho_url
            result[spec_name] = {"value": value, "source_url": source_url}
        return result

    except Exception as e:
        logger.debug(f"CarDekho fallback failed: {e}")
        return {s: {"value": "Not found", "source_url": "N/A"} for s in task.spec_batch}


# ============================================================================
# INTERLEAVED CAR PROCESSOR
# ============================================================================

class InterleavedCarProcessor:
    """
    Main orchestrator for interleaved parallel car processing.

    Processes multiple cars by interleaving different API types:
    - When Gemini is rate-limited, process Custom Search tasks
    - When Custom Search is rate-limited, process Gemini tasks
    - Maintains per-car result accumulators
    """

    def __init__(self):
        self.scheduler = reset_scheduler()
        self.metrics = reset_metrics()
        self.results: Dict[str, CarResult] = {}
        self._search_results_cache: Dict[str, Dict[str, List[Dict]]] = {}
        self._workers_started = False
        self._shutdown = False

    def _create_car_id(self, car: Dict) -> str:
        """Create a unique car ID."""
        brand = car.get("brand", "").lower().replace(" ", "_")
        model = car.get("model", "").lower().replace(" ", "_")
        return f"{brand}_{model}"

    def _create_car_name(self, car: Dict) -> str:
        """Create display name for car."""
        brand = car.get("brand", "")
        model = car.get("model", "")
        return f"{brand} {model}".strip()

    async def generate_tasks_for_car(
        self,
        car: Dict,
        phase: int,
        existing_specs: Dict[str, str] = None
    ) -> List[CarTask]:
        """
        Generate tasks for a car based on phase.

        Phase 0: Official site extraction
        Phase 1: Per-spec search + extraction
        Phase 2: CarDekho fallback
        """
        car_id = self._create_car_id(car)
        car_name = self._create_car_name(car)
        existing_specs = existing_specs or {}
        tasks = []

        batch_size = interleaved_config.spec_batch_size

        if phase == 0:
            # Phase 0: Official site extraction
            url, brand = build_official_brand_url(car_name)
            if url:
                spec_batches = [
                    OFFICIAL_SITE_PRIORITY_SPECS[i:i + batch_size]
                    for i in range(0, len(OFFICIAL_SITE_PRIORITY_SPECS), batch_size)
                ]
                for batch in spec_batches:
                    tasks.append(CarTask(
                        car_id=car_id,
                        car_name=car_name,
                        phase=0,
                        spec_batch=batch,
                        resource_type=ResourceType.GEMINI_FLASH,
                        priority=0,  # Highest priority
                        task_type="official_extract",
                        context={"url": url, "brand": brand},
                    ))

        elif phase == 1:
            # Phase 1: Search + extraction for remaining specs
            remaining_specs = [
                s for s in CAR_SPECS
                if s not in existing_specs or existing_specs.get(s) in ["Not found", "Not Available", ""]
            ]

            # Create search tasks (one per spec for accuracy)
            for spec_name in remaining_specs:
                tasks.append(CarTask(
                    car_id=car_id,
                    car_name=car_name,
                    phase=1,
                    spec_batch=[spec_name],
                    resource_type=ResourceType.CUSTOM_SEARCH,
                    priority=10,
                    task_type="search",
                ))

        elif phase == 2:
            # Phase 2: CarDekho fallback for still-missing specs
            missing_specs = [
                s for s in CAR_SPECS
                if s not in existing_specs or existing_specs.get(s) in ["Not found", "Not Available", ""]
            ]

            if missing_specs:
                cardekho_url = build_cardekho_url(car_name)
                spec_batches = [
                    missing_specs[i:i + batch_size]
                    for i in range(0, len(missing_specs), batch_size)
                ]
                for batch in spec_batches:
                    tasks.append(CarTask(
                        car_id=car_id,
                        car_name=car_name,
                        phase=2,
                        spec_batch=batch,
                        resource_type=ResourceType.GEMINI_FLASH,
                        priority=20,
                        task_type="cardekho_extract",
                        context={"url": cardekho_url},
                    ))

        return tasks

    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes tasks from the scheduler."""
        task_count = 0
        idle_count = 0

        while not self._shutdown:
            try:
                task = await self.scheduler.schedule_next_task()
                if task is None:
                    idle_count += 1
                    # Wait longer before checking - don't exit, just wait for more tasks
                    await asyncio.sleep(0.2)
                    # Only exit if we've been idle for a long time AND shutdown is set
                    if idle_count > 50 and self._shutdown:
                        break
                    continue

                idle_count = 0  # Reset idle counter when we get a task

                # Execute task based on type
                success = False
                try:
                    if task.task_type == "search":
                        results = await execute_search_task(task)
                        # Cache search results for extraction phase
                        if task.car_id not in self._search_results_cache:
                            self._search_results_cache[task.car_id] = {}
                        self._search_results_cache[task.car_id].update(results)
                        success = True
                        self.metrics.record_task_complete(task.resource_type, True)
                        task_count += 1
                        # Print progress every 10 search tasks
                        if task_count % 10 == 0:
                            pending = self.scheduler.get_total_pending()
                            print(f"    Searches: {task_count} done, {pending} pending...")

                    elif task.task_type == "extract":
                        cached_results = self._search_results_cache.get(task.car_id, {})
                        results = await execute_extraction_task(task, cached_results)
                        # Add to car result with actual source URLs
                        if task.car_id in self.results:
                            total_added = 0
                            for spec_name, spec_data in results.items():
                                value = spec_data.get("value", "Not found")
                                url = spec_data.get("source_url", "N/A")
                                # Fallback to zigwheels URL if no valid URL
                                if not url or url in ["N/A", "search_results", ""]:
                                    # Generate zigwheels URL from car name
                                    car_parts = task.car_name.lower().split()
                                    if len(car_parts) >= 2:
                                        brand = car_parts[0]
                                        model = "-".join(car_parts[1:])
                                        url = f"https://www.zigwheels.com/{brand}-cars/{model}"
                                    else:
                                        url = f"https://www.zigwheels.com/cars/{task.car_name.lower().replace(' ', '-')}"
                                added = await self.results[task.car_id].add_specs(
                                    {spec_name: value}, "SEARCH", url
                                )
                                total_added += added
                            if total_added > 0:
                                print(f"    {task.car_name}: +{total_added} specs extracted")
                        success = True
                        self.metrics.record_task_complete(task.resource_type, True)

                    elif task.task_type == "official_extract":
                        results = await execute_official_site_task(task)
                        if task.car_id in self.results:
                            url = task.context.get("url", "N/A")
                            added = await self.results[task.car_id].add_specs(
                                results, "OFFICIAL", url
                            )
                            if added > 0:
                                print(f"    {task.car_name}: +{added} specs from official site")
                        success = True
                        self.metrics.record_task_complete(task.resource_type, True)

                    elif task.task_type == "cardekho_extract":
                        results = await execute_cardekho_fallback_task(task)
                        if task.car_id in self.results:
                            specs = {k: v["value"] for k, v in results.items()}
                            url = task.context.get("url", "N/A")
                            added = await self.results[task.car_id].add_specs(
                                specs, "CARDEKHO", url
                            )
                            if added > 0:
                                print(f"    {task.car_name}: +{added} specs from CarDekho")
                        success = True
                        self.metrics.record_task_complete(task.resource_type, True)

                except Exception as e:
                    print(f"    Task failed ({task.task_type}): {str(e)[:50]}")
                    self.metrics.record_task_complete(task.resource_type, False)

                await self.scheduler.mark_task_complete(task, success)

            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(0.5)

    async def _wait_for_completion(self, cars: List[Dict], phase_name: str, timeout: float = 120) -> None:
        """Wait for all pending tasks to complete with progress output."""
        start = time.monotonic()
        last_total = -1

        while True:
            total_pending = sum(
                self.scheduler.get_pending_count(self._create_car_id(car))
                for car in cars
            )

            if total_pending == 0:
                break

            if total_pending != last_total:
                print(f"    {phase_name}: {total_pending} tasks remaining...")
                last_total = total_pending

            if time.monotonic() - start > timeout:
                print(f"    {phase_name}: Timeout after {timeout:.0f}s, {total_pending} tasks remaining")
                break

            await asyncio.sleep(2.0)

    async def _wait_for_searches(self, cars: List[Dict], timeout: float = 180) -> None:
        """Wait for search tasks to complete with progress output."""
        start = time.monotonic()
        last_done = 0

        while True:
            total_cached = sum(
                len(self._search_results_cache.get(self._create_car_id(car), {}))
                for car in cars
            )
            total_pending = sum(
                self.scheduler.get_pending_count(self._create_car_id(car))
                for car in cars
            )

            # Only count search tasks as pending
            search_pending = total_pending  # Approximation

            if search_pending == 0 or total_cached >= last_done + 20:
                if total_cached > last_done:
                    print(f"    Searches: {total_cached} done, {search_pending} pending...")
                    last_done = total_cached

            if search_pending == 0:
                print(f"    Searches complete: {total_cached} results cached")
                break

            if time.monotonic() - start > timeout:
                print(f"    Search timeout after {timeout:.0f}s, got {total_cached} results")
                break

            await asyncio.sleep(1.0)

    async def _run_phase_for_car(
        self,
        car: Dict,
        phase: int,
        car_result: CarResult
    ) -> int:
        """
        Run a single phase for a single car.

        Returns count of specs found in this phase.
        """
        car_id = self._create_car_id(car)
        car_name = self._create_car_name(car)

        # Generate tasks
        tasks = await self.generate_tasks_for_car(
            car, phase, existing_specs=car_result.specs
        )

        if not tasks:
            return 0

        # Submit all tasks
        submitted = await self.scheduler.submit_tasks(tasks)
        logger.info(f"  {car_name} Phase {phase}: {submitted} tasks submitted")

        # For phase 1, also generate extraction tasks after searches complete
        if phase == 1:
            # Wait for search tasks to complete (with timeout and progress)
            search_tasks = [t for t in tasks if t.task_type == "search"]
            total_searches = len(search_tasks)
            wait_start = time.monotonic()
            last_progress = 0

            while self.scheduler.get_pending_count(car_id) > 0:
                await asyncio.sleep(1.0)  # Check every second
                cached = self._search_results_cache.get(car_id, {})
                done = len(cached)

                # Print progress every 20 searches
                if done >= last_progress + 20:
                    print(f"    {car_name}: {done}/{total_searches} searches done...")
                    last_progress = done

                # Move on if 80% done or timeout after 120s
                if done >= total_searches * 0.8:
                    print(f"    {car_name}: {done}/{total_searches} searches - moving to extraction")
                    break
                if time.monotonic() - wait_start > 120:
                    print(f"    {car_name}: Search timeout, got {done}/{total_searches} - moving to extraction")
                    break

            # Generate extraction tasks in batches
            cached = self._search_results_cache.get(car_id, {})
            spec_names = list(cached.keys())
            batch_size = interleaved_config.spec_batch_size

            extraction_tasks = []
            for i in range(0, len(spec_names), batch_size):
                batch = spec_names[i:i + batch_size]
                extraction_tasks.append(CarTask(
                    car_id=car_id,
                    car_name=car_name,
                    phase=1,
                    spec_batch=batch,
                    resource_type=ResourceType.GEMINI_FLASH,
                    priority=15,
                    task_type="extract",
                ))

            if extraction_tasks:
                await self.scheduler.submit_tasks(extraction_tasks)
                print(f"    {car_name}: {len(extraction_tasks)} extraction batches queued")

        # Wait for all tasks to complete
        timeout = interleaved_config.phase_timeout
        start = time.monotonic()
        last_pending = -1
        while self.scheduler.get_pending_count(car_id) > 0:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                print(f"    {car_name}: Phase {phase} timeout after {timeout:.0f}s")
                break

            pending = self.scheduler.get_pending_count(car_id)
            if pending != last_pending:
                print(f"    {car_name}: {pending} tasks remaining...")
                last_pending = pending
            await asyncio.sleep(2.0)

        # Return count of new specs found
        found = car_result.get_found_count()
        print(f"    {car_name}: Phase {phase} done - {found} specs total")
        return found

    async def _run_car_pipeline(self, car: Dict, car_index: int) -> None:
        """
        Run the full pipeline for a single car independently.
        This enables TRUE parallelism - each car runs at its own pace.

        Pipeline: Official Site -> Search + Extract -> CarDekho Fallback
        """
        car_id = self._create_car_id(car)
        car_name = self._create_car_name(car)
        car_result = self.results[car_id]

        # Add a small stagger to avoid all cars hitting the same API simultaneously
        if car_index > 0:
            await asyncio.sleep(car_index * 0.5)  # Stagger by 0.5s per car

        print(f"  [{car_name}] Starting pipeline...")

        # === PHASE 0: Official Site ===
        phase0_tasks = await self.generate_tasks_for_car(car, phase=0)
        if phase0_tasks:
            await self.scheduler.submit_tasks(phase0_tasks)
            print(f"  [{car_name}] Phase 0: {len(phase0_tasks)} official site tasks submitted")

            # Wait for phase 0 with timeout
            start = time.monotonic()
            while self.scheduler.get_pending_count(car_id) > 0:
                if time.monotonic() - start > 60:
                    print(f"  [{car_name}] Phase 0 timeout")
                    break
                await asyncio.sleep(0.5)

            found = car_result.get_found_count()
            print(f"  [{car_name}] Phase 0 complete: {found} specs from official site")

        # === PHASE 1: Search + Extract ===
        # Generate search tasks
        search_tasks = await self.generate_tasks_for_car(car, phase=1, existing_specs=car_result.specs)
        if search_tasks:
            await self.scheduler.submit_tasks(search_tasks)
            total_searches = len(search_tasks)
            print(f"  [{car_name}] Phase 1: {total_searches} search tasks submitted")

            # Wait for searches (but not too long - process what we get)
            start = time.monotonic()
            last_cached = 0
            while self.scheduler.get_pending_count(car_id) > 0:
                cached_count = len(self._search_results_cache.get(car_id, {}))

                # Progress update every 20 searches
                if cached_count >= last_cached + 20:
                    print(f"  [{car_name}] Searches: {cached_count}/{total_searches}")
                    last_cached = cached_count

                # Move on when 80% done or after 90s
                if cached_count >= total_searches * 0.8:
                    break
                if time.monotonic() - start > 90:
                    print(f"  [{car_name}] Search phase timeout, got {cached_count}/{total_searches}")
                    break

                await asyncio.sleep(0.5)

            # Generate extraction tasks from cached search results
            cached = self._search_results_cache.get(car_id, {})
            spec_names = list(cached.keys())
            if spec_names:
                batch_size = interleaved_config.spec_batch_size
                extraction_tasks = []
                for i in range(0, len(spec_names), batch_size):
                    batch = spec_names[i:i + batch_size]
                    extraction_tasks.append(CarTask(
                        car_id=car_id,
                        car_name=car_name,
                        phase=1,
                        spec_batch=batch,
                        resource_type=ResourceType.GEMINI_FLASH,
                        priority=15,
                        task_type="extract",
                    ))

                await self.scheduler.submit_tasks(extraction_tasks)
                print(f"  [{car_name}] Extraction: {len(extraction_tasks)} batches submitted")

                # Wait for extraction
                start = time.monotonic()
                while self.scheduler.get_pending_count(car_id) > 0:
                    if time.monotonic() - start > 120:
                        break
                    await asyncio.sleep(0.5)

        found_after_phase1 = car_result.get_found_count()
        print(f"  [{car_name}] Phase 1 complete: {found_after_phase1} specs total")

        # === PHASE 2: CarDekho Fallback ===
        fallback_tasks = await self.generate_tasks_for_car(car, phase=2, existing_specs=car_result.specs)
        if fallback_tasks:
            await self.scheduler.submit_tasks(fallback_tasks)
            print(f"  [{car_name}] Phase 2: {len(fallback_tasks)} fallback tasks submitted")

            start = time.monotonic()
            while self.scheduler.get_pending_count(car_id) > 0:
                if time.monotonic() - start > 90:
                    break
                await asyncio.sleep(0.5)

        final_count = car_result.get_found_count()
        print(f"  [{car_name}] Pipeline complete: {final_count}/{len(CAR_SPECS)} specs")

    async def process_cars_interleaved(self, cars: List[Dict]) -> Dict[str, Any]:
        """
        Main entry point - processes multiple cars with TRUE PARALLEL PIPELINES.

        Each car runs its own complete pipeline (Official -> Search -> Extract -> Fallback)
        independently. This enables:
        - Car A doing official extraction while Car B does search
        - Car A doing extraction while Car B does official site
        - Maximum parallelism with different API types
        """
        start_time = time.monotonic()

        print(f"\n{'#' * 60}")
        print(f"TRUE PARALLEL PIPELINE PROCESSING: {len(cars)} cars")
        print(f"{'#' * 60}\n")

        # Initialize results for each car
        for car in cars:
            car_id = self._create_car_id(car)
            car_name = self._create_car_name(car)
            self.results[car_id] = CarResult(car_id=car_id, car_name=car_name)
            self.metrics.start_car(car_id, car_name)
            self._search_results_cache[car_id] = {}

        # Start workers - scale with number of cars
        worker_count = max(interleaved_config.worker_count, len(cars) * 10)
        workers = [asyncio.create_task(self._worker(i)) for i in range(worker_count)]
        self._workers_started = True
        print(f"Started {worker_count} workers for parallel processing\n")

        # Run all car pipelines in parallel - TRUE INTERLEAVING
        print(f"{'=' * 60}")
        print(f"PARALLEL PIPELINES: All cars processing simultaneously")
        print(f"{'=' * 60}\n")

        car_pipelines = [
            self._run_car_pipeline(car, i)
            for i, car in enumerate(cars)
        ]
        await asyncio.gather(*car_pipelines, return_exceptions=True)

        # Shutdown workers
        self._shutdown = True
        await asyncio.sleep(0.5)  # Give workers time to notice shutdown
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        # Phase 3: Skip image extraction here - will be done after variant walk step
        # This avoids CSE rate limits by spacing out CSE-heavy operations
        print(f"\n{'=' * 60}")
        print(f"IMAGE EXTRACTION: Deferred to after variant walk (rate limit protection)")
        print(f"{'=' * 60}\n")

        # Initialize empty image placeholders - images will be extracted later in the pipeline
        for car in cars:
            car_id = self._create_car_id(car)
            self.results[car_id].images = {
                "hero": [], "exterior": [], "interior": [],
                "technology": [], "comfort": [], "safety": []
            }

        # Complete metrics
        for car in cars:
            car_id = self._create_car_id(car)
            car_result = self.results[car_id]
            self.metrics.end_car(car_id)
            self.metrics.car_metrics[car_id].total_specs_found = car_result.get_found_count()

        self.metrics.complete()

        total_time = time.monotonic() - start_time

        # Print final summary
        print(f"\n{'=' * 60}")
        print(f"COMPLETE: {len(cars)} cars in {total_time:.1f}s")
        print(f"{'=' * 60}")

        for car in cars:
            car_id = self._create_car_id(car)
            car_result = self.results[car_id]
            found = car_result.get_found_count()
            accuracy = (found / len(CAR_SPECS) * 100)
            print(f"  {car_result.car_name}: {found}/{len(CAR_SPECS)} specs ({accuracy:.1f}%)")

        self.metrics.print_summary()

        # Build final results
        return {
            "results": {
                car_id: result.to_car_data()
                for car_id, result in self.results.items()
            },
            "total_time": total_time,
            "metrics": self.metrics.to_dict(),
        }


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

async def scrape_cars_parallel(cars: List[Dict]) -> Dict[str, Any]:
    """
    Convenience function to scrape multiple cars in parallel.

    Args:
        cars: List of car dicts, e.g., [{"brand": "Mahindra", "model": "XUV700"}, ...]

    Returns:
        Result dict with "results", "total_time", and "metrics"
    """
    processor = InterleavedCarProcessor()
    return await processor.process_cars_interleaved(cars)


def scrape_cars_parallel_sync(cars: List[Dict]) -> Dict[str, Any]:
    """
    Synchronous wrapper for scrape_cars_parallel.

    Works even when called from within an existing event loop (e.g., Google ADK, FastAPI).
    Runs the async code in a separate thread with its own event loop.
    """
    import concurrent.futures

    def _run_in_new_loop():
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(scrape_cars_parallel(cars))
        finally:
            loop.close()

    # Run in a separate thread to avoid event loop conflicts
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_in_new_loop)
        return future.result()


logger.info("Interleaved processor module initialized")
