import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


def sample_route(route_coordinates, interval=50):
    """
    Sample approximately every `interval` miles
    along the route.
    """

    from routing.station_matcher import (
        calculate_route_distances,
    )

    cumulative = calculate_route_distances(
        route_coordinates
    )

    samples = []

    next_mile = 0

    for index, distance in enumerate(cumulative):

        if distance >= next_mile:
            samples.append({
                "route_mile": round(distance, 2),
                "latitude": route_coordinates[index][0],
                "longitude": route_coordinates[index][1],
            })

            next_mile += interval

    return samples


def reverse_geocode_point(latitude, longitude):
    response = requests.get(
        NOMINATIM_URL,
        params={
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "zoom": 10,
        },
        headers={
            "User-Agent": "fuel-route-optimizer/1.0"
        },
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()

    return data.get("address", {})