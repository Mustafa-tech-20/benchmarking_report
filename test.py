"""Test Vertex AI Grounding with Google Search - Automatic Citations

Uses google-genai SDK with Vertex AI for grounded responses.
"""
import os
import sys
import json

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/mustafa.mohammed/Documents/Mahindra-CloudRun/service.json"

from google import genai
from google.genai.types import (
    GenerateContentConfig,
    GoogleSearch,
    Tool,
)

# Configuration
PROJECT_ID = "srv-ad-nvoc-dev-445421"
LOCATION = "global"  # MUST be "global" for Google Search grounding
MODEL_ID = "gemini-2.5-flash"

# Initialize client
try:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    print(f"✓ Initialized Vertex AI")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Location: {LOCATION}")
    print(f"  Model: {MODEL_ID}\n")
except Exception as e:
    print(f"❌ Error initializing Vertex AI: {e}")
    sys.exit(1)


def print_sources(response):
    """Extract and print source URLs from grounding metadata."""
    if not response.candidates:
        return

    candidate = response.candidates[0]
    metadata = getattr(candidate, "grounding_metadata", None)

    if not metadata:
        print("No grounding metadata found.")
        return

    # Print search queries used
    if metadata.web_search_queries:
        print("\nSearch queries used:")
        for q in metadata.web_search_queries:
            print(f"  - {q}")

    # Print source URLs
    chunks = metadata.grounding_chunks
    if chunks:
        print(f"\nSources ({len(chunks)}):")
        for i, chunk in enumerate(chunks, 1):
            if chunk.web:
                print(f"  [{i}] {chunk.web.title}")
                print(f"       {chunk.web.uri}")
    else:
        print("\nNo source chunks found.")


def test_grounding_basic():
    """Test 1: Basic grounding with automatic citations."""

    print("="*80)
    print("TEST 1: Basic Grounding - Mahindra Thar Search")
    print("="*80)

    google_search_tool = Tool(google_search=GoogleSearch())

    prompt = """What are the key specifications of the 2024 Mahindra Thar Roxx?
Include price, engine options, mileage, safety features, and infotainment."""

    print(f"\nPrompt: {prompt[:100]}...\n")
    print("Generating response with Google Search grounding...\n")

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=GenerateContentConfig(tools=[google_search_tool]),
    )

    print("-" * 80)
    print("RESPONSE:")
    print("-" * 80)
    print(response.text)

    print_sources(response)
    print()


def test_grounding_clinical_trial():
    """Test 2: Extract clinical trial data with citations."""

    print("="*80)
    print("TEST 2: Clinical Trial Data Extraction")
    print("="*80)

    google_search_tool = Tool(google_search=GoogleSearch())

    prompt = """Extract clinical efficacy data for the Semaglutide STEP 1 trial (NCT03548935):
- Weight loss percentage at primary endpoint
- Trial phase
- Sample size
- Duration

Provide the data in JSON format."""

    print(f"\nPrompt: {prompt}\n")
    print("Generating response with Google Search grounding...\n")

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            temperature=0.1,
        ),
    )

    print("-" * 80)
    print("RESPONSE:")
    print("-" * 80)
    print(response.text)

    print_sources(response)
    print()


def test_grounding_simple():
    """Test 3: Simple factual query."""

    print("="*80)
    print("TEST 3: Simple Factual Query")
    print("="*80)

    google_search_tool = Tool(google_search=GoogleSearch())

    prompt = "What is the current price of Bitcoin today?"

    print(f"\nPrompt: {prompt}\n")
    print("Generating response with Google Search grounding...\n")

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=GenerateContentConfig(tools=[google_search_tool]),
    )

    print("-" * 80)
    print("RESPONSE:")
    print("-" * 80)
    print(response.text)

    print_sources(response)
    print()


def main():
    """Run grounding tests."""

    print("\n" + "="*80)
    print("VERTEX AI GROUNDING WITH GOOGLE SEARCH")
    print("="*80)
    print("\nUsing google-genai SDK with location='global'\n")

    try:
        test_grounding_simple()
        print("\n")

        test_grounding_basic()
        print("\n")

        test_grounding_clinical_trial()
        print("\n")

        print("="*80)
        print("DONE")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
