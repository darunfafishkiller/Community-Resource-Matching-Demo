"""
main.py

Entry point for the command-line demo of the
"community resource AI matching" prototype. It:

1. Loads the resource taxonomy.
2. Seeds a few fake provider/seeker records.
3. Accepts one natural-language description (need or offer).
4. Uses an LLM to extract structured fields and map to categories.
5. Creates new categories when needed and inserts them into the DB.
6. Samples a random location near the University of Michigan – Ann Arbor.
7. Writes the extracted record into the database.
8. Uses embeddings to semantically match against existing providers.
9. Prints matched resources and generates a Folium map in the browser.
"""

import os
import subprocess
import sys
import webbrowser
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

import database
import embed_match
import map_view
from extract import extract_resource_info_with_categories
from geo_utils import generate_random_coordinates_ann_arbor


def print_matches(matches: List[Tuple[Dict[str, Any], float]]) -> None:
    """
    Print matched provider resources to the terminal in a compact format.
    """
    if not matches:
        print("No resources with sufficiently high similarity were found.")
        return

    print("\n=== Matched providers (similarity >= 0.5) ===")
    for provider, score in matches:
        print("------------------------------")
        print(f"ID: {provider.get('id')}")
        print(f"Similarity score: {score:.3f}")
        print(f"Category: {provider.get('resource_category')}")
        print(f"Description: {provider.get('resource_description')}")
        print(f"Quantity: {provider.get('quantity')}")
        print(f"Time: {provider.get('time_text')}")
        print(f"Location: {provider.get('location_text')}")
        print(f"Status: {provider.get('status')}")
        print(f"Provider window (UTC): {provider.get('provider_start_time_utc')} -> {provider.get('provider_end_time_utc')}")
        print(f"Seeker window (UTC): {provider.get('seeker_start_time_utc')} -> {provider.get('seeker_end_time_utc')}")
        print(f"Expiry time (UTC): {provider.get('expiry_time_utc')}")
        print(f"Original text: {provider.get('original_text')}")


def main() -> None:
    """
    Main entry point that wires together the full demo flow.
    """
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print(
            "Warning: OPENAI_API_KEY environment variable is not set.\n"
            "Create a .env file in the project root and set OPENAI_API_KEY "
            "before running the full pipeline.\n"
        )

    # a. Create tables (do not delete existing data)
    database.create_tables()

    # b. Seed the default taxonomy
    database.seed_default_categories()

    # c. Seed fake data only when the resources table is empty
    if database.get_resources_row_count() == 0:
        database.seed_fake_provider_records()
        database.seed_fake_seeker_records()
        print("Example provider and seeker records have been inserted into the database.")
    else:
        print("Existing resource data detected; skipping seeding of fake records.")

    # d. Read a single free-text input from the user (one line only; input() reads until Enter)
    print(
        "\nPlease enter ONE natural-language description about a resource need or offer (single line). For example:\n"
        "  We are organizing a small community workshop this Saturday afternoon and need around 3 folding tables and 25 chairs near the central library.\n"
    )
    user_text = input("Type your description (press Enter to use the default example):\n> ").strip()
    if not user_text:
        user_text = (
            "We are organizing a small community workshop this Saturday afternoon "
            "and need around 3 folding tables and 25 chairs near the central library in Ann Arbor."
        )
        print("\nUsing default example:")
        print(user_text)

    # e. Load current category list from the database
    categories = database.get_all_categories()

    # f. Use an LLM to extract structured information and map to categories
    extracted: Dict[str, Any] = extract_resource_info_with_categories(
        user_text=user_text,
        existing_categories=categories,
    )

    # g. If new_category is suggested, insert it into the taxonomy
    new_category = extracted.get("new_category")
    if new_category:
        print(f"\nDetected proposed new category: {new_category}. Inserting into category table.")
        database.insert_category_if_not_exists(new_category)
        if extracted.get("resource_category") == "other":
            extracted["resource_category"] = new_category

    # If the content clearly mentions tables/chairs but the category is event_support/other,
    # promote it to equipment (for both persistence and matching).
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

    # h. Sample a random user location and fill coordinates if missing
    user_lat, user_lon = generate_random_coordinates_ann_arbor()
    if extracted.get("latitude") is None or extracted.get("longitude") is None:
        extracted["latitude"] = user_lat
        extracted["longitude"] = user_lon

    # Map the model's item_description to our DB field resource_description
    if "resource_description" not in extracted and "item_description" in extracted:
        extracted["resource_description"] = extracted.get("item_description")

    # Default status
    extracted.setdefault("status", "available")

    # i. Insert the extracted record and keep the new demand id
    current_demand_id = database.insert_resource(extracted)
    print("User record has been written to the database.")

    # j. Fetch all provider records (includes expiry update + available filter)
    providers = database.fetch_all_providers()

    # If the current user is a seeker (intent == need), only match providers that offer resources
    user_intent = extracted.get("intent")
    user_type = extracted.get("user_type")
    if user_intent == "need" or user_type == "seeker":
        providers = [p for p in providers if p.get("intent") == "offer"]

        # If the seeker has a normalized time window, keep only providers with overlapping windows
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
                    # If the provider has no normalized time window, keep it (relaxed overlap)
                    return True
                latest_start = max(s_start_dt, p_start_dt)
                earliest_end = min(s_end_dt, p_end_dt)
                return latest_start <= earliest_end

            providers = [p for p in providers if windows_overlap(p)]

    # k. Matching logic:
    #    - If resource_category is clear (not other), match within that category and return top-5 by similarity.
    #    - Otherwise, apply a similarity threshold and return top-5.
    pref_cat = extracted.get("resource_category") or ""
    pref_cat_lower = pref_cat.strip().lower()
    same_cat_count = sum(
        1 for p in providers
        if (p.get("resource_category") or "").strip().lower() == pref_cat_lower
    )
    print("[DEBUG] preferred_category =", repr(pref_cat))
    print("[DEBUG] providers with same category =", same_cat_count)

    matches = embed_match.match_query_to_providers(
        query_text=user_text,
        providers=providers,
        similarity_threshold=0.5,
        preferred_category=extracted.get("resource_category"),
        top_k=5,
    )

    # l. Generate and open the map first (computer browser), then decide which record to match
    html_path = map_view.create_provider_map(
        matches,
        output_file="resource_map.html",
        user_location=(user_lat, user_lon),
    )
    if html_path:
        abs_path = os.path.abspath(html_path)
        try:
            webbrowser.open(f"file://{abs_path}")
        except Exception:
            pass
        if sys.platform == "darwin":
            try:
                subprocess.run(["open", abs_path], check=False)
            except Exception:
                pass
        print(f"Map generated (attempted to open in browser): {abs_path}")

    # m. Print matched results
    print_matches(matches)

    # n. After reviewing the map, optionally mark one resource as matched
    if matches:
        choice = input(
            "\nPlease review the map in your browser. To mark one record as matched, enter its ID (or press Enter to skip):\n> "
        ).strip()
        if choice.isdigit():
            chosen_id = int(choice)
            updated_provider = database.update_resource_status(chosen_id, "matched")
            updated_demand = database.update_resource_status(current_demand_id, "matched")
            if updated_provider:
                print(f"Provider resource ID {chosen_id} has been marked as matched.")
            if updated_demand:
                print(f"This demand ID {current_demand_id} has been marked as matched.")
            if updated_provider or updated_demand:
                print(f"Database file: {os.path.abspath(database.DB_NAME)} (refresh/reopen it in your IDE to see updates)")
            if not updated_provider and not updated_demand:
                print("No matching record found. Please double-check that the ID is correct.")


if __name__ == "__main__":
    main()

