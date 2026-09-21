def decode_polyline6(encoded):
    """
    Decode Valhalla's 6-digit precision encoded polyline.
    Returns a list of [latitude, longitude].
    """

    coordinates = []

    index = 0
    lat = 0
    lon = 0

    while index < len(encoded):
        # Decode latitude
        result = 0
        shift = 0

        while True:
            byte = ord(encoded[index]) - 63
            index += 1

            result |= (byte & 0x1F) << shift
            shift += 5

            if byte < 0x20:
                break

        delta_lat = (
            -(result >> 1)
            if result & 1
            else result >> 1
        )

        lat += delta_lat

        # Decode longitude
        result = 0
        shift = 0

        while True:
            byte = ord(encoded[index]) - 63
            index += 1

            result |= (byte & 0x1F) << shift
            shift += 5

            if byte < 0x20:
                break

        delta_lon = (
            -(result >> 1)
            if result & 1
            else result >> 1
        )

        lon += delta_lon

        coordinates.append([
            lat / 1e6,
            lon / 1e6
        ])

    return coordinates

def simplify_route(points, tolerance=0.0015):
    """
    Simplify route geometry using the
    Ramer-Douglas-Peucker algorithm.

    Used only for map display.
    Actual route distance remains the
    distance returned by Valhalla.
    """

    if len(points) <= 2:
        return points

    def perpendicular_distance(point, start, end):
        x, y = point
        x1, y1 = start
        x2, y2 = end

        dx = x2 - x1
        dy = y2 - y1

        if dx == 0 and dy == 0:
            return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5

        t = ((x - x1) * dx + (y - y1) * dy) / (
            dx * dx + dy * dy
        )

        t = max(0, min(1, t))

        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        return (
            (x - closest_x) ** 2
            + (y - closest_y) ** 2
        ) ** 0.5

    def rdp(points):
        if len(points) <= 2:
            return points

        start = points[0]
        end = points[-1]

        max_distance = 0
        index = 0

        for i in range(1, len(points) - 1):
            distance = perpendicular_distance(
                points[i],
                start,
                end
            )

            if distance > max_distance:
                max_distance = distance
                index = i

        if max_distance > tolerance:
            left = rdp(points[:index + 1])
            right = rdp(points[index:])

            return left[:-1] + right

        return [start, end]

    return rdp(points)