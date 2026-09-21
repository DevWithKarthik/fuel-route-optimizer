import time
import re

from django.core.management.base import BaseCommand
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from fuel.models import FuelStation


STATION_IDS = [
    643,
    1419,
    1840,
    2355,
    2683,
    3376,
    3464,
    4564,
    5500,
    5863,
]


def build_geocode_query(station):
    address = station.address.upper()

    match = re.search(
        r"I[- ]?(\d+).*?EXIT\s+([A-Z0-9]+)",
        address
    )

    if match:
        interstate = match.group(1)
        exit_number = match.group(2)

        return (
            f"I-{interstate} Exit {exit_number}, "
            f"{station.city}, {station.state}, USA"
        )

    return (
        f"{station.city}, "
        f"{station.state}, USA"
    )


class Command(BaseCommand):
    help = "Geocode selected fuel stations and save coordinates"

    def handle(self, *args, **options):

        geolocator = Nominatim(
            user_agent="fuel-route-optimizer/1.0"
        )

        stations = FuelStation.objects.filter(
            id__in=STATION_IDS
        ).order_by("id")

        for station in stations:

            if station.latitude is not None and station.longitude is not None:
                self.stdout.write(
                    f"SKIP {station.id} - already has coordinates"
                )
                continue

            query = build_geocode_query(station)

            self.stdout.write(
                f"Geocoding {station.id}: {query}"
            )

            try:
                location = geolocator.geocode(
                    query,
                    timeout=15
                )

                if location:
                    station.latitude = location.latitude
                    station.longitude = location.longitude

                    station.save(
                        update_fields=[
                            "latitude",
                            "longitude",
                        ]
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ {location.latitude}, "
                            f"{location.longitude}"
                        )
                    )

                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "  ✗ No result"
                        )
                    )

            except (
                GeocoderTimedOut,
                GeocoderServiceError,
            ) as error:

                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ {error}"
                    )
                )

            time.sleep(1)