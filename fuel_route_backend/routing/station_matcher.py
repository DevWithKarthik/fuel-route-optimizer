import math


def haversine_distance_miles(lat1, lon1, lat2, lon2):
    earth_radius_miles = 3958.8

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.asin(math.sqrt(a))

    return earth_radius_miles * c


def calculate_route_distances(route_coordinates):
    """
    Calculate cumulative distance at every point
    along the route.

    Returns:
        [
            0.0,
            0.8,
            1.6,
            ...
        ]
    """

    cumulative = [0.0]

    total = 0.0

    for i in range(1, len(route_coordinates)):

        previous = route_coordinates[i - 1]
        current = route_coordinates[i]

        segment_distance = haversine_distance_miles(
            previous[0],
            previous[1],
            current[0],
            current[1],
        )

        total += segment_distance

        cumulative.append(total)

    return cumulative


def find_nearby_stations(
    route_coordinates,
    stations,
    corridor_miles=5,
):
    """
    Find fuel stations close to the route.

    Also calculates the station's approximate
    mile position along the route.
    """

    cumulative_distances = calculate_route_distances(
        route_coordinates
    )

    results = []

    for station in stations:

        if station.latitude is None:
            continue

        if station.longitude is None:
            continue

        minimum_distance = float("inf")
        nearest_route_index = None

        for index, coordinate in enumerate(route_coordinates):

            distance = haversine_distance_miles(
                coordinate[0],
                coordinate[1],
                station.latitude,
                station.longitude,
            )

            if distance < minimum_distance:
                minimum_distance = distance
                nearest_route_index = index

        if minimum_distance <= corridor_miles:

            route_mile = cumulative_distances[
                nearest_route_index
            ]

            results.append({
                "id": station.id,
                "name": station.name,
                "address": station.address,
                "city": station.city,
                "state": station.state,
                "latitude": float(station.latitude),
                "longitude": float(station.longitude),
                "retail_price": float(station.retail_price),
                "distance_from_route": round(
                    minimum_distance,
                    2
                ),
                "route_mile": round(
                    route_mile,
                    2
                ),
            })

    results.sort(
        key=lambda station: station["route_mile"]
    )

    return results