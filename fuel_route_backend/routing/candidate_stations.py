import re

from django.db.models import Q

from fuel.models import FuelStation


HIGHWAY_PATTERN = re.compile(
    r"\b(?:I[- ]?\d+|US[- ]?\d+|SR[- ]?\d+|SH[- ]?\d+|STATE ROUTE[- ]?\d+)\b",
    re.IGNORECASE,
)


def extract_highways(address):
    if not address:
        return []

    matches = HIGHWAY_PATTERN.findall(address)

    normalized = []

    for highway in matches:
        highway = highway.upper()
        highway = re.sub(r"\s*-\s*", "-", highway)
        highway = re.sub(r"\s+", " ", highway)

        normalized.append(highway)

    return list(dict.fromkeys(normalized))


def get_highway_candidates(highways):
    if not highways:
        return FuelStation.objects.none()

    query = Q()

    for highway in highways:
        query |= Q(address__icontains=highway)

    return FuelStation.objects.filter(query).order_by(
        "state",
        "city",
        "name",
    )


def get_route_candidates(route_states, route_roads=None):
    route_roads = route_roads or []

    state_query = Q()

    for state in route_states:
        state_query |= Q(state__iexact=state)

    queryset = FuelStation.objects.filter(state_query)

    if route_roads:
        road_query = Q()

        for road in route_roads:
            road_query |= Q(address__icontains=road)

        queryset = queryset.filter(road_query)

    return queryset.order_by(
        "state",
        "city",
        "name",
    )