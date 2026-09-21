from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .serializers import RoutePreviewSerializer, StartTripSerializer, RefuelSerializer

from locations.service import geocode_location
from routing.service import get_route
from routing.geometry import decode_polyline6, simplify_route
from routing.station_matcher import find_nearby_stations

from fuel.models import FuelStation, Trip
from optimizer.service import optimize_fuel_stops

from django.shortcuts import get_object_or_404
from fuel.models import Trip, FuelStation, RefuelingEvent

class RoutePreviewView(APIView):

    def post(self, request):
        serializer = RoutePreviewSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        start = serializer.validated_data["start"]
        destination = serializer.validated_data["destination"]
        starting_fuel = serializer.validated_data["starting_fuel"]

        try:
            # --------------------------------
            # 1. Geocode locations
            # --------------------------------
            start_location = geocode_location(start)
            destination_location = geocode_location(destination)

            # --------------------------------
            # 2. Get route
            # --------------------------------
            route = get_route(
                start_location["latitude"],
                start_location["longitude"],
                destination_location["latitude"],
                destination_location["longitude"],
            )

            # --------------------------------
            # 3. Decode + simplify route
            # --------------------------------
            route_coordinates = decode_polyline6(
                route["geometry"]
            )

            simplified_route = simplify_route(
                route_coordinates,
                tolerance=0.0015
            )

            # --------------------------------
            # 4. Get stations that have
            #    coordinates
            # --------------------------------
            stations = FuelStation.objects.filter(
                latitude__isnull=False,
                longitude__isnull=False,
            )

            # --------------------------------
            # 5. Find stations near route
            # --------------------------------
            nearby_stations = find_nearby_stations(
                simplified_route,
                stations,
                corridor_miles=10,
            )

            # --------------------------------
            # 6. Optimize fuel stops
            # --------------------------------
            recommended_stops = []

            if nearby_stations:
                recommended_stops = optimize_fuel_stops(
                    total_distance=route["distance_miles"],
                    starting_fuel=starting_fuel,
                    stations=nearby_stations,
                )

            # --------------------------------
            # 7. API response
            # --------------------------------
            return Response({
                "start": start_location,
                "destination": destination_location,

                "vehicle": {
                    "starting_fuel": starting_fuel,
                    "fuel_economy_mpg": 10,
                    "tank_capacity_gallons": 50,
                },

                "route": {
                    "distance_miles": route["distance_miles"],
                    "duration_seconds": route["duration_seconds"],
                    "coordinates": simplified_route,
                },

                "fuel_stations": nearby_stations,

                "recommended_stops": recommended_stops,
            })

        except ValueError as error:
            return Response(
                {"error": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as error:
            return Response(
                {"error": str(error)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StartTripView(APIView):

    def post(self, request):

        serializer = StartTripSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        trip = Trip.objects.create(
            start=data["start"],
            destination=data["destination"],

            start_latitude=data["start_latitude"],
            start_longitude=data["start_longitude"],

            destination_latitude=data["destination_latitude"],
            destination_longitude=data["destination_longitude"],

            total_distance_miles=data["total_distance_miles"],

            starting_fuel=data["starting_fuel"],
            current_fuel=data["starting_fuel"],

            current_route_mile=0,
            total_fuel_purchased=0,
            total_money_spent=0,

            route_geometry=data["route_geometry"],
            fuel_stations=data["fuel_stations"],
            recommended_stops=data["recommended_stops"],

            status="active",
        )

        return Response(
            {
                "message": "Trip started successfully",

                "trip_id": str(trip.trip_id),

                "start": trip.start,
                "destination": trip.destination,

                "total_distance_miles": trip.total_distance_miles,

                "starting_fuel": trip.starting_fuel,
                "current_fuel": trip.current_fuel,

                "current_route_mile": trip.current_route_mile,

                "total_fuel_purchased": trip.total_fuel_purchased,
                "total_money_spent": trip.total_money_spent,

                "status": trip.status,
            },
            status=status.HTTP_201_CREATED
        )
        
        

class RefuelView(APIView):

    def post(self, request, trip_id):

        trip = get_object_or_404(
            Trip,
            trip_id=trip_id,
            status="active",
        )

        serializer = RefuelSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        fuel_station_id = serializer.validated_data[
            "fuel_station_id"
        ]

        gallons = serializer.validated_data[
            "gallons"
        ]

        station = get_object_or_404(
            FuelStation,
            id=fuel_station_id,
        )

        # Find station from the route preview data
        station_data = next(
            (
                item
                for item in trip.fuel_stations
                if int(item.get("id", 0)) == station.id
            ),
            None,
        )

        if station_data is None:
            return Response(
                {
                    "error": (
                        "This fuel station is not "
                        "part of the trip route."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Support both backend snake_case and
        # frontend camelCase station data.
        station_route_mile = station_data.get(
            "route_mile"
        )

        if station_route_mile is None:
            station_route_mile = station_data.get(
                "routeMile"
            )

        if station_route_mile is None:
            return Response(
                {
                    "error": (
                        "Fuel station route position "
                        "is missing."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        station_route_mile = float(
            station_route_mile
        )

        # Prevent travelling backwards
        if (
            station_route_mile
            < trip.current_route_mile
        ):
            return Response(
                {
                    "error": (
                        "This fuel station is behind "
                        "the current trip position."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Vehicle assumptions
        MPG = 10
        TANK_CAPACITY = 50

        # Distance travelled since the last
        # confirmed trip position
        distance_since_last_stop = (
            station_route_mile
            - trip.current_route_mile
        )

        # Fuel consumed to reach the station
        fuel_consumed = (
            distance_since_last_stop / MPG
        )

        # Fuel remaining when reaching station
        fuel_at_station = (
            trip.current_fuel
            - fuel_consumed
        )

        if fuel_at_station < 0:
            return Response(
                {
                    "error": (
                        "This station is not "
                        "reachable with the current fuel."
                    ),
                    "current_fuel": round(
                        trip.current_fuel,
                        2,
                    ),
                    "fuel_required": round(
                        fuel_consumed,
                        2,
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check tank capacity
        if (
            fuel_at_station + gallons
            > TANK_CAPACITY
        ):
            max_gallons = (
                TANK_CAPACITY
                - fuel_at_station
            )

            return Response(
                {
                    "error": (
                        "Refueling amount exceeds "
                        "tank capacity."
                    ),
                    "fuel_at_station": round(
                        fuel_at_station,
                        2,
                    ),
                    "max_gallons": round(
                        max_gallons,
                        2,
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use the actual DB station price
        price = float(
            station.retail_price
        )

        total_cost = (
            gallons * price
        )

        # Updated live fuel balance
        updated_fuel = (
            fuel_at_station
            + gallons
        )

        # Save refueling event
        RefuelingEvent.objects.create(
            trip=trip,
            fuel_station=station,
            route_mile=station_route_mile,
            gallons=gallons,
            price_per_gallon=(
                station.retail_price
            ),
            total_cost=total_cost,
        )

        # Update trip
        trip.current_fuel = updated_fuel

        trip.current_route_mile = (
            station_route_mile
        )

        trip.total_fuel_purchased += (
            gallons
        )

        trip.total_money_spent += (
            total_cost
        )

        trip.save()

        # Calculate remaining trip
        remaining_distance = max(
            0,
            trip.total_distance_miles
            - trip.current_route_mile,
        )

        # Calculate current available range
        available_range = (
            trip.current_fuel * MPG
        )

        return Response(
            {
                "message": (
                    "Refueling recorded "
                    "successfully"
                ),

                "trip_id": str(
                    trip.trip_id
                ),

                "fuel_station": {
                    "id": station.id,
                    "name": station.name,
                    "city": station.city,
                    "state": station.state,
                    "price_per_gallon": price,
                },

                "refueling": {
                    "gallons": round(
                        gallons,
                        2,
                    ),
                    "total_cost": round(
                        total_cost,
                        2,
                    ),
                },

                "trip": {
                    "current_route_mile": round(
                        trip.current_route_mile,
                        2,
                    ),

                    "current_fuel": round(
                        trip.current_fuel,
                        2,
                    ),

                    "available_range_miles": round(
                        available_range,
                        2,
                    ),

                    "remaining_distance_miles": round(
                        remaining_distance,
                        2,
                    ),

                    "total_fuel_purchased": round(
                        trip.total_fuel_purchased,
                        2,
                    ),

                    "total_money_spent": round(
                        trip.total_money_spent,
                        2,
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )
        
        

class TripStatusView(APIView):

    def get(self, request, trip_id):

        trip = get_object_or_404(
            Trip,
            trip_id=trip_id,
        )

        MPG = 10

        remaining_distance = max(
            trip.total_distance_miles - trip.current_route_mile,
            0,
        )

        available_range = trip.current_fuel * MPG

        destination_reachable = (
            available_range >= remaining_distance
        )

        # Refueling history
        refueling_history = []

        for event in trip.refueling_events.select_related(
            "fuel_station"
        ).order_by("created_at"):

            refueling_history.append({
                "station_id": event.fuel_station.id,
                "station_name": event.fuel_station.name,
                "city": event.fuel_station.city,
                "state": event.fuel_station.state,
                "route_mile": round(event.route_mile, 2),
                "gallons": round(event.gallons, 2),
                "price_per_gallon": float(
                    event.price_per_gallon
                ),
                "total_cost": float(
                    event.total_cost
                ),
                "created_at": event.created_at,
            })

        return Response({
            "trip_id": str(trip.trip_id),

            "status": trip.status,

            "start": trip.start,
            "destination": trip.destination,

            "trip": {
                "total_distance_miles": round(
                    trip.total_distance_miles,
                    2,
                ),
                "current_route_mile": round(
                    trip.current_route_mile,
                    2,
                ),
                "remaining_distance_miles": round(
                    remaining_distance,
                    2,
                ),

                "starting_fuel": round(
                    trip.starting_fuel,
                    2,
                ),
                "current_fuel": round(
                    trip.current_fuel,
                    2,
                ),

                "available_range_miles": round(
                    available_range,
                    2,
                ),

                "total_fuel_purchased": round(
                    trip.total_fuel_purchased,
                    2,
                ),

                "total_money_spent": round(
                    trip.total_money_spent,
                    2,
                ),

                "destination_reachable": (
                    destination_reachable
                ),
            },

            "fuel_stations": trip.fuel_stations,

            "recommended_stops": (
                trip.recommended_stops
            ),

            "refueling_history": refueling_history,
        })
        
        
        
class FinishTripView(APIView):

    def post(self, request, trip_id):

        trip = get_object_or_404(
            Trip,
            trip_id=trip_id,
            status="active",
        )

        MPG = 10

        # Distance still remaining
        remaining_distance = max(
            trip.total_distance_miles - trip.current_route_mile,
            0,
        )

        # Fuel required to complete the remaining distance
        fuel_required = remaining_distance / MPG

        # Fuel after reaching destination
        final_fuel = trip.current_fuel - fuel_required

        if final_fuel < 0:
            return Response(
                {
                    "error": "Destination cannot be reached with the current fuel.",
                    "current_fuel": round(
                        trip.current_fuel,
                        2,
                    ),
                    "fuel_required": round(
                        fuel_required,
                        2,
                    ),
                    "additional_fuel_required": round(
                        abs(final_fuel),
                        2,
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Complete trip
        trip.current_route_mile = trip.total_distance_miles
        trip.current_fuel = final_fuel
        trip.status = "completed"
        trip.completed_at = timezone.now()

        trip.save()

        # Total distance driven
        total_distance = trip.total_distance_miles

        # Total fuel consumed
        total_fuel_consumed = (
            trip.starting_fuel
            + trip.total_fuel_purchased
            - trip.current_fuel
        )

        # Average fuel price
        if trip.total_fuel_purchased > 0:
            average_fuel_price = (
                trip.total_money_spent
                / trip.total_fuel_purchased
            )
        else:
            average_fuel_price = 0

        # Fuel cost per mile
        if total_distance > 0:
            fuel_cost_per_mile = (
                trip.total_money_spent
                / total_distance
            )
        else:
            fuel_cost_per_mile = 0

        refueling_history = []

        for event in trip.refueling_events.select_related(
            "fuel_station"
        ).order_by("created_at"):

            refueling_history.append({
                "station_id": event.fuel_station.id,
                "station_name": event.fuel_station.name,
                "city": event.fuel_station.city,
                "state": event.fuel_station.state,
                "route_mile": round(
                    event.route_mile,
                    2,
                ),
                "gallons": round(
                    event.gallons,
                    2,
                ),
                "price_per_gallon": float(
                    event.price_per_gallon
                ),
                "total_cost": float(
                    event.total_cost
                ),
            })

        return Response(
            {
                "message": "Trip completed successfully",

                "trip_id": str(trip.trip_id),

                "status": trip.status,

                "start": trip.start,
                "destination": trip.destination,

                "summary": {
                    "total_distance_miles": round(
                        total_distance,
                        2,
                    ),

                    "starting_fuel": round(
                        trip.starting_fuel,
                        2,
                    ),

                    "total_fuel_purchased": round(
                        trip.total_fuel_purchased,
                        2,
                    ),

                    "total_fuel_consumed": round(
                        total_fuel_consumed,
                        2,
                    ),

                    "remaining_fuel": round(
                        trip.current_fuel,
                        2,
                    ),

                    "remaining_range_miles": round(
                        trip.current_fuel * MPG,
                        2,
                    ),

                    "total_money_spent": round(
                        trip.total_money_spent,
                        2,
                    ),

                    "average_fuel_price": round(
                        average_fuel_price,
                        2,
                    ),

                    "fuel_cost_per_mile": round(
                        fuel_cost_per_mile,
                        2,
                    ),

                    "number_of_stops": (
                        trip.refueling_events.count()
                    ),
                },

                "refueling_history": refueling_history,
            },
            status=status.HTTP_200_OK,
        )