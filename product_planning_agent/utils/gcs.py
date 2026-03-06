import time
import uuid
import json as json_module

import google.auth
from datetime import timedelta
from google.cloud import storage

from benchmarking_agent.config import GCS_BUCKET_NAME, GCS_FOLDER_PREFIX


def get_gcs_client():
    """Get GCS client - works both locally and in Cloud Run"""
    client = storage.Client()
    return client


def upload_html_to_gcs(html_content: str, gcs_destination_path: str) -> str:
    """
    Upload HTML content directly to GCS with proper headers for browser viewing.

    Args:
        html_content: HTML string content with embedded CSS/JS
        gcs_destination_path: Destination path in GCS (without gs://bucket/)

    Returns:
        GCS URI (gs://bucket/path)
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_destination_path)

        blob.content_type = "text/html; charset=utf-8"
        blob.cache_control = "public, max-age=3600"

        # Upload HTML content
        blob.upload_from_string(
            html_content,
            content_type="text/html; charset=utf-8"
        )

        # Set additional metadata after upload
        blob.metadata = {
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff"
        }
        blob.patch()

        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_destination_path}"
        print(f"    Uploaded HTML to GCS: {gcs_uri}")

        return gcs_uri

    except Exception as e:
        print(f" Failed to upload HTML to GCS: {e}")
        raise


def upload_json_to_gcs(json_content: str, gcs_destination_path: str) -> str:
    """
    Upload JSON content directly to GCS.

    Args:
        json_content: JSON string content
        gcs_destination_path: Destination path in GCS (without gs://bucket/)

    Returns:
        GCS URI (gs://bucket/path)
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_destination_path)

        # Set metadata for JSON
        blob.content_type = "application/json; charset=utf-8"
        blob.cache_control = "public, max-age=3600"

        # Upload JSON content directly
        blob.upload_from_string(
            json_content,
            content_type="application/json; charset=utf-8"
        )

        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{gcs_destination_path}"
        print(f"    Uploaded JSON to GCS: {gcs_uri}")

        return gcs_uri

    except Exception as e:
        print(f" Failed to upload JSON to GCS: {e}")
        raise


def generate_signed_url(gcs_path: str, expiration_minutes: int = 60) -> str:
    """Generate signed URL - works locally and in Cloud Run"""

    try:
        credentials, project = google.auth.default()

        # Create client
        client = storage.Client(credentials=credentials, project=project)
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)

        # For Cloud Run, we need to use the service account directly
        # This works with both local service account files and Cloud Run identity
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET"
        )

        print(f"    Generated signed URL (expires in {expiration_minutes} min)")
        return signed_url

    except Exception as e:
        print(f" Failed to generate signed URL: {e}")
        raise


def save_chart_to_gcs(html_content: str, folder_name: str) -> tuple[str, str]:
    """
    Upload HTML report directly to GCS and return GCS URI and browser-viewable signed URL.
    No local file is created. The HTML contains embedded CSS and JavaScript.

    Args:
        html_content: Complete HTML string with CSS/JS embedded
        folder_name: Folder name for organization (e.g., "car_comparison_20250124_123456")

    Returns:
        Tuple of (gcs_uri, signed_url)
    """
    # Generate unique filename with timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"report_{timestamp}_{unique_id}.html"

    print(f"\n Uploading interactive HTML report to Google Cloud Storage...")
    print(f"  Report contains: HTML + CSS + JavaScript + Charts")

    # Upload HTML content directly to GCS with proper headers
    gcs_path = f"{GCS_FOLDER_PREFIX}{folder_name}/{filename}"
    gcs_uri = upload_html_to_gcs(html_content, gcs_path)

    # Generate signed URL that opens in browser
    signed_url = generate_signed_url(gcs_path)

    print(f"  HTML Report ready!")
    print(f"  GCS: {gcs_uri}")
    print(f"  URL: {signed_url[:80]}...")
    print(f"  Click URL to view in browser")

    return gcs_uri, signed_url


def save_json_to_gcs(json_data: dict, folder_name: str) -> tuple[str, str]:
    """
    Upload JSON data directly to GCS and return GCS URI and signed URL.
    No local file is created.

    Args:
        json_data: Dictionary to convert to JSON
        folder_name: Folder name for organization

    Returns:
        Tuple of (gcs_uri, signed_url)
    """
    # Generate unique filename
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"data_{timestamp}_{unique_id}.json"

    print(f"\n Uploading JSON data to Google Cloud Storage...")

    # Convert dict to JSON string
    json_content = json_module.dumps(json_data, indent=2)

    # Upload JSON content directly to GCS
    gcs_path = f"{GCS_FOLDER_PREFIX}{folder_name}/{filename}"
    gcs_uri = upload_json_to_gcs(json_content, gcs_path)

    # Generate signed URL
    signed_url = generate_signed_url(gcs_path)

    print(f" JSON Data ready!")
    print(f" GCS: {gcs_uri}")
    print(f"      🔗 URL: {signed_url[:80]}...")

    return gcs_uri, signed_url
