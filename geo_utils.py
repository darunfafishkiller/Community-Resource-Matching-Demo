"""
geo_utils.py

Small helper functions related to geographic locations.
"""

import random
from typing import Tuple


def generate_random_coordinates_ann_arbor() -> Tuple[float, float]:
    """
    Randomly sample a latitude/longitude pair in a small bounding box
    around the University of Michigan – Ann Arbor campus.

    This is intentionally very simple and is meant only for a
    **classroom demo**, not for precise geospatial modeling.
    """
    lat_min, lat_max = 42.27, 42.30
    lon_min, lon_max = -83.75, -83.71

    latitude = random.uniform(lat_min, lat_max)
    longitude = random.uniform(lon_min, lon_max)

    return latitude, longitude

