FUEL_ECONOMY_MPG = 10
TANK_CAPACITY_GALLONS = 50
MAX_RANGE_MILES = 500


def optimize_fuel_stops(
    total_distance,
    starting_fuel,
    stations,
):
    """
    Find cost-effective fuel stops while respecting:
    - 10 MPG fuel economy
    - 50 gallon tank
    - 500 mile maximum range
    - current fuel level
    - station route position
    """

    current_fuel = float(starting_fuel)
    current_mile = 0.0

    selected_stops = []

    stations = sorted(
        stations,
        key=lambda station: station["route_mile"]
    )

    while True:

        remaining_distance = (
            total_distance - current_mile
        )

        current_range = (
            current_fuel * FUEL_ECONOMY_MPG
        )

        # Destination is reachable
        if current_range >= remaining_distance:
            break

        # Stations we can physically reach
        reachable_stations = [
            station
            for station in stations
            if (
                station["route_mile"] > current_mile
                and
                station["route_mile"]
                <= current_mile + current_range
            )
        ]

        if not reachable_stations:
            raise ValueError(
                "No reachable fuel station found "
                "before the vehicle runs out of fuel."
            )

        # ------------------------------------------------
        # Choose station
        # ------------------------------------------------

        best_station = min(
            reachable_stations,
            key=lambda station: (
                station["retail_price"],
                station["route_mile"],
            )
        )

        distance_to_station = (
            best_station["route_mile"]
            - current_mile
        )

        fuel_needed_to_station = (
            distance_to_station
            / FUEL_ECONOMY_MPG
        )

        fuel_at_arrival = (
            current_fuel
            - fuel_needed_to_station
        )

        # ------------------------------------------------
        # Calculate how much fuel is required
        # ------------------------------------------------

        remaining_after_station = (
            total_distance
            - best_station["route_mile"]
        )

        fuel_required_to_finish = (
            remaining_after_station
            / FUEL_ECONOMY_MPG
        )

        # We don't necessarily need a full tank.
        # Buy enough to make destination reachable,
        # but never exceed tank capacity.
        required_purchase = max(
            0,
            fuel_required_to_finish
            - fuel_at_arrival
        )

        purchase_gallons = min(
            required_purchase,
            TANK_CAPACITY_GALLONS
            - fuel_at_arrival,
        )

        selected_stops.append({
            **best_station,

            "distance_from_current": round(
                distance_to_station,
                2,
            ),

            "fuel_needed_to_reach": round(
                fuel_needed_to_station,
                2,
            ),

            "fuel_at_arrival": round(
                fuel_at_arrival,
                2,
            ),

            "fuel_required_to_finish": round(
                fuel_required_to_finish,
                2,
            ),

            "recommended_purchase": round(
                purchase_gallons,
                2,
            ),

            "estimated_cost": round(
                purchase_gallons
                * best_station["retail_price"],
                2,
            ),
        })

        # Update simulated vehicle state
        current_fuel = (
            fuel_at_arrival
            + purchase_gallons
        )

        current_mile = (
            best_station["route_mile"]
        )

    return selected_stops