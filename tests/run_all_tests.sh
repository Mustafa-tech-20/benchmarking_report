#!/bin/bash

# Run all test suites for the benchmarking agent
# Usage: ./run_all_tests.sh [test_type]
#   test_type: search, extraction, e2e, or all (default: all)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get test type
TEST_TYPE=${1:-all}

echo ""
echo "###############################################################################"
echo "#                    CAR BENCHMARKING AGENT - TEST SUITE                     #"
echo "###############################################################################"
echo ""

# Function to run a test
run_test() {
    local test_name=$1
    local test_file=$2

    echo ""
    echo -e "${YELLOW}Running: $test_name${NC}"
    echo "-----------------------------------------------------------------------------"

    if python "$test_file"; then
        echo -e "${GREEN}✓ $test_name PASSED${NC}"
        return 0
    else
        echo -e "${RED}✗ $test_name FAILED${NC}"
        return 1
    fi
}

# Track results
TOTAL_TESTS=0
PASSED_TESTS=0

# Run tests based on type
case $TEST_TYPE in
    search)
        echo "Running Custom Search API tests only..."
        run_test "Custom Search API" "tests/test_custom_search.py" && PASSED_TESTS=$((PASSED_TESTS+1))
        TOTAL_TESTS=1
        ;;

    extraction)
        echo "Running Gemini Extraction tests only..."
        run_test "Gemini Extraction" "tests/test_gemini_extraction.py" && PASSED_TESTS=$((PASSED_TESTS+1))
        TOTAL_TESTS=1
        ;;

    e2e)
        echo "Running End-to-End tests only..."
        run_test "End-to-End" "tests/test_end_to_end.py" && PASSED_TESTS=$((PASSED_TESTS+1))
        TOTAL_TESTS=1
        ;;

    all)
        echo "Running all test suites..."

        # Test 1: Custom Search API
        run_test "Custom Search API" "tests/test_custom_search.py" && PASSED_TESTS=$((PASSED_TESTS+1))
        TOTAL_TESTS=$((TOTAL_TESTS+1))

        # Test 2: Gemini Extraction
        run_test "Gemini Extraction" "tests/test_gemini_extraction.py" && PASSED_TESTS=$((PASSED_TESTS+1))
        TOTAL_TESTS=$((TOTAL_TESTS+1))

        # Test 3: End-to-End
        run_test "End-to-End" "tests/test_end_to_end.py" && PASSED_TESTS=$((PASSED_TESTS+1))
        TOTAL_TESTS=$((TOTAL_TESTS+1))
        ;;

    *)
        echo -e "${RED}Invalid test type: $TEST_TYPE${NC}"
        echo "Usage: $0 [search|extraction|e2e|all]"
        exit 1
        ;;
esac

# Print summary
echo ""
echo "==============================================================================="
echo "                              TEST SUMMARY                                     "
echo "==============================================================================="
echo "Total Tests: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $((TOTAL_TESTS - PASSED_TESTS))"

if [ $PASSED_TESTS -eq $TOTAL_TESTS ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    exit 1
fi
