import React, { useMemo, useState } from "react";
import {
  MapContainer,
  Marker,
  Popup,
  Polyline,
  TileLayer,
} from "react-leaflet";
import L from "leaflet";

import {
  previewRoute,
  startTrip,
  getTripStatus,
  refuelTrip,
  finishTrip,
} from "./api";

const MPG = 10;
const MAX_FUEL = 50;
const MAX_RANGE = MAX_FUEL * MPG;

const createIcon = (className) =>
  L.divIcon({
    className: "",
    html: `<div class="map-pin ${className}"></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });

const icons = {
  start: createIcon("start-pin"),
  end: createIcon("end-pin"),
  station: createIcon("station-pin"),
  recommended: createIcon("recommended-pin"),
};

function normalizeStation(station) {
  const cityState = [station.city, station.state]
    .filter(Boolean)
    .join(", ");

  return {
    id: Number(station.id ?? station.station_id),
    name: station.name ?? station.station_name ?? "Fuel Station",
    city: cityState || station.city || "",
    price: Number(
      station.retail_price ??
      station.price ??
      station.price_per_gallon ??
      0
    ),
    routeMile: Number(station.route_mile ?? 0),
    position: [
      Number(station.latitude),
      Number(station.longitude),
    ],
    address: station.address ?? "",
  };
}

function normalizeRecommendedStop(stop, stationList = []) {
  const id = Number(
    stop.id ??
    stop.station_id ??
    stop.fuel_station_id
  );

  const matchedStation = stationList.find(
    (station) => station.id === id
  );

  return {
    ...stop,
    id,
    name:
      stop.name ??
      stop.station_name ??
      matchedStation?.name ??
      "Fuel Station",
    city:
      stop.city ??
      matchedStation?.city ??
      "",
    price: Number(
      stop.price ??
      stop.retail_price ??
      stop.price_per_gallon ??
      matchedStation?.price ??
      0
    ),
    routeMile: Number(
      stop.route_mile ??
      matchedStation?.routeMile ??
      0
    ),
  };
}

export default function App() {
  const [startLocation, setStartLocation] =
    useState("Dallas, TX");
  const [destination, setDestination] =
    useState("Chicago, IL");
  const [startingFuel, setStartingFuel] =
    useState("30");

  const [routeShown, setRouteShown] =
    useState(false);
  const [tripStarted, setTripStarted] =
    useState(false);
  const [tripFinished, setTripFinished] =
    useState(false);

  const [routeCoordinates, setRouteCoordinates] =
    useState([]);
  const [stations, setStations] =
    useState([]);
  const [optimizedStops, setOptimizedStops] =
    useState([]);
  const [totalTripDistance, setTotalTripDistance] =
    useState(0);

  const [startPoint, setStartPoint] =
    useState([]);
  const [destinationPoint, setDestinationPoint] =
    useState([]);

  const [tripId, setTripId] =
    useState(null);

  const [selectedStation, setSelectedStation] =
    useState(null);
  const [pendingRefuelStation, setPendingRefuelStation] =
    useState(null);
  const [currentStation, setCurrentStation] =
    useState(null);

  const [currentRouteMile, setCurrentRouteMile] =
    useState(0);
  const [currentFuel, setCurrentFuel] =
    useState(Number(startingFuel) || 0);

  const [totalFuelPurchased, setTotalFuelPurchased] =
    useState(0);
  const [totalSpent, setTotalSpent] =
    useState(0);

  const [gallons, setGallons] =
    useState("");

  const [refuels, setRefuels] =
    useState([]);

  const [error, setError] =
    useState("");
  const [refuelError, setRefuelError] =
    useState("");
  const [loading, setLoading] =
    useState(false);

  const [tripReport, setTripReport] =
    useState(null);

  const startingFuelNumber =
    Number(startingFuel) || 0;

  const availableRange =
    Math.max(0, currentFuel * MPG);

  const remainingTripDistance =
    Math.max(
      0,
      totalTripDistance - currentRouteMile
    );

  const plannedStopIds = useMemo(
    () =>
      new Set(
        optimizedStops.map(
          (station) =>
            Number(
              station.id ??
              station.station_id
            )
        )
      ),
    [optimizedStops]
  );

  const selectedDistanceFromCurrent =
    selectedStation
      ? selectedStation.routeMile - currentRouteMile
      : null;

  const selectedFuelRequired =
    selectedStation &&
      selectedDistanceFromCurrent !== null &&
      selectedDistanceFromCurrent > 0
      ? selectedDistanceFromCurrent / MPG
      : 0;

  const selectedReachable =
    !!selectedStation &&
    selectedDistanceFromCurrent >= 0 &&
    selectedDistanceFromCurrent <= availableRange;

  const fuelNeededToFinish =
    Math.max(
      0,
      remainingTripDistance / MPG
    );

  const additionalFuelToFinish =
    Math.max(
      0,
      fuelNeededToFinish - currentFuel
    );

  const needsRefuelBeforeContinuing =
    !!selectedStation &&
    selectedDistanceFromCurrent === 0 &&
    remainingTripDistance > availableRange;

  const nextStationAhead =
    [...stations]
      .filter(
        (station) =>
          station.routeMile > currentRouteMile
      )
      .sort(
        (a, b) =>
          a.routeMile - b.routeMile
      )[0] || null;

  const fuelNeededFromCurrentToNext =
    nextStationAhead
      ? Math.max(
        0,
        (nextStationAhead.routeMile -
          currentRouteMile) /
        MPG
      )
      : fuelNeededToFinish;

  const additionalFuelNeeded =
    Math.max(
      0,
      fuelNeededFromCurrentToNext -
      currentFuel
    );

  // Refueling UI calculations. The backend remains the
  // authoritative source for the final fuel calculation.
  const fuelBeforeRefuel = pendingRefuelStation
    ? Math.max(
      0,
      currentFuel -
      Math.max(
        0,
        pendingRefuelStation.routeMile -
        currentRouteMile
      ) /
      MPG
    )
    : 0;

  const availableTankCapacity = Math.max(
    0,
    MAX_FUEL - fuelBeforeRefuel
  );

  const enteredRefuelGallons = Number(gallons);

  const refuelInputInvalid =
    gallons !== "" &&
    (!Number.isFinite(enteredRefuelGallons) ||
      enteredRefuelGallons <= 0);

  const refuelExceedsCapacity =
    gallons !== "" &&
    Number.isFinite(enteredRefuelGallons) &&
    enteredRefuelGallons > availableTankCapacity;

  const refuelInputMessage =
    refuelInputInvalid
      ? "Please enter a valid number of gallons."
      : refuelExceedsCapacity
        ? `You can add only ${availableTankCapacity.toFixed(1)} gallons. Tank capacity is ${MAX_FUEL} gallons.`
        : "";

  const refuelInputValid =
    gallons !== "" &&
    Number.isFinite(enteredRefuelGallons) &&
    enteredRefuelGallons > 0 &&
    enteredRefuelGallons <= availableTankCapacity;

  /*
   * SHOW ROUTE
   *
   * This calls Django once.
   * Django geocodes both locations, calls Valhalla,
   * matches stations and runs the optimizer.
   */
  const handleShowRoute = async () => {
    setError("");

    // Clear previous route before calculating a new one
    setRouteShown(false);
    setRouteCoordinates([]);
    setStations([]);
    setOptimizedStops([]);
    setTotalTripDistance(0);
    setStartPoint([]);
    setDestinationPoint([]);
    setTripId(null);
    setTripStarted(false);
    setTripFinished(false);
    setSelectedStation(null);
    setPendingRefuelStation(null);
    setCurrentStation(null);
    setCurrentRouteMile(0);
    setTotalFuelPurchased(0);
    setTotalSpent(0);
    setRefuels([]);
    setTripReport(null);

    const fuel = Number(startingFuel);

    if (
      !startLocation.trim() ||
      !destination.trim()
    ) {
      setError(
        "Please enter start and destination."
      );
      return;
    }

    if (
      Number.isNaN(fuel) ||
      fuel < 0 ||
      fuel > MAX_FUEL
    ) {
      setError(
        "Starting fuel must be between 0 and 50 gallons."
      );
      return;
    }

    setLoading(true);

    try {
      const data = await previewRoute({
        start: startLocation.trim(),
        destination: destination.trim(),
        starting_fuel: fuel,
      });

      const normalizedStations = (
        data.fuel_stations || []
      )
        .map(normalizeStation)
        .filter(
          (station) =>
            Number.isFinite(station.position[0]) &&
            Number.isFinite(station.position[1])
        );

      const normalizedStops = (
        data.recommended_stops || []
      ).map((stop) =>
        normalizeRecommendedStop(
          stop,
          normalizedStations
        )
      );

      const coordinates =
        data.route?.coordinates || [];

      setStartPoint([
        Number(data.start.latitude),
        Number(data.start.longitude),
      ]);

      setDestinationPoint([
        Number(data.destination.latitude),
        Number(data.destination.longitude),
      ]);

      setRouteCoordinates(coordinates);
      setStations(normalizedStations);
      setOptimizedStops(normalizedStops);
      setTotalTripDistance(
        Number(
          data.route?.distance_miles ?? 0
        )
      );

      setRouteShown(true);
      setTripStarted(false);
      setTripFinished(false);

      setTripId(null);
      setSelectedStation(null);
      setPendingRefuelStation(null);
      setCurrentStation(null);

      setCurrentRouteMile(0);
      setCurrentFuel(fuel);

      setTotalFuelPurchased(0);
      setTotalSpent(0);
      setRefuels([]);

      setTripReport(null);
    } catch (requestError) {
      setError(
        requestError.message ||
        "Unable to calculate route."
      );
    } finally {
      setLoading(false);
    }
  };

  /*
   * START TRIP
   *
   * Uses the already generated preview.
   * No second Valhalla call.
   */
  const handleStartTrip = async () => {
    setError("");

    if (!routeCoordinates.length) {
      setError(
        "Please calculate the route first."
      );
      return;
    }

    setLoading(true);

    try {
      const data = await startTrip({
        start: startLocation,
        destination,

        start_latitude: startPoint[0],
        start_longitude: startPoint[1],

        destination_latitude:
          destinationPoint[0],
        destination_longitude:
          destinationPoint[1],

        total_distance_miles:
          totalTripDistance,

        starting_fuel:
          startingFuelNumber,

        route_geometry:
          routeCoordinates,

        fuel_stations:
          stations,

        recommended_stops:
          optimizedStops,
      });

      setTripId(data.trip_id);

      setTripStarted(true);
      setTripFinished(false);

      setSelectedStation(null);
      setPendingRefuelStation(null);
      setCurrentStation(null);

      setCurrentRouteMile(
        Number(
          data.current_route_mile ?? 0
        )
      );

      setCurrentFuel(
        Number(
          data.current_fuel ??
          startingFuelNumber
        )
      );

      setTotalFuelPurchased(
        Number(
          data.total_fuel_purchased ?? 0
        )
      );

      setTotalSpent(
        Number(
          data.total_money_spent ?? 0
        )
      );

      setRefuels([]);
    } catch (requestError) {
      setError(
        requestError.message ||
        "Unable to start trip."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleStationClick = (station) => {
    if (!routeShown) return;

    setSelectedStation(station);
    setError("");
    setRefuelError("");

    if (!pendingRefuelStation) {
      setGallons("");
    }
  };

  /*
   * Confirm that the driver actually stopped at the
   * selected station. The database is updated only after
   * Record Refuel.
   */
  const handleStoppedHere = () => {
    setError("");
    setRefuelError("");

    if (!tripStarted || !tripId) {
      setError(
        "Start the trip before confirming a fuel stop."
      );
      return;
    }

    if (!selectedStation) {
      setError(
        "Select a fuel station from the map first."
      );
      return;
    }

    const distanceToStation =
      selectedStation.routeMile -
      currentRouteMile;

    if (distanceToStation < 0) {
      setError(
        "This station is behind your current trip position."
      );
      return;
    }

    if (
      distanceToStation >
      availableRange
    ) {
      setError(
        "This station is not currently reachable. Use Refuel Here below."
      );
      return;
    }

    setPendingRefuelStation(
      selectedStation
    );
    setGallons("");

    document
      .getElementById("refuel")
      ?.scrollIntoView({
        behavior: "smooth",
      });
  };

  /*
   * Refuel at the current confirmed station when the
   * next selected station cannot be reached.
   */
  const handleRefuelHere = () => {
    setError("");
    setRefuelError("");

    if (!tripStarted || !tripId) {
      return;
    }

    if (!currentStation) {
      setError(
        "There is no confirmed fuel station yet."
      );
      return;
    }

    setPendingRefuelStation(
      currentStation
    );

    const fuelToAdd =
      additionalFuelToFinish > 0
        ? additionalFuelToFinish
        : additionalFuelNeeded;

    setGallons(
      fuelToAdd > 0
        ? fuelToAdd.toFixed(1)
        : ""
    );

    document
      .getElementById("refuel")
      ?.scrollIntoView({
        behavior: "smooth",
      });
  };

  /*
   * RECORD REFUEL
   *
   * The backend performs the authoritative calculation:
   * distance travelled, fuel consumed, fuel at station,
   * tank capacity, purchase cost and trip totals.
   */
  const handleRecordRefuel = async () => {
    setRefuelError("");

    if (!tripId) {
      setRefuelError("No active trip found.");
      return;
    }

    if (!pendingRefuelStation) {
      setRefuelError(
        "Select a station and click I stopped here first."
      );
      return;
    }

    const purchasedGallons =
      Number(gallons);

    if (
      !Number.isFinite(purchasedGallons) ||
      purchasedGallons <= 0
    ) {
      setRefuelError(
        "Please enter a valid number of gallons."
      );
      return;
    }

    if (purchasedGallons > availableTankCapacity) {
      setRefuelError(
        `You can add only ${availableTankCapacity.toFixed(1)} gallons. Tank capacity is ${MAX_FUEL} gallons.`
      );
      return;
    }

    setLoading(true);

    try {
      const data = await refuelTrip(
        tripId,
        pendingRefuelStation.id,
        purchasedGallons
      );

      const trip = data.trip || {};
      const station =
        data.fuel_station || {};

      const stationForState = {
        ...pendingRefuelStation,
        id: Number(
          station.id ??
          pendingRefuelStation.id
        ),
        name:
          station.name ??
          pendingRefuelStation.name,
        city:
          [station.city, station.state]
            .filter(Boolean)
            .join(", ") ||
          pendingRefuelStation.city,
        price: Number(
          station.price_per_gallon ??
          pendingRefuelStation.price
        ),
      };

      const refueling =
        data.refueling || {};

      const newRefuel = {
        id: Date.now(),
        stationId:
          stationForState.id,
        station:
          stationForState.name,
        city:
          stationForState.city,
        routeMile: Number(
          trip.current_route_mile ??
          pendingRefuelStation.routeMile
        ),
        gallons: Number(
          refueling.gallons ??
          purchasedGallons
        ),
        price: Number(
          stationForState.price
        ),
        cost: Number(
          refueling.total_cost ?? 0
        ),
      };

      setCurrentRouteMile(
        Number(
          trip.current_route_mile ?? 0
        )
      );

      setCurrentFuel(
        Number(
          trip.current_fuel ?? 0
        )
      );

      setTotalFuelPurchased(
        Number(
          trip.total_fuel_purchased ?? 0
        )
      );

      setTotalSpent(
        Number(
          trip.total_money_spent ?? 0
        )
      );

      setCurrentStation(
        stationForState
      );

      setRefuels(
        (previous) => [
          ...previous,
          newRefuel,
        ]
      );

      setPendingRefuelStation(null);
      setGallons("");
      setRefuelError("");

      setSelectedStation(
        stationForState
      );
    } catch (requestError) {
      setRefuelError(
        requestError.message ||
        "Unable to record refueling."
      );
    } finally {
      setLoading(false);
    }
  };

  /*
   * Optional live status refresh.
   * This uses the GET trip endpoint without recalculating
   * the route.
   */
  const handleRefreshTrip = async () => {
    if (!tripId) return;

    setError("");

    try {
      const data =
        await getTripStatus(tripId);

      const trip = data.trip || {};

      setCurrentRouteMile(
        Number(
          trip.current_route_mile ?? 0
        )
      );

      setCurrentFuel(
        Number(
          trip.current_fuel ?? 0
        )
      );

      setTotalFuelPurchased(
        Number(
          trip.total_fuel_purchased ?? 0
        )
      );

      setTotalSpent(
        Number(
          trip.total_money_spent ?? 0
        )
      );

      if (
        Array.isArray(
          data.refueling_history
        )
      ) {
        setRefuels(
          data.refueling_history.map(
            (item, index) => ({
              id:
                item.id ??
                `${item.station_id}-${index}`,
              station:
                item.station_name,
              city:
                [item.city, item.state]
                  .filter(Boolean)
                  .join(", "),
              routeMile:
                Number(
                  item.route_mile
                ),
              gallons:
                Number(
                  item.gallons
                ),
              price:
                Number(
                  item.price_per_gallon
                ),
              cost:
                Number(
                  item.total_cost
                ),
            })
          )
        );
      }
    } catch (requestError) {
      setError(
        requestError.message ||
        "Unable to refresh trip."
      );
    }
  };

  /*
   * FINISH TRIP
   *
   * Backend calculates the authoritative final report.
   */
  const handleFinishTrip = async () => {
    setError("");

    if (!tripId) {
      setError(
        "No active trip found."
      );
      return;
    }

    setLoading(true);

    try {
      const data =
        await finishTrip(tripId);

      const summary =
        data.summary || {};

      const history =
        Array.isArray(
          data.refueling_history
        )
          ? data.refueling_history.map(
            (item, index) => ({
              id:
                item.id ??
                `${item.station_id}-${index}`,
              station:
                item.station_name,
              city:
                [item.city, item.state]
                  .filter(Boolean)
                  .join(", "),
              routeMile:
                Number(
                  item.route_mile
                ),
              gallons:
                Number(
                  item.gallons
                ),
              price:
                Number(
                  item.price_per_gallon
                ),
              cost:
                Number(
                  item.total_cost
                ),
            })
          )
          : refuels;

      setTripReport({
        startLocation:
          data.start ?? startLocation,
        destination:
          data.destination ?? destination,
        totalDistance:
          Number(
            summary.total_distance_miles ??
            totalTripDistance
          ),
        startingFuel:
          Number(
            summary.starting_fuel ??
            startingFuelNumber
          ),
        totalFuelPurchased:
          Number(
            summary.total_fuel_purchased ??
            totalFuelPurchased
          ),
        fuelConsumed:
          Number(
            summary.total_fuel_consumed ?? 0
          ),
        endingFuel:
          Number(
            summary.remaining_fuel ?? 0
          ),
        remainingRange:
          Number(
            summary.remaining_range_miles ??
            0
          ),
        totalSpent:
          Number(
            summary.total_money_spent ??
            totalSpent
          ),
        averageFuelPrice:
          Number(
            summary.average_fuel_price ?? 0
          ),
        fuelCostPerMile:
          Number(
            summary.fuel_cost_per_mile ?? 0
          ),
        numberOfStops:
          Number(
            summary.number_of_stops ??
            history.length
          ),
        refuels: history,
      });

      setCurrentRouteMile(
        Number(
          summary.total_distance_miles ??
          totalTripDistance
        )
      );

      setCurrentFuel(
        Number(
          summary.remaining_fuel ?? 0
        )
      );

      setRefuels(history);
      setTripStarted(false);
      setTripFinished(true);
      setPendingRefuelStation(null);
    } catch (requestError) {
      setError(
        requestError.message ||
        "Unable to finish trip."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">

      {/* HEADER */}
      <header>
        <div>
          <div className="brand">
            FuelRoute
          </div>

          <div className="tagline">
            Fuel cost optimization for your journey
          </div>
        </div>

        <div
          className={`status ${tripStarted
            ? "active"
            : "preview"
            }`}
        >
          {tripStarted
            ? "Trip Active"
            : tripFinished
              ? "Trip Completed"
              : routeShown
                ? "Route Preview"
                : "Plan Trip"}
        </div>
      </header>


      <main>

        {/* PLANNER */}
        {!tripFinished && (
          <section className="card planner">

            <div className="heading">

              <div>
                <span className="eyebrow">
                  Trip Planner
                </span>

                <h1>
                  Plan your route
                </h1>
              </div>

              <span className="assumption">
                10 MPG · 500-mile maximum range
              </span>

            </div>


            <div className="form-grid">

              <label>
                <span>
                  Start location
                </span>

                <input
                  value={startLocation}
                  onChange={(event) =>
                    setStartLocation(
                      event.target.value
                    )
                  }
                  disabled={tripStarted}
                />
              </label>


              <label>
                <span>
                  Destination
                </span>

                <input
                  value={destination}
                  onChange={(event) =>
                    setDestination(
                      event.target.value
                    )
                  }
                  disabled={tripStarted}
                />
              </label>


              <label>
                <span>
                  Starting fuel
                </span>

                <div className="suffix">

                  <input
                    type="number"
                    min="0"
                    max="50"
                    step="0.1"
                    value={startingFuel}
                    onChange={(event) =>
                      setStartingFuel(
                        event.target.value
                      )
                    }
                    disabled={tripStarted}
                  />

                  <i>
                    gal
                  </i>

                </div>
              </label>


              {!tripStarted && (
                <button
                  className="primary"
                  onClick={
                    handleShowRoute
                  }
                  disabled={loading}
                >
                  {loading
                    ? "Calculating..."
                    : "Show Route"}
                </button>
              )}

            </div>


            {error && (
              <div
                className="error-message"
                style={{
                  marginTop: "12px",
                  color: "#a33",
                  fontSize: "12px",
                }}
              >
                {error}
              </div>
            )}


            {routeShown && (
              <div className="route-summary">

                <div>
                  <span>
                    Route distance
                  </span>

                  <strong>
                    {totalTripDistance} mi
                  </strong>
                </div>


                <div>
                  <span>
                    Starting range
                  </span>

                  <strong>
                    {(
                      startingFuelNumber *
                      MPG
                    ).toFixed(0)}{" "}
                    mi
                  </strong>
                </div>


                <div>
                  <span>
                    Status
                  </span>

                  <strong>
                    {tripStarted
                      ? "Trip Active"
                      : "Ready to review"}
                  </strong>
                </div>


                {!tripStarted ? (
                  <button
                    className="start"
                    onClick={
                      handleStartTrip
                    }
                    disabled={loading}
                  >
                    {loading
                      ? "Starting..."
                      : "Start Trip"}
                  </button>
                ) : (
                  <button
                    className="finish"
                    onClick={
                      handleFinishTrip
                    }
                    disabled={loading}
                  >
                    {loading
                      ? "Finishing..."
                      : "Finish Trip"}
                  </button>
                )}

              </div>
            )}

          </section>
        )}


        {/* MAP + TRIP */}
        {routeShown &&
          !tripFinished && (
            <section className="workspace">

              <div className="card map">

                <MapContainer
                  bounds={routeCoordinates}
                  boundsOptions={{
                    padding: [30, 30],
                  }}
                  scrollWheelZoom={true}
                >

                  <TileLayer
                    attribution="&copy; OpenStreetMap contributors"
                    url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />


                  <Polyline
                    positions={routeCoordinates}
                    pathOptions={{
                      weight: 5,
                    }}
                  />


                  {/* startPoint */}
                  <Marker
                    position={startPoint}
                    icon={icons.start}
                  >
                    <Popup>
                      <b>
                        Start
                      </b>

                      <br />

                      {startLocation}
                    </Popup>
                  </Marker>


                  {/* destinationPointINATION */}
                  <Marker
                    position={destinationPoint}
                    icon={icons.end}
                  >
                    <Popup>
                      <b>
                        Destination
                      </b>

                      <br />

                      {destination}
                    </Popup>
                  </Marker>


                  {/* FUEL stations */}
                  {stations.map(
                    (station) => (
                      <Marker
                        key={station.id}
                        position={
                          station.position
                        }
                        icon={
                          selectedStation?.id ===
                            station.id
                            ? icons.recommended
                            : plannedStopIds.has(
                              station.id
                            )
                              ? icons.recommended
                              : icons.station
                        }
                        eventHandlers={{
                          click: () =>
                            handleStationClick(
                              station
                            ),
                        }}
                      >

                        <Popup>

                          <b>
                            {station.name}
                          </b>

                          <br />

                          {station.city}

                          <br />

                          $
                          {Number(
                            station.price ?? 0
                          ).toFixed(2)}{" "}
                          / gallon

                          <br />

                          {station.routeMile} mi
                          from start

                          {plannedStopIds.has(
                            station.id
                          ) && (
                              <>
                                <br />

                                <b>
                                  Suggested stop
                                </b>
                              </>
                            )}

                        </Popup>

                      </Marker>
                    )
                  )}

                </MapContainer>

              </div>


              {/* RIGHT PANEL */}
              <aside className="card side">

                {/* LIVE METRICS */}
                <div className="metrics">

                  <div>
                    <span>
                      Current fuel
                    </span>

                    <b>
                      {currentFuel.toFixed(
                        1
                      )}{" "}
                      gal
                    </b>
                  </div>


                  <div>
                    <span>
                      Available range
                    </span>

                    <b>
                      {availableRange.toFixed(
                        0
                      )}{" "}
                      mi
                    </b>
                  </div>


                  <div>
                    <span>
                      Distance travelled
                    </span>

                    <b>
                      {currentRouteMile.toFixed(
                        0
                      )}{" "}
                      mi
                    </b>
                  </div>


                  <div>
                    <span>
                      Remaining trip
                    </span>

                    <b>
                      {remainingTripDistance.toFixed(
                        0
                      )}{" "}
                      mi
                    </b>
                  </div>


                  <div>
                    <span>
                      Fuel spent
                    </span>

                    <b>
                      ${totalSpent.toFixed(
                        2
                      )}
                    </b>
                  </div>

                </div>


                {/* BEFORE startPoint */}
                {!tripStarted && (
                  <div className="note">

                    <span className="eyebrow">
                      Optimized route
                    </span>

                    <h2>
                      Review the route
                    </h2>

                    <p>
                      Fuel stations are already
                      shown on the map. The highlighted
                      stations are the current optimized
                      plan.
                    </p>

                    {optimizedStops.length >
                      0 && (
                        <div
                          className="history"
                          style={{
                            marginTop: "12px",
                          }}
                        >

                          <span className="eyebrow">
                            Suggested stops
                          </span>

                          {optimizedStops.map(
                            (station) => (
                              <div
                                className="history-row"
                                key={
                                  station.id
                                }
                              >
                                <div>
                                  <b>
                                    {
                                      station.name
                                    }
                                  </b>

                                  <small>
                                    {
                                      station.city
                                    }{" "}
                                    ·{" "}
                                    {
                                      station.routeMile
                                    }{" "}
                                    mi · $
                                    {station.price.toFixed(
                                      2
                                    )}
                                    /gal
                                  </small>
                                </div>
                              </div>
                            )
                          )}

                        </div>
                      )}

                  </div>
                )}


                {/* AFTER startPoint */}
                {tripStarted && (
                  <>
                    {!selectedStation ? (
                      <div className="note">

                        <span className="eyebrow">
                          Select a station
                        </span>

                        <h2>
                          Choose a fuel station
                        </h2>

                        <p>
                          Click any fuel-station
                          marker on the map. Its
                          price, distance and remaining
                          trip will appear here.
                        </p>

                      </div>
                    ) : (
                      <div className="recommend">

                        <span className="eyebrow">
                          {selectedReachable
                            ? "Selected fuel station"
                            : "Fuel station not currently reachable"}
                        </span>

                        <h2>
                          {
                            selectedStation.name
                          }
                        </h2>

                        <p>
                          {
                            selectedStation.city
                          }
                        </p>


                        <div className="detail">

                          <span>
                            Price
                          </span>

                          <b>
                            $
                            {Number(
                              selectedStation.price ?? 0
                            ).toFixed(2)}{" "}
                            / gal
                          </b>

                        </div>


                        <div className="detail">

                          <span>
                            Distance from current
                          </span>

                          <b>
                            {Math.max(
                              0,
                              selectedDistanceFromCurrent
                            ).toFixed(0)}{" "}
                            mi
                          </b>

                        </div>


                        <div className="detail">

                          <span>
                            Remaining trip after stop
                          </span>

                          <b>
                            {Math.max(
                              0,
                              totalTripDistance -
                              selectedStation.routeMile
                            ).toFixed(0)}{" "}
                            mi
                          </b>

                        </div>


                        <div className="detail">

                          <span>
                            Fuel needed to reach
                          </span>

                          <b>
                            {selectedFuelRequired.toFixed(
                              1
                            )}{" "}
                            gal
                          </b>

                        </div>


                        <div className="detail">

                          <span>
                            Current fuel
                          </span>

                          <b>
                            {currentFuel.toFixed(
                              1
                            )}{" "}
                            gal
                          </b>

                        </div>


                        {needsRefuelBeforeContinuing ? (
                          <>
                            <p
                              style={{
                                color: "#9a5a12",
                                lineHeight: 1.5,
                                marginTop: "12px",
                              }}
                            >
                              You are at this station, but your
                              current fuel is not enough to reach
                              the destination.
                              You need at least{" "}
                              <b>
                                {additionalFuelToFinish.toFixed(
                                  1
                                )}{" "}
                                gal more
                              </b>{" "}
                              to complete the remaining{" "}
                              <b>
                                {remainingTripDistance.toFixed(
                                  0
                                )}{" "}
                                mi
                              </b>.
                            </p>

                            <button
                              className="stop"
                              onClick={
                                handleRefuelHere
                              }
                            >
                              Refuel Here
                            </button>
                          </>
                        ) : selectedReachable ? (
                          <>
                            <p
                              style={{
                                color: "#14763d",
                                lineHeight: 1.5,
                                marginTop: "12px",
                              }}
                            >
                              This station is reachable
                              with your current fuel.
                              Click <b>I stopped here</b>
                              when you actually stop.
                            </p>

                            <button
                              className="stop"
                              onClick={
                                handleStoppedHere
                              }
                            >
                              I stopped here
                            </button>
                          </>
                        ) : (
                          <>
                            <p
                              style={{
                                color: "#9a5a12",
                                lineHeight: 1.5,
                                marginTop: "12px",
                              }}
                            >
                              You do not have enough
                              fuel to reach this station.
                              Select a reachable station
                              or use the refuel option
                              at your current station.
                            </p>

                            {currentStation && (
                              <button
                                className="stop"
                                onClick={
                                  handleRefuelHere
                                }
                              >
                                Refuel at Current Station
                              </button>
                            )}
                          </>
                        )}

                      </div>
                    )}


                    {/* ACTUAL PURCHASE */}
                    {pendingRefuelStation && (
                      <div
                        className="refuel"
                        id="refuel"
                      >

                        <span className="eyebrow">
                          Actual purchase
                        </span>

                        <p>
                          <b>
                            {
                              pendingRefuelStation.name
                            }
                          </b>
                          {" · "}
                          {
                            pendingRefuelStation.city
                          }
                          {" · $"}
                          {
                            pendingRefuelStation.price.toFixed(
                              2
                            )
                          }
                          {" / gal"}
                        </p>


                        <h3>
                          How many gallons did you purchase?
                        </h3>


                        <div className="detail">

                          <span>
                            Fuel before refuel
                          </span>

                          <b>
                            {fuelBeforeRefuel.toFixed(1)}{" "}
                            gal
                          </b>

                        </div>

                        <div className="detail">

                          <span>
                            Available tank capacity
                          </span>

                          <b>
                            {availableTankCapacity.toFixed(1)}{" "}
                            gal
                          </b>

                        </div>

                        <div
                          style={{
                            marginBottom: "10px",
                            color: "#7a8592",
                            fontSize: "11px",
                          }}
                        >
                          Maximum purchase: {availableTankCapacity.toFixed(1)} gal
                        </div>

                        <div className="refuel-row">

                          <input
                            type="number"
                            min="0.1"
                            max={availableTankCapacity}
                            step="0.1"
                            value={gallons}
                            onChange={(event) => {
                              setGallons(
                                event.target.value
                              );
                              setRefuelError("");
                            }}
                            placeholder="20"
                            aria-invalid={
                              refuelInputInvalid ||
                              refuelExceedsCapacity
                            }
                          />

                          <button
                            onClick={
                              handleRecordRefuel
                            }
                            disabled={
                              loading ||
                              !refuelInputValid
                            }
                            style={{
                              opacity:
                                loading ||
                                  !refuelInputValid
                                  ? 0.55
                                  : 1,
                              cursor:
                                loading ||
                                  !refuelInputValid
                                  ? "not-allowed"
                                  : "pointer",
                            }}
                          >
                            {loading
                              ? "Saving..."
                              : "Record Refuel"}
                          </button>

                        </div>

                        {(refuelInputMessage ||
                          refuelError) && (
                            <div
                              className="error-message"
                              style={{
                                marginTop: "10px",
                                marginBottom: 0,
                                color: "#9b3535",
                                background: "#fff7f7",
                                borderColor: "#f0cccc",
                              }}
                            >
                              {refuelInputMessage ||
                                refuelError}
                            </div>
                          )}

                      </div>
                    )}


                    {/* REFUEL HISTORY */}
                    {refuels.length > 0 && (
                      <div className="history">

                        <span className="eyebrow">
                          Refueling history
                        </span>

                        {refuels.map(
                          (refuel) => (
                            <div
                              className="history-row"
                              key={refuel.id}
                            >

                              <div>

                                <b>
                                  {
                                    refuel.station
                                  }
                                </b>

                                <small>
                                  {
                                    refuel.city
                                  }{" "}
                                  ·{" "}
                                  {
                                    refuel.routeMile
                                  }{" "}
                                  mi ·{" "}
                                  {
                                    refuel.gallons.toFixed(
                                      1
                                    )
                                  }{" "}
                                  gal × $
                                  {
                                    refuel.price.toFixed(
                                      2
                                    )
                                  }
                                </small>

                              </div>

                              <b>
                                $
                                {
                                  refuel.cost.toFixed(
                                    2
                                  )
                                }
                              </b>

                            </div>
                          )
                        )}

                      </div>
                    )}

                  </>
                )}

              </aside>

            </section>
          )}


        {/* FINAL TRIP REPORT */}
        {tripFinished &&
          tripReport && (
            <section className="card trip-report">

              <div className="section-heading">

                <div>
                  <span className="eyebrow">
                    Travel History
                  </span>

                  <h1>
                    Trip completed
                  </h1>

                  <p>
                    {
                      tripReport.startLocation
                    }{" "}
                    →{" "}
                    {
                      tripReport.destination
                    }
                  </p>
                </div>

                <span className="status active">
                  Completed
                </span>

              </div>


              <div className="report-grid">

                <div className="report-card">
                  <span>
                    Start location
                  </span>

                  <strong>
                    {
                      tripReport.startLocation
                    }
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Destination
                  </span>

                  <strong>
                    {
                      tripReport.destination
                    }
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Total distance
                  </span>

                  <strong>
                    {
                      tripReport.totalDistance
                    }{" "}
                    mi
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Starting fuel
                  </span>

                  <strong>
                    {
                      tripReport.startingFuel.toFixed(
                        1
                      )
                    }{" "}
                    gal
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Total fuel purchased
                  </span>

                  <strong>
                    {
                      tripReport.totalFuelPurchased.toFixed(
                        1
                      )
                    }{" "}
                    gal
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Fuel consumed
                  </span>

                  <strong>
                    {
                      tripReport.fuelConsumed.toFixed(
                        1
                      )
                    }{" "}
                    gal
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Remaining fuel
                  </span>

                  <strong>
                    {
                      tripReport.endingFuel.toFixed(
                        1
                      )
                    }{" "}
                    gal
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Remaining range
                  </span>

                  <strong>
                    {
                      tripReport.remainingRange.toFixed(
                        0
                      )
                    }{" "}
                    mi
                  </strong>
                </div>


                <div className="report-card highlight">
                  <span>
                    Total money spent on fuel
                  </span>

                  <strong>
                    $
                    {
                      tripReport.totalSpent.toFixed(
                        2
                      )
                    }
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Average fuel price
                  </span>

                  <strong>
                    $
                    {
                      tripReport.averageFuelPrice.toFixed(
                        2
                      )
                    }{" "}
                    / gal
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Fuel cost per mile
                  </span>

                  <strong>
                    $
                    {
                      tripReport.fuelCostPerMile.toFixed(
                        2
                      )
                    }{" "}
                    / mi
                  </strong>
                </div>


                <div className="report-card">
                  <span>
                    Fuel stops
                  </span>

                  <strong>
                    {
                      tripReport.numberOfStops
                    }
                  </strong>
                </div>

              </div>


              <div className="history">

                <span className="eyebrow">
                  Refueling history
                </span>

                {tripReport.refuels.map(
                  (refuel) => (
                    <div
                      className="history-row"
                      key={refuel.id}
                    >

                      <div>
                        <b>
                          {
                            refuel.station
                          }
                        </b>

                        <small>
                          {
                            refuel.city
                          }{" "}
                          ·{" "}
                          {
                            refuel.routeMile
                          }{" "}
                          mi ·{" "}
                          {
                            refuel.gallons.toFixed(
                              1
                            )
                          }{" "}
                          gal × $
                          {
                            refuel.price.toFixed(
                              2
                            )
                          }
                        </small>
                      </div>

                      <b>
                        $
                        {
                          refuel.cost.toFixed(
                            2
                          )
                        }
                      </b>

                    </div>
                  )
                )}

              </div>


              <button
                className="primary"
                onClick={() => {
                  setRouteShown(false);
                  setTripFinished(false);
                  setTripReport(null);
                  setTripId(null);

                  setRouteCoordinates([]);
                  setStations([]);
                  setOptimizedStops([]);
                  setTotalTripDistance(0);
                  setStartPoint([]);
                  setDestinationPoint([]);

                  setSelectedStation(null);
                  setPendingRefuelStation(null);
                  setCurrentStation(null);

                  setCurrentRouteMile(0);
                  setCurrentFuel(
                    Number(startingFuel) ||
                    0
                  );

                  setTotalFuelPurchased(0);
                  setTotalSpent(0);
                  setRefuels([]);
                  setGallons("");
                  setError("");
                }}
              >
                Plan Another Trip
              </button>

            </section>
          )}

      </main>

    </div>
  );
}
