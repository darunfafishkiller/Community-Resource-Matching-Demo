"""
pipeline.py

Shared end-to-end pipeline that turns:
  user_text → extraction → DB write → semantic matching.
Used by both main.py (CLI) and whatsapp_server.py (WhatsApp).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import database
import embed_match
from extract import extract_resource_info_with_categories
from geo_utils import generate_random_coordinates_ann_arbor


def run_matching_pipeline(user_text: str) -> Dict[str, Any]:
    """
    Run the end-to-end pipeline for a single user input:
    extract → write to DB → semantic matching.
    Returns current_demand_id, matches, user_lat, user_lon, extracted, etc.
    """
    categories = database.get_all_categories()
    extracted: Dict[str, Any] = extract_resource_info_with_categories(
        user_text=user_text,
        existing_categories=categories,
    )

    new_category = extracted.get("new_category")
    if new_category:
        database.insert_category_if_not_exists(new_category)
        if extracted.get("resource_category") == "other":
            extracted["resource_category"] = new_category

    text_for_table_chair = " ".join([
        user_text or "",
        extracted.get("original_text") or "",
        extracted.get("resource_description") or "",
        extracted.get("item_description") or "",
    ]).lower()
    if ("table" in text_for_table_chair or "chair" in text_for_table_chair) and (
        (extracted.get("resource_category") or "").strip().lower() in ("event_support", "other")
    ):
        extracted["resource_category"] = "equipment"

    user_lat, user_lon = generate_random_coordinates_ann_arbor()
    if extracted.get("latitude") is None or extracted.get("longitude") is None:
        extracted["latitude"] = user_lat
        extracted["longitude"] = user_lon

    if "resource_description" not in extracted and "item_description" in extracted:
        extracted["resource_description"] = extracted.get("item_description")
    extracted.setdefault("status", "available")

    current_demand_id = database.insert_resource(extracted)
    providers = database.fetch_all_providers()

    user_intent = extracted.get("intent")
    user_type = extracted.get("user_type")
    if user_intent == "need" or user_type == "seeker":
        providers = [p for p in providers if p.get("intent") == "offer"]

        s_start = extracted.get("seeker_start_time_utc")
        s_end = extracted.get("seeker_end_time_utc")

        def parse_iso(ts: Optional[str]) -> Optional[datetime]:
            if not ts:
                return None
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return None

        s_start_dt = parse_iso(s_start)
        s_end_dt = parse_iso(s_end)

        if s_start_dt and s_end_dt:
            def windows_overlap(p: Dict[str, Any]) -> bool:
                p_start_dt = parse_iso(p.get("provider_start_time_utc"))
                p_end_dt = parse_iso(p.get("provider_end_time_utc"))
                if not p_start_dt or not p_end_dt:
                    return True
                latest_start = max(s_start_dt, p_start_dt)
                earliest_end = min(s_end_dt, p_end_dt)
                return latest_start <= earliest_end

            providers = [p for p in providers if windows_overlap(p)]

    matches: List[Tuple[Dict[str, Any], float]] = embed_match.match_query_to_providers(
        query_text=user_text,
        providers=providers,
        similarity_threshold=0.5,
        preferred_category=extracted.get("resource_category"),
        top_k=5,
    )

    return {
        "current_demand_id": current_demand_id,
        "matches": matches,
        "user_lat": user_lat,
        "user_lon": user_lon,
        "extracted": extracted,
    }


def format_matches_for_reply(matches: List[Tuple[Dict[str, Any], float]]) -> str:
    """Format matching results as plain text, suitable for channels like WhatsApp."""
    if not matches:
        return (
            "No sufficiently similar resources were found. "
            "Please try again later or describe your need/offer in a different way."
        )
    lines = ["We found the following matching resources:\n"]
    for i, (provider, score) in enumerate(matches, 1):
        lines.append(f"[{i}] ID: {provider.get('id')} | similarity: {score:.2f}")
        lines.append(f"  Category: {provider.get('resource_category')}")
        lines.append(f"  Description: {provider.get('resource_description')}")
        lines.append(f"  Quantity: {provider.get('quantity')} | Time: {provider.get('time_text')}")
        lines.append(f"  Location: {provider.get('location_text')}")
        lines.append("")
    lines.append(
        "If you want to mark one of these as matched, please reply with its numeric ID. "
        "For the demo map view, open resource_map.html on a computer."
    )
    return "\n".join(lines)
