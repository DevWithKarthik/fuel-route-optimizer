import re
import time

from django.core.management.base import BaseCommand
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from fuel.models import FuelStation


REQUEST_DELAY = 1.1


def clean_station_name(name):
    """
    Remove OPIS-specific numbering and normalize common
    truck-stop naming variations.
    """
    if not name:
        return ""

    value = name.upper().strip()

    # Remove # numbers
    value = re.sub(r"\s*#\s*\d+[A-Z-]*", "", value)

    # Remove trailing numeric identifiers
    value = re.sub(r"\s+\d+$", "", value)

    # Normalize common naming differences
    replacements = {
        "TRAVEL CENTERS": "TRAVEL CENTER",
        "TRAVEL PLAZAS": "TRAVEL PLAZA",
        "TRAVEL STOPS": "TRAVEL STOP",
        "TRUCK STOPS": "TRUCK STOP",
        "TRUCKSTOP": "TRUCK STOP",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def remove_generic_words(name):
    """
    Produce a shorter brand-oriented query.
    """
    if not name:
        return ""

    value = clean_station_name(name)

    generic_words = [
        "TRAVEL CENTER",
        "TRAVEL PLAZA",
        "TRAVEL STOP",
        "TRUCK STOP",
        "TRUCK CENTER",
        "FUEL CENTER",
        "FUEL STOP",
        "FOOD STORE",
        "FOOD & FUEL",
        "STOPPING CENTER",
    ]

    for word in generic_words:
        value = value.replace(word, "")

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def extract_highway(address):
    """
    Extract highway such as I-75, I-40, I-10.
    """
    if not address:
        return None

    match = re.search(
        r"\bI[- ]?(\d{1,3})\b",
        address.upper(),
    )

    if not match:
        return None

    return f"I-{match.group(1)}"


def extract_exit(address):
    """
    Extract exit number such as:
    EXIT 144-B
    EXIT 359
    EXIT 200
    """
    if not address:
        return None

    match = re.search(
        r"\bEXIT\s+([A-Z0-9-]+)",
        address.upper(),
    )

    if not match:
        return None

    return match.group(1)


def build_queries(station):
    """
    Build multiple geocoding queries.

    We deliberately avoid using the full OPIS address
    as the first query because many OPIS addresses are
    highway/exit descriptions rather than street addresses.
    """

    name = station.name.strip()
    clean_name = clean_station_name(name)
    brand_name = remove_generic_words(name)

    city = station.city.strip()
    state = station.state.strip()

    queries = []

    # ---------------------------------------------------------
    # 1. Original truck-stop name
    # ---------------------------------------------------------

    if name:
        queries.append(
            f"{name}, {city}, {state}, USA"
        )

    # ---------------------------------------------------------
    # 2. Cleaned truck-stop name
    # ---------------------------------------------------------

    if clean_name and clean_name != name.upper():
        queries.append(
            f"{clean_name}, {city}, {state}, USA"
        )

    # ---------------------------------------------------------
    # 3. Brand-oriented search
    # ---------------------------------------------------------

    if brand_name and len(brand_name) >= 3:
        queries.append(
            f"{brand_name}, {city}, {state}, USA"
        )

    # ---------------------------------------------------------
    # 4. Highway + Exit
    # ---------------------------------------------------------

    highway = extract_highway(station.address)
    exit_number = extract_exit(station.address)

    if highway and exit_number:
        queries.append(
            f"{highway} Exit {exit_number}, "
            f"{city}, {state}, USA"
        )

    # ---------------------------------------------------------
    # 5. Highway + City + State
    # ---------------------------------------------------------

    if highway:
        queries.append(
            f"{highway}, {city}, {state}, USA"
        )

    # Remove duplicates while preserving order
    unique_queries = []

    for query in queries:
        query = query.strip()

        if query and query not in unique_queries:
            unique_queries.append(query)

    return unique_queries


def result_is_reasonable(location, station):
    """
    Basic validation.

    We do not accept a completely unrelated result.

    If Nominatim returns a result containing the expected
    city/state, it is considered usable.

    We intentionally do NOT use city-center coordinates
    when no actual result was found.
    """

    address = (location.address or "").upper()

    city = station.city.upper().strip()
    state = station.state.upper().strip()

    city_match = city in address

    # State can appear as abbreviation or full name.
    state_match = state in address

    return city_match and state_match


class Command(BaseCommand):

    help = (
        "Geocode missing fuel stations using multiple "
        "POI and highway-based queries."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process this many missing stations",
        )

        parser.add_argument(
            "--reset",
            action="store_true",
            help="Re-geocode stations that already have coordinates",
        )

    def handle(self, *args, **options):

        limit = options["limit"]
        reset = options["reset"]

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "========== MULTI-FALLBACK GEOCODING =========="
            )
        )

        queryset = FuelStation.objects.all().order_by("id")

        if not reset:
            queryset = queryset.filter(
                latitude__isnull=True,
                longitude__isnull=True,
            )

        if limit:
            queryset = queryset[:limit]

        stations = list(queryset)

        if not stations:

            self.stdout.write(
                self.style.SUCCESS(
                    "No stations need geocoding."
                )
            )

            return

        self.stdout.write(
            f"Stations to process: {len(stations)}"
        )

        geolocator = Nominatim(
            user_agent="fuel-route-optimizer/1.0"
        )

        updated = 0
        no_result = 0
        errors = 0

        # ---------------------------------------------------------
        # PROCESS
        # ---------------------------------------------------------

        for index, station in enumerate(
            stations,
            start=1,
        ):

            self.stdout.write("")
            self.stdout.write(
                f"[{index}/{len(stations)}] "
                f"{station.name}"
            )

            queries = build_queries(station)

            found = False

            for query_index, query in enumerate(
                queries,
                start=1,
            ):

                self.stdout.write(
                    f"  Try {query_index}: {query}"
                )

                try:

                    location = geolocator.geocode(
                        query,
                        timeout=20,
                        exactly_one=True,
                    )

                    if not location:
                        self.stdout.write(
                            "    → No result"
                        )

                        time.sleep(REQUEST_DELAY)
                        continue

                    if not result_is_reasonable(
                        location,
                        station,
                    ):

                        self.stdout.write(
                            "    → Result rejected "
                            "(city/state mismatch)"
                        )

                        time.sleep(REQUEST_DELAY)
                        continue

                    # -------------------------------------------------
                    # SAVE
                    # -------------------------------------------------

                    station.latitude = location.latitude
                    station.longitude = location.longitude

                    station.save(
                        update_fields=[
                            "latitude",
                            "longitude",
                            "updated_at",
                        ]
                    )

                    updated += 1
                    found = True

                    self.stdout.write(
                        self.style.SUCCESS(
                            "    ✓ MATCHED"
                        )
                    )

                    self.stdout.write(
                        f"    Latitude: "
                        f"{location.latitude}"
                    )

                    self.stdout.write(
                        f"    Longitude: "
                        f"{location.longitude}"
                    )

                    self.stdout.write(
                        f"    Location: "
                        f"{location.address}"
                    )

                    break

                except GeocoderTimedOut:

                    errors += 1

                    self.stdout.write(
                        "    → Timeout"
                    )

                except GeocoderServiceError as error:

                    errors += 1

                    self.stdout.write(
                        f"    → Service error: {error}"
                    )

                except Exception as error:

                    errors += 1

                    self.stdout.write(
                        f"    → Error: {error}"
                    )

                time.sleep(REQUEST_DELAY)

            if not found:

                no_result += 1

                self.stdout.write(
                    self.style.WARNING(
                        "  ✗ No reliable coordinate found"
                    )
                )

            # Small delay between stations
            time.sleep(REQUEST_DELAY)

        # ---------------------------------------------------------
        # FINAL SUMMARY
        # ---------------------------------------------------------

        remaining = FuelStation.objects.filter(
            latitude__isnull=True,
            longitude__isnull=True,
        ).count()

        total = FuelStation.objects.count()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "========== GEOCODING COMPLETED =========="
            )
        )

        self.stdout.write(
            f"Processed: {len(stations)}"
        )

        self.stdout.write(
            f"Coordinates updated: {updated}"
        )

        self.stdout.write(
            f"No reliable result: {no_result}"
        )

        self.stdout.write(
            f"Errors: {errors}"
        )

        self.stdout.write(
            f"Total stations: {total}"
        )

        self.stdout.write(
            f"Still missing coordinates: {remaining}"
        )