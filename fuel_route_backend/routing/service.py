import requests


VALHALLA_URL = "https://valhalla1.openstreetmap.de/route"


def get_route(start_lat, start_lon, end_lat, end_lon):
    payload = {
        "locations": [
            {
                "lat": start_lat,
                "lon": start_lon,
            },
            {
                "lat": end_lat,
                "lon": end_lon,
            },
        ],
        "costing": "auto",
        "directions_options": {
            "units": "miles",
        },
    }

    response = requests.post(
        VALHALLA_URL,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    trip = data["trip"]
    summary = trip["summary"]

    leg = trip["legs"][0]

    return {
        "distance_miles": summary["length"],
        "duration_seconds": summary["time"],
        "geometry": leg["shape"],
        "maneuvers": leg.get("maneuvers", []),
    }