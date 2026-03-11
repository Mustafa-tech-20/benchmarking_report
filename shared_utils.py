"""
Shared utility functions across all agents
"""
import json
from json_repair import repair_json
from typing import Any, Dict, Optional


def safe_json_parse(json_string: str, fallback: Optional[Any] = None) -> Any:
    """
    Safely parse JSON with automatic repair for malformed JSON.

    Args:
        json_string: JSON string to parse
        fallback: Value to return if parsing fails (default: None)

    Returns:
        Parsed JSON object or fallback value
    """
    try:
        # First try with json-repair
        repaired = repair_json(json_string)
        return json.loads(repaired)
    except Exception as repair_error:
        # Fallback to standard JSON parsing
        try:
            return json.loads(json_string)
        except Exception as json_error:
            print(f"  JSON parsing failed: {str(json_error)[:100]}")
            return fallback


def clean_json_response(response_text: str) -> str:
    """
    Clean Gemini response to extract JSON.

    Args:
        response_text: Raw response from Gemini

    Returns:
        Cleaned JSON string
    """
    # Remove markdown code blocks
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join([line for line in lines if not line.strip().startswith("```")])

    # Remove "json" prefix
    if response_text.strip().startswith("json"):
        response_text = response_text.strip()[4:].strip()

    return response_text.strip()
