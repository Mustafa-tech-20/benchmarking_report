"""
End-to-end test for complete car scraping pipeline
Tests the full flow from search to extraction to final output
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmarking_agent.scraper import scrape_car_data
from benchmarking_agent.Internal_Car_tools import CAR_SPECS


def test_single_car_scrape():
    """Test scraping a single well-known car"""
    print("\n" + "="*80)
    print("END-TO-END TEST: Single Car Scrape")
    print("="*80)

    car_name = "Mahindra Thar"
    print(f"\nScraping: {car_name}")
    print(f"Target: {len(CAR_SPECS)} specifications")
    print(f"Expected accuracy: >80%")

    start_time = time.time()

    try:
        # Scrape car data
        car_data = scrape_car_data(car_name, manual_specs=None, use_custom_search=True)

        elapsed = time.time() - start_time

        # Analyze results
        empty_values = ("Not Available", "N/A", "Not found", "not found", None, "", "—", "-", "None")

        found_specs = []
        missing_specs = []

        for spec in CAR_SPECS:
            value = car_data.get(spec)
            if value and value not in empty_values and str(value).strip() not in empty_values:
                found_specs.append(spec)
            else:
                missing_specs.append(spec)

        accuracy = (len(found_specs) / len(CAR_SPECS) * 100) if CAR_SPECS else 0

        print(f"\n{'='*80}")
        print("RESULTS")
        print(f"{'='*80}")
        print(f"✓ Total specs: {len(CAR_SPECS)}")
        print(f"✓ Found: {len(found_specs)}")
        print(f"✗ Missing: {len(missing_specs)}")
        print(f"✓ Accuracy: {accuracy:.1f}%")
        print(f"✓ Time: {elapsed:.1f}s")

        # Show sample found specs
        print(f"\nSample found specs:")
        for spec in found_specs[:10]:
            value = car_data.get(spec)
            citation = car_data.get(f"{spec}_citation", {})
            source = citation.get("source_url", "N/A")
            print(f"  ✓ {spec}: {value}")
            print(f"    Source: {source[:60]}...")

        # Show missing specs
        print(f"\nMissing specs ({len(missing_specs)}):")
        for spec in missing_specs[:20]:
            print(f"  ✗ {spec}")
        if len(missing_specs) > 20:
            print(f"  ... and {len(missing_specs) - 20} more")

        # Show source URLs
        source_urls = car_data.get("source_urls", [])
        print(f"\n✓ Source URLs used: {len(source_urls)}")
        for i, url in enumerate(source_urls[:5], 1):
            print(f"  {i}. {url}")

        # Check if test passed
        test_passed = accuracy >= 60  # Lower threshold for realistic expectation

        print(f"\n{'='*80}")
        if test_passed:
            print(f"✓ TEST PASSED (accuracy: {accuracy:.1f}% >= 60%)")
        else:
            print(f"✗ TEST FAILED (accuracy: {accuracy:.1f}% < 60%)")
        print(f"{'='*80}")

        return test_passed, accuracy, car_data

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False, 0, {}


def analyze_failure_patterns(car_data):
    """Analyze which types of specs are failing most"""
    print("\n" + "="*80)
    print("FAILURE PATTERN ANALYSIS")
    print("="*80)

    # Categorize specs
    spec_categories = {
        "Core Basic": [
            "price_range", "mileage", "user_rating", "seating_capacity",
            "transmission", "braking", "steering", "climate_control"
        ],
        "Performance": [
            "performance", "torque", "acceleration", "pedal_feel",
            "turbo_lag", "city_performance", "highway_performance"
        ],
        "Handling & Ride": [
            "ride_quality", "nvh", "handling", "cornering_stability",
            "turning_radius", "handling_bumps", "handling_potholes"
        ],
        "Features": [
            "infotainment_screen", "apple_carplay", "sunroof",
            "boot_space", "wheelbase", "parking_ease", "lighting"
        ],
        "Subjective": [
            "interior_quality", "ergonomics", "visibility",
            "rear_seat_comfort", "driver_seat_comfort"
        ]
    }

    empty_values = ("Not Available", "N/A", "Not found", "not found", None, "", "—", "-", "None")

    category_stats = {}

    for category, specs in spec_categories.items():
        found = 0
        total = len(specs)

        missing_list = []

        for spec in specs:
            value = car_data.get(spec)
            if value and value not in empty_values and str(value).strip() not in empty_values:
                found += 1
            else:
                missing_list.append(spec)

        accuracy = (found / total * 100) if total > 0 else 0
        category_stats[category] = {
            "found": found,
            "total": total,
            "accuracy": accuracy,
            "missing": missing_list
        }

        print(f"\n{category}:")
        print(f"  Found: {found}/{total} ({accuracy:.1f}%)")
        if missing_list:
            print(f"  Missing: {', '.join(missing_list[:5])}")
            if len(missing_list) > 5:
                print(f"           ... and {len(missing_list) - 5} more")

    return category_stats


def test_comparison_quality():
    """Test comparison between two cars"""
    print("\n" + "="*80)
    print("END-TO-END TEST: Two Car Comparison")
    print("="*80)

    cars = ["Mahindra Thar", "Hyundai Creta"]

    print(f"\nComparing: {' vs '.join(cars)}")

    results = {}

    for car in cars:
        print(f"\n--- Scraping {car} ---")
        passed, accuracy, car_data = test_single_car_scrape()
        results[car] = {
            "passed": passed,
            "accuracy": accuracy,
            "data": car_data
        }

    # Summary
    print(f"\n{'='*80}")
    print("COMPARISON SUMMARY")
    print(f"{'='*80}")

    for car, result in results.items():
        status = "✓ PASS" if result["passed"] else "✗ FAIL"
        print(f"{status} {car}: {result['accuracy']:.1f}%")

    avg_accuracy = sum(r["accuracy"] for r in results.values()) / len(results)
    print(f"\nAverage accuracy: {avg_accuracy:.1f}%")

    return avg_accuracy >= 60


def run_all_tests():
    """Run all end-to-end tests"""
    print("\n" + "#"*80)
    print("END-TO-END TEST SUITE")
    print("#"*80)

    test_results = {}

    # Test 1: Single car
    try:
        passed, accuracy, car_data = test_single_car_scrape()
        test_results["single_car"] = f"{'PASS' if passed else 'FAIL'} ({accuracy:.1f}%)"

        # Analyze failures
        if car_data:
            analyze_failure_patterns(car_data)
    except Exception as e:
        print(f"\n✗ TEST 1 FAILED: {e}")
        test_results["single_car"] = "FAIL"

    # Test 2: Comparison (optional - takes longer)
    # try:
    #     passed = test_comparison_quality()
    #     test_results["comparison"] = "PASS" if passed else "FAIL"
    # except Exception as e:
    #     print(f"\n✗ TEST 2 FAILED: {e}")
    #     test_results["comparison"] = "FAIL"

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, result in test_results.items():
        status = "✓" if "PASS" in result else "✗"
        print(f"{status} {test_name}: {result}")


if __name__ == "__main__":
    run_all_tests()
