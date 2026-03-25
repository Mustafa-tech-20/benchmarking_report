"""
Vehicle Development Agent Core Module

Contains:
- scraper: Car specification scraping with multi-phase extraction
- resource_scheduler: API-interleaved rate limiting and task scheduling
- interleaved_processor: Multi-car parallel processing orchestration
- scraper_metrics: Performance monitoring and metrics collection
- async_utils: Async utilities for rate limiting and HTTP operations
"""

# Export key functions for easy access
# These are lazy-loaded to avoid circular imports

__all__ = [
    "scrape_car_data",
    "scrape_cars_parallel",
    "InterleavedCarProcessor",
    "ResourceScheduler",
    "ScraperMetrics",
]


def __getattr__(name):
    """Lazy loading of module components."""
    if name == "scrape_car_data":
        from .scraper import scrape_car_data
        return scrape_car_data
    elif name == "scrape_cars_parallel":
        from .scraper import scrape_cars_parallel
        return scrape_cars_parallel
    elif name == "InterleavedCarProcessor":
        from .interleaved_processor import InterleavedCarProcessor
        return InterleavedCarProcessor
    elif name == "ResourceScheduler":
        from .resource_scheduler import ResourceScheduler
        return ResourceScheduler
    elif name == "ScraperMetrics":
        from .scraper_metrics import ScraperMetrics
        return ScraperMetrics
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
