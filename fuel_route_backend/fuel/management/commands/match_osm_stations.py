import re
import time
import requests

from django.core.management.base import BaseCommand
from django.db import transaction

from fuel.models import FuelStation


OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Continental USA bounding box.
# We query only fuel stations, not all OSM objects.
USA_BBOX = "24.396308,-125.0,49.384358,-66.93457"


def normalize(value):
    if not value:
        return ""

    value = value.upper()
    value = value.replace("&", " AND ")

    value = re.sub(r"[^A-Z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def similarity(a, b):
    a = normalize(a)
    b = normalize(b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    if a in b or b in a:
        return 0.92

    a_words = set(a.split())
    b_words = set(b.split())

    if not a_words or not b_words:
        return 0.0

    intersection = len(a_words & b_words)
    union = len(a_words | b_words)

    return intersection / union


def extract_highways(address):
    if not address:
        return set()

    address = address.upper()

    matches = re.findall(
        r"\bI[- ]?(\d{1,3})\b",
        address
    )

    return {
        f"I-{number}"
        for number in matches
    }


def extract_osm_highways(tags):
    values = []

    for key in [
        "ref",
        "destination",
        "description",
        "addr:street",
    ]:
        value = tags.get(key, "")
        if value:
            values.append(value)

    text = " ".join(values).upper()

    matches = re.findall(
        r"\bI[- ]?(\d{1,3})\b",
        text
    )

    return {
        f"I-{number}"
        for number in matches
    }


def query_overpass():
    query = f"""
    [out:json][timeout:900];

    (
      node["amenity"="fuel"]({USA_BBOX});
      way["amenity"="fuel"]({USA_BBOX});
      relation["amenity"="fuel"]({USA_BBOX});
    );

    out center tags;
    """

    print("Downloading USA OSM fuel stations...")
    print("This is ONE request only.")

    response = requests.post(
        OVERPASS_URL,
        data=query,
        timeout=1000,
        headers={
            "User-Agent": "fuel-route-optimizer/1.0"
        },
    )

    response.raise_for_status()

    return response.json()


def get_coordinates(element):
    if element["type"] == "node":
        return (
            element.get("lat"),
            element.get("lon"),
        )

    center = element.get("center", {})

    return (
        center.get("lat"),
        center.get("lon"),
    )


def build_osm_station(element):
    tags = element.get("tags", {})

    latitude, longitude = get_coordinates(element)

    if latitude is None or longitude is None:
        return None

    name = (
        tags.get("name")
        or tags.get("brand")
        or tags.get("operator")
        or ""
    )

    if not name:
        return None

    return {
        "osm_id": f'{element["type"]}/{element["id"]}',
        "name": name,
        "brand": tags.get("brand", ""),
        "operator": tags.get("operator", ""),
        "city": tags.get("addr:city", ""),
        "state": tags.get("addr:state", ""),
        "postcode": tags.get("addr:postcode", ""),
        "street": tags.get("addr:street", ""),
        "ref": tags.get("ref", ""),
        "latitude": latitude,
        "longitude": longitude,
        "highways": extract_osm_highways(tags),
    }


def load_osm_stations():
    data = query_overpass()

    stations = []

    for element in data.get("elements", []):
        station = build_osm_station(element)

        if station:
            stations.append(station)

    return stations


def state_matches(opis_state, osm_state):
    if not osm_state:
        return True

    return normalize(opis_state) == normalize(osm_state)


def score_match(opis, osm):
    name = normalize(opis.name)

    osm_name = normalize(osm["name"])
    osm_brand = normalize(osm["brand"])
    osm_operator = normalize(osm["operator"])

    city_score = similarity(
        opis.city,
        osm["city"]
    )

    name_score = max(
        similarity(name, osm_name),
        similarity(name, osm_brand),
        similarity(name, osm_operator),
    )

    highway_score = 0.0

    opis_highways = extract_highways(opis.address)
    osm_highways = osm["highways"]

    if opis_highways and osm_highways:
        if opis_highways & osm_highways:
            highway_score = 1.0

    # Strong city match is extremely important.
    if city_score < 0.80:
        return 0.0

    score = (
        name_score * 0.60
        + city_score * 0.30
        + highway_score * 0.10
    )

    return score


def find_best_match(opis, osm_stations):
    best = None
    best_score = 0.0

    for osm in osm_stations:

        if not state_matches(
            opis.state,
            osm["state"]
        ):
            continue

        score = score_match(opis, osm)

        if score > best_score:
            best_score = score
            best = osm

    return best, best_score


class Command(BaseCommand):

    help = (
        "Download USA OSM fuel stations once and "
        "match them locally against OPIS fuel stations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-score",
            type=float,
            default=0.82,
        )

    def handle(self, *args, **options):

        min_score = options["min_score"]

        # ---------------------------------------------------------
        # STEP 1
        # ---------------------------------------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "========== USA OSM FUEL STATIONS =========="
            )
        )

        try:
            osm_stations = load_osm_stations()

        except requests.RequestException as error:

            self.stdout.write(
                self.style.ERROR(
                    f"OSM download failed: {error}"
                )
            )

            return

        self.stdout.write(
            self.style.SUCCESS(
                f"OSM fuel stations downloaded: "
                f"{len(osm_stations)}"
            )
        )

        # ---------------------------------------------------------
        # STEP 2
        # ---------------------------------------------------------

        opis_stations = list(
            FuelStation.objects.filter(
                latitude__isnull=True,
                longitude__isnull=True,
            ).order_by("id")
        )

        self.stdout.write(
            f"OPIS stations requiring coordinates: "
            f"{len(opis_stations)}"
        )

        updated = 0
        unmatched = 0

        # ---------------------------------------------------------
        # STEP 3
        # ---------------------------------------------------------

        for index, opis in enumerate(
            opis_stations,
            start=1
        ):

            best, score = find_best_match(
                opis,
                osm_stations,
            )

            if not best or score < min_score:

                unmatched += 1

                if index % 100 == 0:

                    self.stdout.write(
                        f"[{index}/{len(opis_stations)}] "
                        f"matched={updated}, "
                        f"unmatched={unmatched}"
                    )

                continue

            with transaction.atomic():

                opis.latitude = best["latitude"]
                opis.longitude = best["longitude"]

                opis.save(
                    update_fields=[
                        "latitude",
                        "longitude",
                        "updated_at",
                    ]
                )

            updated += 1

            if index % 25 == 0:

                self.stdout.write(
                    f"[{index}/{len(opis_stations)}] "
                    f"{opis.name} → "
                    f"{best['name']} "
                    f"score={score:.2f} "
                    f"({best['latitude']}, "
                    f"{best['longitude']})"
                )

        # ---------------------------------------------------------
        # FINAL
        # ---------------------------------------------------------

        missing = FuelStation.objects.filter(
            latitude__isnull=True,
            longitude__isnull=True,
        ).count()

        total = FuelStation.objects.count()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "========== COMPLETED =========="
            )
        )

        self.stdout.write(
            f"OSM stations: {len(osm_stations)}"
        )

        self.stdout.write(
            f"Updated: {updated}"
        )

        self.stdout.write(
            f"Unmatched: {unmatched}"
        )

        self.stdout.write(
            f"Total OPIS: {total}"
        )

        self.stdout.write(
            f"Still missing coordinates: {missing}"
        )