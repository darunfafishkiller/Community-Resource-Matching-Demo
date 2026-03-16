"""
map_view.py

Use Folium to plot matched provider resources on an interactive map.
"""

from typing import Any, Dict, List, Optional, Tuple

import folium


def create_provider_map(
    matches: List[Tuple[Dict[str, Any], float]],
    output_file: str = "resource_map.html",
    user_location: Optional[Tuple[float, float]] = None,
) -> Optional[str]:
    """
    Create a Folium map based on matching results and save it as an HTML file.

    Args:
      matches: list where each item is (provider_dict, similarity_score)
      output_file: output HTML filename
    """
    # Collect all points that have latitude/longitude
    points: List[Tuple[float, float, Dict[str, Any], float]] = []
    for provider, score in matches:
        lat = provider.get("latitude")
        lon = provider.get("longitude")
        if lat is None or lon is None:
            continue
        points.append((lat, lon, provider, score))

    if not points and not user_location:
        print("No latitude/longitude information to plot; cannot create map.")
        return None

    # Use the first provider point or the user point as the map center
    if points:
        first_lat, first_lon, _, _ = points[0]
    else:
        first_lat, first_lon = user_location  # type: ignore[misc]
    m = folium.Map(location=[first_lat, first_lon], zoom_start=13)

    def icon_color_for_category(category: str) -> str:
        """
        Map resource categories to simple marker colors for visualization.
        """
        mapping = {
            "equipment": "blue",
            "space": "green",
            "storage": "purple",
            "event_support": "orange",
            "transportation": "darkred",
            "materials": "cadetblue",
            "food_support": "red",
            "childcare": "pink",
            "volunteer_help": "lightgray",
        }
        return mapping.get((category or "").strip(), "gray")

    for lat, lon, provider, score in points:
        popup_lines = [
            f"ID: {provider.get('id', '')}",
            f"Category: {provider.get('resource_category')}",
            f"Description: {provider.get('resource_description')}",
            f"Quantity: {provider.get('quantity')}",
            f"Time: {provider.get('time_text')}",
            f"Location: {provider.get('location_text')}",
            f"Similarity: {score:.3f}",
            f"Original text: {provider.get('original_text', '')}",
        ]
        popup_html = "<br>".join(popup_lines)

        category = provider.get("resource_category") or ""
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=category or "resource",
            icon=folium.Icon(color=icon_color_for_category(category), icon="info-sign"),
        ).add_to(m)

    # If we have a user location, add a circle marker for it
    if user_location is not None:
        u_lat, u_lon = user_location
        folium.CircleMarker(
            location=[u_lat, u_lon],
            radius=8,
            color="black",
            fill=True,
            fill_color="yellow",
            fill_opacity=0.8,
            popup="User location",
            tooltip="You (query)",
        ).add_to(m)

    m.save(output_file)
    print(f"Map saved to: {output_file}")
    return output_file

