from rest_framework import serializers
from fuel.models import Trip

class RoutePreviewSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=255)
    destination = serializers.CharField(max_length=255)
    starting_fuel = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=50
    )
    
class StartTripSerializer(serializers.Serializer):
    start = serializers.CharField()
    destination = serializers.CharField()

    start_latitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    start_longitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    destination_latitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    destination_longitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    total_distance_miles = serializers.FloatField()
    starting_fuel = serializers.FloatField()

    route_geometry = serializers.ListField()
    fuel_stations = serializers.ListField()
    recommended_stops = serializers.ListField()

class RefuelSerializer(serializers.Serializer):
    fuel_station_id = serializers.IntegerField()
    gallons = serializers.FloatField(min_value=0.01)