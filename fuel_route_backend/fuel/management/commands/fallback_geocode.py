import time
import requests

from django.core.management.base import BaseCommand
from fuel.models import FuelStation


ARCGIS_URL = (
    "https://geocode-api.arcgis.com/arcgis/rest/services/"
    "World/GeocodeServer/findAddressCandidates"
)


class Command(BaseCommand):
    help = "Fallback geocode fuel stations using ArcGIS"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of stations to process",
        )

    def handle(self, *args, **options):

        limit = options["limit"]

        queryset = FuelStation.objects.filter(
            latitude__isnull=True,
            longitude__isnull=True,
        ).order_by("id")

        if limit:
            queryset = queryset[:limit]

        stations = list(queryset)

        self.stdout.write(
            f"Stations to process: {len(stations)}"
        )

        updated = 0
        failed = 0

        for index, station in enumerate(stations, start=1):

            queries = [
                f"{station.name}, {station.city}, {station.state}, USA",
                f"{station.address}, {station.city}, {station.state}, USA",
            ]

            found = None

            for query in queries:

                self.stdout.write(
                    f"[{index}/{len(stations)}] Searching: {query}"
                )

                try:
                    response = requests.get(
                        ARCGIS_URL,
                        params={
                            "SingleLine": query,
                            "f": "json",
                            "maxLocations": 1,
                            "outFields": "*",
                        },
                        timeout=15,
                    )

                    response.raise_for_status()

                    data = response.json()

                    candidates = data.get("candidates", [])

                    if candidates:
                        candidate = candidates[0]

                        # Only accept reasonably confident matches.
                        score = candidate.get("score", 0)

                        if score >= 80:
                            location = candidate["location"]

                            found = (
                                float(location["y"]),
                                float(location["x"]),
                                score,
                            )
                            break

                except Exception as error:

                    self.stdout.write(
                        self.style.WARNING(
                            f"  Geocoder error: {error}"
                        )
                    )

            if found:

                latitude, longitude, score = found

                station.latitude = latitude
                station.longitude = longitude

                station.save(
                    update_fields=[
                        "latitude",
                        "longitude",
                        "updated_at",
                    ]
                )

                updated += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  FOUND: {latitude}, {longitude} "
                        f"(score={score})"
                    )
                )

            else:

                failed += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"  NOT FOUND: {station.name}"
                    )
                )

            # Small delay so we don't hammer the service.
            time.sleep(0.15)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Fallback geocoding completed."
            )
        )

        self.stdout.write(
            f"Updated: {updated}"
        )

        self.stdout.write(
            f"Failed: {failed}"
        )