from routing.service import get_route
from routing.geometry import decode_polyline6


result = get_route(
    32.7767,
    -96.7970,
    41.8781,
    -87.6298,
)

coordinates = decode_polyline6(result["geometry"])

print("Distance:", result["distance_miles"])
print("Number of route points:", len(coordinates))
print("First point:", coordinates[0])
print("Last point:", coordinates[-1])