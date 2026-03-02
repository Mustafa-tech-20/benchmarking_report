"""
Debug utility for the car scraper
Helps diagnose issues with search quality and extraction accuracy
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmarking_agent.scraper import (
    custom_search,
    extract_spec_value,
    bulk_extract_specs,
)
from benchmarking_agent.scraper_improved import (
    custom_search_improved,
    extract_spec_value_improved,
    bulk_extract_specs_improved,
    validate_spec_value,
)


def debug_search(car_name: str, spec_name: str):
    """Debug search results for a specific car and spec"""
    print(f"\n{'='*80}")
    print(f"DEBUG: Search for {car_name} - {spec_name}")
    print(f"{'='*80}")

    query = f"{car_name} {spec_name.replace('_', ' ')}"
    print(f"\nQuery: {query}")

    # Test current search
    print(f"\n--- CURRENT SEARCH ---")
    result = custom_search(query, spec_name)
    results = result.get("results", [])

    print(f"Results: {len(results)}")

    if results:
        print(f"\nTop 5 results:")
        for i, r in enumerate(results[:5], 1):
            print(f"\n{i}. [{r.get('domain')}]")
            print(f"   Title: {r.get('title')[:70]}...")
            print(f"   Snippet: {r.get('snippet')[:150]}...")
            print(f"   URL: {r.get('url')[:70]}...")

    # Test improved search
    print(f"\n--- IMPROVED SEARCH ---")
    try:
        improved_results = custom_search_improved(query, num_results=10)
        print(f"Results: {len(improved_results)}")

        if improved_results:
            print(f"\nTop 5 results:")
            for i, r in enumerate(improved_results[:5], 1):
                print(f"\n{i}. [{r.get('domain')}]")
                print(f"   Title: {r.get('title')[:70]}...")
                print(f"   Snippet: {r.get('snippet')[:150]}...")
    except Exception as e:
        print(f"Error: {e}")

    return results


def debug_extraction(car_name: str, spec_name: str, search_results: list):
    """Debug extraction from search results"""
    print(f"\n{'='*80}")
    print(f"DEBUG: Extraction for {car_name} - {spec_name}")
    print(f"{'='*80}")

    if not search_results:
        print("No search results to extract from")
        return

    # Test current extraction
    print(f"\n--- CURRENT EXTRACTION ---")
    search_data = {"results": search_results}
    result = extract_spec_value(spec_name, search_data, car_name)

    print(f"Extracted value: {result['value']}")
    print(f"Citations: {len(result.get('citations', []))}")

    # Test improved extraction
    print(f"\n--- IMPROVED EXTRACTION ---")
    try:
        improved_result = extract_spec_value_improved(spec_name, search_results, car_name)
        improved_value = improved_result['value']

        print(f"Extracted value: {improved_value}")
        print(f"Citations: {len(improved_result.get('citations', []))}")

        # Validate
        is_valid = validate_spec_value(spec_name, improved_value)
        print(f"Validation: {'✓ Valid' if is_valid else '✗ Invalid/Missing'}")

    except Exception as e:
        print(f"Error: {e}")


def debug_bulk_extraction(car_name: str, specs: list):
    """Debug bulk extraction for multiple specs"""
    print(f"\n{'='*80}")
    print(f"DEBUG: Bulk Extraction for {car_name}")
    print(f"{'='*80}")

    # Do a broad search first
    query = f"{car_name} specifications review price mileage performance"
    print(f"\nBroad search query: {query}")

    result = custom_search(query, "broad")
    search_results = result.get("results", [])

    print(f"Broad search results: {len(search_results)}")

    if not search_results:
        print("No results to extract from")
        return

    # Test current bulk extraction
    print(f"\n--- CURRENT BULK EXTRACTION ({len(specs)} specs) ---")
    current_extracted = bulk_extract_specs(car_name, search_results, specs)

    found = sum(1 for v in current_extracted.values() if v and "Not" not in str(v) and "Error" not in str(v))
    print(f"Found: {found}/{len(specs)} ({found/len(specs)*100:.1f}%)")

    for spec, value in current_extracted.items():
        status = "✓" if value and "Not" not in str(value) and "Error" not in str(value) else "✗"
        print(f"  {status} {spec}: {value}")

    # Test improved bulk extraction
    print(f"\n--- IMPROVED BULK EXTRACTION ({len(specs)} specs) ---")
    try:
        improved_extracted = bulk_extract_specs_improved(car_name, search_results, specs)

        found = sum(1 for v in improved_extracted.values() if v and "Not" not in str(v) and "Error" not in str(v))
        print(f"Found: {found}/{len(specs)} ({found/len(specs)*100:.1f}%)")

        for spec, value in improved_extracted.items():
            is_valid = validate_spec_value(spec, value)
            status = "✓" if is_valid else "✗"
            print(f"  {status} {spec}: {value}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def compare_methods(car_name: str):
    """Compare current vs improved methods"""
    print(f"\n{'='*80}")
    print(f"COMPARISON: Current vs Improved Methods")
    print(f"Car: {car_name}")
    print(f"{'='*80}")

    test_specs = [
        "price_range",
        "mileage",
        "performance",
        "torque",
        "seating_capacity",
        "ride_quality",
        "nvh",
        "steering",
    ]

    # Broad search
    query = f"{car_name} specifications review"
    result = custom_search(query, "broad")
    search_results = result.get("results", [])

    print(f"\nBroad search: {len(search_results)} results")

    # Compare bulk extraction
    print(f"\n{'='*80}")
    print(f"BULK EXTRACTION COMPARISON")
    print(f"{'='*80}")

    print("\nCurrent method:")
    current = bulk_extract_specs(car_name, search_results, test_specs)
    current_found = sum(1 for v in current.values() if v and "Not" not in str(v) and "Error" not in str(v))
    print(f"  Found: {current_found}/{len(test_specs)} ({current_found/len(test_specs)*100:.1f}%)")

    print("\nImproved method:")
    improved = bulk_extract_specs_improved(car_name, search_results, test_specs)
    improved_found = sum(1 for v in improved.values() if v and "Not" not in str(v) and "Error" not in str(v))
    print(f"  Found: {improved_found}/{len(test_specs)} ({improved_found/len(test_specs)*100:.1f}%)")

    # Show comparison
    print(f"\n{'='*80}")
    print(f"SPEC-BY-SPEC COMPARISON")
    print(f"{'='*80}")
    print(f"\n{'Spec':<20} {'Current':<30} {'Improved':<30}")
    print("-" * 80)

    for spec in test_specs:
        current_val = current.get(spec, "")[:28]
        improved_val = improved.get(spec, "")[:28]
        print(f"{spec:<20} {current_val:<30} {improved_val:<30}")

    # Summary
    improvement = improved_found - current_found
    improvement_pct = (improvement / len(test_specs) * 100) if test_specs else 0

    print(f"\n{'='*80}")
    print(f"IMPROVEMENT: +{improvement} specs ({improvement_pct:+.1f}%)")
    print(f"{'='*80}")


def main():
    parser = argparse.ArgumentParser(description="Debug car scraper")
    parser.add_argument("command", choices=["search", "extract", "bulk", "compare"],
                        help="Debug command to run")
    parser.add_argument("--car", required=True, help="Car name (e.g., 'Mahindra Thar')")
    parser.add_argument("--spec", help="Spec name (for search/extract commands)")
    parser.add_argument("--specs", help="Comma-separated spec names (for bulk command)")

    args = parser.parse_args()

    if args.command == "search":
        if not args.spec:
            print("Error: --spec required for search command")
            return
        debug_search(args.car, args.spec)

    elif args.command == "extract":
        if not args.spec:
            print("Error: --spec required for extract command")
            return
        results = debug_search(args.car, args.spec)
        if results:
            debug_extraction(args.car, args.spec, results)

    elif args.command == "bulk":
        if args.specs:
            specs = [s.strip() for s in args.specs.split(",")]
        else:
            specs = ["price_range", "mileage", "performance", "torque", "seating_capacity"]
        debug_bulk_extraction(args.car, specs)

    elif args.command == "compare":
        compare_methods(args.car)


if __name__ == "__main__":
    main()
