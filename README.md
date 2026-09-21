# 🚗 Fuel Route Optimization

> Route planning and fuel-stop optimization using Django REST Framework, React, Leaflet and Valhalla.

## 🎯 Project Overview

The application calculates a driving route between two locations in the USA, identifies fuel stations near the route, and recommends reachable refueling stops based on fuel price and available fuel.

## ✨ Key Features

| Feature | Description |
|---|---|
| 🗺️ Route Preview | Calculates and displays the route between two USA locations |
| ⛽ Fuel Stations | Identifies stations located near the route |
| 💰 Fuel Optimization | Considers fuel price and station reachability |
| 🚗 Trip Simulation | Tracks fuel and route progress during a trip |
| 🧾 Refueling | Records actual gallons purchased and fuel cost |
| 📊 Trip Summary | Calculates total fuel usage and expenditure |
| ⚡ Efficient Routing | Uses a main routing request instead of routing to every station |
| 🛡️ Validation | Validates fuel capacity, reachability and trip state |

## 🛠️ Technology Stack

### Backend
- Python
- Django
- Django REST Framework
- PostgreSQL
- SQLite fallback
- Requests
- Geopy

### Frontend
- React
- Vite
- JavaScript
- Leaflet
- React-Leaflet

### External Services

| Service | Purpose |
|---|---|
| Valhalla | Driving route calculation |
| OpenStreetMap | Map tiles |
| Nominatim | Geocoding during data preparation and location resolution |

## 📁 Project Structure

```text
fuel-route-optimizer/
├── README.md
├── .gitignore
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── datas/
│   │   ├── fuel-prices-for-be-assessment.csv
│   │   └── fuel-stations-geocoded.csv
│   ├── fuel/
│   │   ├── models.py
│   │   └── management/commands/
│   │       ├── import_fuel_stations.py
│   │       ├── geocode_stations.py
│   │       └── export_geocoded_stations.py
│   ├── locations/
│   ├── routing/
│   ├── optimizer/
│   └── route_api/
└── frontend/
    ├── package.json
    ├── package-lock.json
    ├── .env.example
    ├── public/
    └── src/
```

## 🚀 Getting Started

### Prerequisites

- Python 3.x
- pip
- Node.js and npm
- Git
- PostgreSQL (optional when using SQLite fallback)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` when using PostgreSQL:

```env
DB_NAME=fuel_route_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

Create the database schema:

```bash
python manage.py migrate
```

Import the prepared station dataset:

```bash
python manage.py import_fuel_stations
```

Start Django:

```bash
python manage.py runserver
```

Backend: `http://127.0.0.1:8000/`

API base: `http://127.0.0.1:8000/api/v1/`

### Frontend

```bash
cd frontend
npm install
```

Create `.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Start Vite:

```bash
npm run dev
```

Open `http://localhost:5173/`.

## 🧠 Application Flow

```text
Start + Destination + Starting Fuel
                ↓
         React Frontend
                ↓
        Django REST API
                ↓
      Route / Geocoding
                ↓
           Valhalla
                ↓
        Route Geometry
                ↓
     Nearby Fuel Stations
                ↓
      Fuel Stop Optimization
                ↓
        Interactive Map
                ↓
          Start Trip
                ↓
       Refuel & Track Trip
                ↓
          Finish Trip
                ↓
         Trip Summary
```

## ⛽ Fuel Model

Assessment assumptions:

```text
Fuel efficiency : 10 MPG
Maximum range   : 500 miles
```

The corresponding maximum usable fuel is derived as:

```text
500 miles ÷ 10 MPG = 50 gallons
```

Fuel consumed:

```text
Fuel Consumed = Distance Travelled ÷ MPG
```

Remaining range:

```text
Available Range = Current Fuel × MPG
```

Refueling cost:

```text
Refueling Cost = Gallons Purchased × Station Price
```

## 🧮 Fuel Stop Optimization

Stations are first identified near the calculated route. The optimizer considers:

- Current fuel level
- Remaining driving range
- Station position along the route
- Fuel price
- Remaining trip distance
- Station reachability

Only stations ahead of the current route position and reachable with available fuel are considered for the next stop. The implementation focuses on reducing fuel cost while maintaining trip feasibility.

## 🗺️ Routing Strategy

Valhalla calculates the primary driving route from start to destination. The returned route geometry is then used to identify fuel stations near the route. This avoids making an individual routing request for every station.

## 🌎 Geospatial Data Processing

The supplied fuel-price dataset does not contain latitude and longitude for the fuel stations.

A preprocessing workflow was used:

```text
Original CSV
    ↓
Station Address
    ↓
Geocoding Process
    ↓
Latitude + Longitude
    ↓
Prepared CSV
    ↓
FuelStation Database
```

Prepared dataset:

```text
backend/datas/fuel-stations-geocoded.csv
```

Geocoding utility:

```text
backend/fuel/management/commands/geocode_stations.py
```

Geocoding is not performed for every fuel station during normal route calculation. Stored coordinates are used at runtime.

Records without reliable coordinates are retained but cannot currently be geographically matched to a route.

## 🔌 API Endpoints

### Route Preview

```http
POST /api/v1/routes/preview/
```

```json
{
  "start": "Dallas, TX",
  "destination": "Chicago, IL",
  "starting_fuel": 30
}
```

Returns route geometry, distance, locations, nearby stations and recommended stops.

### Start Trip

```http
POST /api/v1/trips/
```

Starts a trip using the confirmed route.

### Trip Status

```http
GET /api/v1/trips/{trip_id}/
```

Returns current fuel, route position, remaining distance, recommendation, fuel purchased and spending.

### Record Refueling

```http
POST /api/v1/trips/{trip_id}/refuel/
```

```json
{
  "fuel_station_id": 152,
  "gallons": 20
}
```

The backend uses the stored station price to calculate cost.

### Finish Trip

```http
POST /api/v1/trips/{trip_id}/finish/
```

Returns the final trip report.

## 🧪 Testing with Postman

Recommended flow:

```text
1. POST /routes/preview/
2. POST /trips/
3. GET /trips/{trip_id}/
4. POST /trips/{trip_id}/refuel/
5. GET /trips/{trip_id}/
6. POST /trips/{trip_id}/finish/
```

Verify route rendering, station markers, recommended stops, fuel balance, refueling calculations, total spending and final report.

## 🛡️ Validation & Error Handling

The application validates:

- Starting fuel amount
- Fuel station reachability
- Route progression
- Refueling amount
- Vehicle tank capacity
- Invalid station selections
- Invalid trip states
- Backward route movement

HTTP errors include `400 Bad Request`, `404 Not Found` and `500 Internal Server Error` where applicable.

## 🔐 Security & Configuration

Do not commit `.env` files or credentials. Commit `.env.example` templates only.

`node_modules/`, build output, Python caches and virtual environments are excluded through `.gitignore`.

## 🧪 Complete Local Run

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_fuel_stations
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 📌 Assumptions

- Vehicle fuel efficiency is 10 MPG.
- Maximum driving range is 500 miles.
- Fuel prices come from the supplied assessment dataset.
- Fuel stations are matched using geographic proximity to the route.
- Stored station coordinates are used during runtime.
- External routing services are used for route calculation.

## ⚠️ Limitations

- Geographic coordinates are not available for every supplied station record.
- Routing and geocoding depend on external services.
- Public map/routing services may have usage and rate limitations.
- Fuel prices are based on the supplied dataset and are not real-time.
- The optimization strategy is scoped to the assessment and can be enhanced for production-scale use.

## 🚀 Future Improvements

- More comprehensive coordinate enrichment
- PostGIS spatial queries
- More advanced global optimization
- Real-time fuel prices
- Authentication and user accounts
- Trip history persistence
- Route caching
- CI/CD and automated deployment
- Automated test coverage

## 👨‍💻 Author

**Karthik M**  
Python Full Stack Developer
