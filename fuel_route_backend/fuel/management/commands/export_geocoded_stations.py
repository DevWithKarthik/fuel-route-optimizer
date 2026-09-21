import csv
import os

from django.core.management.base import BaseCommand
from fuel.models import FuelStation


class Command(BaseCommand):
    help = "Export all fuel stations with stored latitude and longitude"

    def handle(self, *args, **options):
        output_dir = "datas"
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(
            output_dir,
            "fuel-stations-geocoded.csv"
        )

        stations = FuelStation.objects.all().order_by("id")

        total = stations.count()
        geocoded = stations.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).count()

        with open(output_file, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            writer.writerow([
                "OPIS Truckstop ID",
                "Truckstop Name",
                "Address",
                "City",
                "State",
                "Rack ID",
                "Retail Price",
                "latitude",
                "longitude",
            ])

            for station in stations:
                writer.writerow([
                    station.opis_truckstop_id,
                    station.name,
                    station.address,
                    station.city,
                    station.state,
                    station.rack_id,
                    station.retail_price,
                    station.latitude if station.latitude is not None else "",
                    station.longitude if station.longitude is not None else "",
                ])

        self.stdout.write(
            self.style.SUCCESS(
                f"Export completed successfully.\n"
                f"Total stations: {total}\n"
                f"Stations with coordinates: {geocoded}\n"
                f"Stations without coordinates: {total - geocoded}\n"
                f"File: {output_file}"
            )
        )