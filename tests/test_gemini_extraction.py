"""
Test Gemini extraction accuracy
Tests extraction from known good snippets
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmarking_agent.scraper import extract_spec_value, bulk_extract_specs


# Sample real snippets for testing
SAMPLE_SNIPPETS = {
    "mahindra_thar": [
        {
            "domain": "autocarindia.com",
            "title": "Mahindra Thar price, specifications, mileage",
            "snippet": "Mahindra Thar price starts at Rs 11.35 lakh and goes up to Rs 17.60 lakh. The Thar is available with a 2.0-litre turbo-petrol engine producing 150bhp and 300Nm, and a 2.2-litre diesel producing 130bhp and 300Nm. Mileage is rated at 15.2 kmpl for diesel.",
            "url": "https://www.autocarindia.com/cars/mahindra/thar"
        },
        {
            "domain": "zigwheels.com",
            "title": "Mahindra Thar Specifications & Features",
            "snippet": "Thar comes with 5 seater capacity. It features manual and automatic transmission options. The ride quality is comfortable on highways but can be stiff on rough terrain. Steering is light and easy to maneuver.",
            "url": "https://www.zigwheels.com/mahindra-cars/thar"
        },
        {
            "domain": "overdrive.in",
            "title": "Mahindra Thar Review - Performance and Handling",
            "snippet": "The Thar's turbo-petrol motor delivers strong performance with 150 bhp power. 0-100 km/h comes up in 10.5 seconds. The NVH levels are well controlled with minimal engine noise filtering into the cabin. Braking is handled by disc brakes on all four wheels.",
            "url": "https://www.overdrive.in/reviews/mahindra-thar-review"
        },
    ]
}

EXPECTED_VALUES = {
    "mahindra_thar": {
        "price_range": "₹11.35-17.60 Lakh",
        "mileage": "15.2 kmpl",
        "seating_capacity": "5 Seater",
        "performance": "150 bhp",
        "torque": "300 Nm",
        "acceleration": "10.5 seconds",
        "nvh": "well controlled, minimal engine noise",
        "braking": "disc brakes on all four wheels",
        "steering": "light and easy to maneuver",
        "ride_quality": "comfortable on highways, stiff on rough terrain",
    }
}


def test_single_spec_extraction():
    """Test extracting individual specs"""
    print("\n" + "="*80)
    print("TEST 1: Single Spec Extraction")
    print("="*80)

    car_name = "Mahindra Thar"
    snippets = SAMPLE_SNIPPETS["mahindra_thar"]
    expected = EXPECTED_VALUES["mahindra_thar"]

    results = []

    for spec_name in ["price_range", "mileage", "performance", "seating_capacity", "nvh"]:
        print(f"\nExtracting: {spec_name}")

        # Create search data format
        search_data = {"results": snippets}

        # Extract
        result = extract_spec_value(spec_name, search_data, car_name)
        extracted_value = result["value"]
        expected_value = expected.get(spec_name, "")

        # Check if extraction is correct
        is_correct = expected_value.lower() in extracted_value.lower() or extracted_value.lower() in expected_value.lower()

        print(f"  Expected: {expected_value}")
        print(f"  Extracted: {extracted_value}")
        print(f"  Status: {'✓ PASS' if is_correct else '✗ FAIL'}")

        results.append({
            "spec": spec_name,
            "expected": expected_value,
            "extracted": extracted_value,
            "correct": is_correct
        })

    # Summary
    correct_count = sum(1 for r in results if r["correct"])
    total_count = len(results)
    accuracy = (correct_count / total_count * 100) if total_count > 0 else 0

    print(f"\n✓ Accuracy: {correct_count}/{total_count} ({accuracy:.1f}%)")

    return accuracy


def test_bulk_extraction():
    """Test bulk extraction of multiple specs at once"""
    print("\n" + "="*80)
    print("TEST 2: Bulk Spec Extraction")
    print("="*80)

    car_name = "Mahindra Thar"
    snippets = SAMPLE_SNIPPETS["mahindra_thar"]
    expected = EXPECTED_VALUES["mahindra_thar"]

    # Test different group sizes
    group_sizes = [5, 10, 20]

    for group_size in group_sizes:
        print(f"\n--- Testing group size: {group_size} ---")

        specs_to_extract = list(expected.keys())[:group_size]

        # Extract
        extracted = bulk_extract_specs(car_name, snippets, specs_to_extract)

        # Check accuracy
        correct = 0
        for spec in specs_to_extract:
            if spec in expected:
                extracted_val = extracted.get(spec, "")
                expected_val = expected[spec]

                # Check if extracted value contains expected info
                if expected_val and extracted_val:
                    if expected_val.lower() in str(extracted_val).lower() or str(extracted_val).lower() in expected_val.lower():
                        correct += 1
                        print(f"  ✓ {spec}: {extracted_val}")
                    elif "Not" not in str(extracted_val) and "Error" not in str(extracted_val):
                        # Found something, might be correct
                        print(f"  ? {spec}: {extracted_val} (expected: {expected_val})")
                    else:
                        print(f"  ✗ {spec}: {extracted_val} (expected: {expected_val})")

        accuracy = (correct / len(specs_to_extract) * 100) if specs_to_extract else 0
        print(f"\n  Accuracy: {correct}/{len(specs_to_extract)} ({accuracy:.1f}%)")


def test_extraction_with_missing_data():
    """Test extraction when spec is not in snippets"""
    print("\n" + "="*80)
    print("TEST 3: Extraction with Missing Data")
    print("="*80)

    car_name = "Mahindra Thar"
    snippets = SAMPLE_SNIPPETS["mahindra_thar"]

    # Test specs that are NOT in the snippets
    missing_specs = ["boot_space", "sunroof", "infotainment_screen", "wheelbase"]

    print("\nTesting specs that should return 'Not found':")

    correct_not_found = 0
    for spec in missing_specs:
        search_data = {"results": snippets}
        result = extract_spec_value(spec, search_data, car_name)
        value = result["value"]

        is_correct = "Not" in value or "not found" in value.lower() or "N/A" in value

        print(f"  {spec}: {value} {'✓' if is_correct else '✗'}")

        if is_correct:
            correct_not_found += 1

    accuracy = (correct_not_found / len(missing_specs) * 100) if missing_specs else 0
    print(f"\n✓ Correctly identified missing: {correct_not_found}/{len(missing_specs)} ({accuracy:.1f}%)")

    return accuracy


def test_extraction_prompt_quality():
    """Test if extraction prompts are working well"""
    print("\n" + "="*80)
    print("TEST 4: Extraction Prompt Quality")
    print("="*80)

    # Test different spec types
    spec_categories = {
        "Numeric (with units)": ["price_range", "mileage", "performance", "torque"],
        "Subjective (descriptive)": ["nvh", "ride_quality", "steering"],
        "Categorical": ["seating_capacity", "transmission"],
    }

    car_name = "Mahindra Thar"
    snippets = SAMPLE_SNIPPETS["mahindra_thar"]
    expected = EXPECTED_VALUES["mahindra_thar"]

    category_results = {}

    for category, specs in spec_categories.items():
        print(f"\n{category}:")
        correct = 0
        total = 0

        for spec in specs:
            if spec in expected:
                search_data = {"results": snippets}
                result = extract_spec_value(spec, search_data, car_name)
                extracted = result["value"]
                expected_val = expected[spec]

                is_correct = expected_val.lower() in extracted.lower() or extracted.lower() in expected_val.lower()

                print(f"  {spec}: {'✓' if is_correct else '✗'}")
                print(f"    Expected: {expected_val}")
                print(f"    Extracted: {extracted}")

                if is_correct:
                    correct += 1
                total += 1

        accuracy = (correct / total * 100) if total > 0 else 0
        category_results[category] = accuracy
        print(f"  Accuracy: {correct}/{total} ({accuracy:.1f}%)")

    return category_results


def run_all_tests():
    """Run all extraction tests"""
    print("\n" + "#"*80)
    print("GEMINI EXTRACTION TEST SUITE")
    print("#"*80)

    results = {}

    # Test 1: Single spec extraction
    try:
        accuracy = test_single_spec_extraction()
        results["single_spec"] = f"{'PASS' if accuracy >= 80 else 'FAIL'} ({accuracy:.1f}%)"
    except Exception as e:
        print(f"\n✗ TEST 1 FAILED: {e}")
        results["single_spec"] = "FAIL"

    # Test 2: Bulk extraction
    try:
        test_bulk_extraction()
        results["bulk_extraction"] = "COMPLETED"
    except Exception as e:
        print(f"\n✗ TEST 2 FAILED: {e}")
        results["bulk_extraction"] = "FAIL"

    # Test 3: Missing data
    try:
        accuracy = test_extraction_with_missing_data()
        results["missing_data"] = f"{'PASS' if accuracy >= 70 else 'FAIL'} ({accuracy:.1f}%)"
    except Exception as e:
        print(f"\n✗ TEST 3 FAILED: {e}")
        results["missing_data"] = "FAIL"

    # Test 4: Prompt quality
    try:
        category_results = test_extraction_prompt_quality()
        avg_accuracy = sum(category_results.values()) / len(category_results)
        results["prompt_quality"] = f"{'PASS' if avg_accuracy >= 70 else 'FAIL'} ({avg_accuracy:.1f}%)"
    except Exception as e:
        print(f"\n✗ TEST 4 FAILED: {e}")
        results["prompt_quality"] = "FAIL"

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, result in results.items():
        status = "✓" if "PASS" in result or "COMPLETED" in result else "✗"
        print(f"{status} {test_name}: {result}")


if __name__ == "__main__":
    run_all_tests()
