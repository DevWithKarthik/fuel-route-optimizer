import csv
import io

import requests

from django.core.management.base import BaseCommand
from django.db import transaction

from fuel.models import FuelStation


CENSUS_URL = (
    "https://geocoding.geo.census.gov/"
    "geocoder/locations/addressbatch"
)

BATCH_SIZE = 9000


class Command(BaseCommand):
    help = "Batch geocode fuel stations using the US Census Geocoder"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process this many stations"
        )

        parser.add_argument(
            "--reset",
            action="store_true",
            help="Re-geocode stations even if coordinates exist"
        )

    def handle(self, *args, **options):

        limit = options["limit"]
        reset = options["reset"]

        queryset = FuelStation.objects.all().order_by("id")

        if not reset:
            queryset = queryset.filter(
                latitude__isnull=True,
                longitude__isnull=True
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

        csv_buffer = io.StringIO()

        writer = csv.writer(csv_buffer)

        # Census batch format:
        # Unique ID, Street, City, State, ZIP
        for station in stations:
            writer.writerow([
                station.id,
                station.address,
                station.city,
                station.state,
                "",
            ])

        csv_buffer.seek(0)

        self.stdout.write(
            "Sending batch to US Census Geocoder..."
        )

        try:
            response = requests.post(
                CENSUS_URL,
                params={
                    "benchmark": "Public_AR_Current",
                },
                files={
                    "addressFile": (
                        "fuel_stations.csv",
                        csv_buffer.getvalue().encode("utf-8"),
                        "text/csv",
                    )
                },
                timeout=180,
            )

            response.raise_for_status()

        except requests.RequestException as error:
            self.stdout.write(
                self.style.ERROR(
                    f"Census Geocoder request failed: {error}"
                )
            )
            return

        updated = 0
        no_match = 0
        errors = 0

        results = csv.reader(
            io.StringIO(
                response.content.decode(
                    "utf-8",
                    errors="replace"
                )
            )
        )

        for row in results:

            if len(row) < 3:
                errors += 1
                continue

            try:
                station_id = int(row[0])

                status = row[2].strip()

                if status != "Match":
                    no_match += 1
                    continue

                if len(row) < 6:
                    errors += 1
                    continue

                coordinates = row[5].strip()

                longitude, latitude = coordinates.split(",")

                latitude = float(latitude)
                longitude = float(longitude)

                with transaction.atomic():

                    station = FuelStation.objects.get(
                        id=station_id
                    )

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

            except Exception as error:
                errors += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"Could not process row: {error}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Geocoding completed."
            )
        )

        self.stdout.write(
            f"Updated coordinates: {updated}"
        )

        self.stdout.write(
            f"No match: {no_match}"
        )

        self.stdout.write(
            f"Errors: {errors}"
        )