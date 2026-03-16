"""
extract.py

Use an OpenAI LLM to extract structured information about community
resources from free-text input, and map them into an existing taxonomy.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

# Load .env (for OPENAI_API_KEY and other settings)
load_dotenv()

# Create an OpenAI client (reads API key from environment variables)
client = OpenAI()


def extract_resource_info_with_categories(
    user_text: str,
    existing_categories: List[str],
) -> Dict[str, Any]:
    """
    Use an LLM to extract structured fields and perform category mapping.

    Args:
      user_text: natural-language description (need or offer)
      existing_categories: list of currently known resource category names

    Expected fields (some free text, some normalized):
      - intent
      - user_type
      - item_description
      - quantity
      - time_text
      - location_text
      - resource_category   (prefer a value from existing_categories)
      - new_category        (only when no existing category fits)
      - latitude
      - longitude
      - provider_start_time_utc  (ISO 8601 string or null)
      - provider_end_time_utc    (ISO 8601 string or null)
      - seeker_start_time_utc    (ISO 8601 string or null)
      - seeker_end_time_utc      (ISO 8601 string or null)
      - expiry_time_utc          (ISO 8601 string or null)
      - original_text
    """
    # Current UTC time, so the model can interpret relative time expressions
    now_utc = datetime.now(timezone.utc).isoformat()

    # Put the category list into the prompt so the model can choose
    categories_str = ", ".join(existing_categories)

    system_instruction = (
        "You are an assistant that extracts structured information about "
        "community resources (needs or offers).\n\n"
        f"Current UTC time is: {now_utc}.\n\n"
        "You MUST respond with ONLY one valid JSON object and nothing else.\n\n"
        "Fields:\n"
        "- intent: one of ['need', 'offer', 'other']\n"
        "- user_type: one of ['provider', 'seeker', 'other']\n"
        "- item_description: short free-text description of the resource\n"
        "- quantity: short string describing approximate quantity\n"
        "- time_text: natural language time window or 'unspecified'\n"
        "- location_text: natural language location description\n"
        "- resource_category: choose ONE category from this list if possible: "
        f"[{categories_str}]\n"
        "- new_category: if and only if no existing category fits reasonably, "
        "set resource_category to 'other' and propose a short new_category name "
        "(like 'audio_equipment'); otherwise set new_category to null or ''\n"
        "- latitude: float if you can reasonably guess based on the city/location, else null\n"
        "- longitude: float if you can reasonably guess based on the city/location, else null\n"
        "- provider_start_time_utc: ISO 8601 string for when a provider's availability starts, "
        "or null if this does not apply\n"
        "- provider_end_time_utc: ISO 8601 string for when a provider's availability ends, "
        "or null if this does not apply\n"
        "- seeker_start_time_utc: ISO 8601 string for when a seeker's need starts, "
        "or null if this does not apply\n"
        "- seeker_end_time_utc: ISO 8601 string for when a seeker's need ends, "
        "or null if this does not apply\n"
        "- expiry_time_utc: ISO 8601 string for when this record should be considered expired "
        "based on the described time window (for example, 'next two weeks' means about 14 days "
        "from now), or null if unknown\n"
        "- original_text: copy of the original user input\n\n"
        "All *_time_utc fields should be either null or a valid ISO 8601 datetime in UTC "
        "(for example '2026-03-12T15:30:00+00:00').\n"
        "Do not include any explanations or extra text outside the JSON."
    )

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_text},
        ],
        temperature=0.1,
    )

    json_str = completion.choices[0].message.content.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback: if the model output is not strict JSON, return a minimal valid structure
        data = {
            "intent": "other",
            "user_type": "other",
            "item_description": user_text,
            "quantity": "unspecified",
            "time_text": "unspecified",
            "location_text": "unspecified",
            "resource_category": "other",
            "new_category": None,
            "latitude": None,
            "longitude": None,
            "provider_start_time_utc": None,
            "provider_end_time_utc": None,
            "seeker_start_time_utc": None,
            "seeker_end_time_utc": None,
            "expiry_time_utc": None,
            "original_text": user_text,
        }

    # Ensure original_text is always present
    data.setdefault("original_text", user_text)

    # Ensure resource_category is always present
    if not data.get("resource_category"):
        data["resource_category"] = "other"

    # Normalize new_category: treat empty string as None
    new_cat = data.get("new_category")
    if isinstance(new_cat, str) and not new_cat.strip():
        data["new_category"] = None

    # Heuristic: if the text mentions tables/chairs but the model chose event_support/other,
    # promote it to equipment to improve matching for table/chair requests.
    orig_lower = (data.get("original_text") or user_text).lower()
    current_cat = (data.get("resource_category") or "").strip().lower()
    if ("table" in orig_lower or "chair" in orig_lower) and current_cat in ("event_support", "other"):
        data["resource_category"] = "equipment"

    # Normalize coordinate types: if a value is a string, try to cast to float
    for key in ("latitude", "longitude"):
        value = data.get(key)
        if isinstance(value, str):
            try:
                data[key] = float(value)
            except ValueError:
                data[key] = None

    # Very small demo-friendly time fallback:
    # If this is a need (intent == 'need') and the text contains "this Saturday afternoon",
    # and seeker_* is still empty, fill the next Saturday 13:00-17:00 UTC.
    text_lower = data.get("original_text", user_text).lower()
    if (
        ("this saturday afternoon" in text_lower or "this saturday" in text_lower)
        and data.get("intent") == "need"
    ):
        if not data.get("seeker_start_time_utc") or not data.get("seeker_end_time_utc"):
            # Find the next Saturday from now_utc
            now_dt = datetime.fromisoformat(now_utc)
            weekday = now_dt.weekday()  # Monday=0 ... Sunday=6
            # Saturday = 5
            days_ahead = (5 - weekday) % 7
            target_date = now_dt.date() if days_ahead == 0 else (now_dt.date().fromordinal(now_dt.date().toordinal() + days_ahead))

            start_dt = datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=13,
                minute=0,
                tzinfo=timezone.utc,
            )
            end_dt = datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=17,
                minute=0,
                tzinfo=timezone.utc,
            )
            data["seeker_start_time_utc"] = start_dt.isoformat()
            data["seeker_end_time_utc"] = end_dt.isoformat()

            # Set expiry near the end of that day (simple demo behavior)
            expiry_dt = datetime(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
                hour=23,
                minute=0,
                tzinfo=timezone.utc,
            )
            data.setdefault("expiry_time_utc", expiry_dt.isoformat())

    return data

