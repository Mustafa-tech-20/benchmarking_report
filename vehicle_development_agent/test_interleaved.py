#!/usr/bin/env python3
"""
Test script for the interleaved car processor.

Usage:
    python -m vehicle_development_agent.test_interleaved

Expected output:
- Process 2 cars in ~2-3 minutes (down from 7-10 minutes)
- Metrics showing resource utilization
"""
import asyncio
import time
import sys


def test_interleaved_processor():
    """Test the interleaved processor with 2 cars."""
    print("=" * 60)
    print("INTERLEAVED PROCESSOR TEST")
    print("=" * 60)
    print()

    # Import inside function to avoid import errors during syntax check
    from vehicle_development_agent.core.interleaved_processor import InterleavedCarProcessor

    # Test cars
    cars = [
        {"brand": "Mahindra", "model": "XUV700"},
        {"brand": "Tata", "model": "Nexon"},
    ]

    print(f"Testing with {len(cars)} cars:")
    for car in cars:
        print(f"  - {car['brand']} {car['model']}")
    print()

    # Create processor and run
    processor = InterleavedCarProcessor()

    start_time = time.time()
    result = asyncio.run(processor.process_cars_interleaved(cars))
    elapsed = time.time() - start_time

    # Print results
    print()
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Total time: {elapsed:.1f}s")
    print(f"Expected: ~120-180s (2-3 minutes)")
    print()

    if elapsed < 300:  # Less than 5 minutes
        print("SUCCESS: Processing time is within expected range!")
    else:
        print("WARNING: Processing time exceeded expected range")

    print()
    print("Per-car results:")
    for car_id, car_data in result.get("results", {}).items():
        found = sum(
            1 for key, val in car_data.items()
            if not key.endswith("_citation")
            and key not in ["car_name", "method", "source_urls", "images"]
            and val not in ["Not Available", "Not found", ""]
        )
        print(f"  {car_data['car_name']}: {found} specs found")

    print()
    print("Metrics summary:")
    metrics = result.get("metrics", {})
    print(f"  Duration: {metrics.get('duration_seconds', 0):.1f}s")
    print(f"  Tasks completed: {metrics.get('total_tasks_completed', 0)}")
    print(f"  Tasks failed: {metrics.get('total_tasks_failed', 0)}")

    utilization = metrics.get("resource_utilization", {})
    if utilization:
        print("  Resource utilization:")
        for resource, util in utilization.items():
            print(f"    {resource}: {util:.1f}%")

    return result


def test_sync_wrapper():
    """Test the synchronous wrapper."""
    print("=" * 60)
    print("SYNC WRAPPER TEST")
    print("=" * 60)
    print()

    from vehicle_development_agent.core.scraper import scrape_cars_parallel

    cars = [
        {"brand": "Hyundai", "model": "Creta"},
    ]

    print(f"Testing sync wrapper with {len(cars)} car...")
    start_time = time.time()
    result = scrape_cars_parallel(cars)
    elapsed = time.time() - start_time

    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"Results: {len(result.get('results', {}))} cars processed")

    return result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        test_sync_wrapper()
    else:
        test_interleaved_processor()
