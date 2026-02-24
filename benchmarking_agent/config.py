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

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GCS_FOLDER_PREFIX = "car-comparisons/"
SIGNED_URL_EXPIRATION_HOURS = 168  # URLs expire after 6 days
