import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from fuel.models import FuelStation


class Command(BaseCommand):
    help = "Import fuel station data from geocoded CSV into database"

    def handle(self, *args, **options):
        csv_path = (
            Path(__file__).resolve().parents[3]
            / "datas"
            / "fuel-stations-geocoded.csv"
        )

        if not csv_path.exists():
            raise CommandError(
                f"CSV file not found: {csv_path}"
            )

        stations = []

        with csv_path.open(
            mode="r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            for row_number, row in enumerate(reader, start=2):
                try:
                    retail_price = Decimal(
                        row["Retail Price"].strip()
                    )

                    latitude = (
                        Decimal(row["latitude"].strip())
                        if row.get("latitude", "").strip()
                        else None
                    )

                    longitude = (
                        Decimal(row["longitude"].strip())
                        if row.get("longitude", "").strip()
                        else None
                    )

                    station = FuelStation(
                        opis_truckstop_id=row[
                            "OPIS Truckstop ID"
                        ].strip(),

                        name=row[
                            "Truckstop Name"
                        ].strip(),

                        address=row[
                            "Address"
                        ].strip(),

                        city=row[
                            "City"
                        ].strip(),

                        state=row[
                            "State"
                        ].strip(),

                        rack_id=int(
                            row["Rack ID"].strip()
                        ),

                        retail_price=retail_price,

                        latitude=latitude,
                        longitude=longitude,
                    )

                    stations.append(station)

                except (
                    KeyError,
                    ValueError,
                    InvalidOperation
                ) as error:

                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping row {row_number}: {error}"
                        )
                    )

        if not stations:
            raise CommandError(
                "No valid fuel station records found."
            )

        FuelStation.objects.bulk_create(
            stations,
            batch_size=1000
        )

        geocoded_count = sum(
            1
            for station in stations
            if station.latitude is not None
            and station.longitude is not None
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported "
                f"{len(stations)} fuel stations.\n"
                f"Stations with coordinates: "
                f"{geocoded_count}\n"
                f"Stations without coordinates: "
                f"{len(stations) - geocoded_count}"
            )
        )