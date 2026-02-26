"""Test Vertex AI Grounding with Domain Preference

Note: Google Search grounding only supports excludeDomains, NOT includeDomains.
We use prompt engineering to guide searches to preferred domains.
"""
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/mustafa.mohammed/Documents/Mahindra-CloudRun/service.json"

from google import genai
from google.genai.types import (
    GenerateContentConfig,
    GoogleSearch,
    Tool,
)

# Configuration
PROJECT_ID = "srv-ad-nvoc-dev-445421"
LOCATION = "global"
MODEL_ID = "gemini-2.5-flash"

# Preferred automotive domains
PREFERRED_DOMAINS = [
    # Indian automotive sites
    "team-bhp.com",
    "autocarindia.com",
    "overdrive.in",
    "zigwheels.com",
    "carwale.com",
    "cardekho.com",
    "autocarpro.in",
    "evreporter.com",
    "motoringworld.in",
    # International automotive sites
    "bestsellingcarsblog.com",
    "esource.com",
    "orovel.net",
    "evadoption.com",
    "insideevs.com",
    "autoprove.net",
    "gasgoo.com",
    "response.jp",
    "carnewschina.com",
    "autoblog.com",
    "autohome.com.cn",
    "autonews.com",
    "autonetmagz.com",
    "paultan.org",
    "chinaelectricvehicles.com",
    "chinacartimes.com",
    "jalopnik.com",
    "just-auto.com",
    "leftlanenews.com",
    "egmcartech.com",
    "autocar.co.uk",
    "automobilemag.com",
    "automobile.tn",
    "wandaloo.com",
    "motory.com",
    "zigwheels.ae",
    "chileautos.cl",
]

# Domains to EXCLUDE (non-automotive, generic sites)
EXCLUDE_DOMAINS = [
    "wikipedia.org",
    "youtube.com",
    "reddit.com",
    "quora.com",
    "facebook.com",
    "twitter.com",
    "instagram.com",
]

# Initialize client
try:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    print(f"✓ Initialized Vertex AI")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Location: {LOCATION}")
    print(f"  Model: {MODEL_ID}\n")
except Exception as e:
    print(f"❌ Error initializing: {e}")
    exit(1)


def print_sources(response):
    """Extract and print source URLs with domain check."""
    if not response.candidates:
        return []

    candidate = response.candidates[0]
    metadata = getattr(candidate, "grounding_metadata", None)

    if not metadata:
        print("No grounding metadata found.")
        return []

    sources = []

    # Print search queries
    if metadata.web_search_queries:
        print("\nSearch queries:")
        for q in metadata.web_search_queries:
            print(f"  - {q}")

    # Print sources with domain check
    chunks = metadata.grounding_chunks
    if chunks:
        print(f"\n" + "-" * 60)
        print(f"SOURCES ({len(chunks)}):")
        print("-" * 60)

        preferred_count = 0
        for i, chunk in enumerate(chunks, 1):
            if chunk.web:
                domain = chunk.web.title.lower() if chunk.web.title else "unknown"
                is_preferred = any(d.split('.')[0] in domain for d in PREFERRED_DOMAINS)
                if is_preferred:
                    preferred_count += 1
                status = "✓" if is_preferred else "○"
                print(f"  {status} [{i}] {domain}")
                sources.append({"domain": domain, "preferred": is_preferred})

        print(f"\n  → {preferred_count}/{len(chunks)} from preferred automotive domains")
    else:
        print("\nNo sources found.")

    return sources


def search_car_specs(car_name: str):
    """Search for car specifications with domain preference."""

    print("="*70)
    print(f"SEARCHING: {car_name}")
    print("="*70)

    # Use excludeDomains to block unwanted sites
    google_search_tool = Tool(
        google_search=GoogleSearch(
            exclude_domains=EXCLUDE_DOMAINS
        )
    )

    # Build domain hints for prompt
    top_domains = ", ".join(PREFERRED_DOMAINS[:10])

    prompt = f"""Search for detailed specifications and reviews of {car_name}.

IMPORTANT: Prioritize information from these automotive websites:
{top_domains}

Find:
- Price range (ex-showroom and on-road)
- Engine options (petrol/diesel, power, torque)
- Mileage (ARAI and real-world)
- Safety features and ratings
- User reviews and expert opinions
- Key features (infotainment, comfort, off-road capability)

Return a comprehensive JSON with all specifications found."""

    print(f"\nSearching with exclude_domains: {EXCLUDE_DOMAINS[:3]}...")
    print(f"Preferred sources: {top_domains[:50]}...\n")

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=GenerateContentConfig(
            tools=[google_search_tool],
            temperature=0.1,
        ),
    )

    print("-" * 70)
    print("RESPONSE:")
    print("-" * 70)
    print(response.text)

    print_sources(response)
    print()
    return response


def main():
    """Run automotive search tests."""

    print("\n" + "="*70)
    print("AUTOMOTIVE SPECIFICATIONS SEARCH")
    print("Using Google Search with excludeDomains + prompt engineering")
    print("="*70)
    print(f"\nNote: API only supports excludeDomains, not includeDomains.")
    print(f"Using prompt hints to guide searches to preferred domains.\n")

    try:
        # Search for car specs
        search_car_specs("Mahindra Thar Roxx 2024")

        print("="*70)
        print("DONE")
        print("="*70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
