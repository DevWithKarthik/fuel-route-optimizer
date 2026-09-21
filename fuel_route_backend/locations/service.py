from geopy.geocoders import Nominatim


geolocator = Nominatim(
    user_agent="fuel-route-optimizer"
)


def geocode_location(location):
    result = geolocator.geocode(
        location,
        timeout=10
    )

    if not result:
        raise ValueError(
            f"Location not found: {location}"
        )

    return {
        "latitude": result.latitude,
        "longitude": result.longitude,
        "display_name": result.address,
    }