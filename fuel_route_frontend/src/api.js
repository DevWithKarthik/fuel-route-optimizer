const API_BASE_URL = "http://127.0.0.1:8000/api/v1";

export async function previewRoute(data) {
    const response = await fetch(
        `${API_BASE_URL}/routes/preview/`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(data),
        }
    );

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            result.error || "Unable to calculate route"
        );
    }

    return result;
}

export async function startTrip(data) {
    const response = await fetch(
        `${API_BASE_URL}/trips/`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(data),
        }
    );

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            result.error || "Unable to start trip"
        );
    }

    return result;
}

export async function getTripStatus(tripId) {
    const response = await fetch(
        `${API_BASE_URL}/trips/${tripId}/`
    );

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            result.error || "Unable to get trip status"
        );
    }

    return result;
}

export async function refuelTrip(
    tripId,
    fuelStationId,
    gallons
) {
    const response = await fetch(
        `${API_BASE_URL}/trips/${tripId}/refuel/`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                fuel_station_id: fuelStationId,
                gallons: Number(gallons),
            }),
        }
    );

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            result.error || "Unable to record refueling"
        );
    }

    return result;
}

export async function finishTrip(tripId) {
    const response = await fetch(
        `${API_BASE_URL}/trips/${tripId}/finish/`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
        }
    );

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            result.error || "Unable to finish trip"
        );
    }

    return result;
}