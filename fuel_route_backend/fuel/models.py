from django.db import models

import uuid


class FuelStation(models.Model):
    
    opis_truckstop_id = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=50, db_index=True)

    rack_id = models.IntegerField()

    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    retail_price = models.DecimalField(max_digits=8, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"
    

class Trip(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
    ]

    trip_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    start = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)

    start_latitude = models.DecimalField(max_digits=10, decimal_places=7)
    start_longitude = models.DecimalField(max_digits=10, decimal_places=7)

    destination_latitude = models.DecimalField(max_digits=10, decimal_places=7)
    destination_longitude = models.DecimalField(max_digits=10, decimal_places=7)

    total_distance_miles = models.FloatField()

    starting_fuel = models.FloatField()
    current_fuel = models.FloatField(default=0)

    current_route_mile = models.FloatField(default=0)

    total_fuel_purchased = models.FloatField(default=0)
    total_money_spent = models.FloatField(default=0)

    # Store preview route so we don't call Valhalla again
    route_geometry = models.JSONField(default=list)

    # Store stations returned during preview
    fuel_stations = models.JSONField(default=list)

    # Store optimizer result
    recommended_stops = models.JSONField(default=list)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active"
    )

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.start} → {self.destination}"


class RefuelingEvent(models.Model):

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="refueling_events"
    )

    fuel_station = models.ForeignKey(
        "FuelStation",
        on_delete=models.PROTECT
    )

    route_mile = models.FloatField()

    gallons = models.FloatField()

    price_per_gallon = models.DecimalField(
        max_digits=10,
        decimal_places=6
    )

    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.trip} - {self.gallons} gallons"