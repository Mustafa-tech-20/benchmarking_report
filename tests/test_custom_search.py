"""
Test Custom Search API functionality
Tests search quality, domain coverage, and snippet relevance
"""
import sys
import os
import json
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from benchmarking_agent.scraper import custom_search
from benchmarking_agent.config import SEARCH_SITES, GOOGLE_API_KEY, SEARCH_ENGINE_ID


def test_custom_search_basic():
    """Test basic search functionality"""
    print("\n" + "="*80)
    print("TEST 1: Basic Custom Search")
    print("="*80)

    query = "Mahindra Thar price specifications"
    spec_name = "price_range"

    print(f"Query: {query}")
    print(f"Spec: {spec_name}")

    result = custom_search(query, spec_name)
    results = result.get("results", [])

    print(f"\n✓ Results returned: {len(results)}")

    # Check domain diversity
    domains = set(r.get("domain", "") for r in results)
    print(f"✓ Unique domains: {len(domains)}")
    print(f"  Domains: {', '.join(list(domains)[:10])}")

    # Check snippet quality
    if results:
        print(f"\n✓ Sample result:")
        sample = results[0]
        print(f"  Domain: {sample.get('domain')}")
        print(f"  Title: {sample.get('title')[:80]}...")
        print(f"  Snippet: {sample.get('snippet')[:150]}...")

    return len(results) > 0, domains


def test_search_domain_coverage():
    """Test if search is hitting configured domains"""
    print("\n" + "="*80)
    print("TEST 2: Domain Coverage")
    print("="*80)

    test_queries = [
        ("Mahindra Thar price mileage", "basic_specs"),
        ("Hyundai Creta ride quality NVH", "ride_specs"),
        ("Maruti Swift steering braking", "handling_specs"),
    ]

    all_domains = set()

    for query, spec_type in test_queries:
        result = custom_search(query, spec_type)
        results = result.get("results", [])
        domains = set(r.get("domain", "") for r in results)
        all_domains.update(domains)
        print(f"\n{spec_type}: {len(results)} results from {len(domains)} domains")

    print(f"\n✓ Total unique domains hit: {len(all_domains)}")
    print(f"✓ Configured sites: {len(SEARCH_SITES)}")
    print(f"✓ Coverage: {len(all_domains)/len(SEARCH_SITES)*100:.1f}%")

    # Check which tier 1 sites are being hit
    tier1_sites = ["autocarindia.com", "zigwheels.com", "overdrive.in", "team-bhp.com"]
    tier1_hit = [site for site in tier1_sites if any(site in d for d in all_domains)]
    print(f"\n✓ Tier 1 sites hit: {len(tier1_hit)}/{len(tier1_sites)}")
    print(f"  {tier1_hit}")

    return len(all_domains)


def test_search_snippet_relevance():
    """Test if snippets contain relevant spec information"""
    print("\n" + "="*80)
    print("TEST 3: Snippet Relevance")
    print("="*80)

    test_cases = [
        ("Mahindra Thar price range", "price", ["lakh", "₹", "rs", "price", "cost"]),
        ("Hyundai Creta mileage fuel efficiency", "mileage", ["kmpl", "km/l", "mileage", "fuel"]),
        ("Maruti Swift performance power", "performance", ["bhp", "hp", "power", "kw"]),
        ("Honda City torque", "torque", ["nm", "torque", "kgm"]),
    ]

    results_summary = []

    for query, spec, keywords in test_cases:
        result = custom_search(query, spec)
        results = result.get("results", [])

        # Check how many snippets contain relevant keywords
        relevant_count = 0
        for r in results:
            snippet = r.get("snippet", "").lower()
            if any(kw in snippet for kw in keywords):
                relevant_count += 1

        relevance_pct = (relevant_count / len(results) * 100) if results else 0
        results_summary.append({
            "spec": spec,
            "total_results": len(results),
            "relevant_results": relevant_count,
            "relevance_pct": relevance_pct
        })

        print(f"\n{spec}:")
        print(f"  Total results: {len(results)}")
        print(f"  Relevant: {relevant_count} ({relevance_pct:.1f}%)")

        # Show sample relevant snippet
        for r in results:
            snippet = r.get("snippet", "").lower()
            if any(kw in snippet for kw in keywords):
                print(f"  Sample: {r.get('snippet')[:100]}...")
                break

    avg_relevance = sum(r["relevance_pct"] for r in results_summary) / len(results_summary)
    print(f"\n✓ Average relevance: {avg_relevance:.1f}%")

    return avg_relevance


def test_api_configuration():
    """Test API key and search engine ID configuration"""
    print("\n" + "="*80)
    print("TEST 4: API Configuration")
    print("="*80)

    print(f"✓ Google API Key: {'*' * 10}{GOOGLE_API_KEY[-4:] if GOOGLE_API_KEY else 'NOT SET'}")
    print(f"✓ Search Engine ID: {SEARCH_ENGINE_ID if SEARCH_ENGINE_ID else 'NOT SET'}")
    print(f"✓ Configured sites: {len(SEARCH_SITES)}")

    if not GOOGLE_API_KEY:
        print("\n✗ ERROR: GOOGLE_API_KEY not set!")
        return False

    if not SEARCH_ENGINE_ID:
        print("\n✗ ERROR: SEARCH_ENGINE_ID not set!")
        return False

    print("\n✓ Configuration OK")
    return True


def test_search_quality_for_specs():
    """Test search quality for different spec categories"""
    print("\n" + "="*80)
    print("TEST 5: Search Quality by Spec Category")
    print("="*80)

    spec_tests = {
        "Core Specs": [
            ("Mahindra Thar price range", "price_range"),
            ("Mahindra Thar mileage fuel efficiency", "mileage"),
            ("Mahindra Thar seating capacity", "seating_capacity"),
        ],
        "Performance Specs": [
            ("Mahindra Thar engine power bhp", "performance"),
            ("Mahindra Thar torque nm", "torque"),
            ("Mahindra Thar 0-100 acceleration", "acceleration"),
        ],
        "Subjective Specs": [
            ("Mahindra Thar ride quality comfort", "ride_quality"),
            ("Mahindra Thar NVH noise vibration", "nvh"),
            ("Mahindra Thar steering feel", "steering"),
        ],
    }

    category_results = {}

    for category, tests in spec_tests.items():
        print(f"\n{category}:")
        results_count = []

        for query, spec in tests:
            result = custom_search(query, spec)
            results = result.get("results", [])
            results_count.append(len(results))
            print(f"  {spec}: {len(results)} results")

        avg_results = sum(results_count) / len(results_count)
        category_results[category] = avg_results
        print(f"  Average: {avg_results:.1f} results/spec")

    return category_results


def run_all_tests():
    """Run all custom search tests"""
    print("\n" + "#"*80)
    print("CUSTOM SEARCH API TEST SUITE")
    print("#"*80)

    results = {}

    # Test 1: Basic functionality
    try:
        success, domains = test_custom_search_basic()
        results["basic_search"] = "PASS" if success else "FAIL"
    except Exception as e:
        print(f"\n✗ TEST 1 FAILED: {e}")
        results["basic_search"] = "FAIL"

    # Test 2: Domain coverage
    try:
        domain_count = test_search_domain_coverage()
        results["domain_coverage"] = f"PASS ({domain_count} domains)"
    except Exception as e:
        print(f"\n✗ TEST 2 FAILED: {e}")
        results["domain_coverage"] = "FAIL"

    # Test 3: Snippet relevance
    try:
        relevance = test_search_snippet_relevance()
        results["snippet_relevance"] = f"{'PASS' if relevance > 50 else 'FAIL'} ({relevance:.1f}%)"
    except Exception as e:
        print(f"\n✗ TEST 3 FAILED: {e}")
        results["snippet_relevance"] = "FAIL"

    # Test 4: Configuration
    try:
        config_ok = test_api_configuration()
        results["configuration"] = "PASS" if config_ok else "FAIL"
    except Exception as e:
        print(f"\n✗ TEST 4 FAILED: {e}")
        results["configuration"] = "FAIL"

    # Test 5: Quality by category
    try:
        category_results = test_search_quality_for_specs()
        results["category_quality"] = "PASS"
    except Exception as e:
        print(f"\n✗ TEST 5 FAILED: {e}")
        results["category_quality"] = "FAIL"

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, result in results.items():
        status = "✓" if "PASS" in result else "✗"
        print(f"{status} {test_name}: {result}")

    passed = sum(1 for r in results.values() if "PASS" in r)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")


if __name__ == "__main__":
    run_all_tests()
