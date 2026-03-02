import os
import vertexai
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-south1")
vertexai.init(project=PROJECT_ID, location=LOCATION)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

# Sites to search - Complete list from Custom Search Engine
# Prioritized: Indian sites first, then international, then regional
SEARCH_SITES = [
    # Tier 1: Indian sites (best for local market)
    "autocarindia.com",        # Top Indian auto publication
    "autocarpro.in",           # Industry focused
    "overdrive.in",            # Quality reviews
    "zigwheels.com",           # Spec comparison tool
    "zigwheels.ae",            # Middle East specs
    "egmcartech.com",          # Indian tech
    "motoringworld.in",        # Indian reviews
    "team-bhp.com",            # Forum with detailed data

    # Tier 2: Major international publications
    "autocar.co.uk",           # UK publication
    "autoblog.com",            # US major site
    "automobilemag.com",       # US magazine
    "just-auto.com",           # Industry news
    "leftlanenews.com",        # Auto news
    "jalopnik.com",            # Enthusiast site

    # Tier 3: Regional/Specialized (use if comparing regional cars)
    "paultan.org",             # Malaysia
    "autonetmagz.com",         # Indonesia
    "wandaloo.com",            # Morocco
    "automobile.tn",           # Tunisia
    "ksa.motory.com",          # Saudi Arabia
    "carnewschina.com",        # China
    "chinacartimes.com",       # China
    "chinaevs.org",            # China EVs
    "autohome.com.cn",         # China
    "autonews.gasgoo.com",     # China
    "response.jp",             # Japan
    "autoprove.net",           # Japan
    "noticias.r7.com",         # Brazil
    "chileautos.cl",           # Chile
    "evreporter.com",          # EV focused
    "insideevs.com",           # EV news

    # Tier 4: Specialized/Less useful
    "bestsellingcarsblog.com", # Sales data
    "autonews.com",            # News only
    "orovel.net",              # Battery specs
    "esource.com",             # Battery data
]

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GCS_FOLDER_PREFIX = "car-comparisons/"
SIGNED_URL_EXPIRATION_HOURS = 168  # URLs expire after 6 days
