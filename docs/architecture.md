# Technical Architecture

## System Overview

```
┌──────────────────────────────────────────────────────┐
│                    Client Layer                       │
│  Swagger UI (/docs)  │  curl  │  Mintlify  │  Tests  │
└──────────────┬───────────────────────────────────────┘
               │ HTTP (JSON / multipart)
               ▼
┌──────────────────────────────────────────────────────┐
│                  FastAPI Application                  │
│                                                      │
│  ┌────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Middleware │  │  Auth    │  │  OpenAPI Schema  │  │
│  │  (Uvicorn) │  │  Dep     │  │  Auto-generation │  │
│  └─────┬──────┘  └────┬─────┘  └──────────────────┘  │
│        │              │                               │
│  ┌─────▼──────────────▼──────────────────────────┐   │
│  │              Route Handlers                    │   │
│  │  Dealerships │ Cars │ Services │ Search │ Sys  │   │
│  └─────────────────────┬─────────────────────────┘   │
│                        │                              │
│  ┌─────────────────────▼─────────────────────────┐   │
│  │           Pydantic Schemas (schemas.py)        │   │
│  │  Request validation │ Response serialization   │   │
│  └─────────────────────┬─────────────────────────┘   │
│                        │                              │
│  ┌─────────────────────▼─────────────────────────┐   │
│  │           SQLAlchemy ORM (models.py)           │   │
│  │  Dealership │ Car │ ServiceRecord              │   │
│  └─────────────────────┬─────────────────────────┘   │
│                        │                              │
│  ┌─────────────────────▼─────────────────────────┐   │
│  │           Database Layer (database.py)         │   │
│  │  Engine │ SessionLocal │ get_db dependency     │   │
│  └─────────────────────┬─────────────────────────┘   │
└────────────────────────┼─────────────────────────────┘
                         │ SQLite driver
                         ▼
                  ┌──────────────┐
                  │ dealership.db│
                  │   (SQLite)   │
                  └──────────────┘
```

## File Breakdown

### `database.py` — Database Configuration

The thinnest layer. Creates a SQLAlchemy engine pointed at a local SQLite file and exposes a `get_db()` generator that FastAPI uses as a dependency to inject database sessions into route handlers.

```
Engine (sqlite:///dealership.db)
    └── SessionLocal (sessionmaker)
         └── get_db() → yields Session per request
```

The `check_same_thread=False` argument is SQLite-specific. SQLite's default Python driver restricts connections to the thread that created them. Since FastAPI processes requests across a thread pool, this flag is required. It's safe here because each request gets its own session via the `get_db()` dependency — there's no concurrent access to a single connection.

### `models.py` — Data Models

Three SQLAlchemy ORM models define the database schema:

```
Dealership (1)
    │
    ├──< Car (many)
    │       │
    │       └──< ServiceRecord (many)
    │
    └── cascade: all, delete-orphan
```

**Dealership** — The top-level entity. Represents a physical car dealership location. Deleting a dealership cascades to all its cars and their service records.

**Car** — Belongs to exactly one dealership (but can be transferred). Tracks status via a `CarStatus` enum with four states:

```
                    ┌─────────────┐
           ┌───────│  available  │◄──────┐
           │       └──────┬──────┘       │
           │              │              │
      reserve()      sell()      complete_service()
           │              │        (if last open)
           ▼              ▼              │
    ┌────────────┐  ┌──────────┐  ┌──────┴───────┐
    │  reserved  │  │   sold   │  │  in_service  │
    └─────┬──────┘  └──────────┘  └──────────────┘
          │                              ▲
     unreserve()              create_service()
          │
          ▼
    ┌────────────┐
    │  available │
    └────────────┘
```

**ServiceRecord** — Belongs to a car. Tracks maintenance work with a `ServiceType` enum (oil change, brake inspection, etc.). Creating a service record sets the car's status to `in_service`. Completing the last open service record returns the car to `available`.

### `schemas.py` — Request/Response Contracts

Pydantic v2 models that define what the API accepts and returns. Organized into groups:

| Group | Schemas | Purpose |
|-------|---------|---------|
| Enums | `CarStatus`, `ServiceType`, `SortOrder`, `CarSortField`, `SearchResultType` | Constrained string values |
| Pagination | `PaginatedResponse[T]` | Generic wrapper for paginated lists |
| Dealership | `Create`, `Update`, `Response`, `WithCars`, `Stats` | Dealership CRUD + computed aggregations |
| Car | `Create`, `Update`, `Response`, `WithServices`, `BulkCreate`, `BulkResponse`, `TransferRequest` | Car CRUD + workflow operations |
| Service | `Create`, `Update`, `Response` | Service record CRUD |
| Composite | `SearchResult`, `SearchResponse`, `CompareRequest`, `CompareResponse`, `HealthResponse` | Cross-resource operations |

The separation between `Create`, `Update`, and `Response` schemas for each entity is a FastAPI convention. It enforces that:

- **Create** schemas only accept the fields needed to create a resource (no `id`, no timestamps)
- **Update** schemas make all fields optional (for PATCH semantics)
- **Response** schemas include computed and auto-generated fields (`id`, `created_at`, `status`)

### `main.py` — Application and Routes

The FastAPI application with all 28 route handlers. Routes are organized by tag:

**System** (1 endpoint)
- `GET /health` — Returns API version, database connectivity, and record counts.

**Dealerships** (6 endpoints)
- Standard CRUD with pagination on the list endpoint.
- `GET /dealerships/{id}/stats` — Computed aggregation endpoint that calculates inventory value, sales revenue, average days to sell, and most common make from raw car data.

**Cars** (12 endpoints)
- CRUD with advanced listing (10 filter params, 2 sort params, pagination).
- `POST /dealerships/{id}/cars/bulk` — Accepts an array of cars. Uses `db.flush()` per car to catch individual failures without rolling back the entire batch. Returns both `created` and `failed` arrays.
- `POST /cars/{id}/sell`, `/reserve`, `/unreserve` — State transition endpoints with guard clauses.
- `POST /cars/{id}/transfer` — Moves a car to a different dealership by updating its `dealership_id`.
- `POST /cars/{id}/photo` — Multipart file upload. Validates content type, generates a UUID-based filename, saves to `uploads/`, and stores the URL path on the car record.
- `POST /cars/compare` — Accepts 2–5 car IDs, returns the cars with computed min/max/spread for price, mileage, and year.

**Service Records** (6 endpoints)
- Created via the 3-level nested path: `POST /dealerships/{id}/cars/{id}/services`
- `POST /services/{id}/complete` — Marks service complete, checks if any open services remain, and returns the car to `available` if not.

**Search** (1 endpoint)
- `GET /search?q=...` — Searches across dealership names/addresses and car make/model/color/VIN. Returns a unified `SearchResult` list with `result_type` discriminator and basic relevance scoring.

## Authentication Model

Authentication is implemented as a FastAPI dependency (`verify_api_key`) that reads the `x-api-key` header. It's applied selectively:

| Requires Auth | Public |
|---------------|--------|
| Create / Update / Delete (all entities) | List / Get (all entities) |
| Sell / Reserve / Unreserve / Transfer | Search |
| Photo upload | Health check |
| Bulk operations | Compare |
| Complete service | Stats |

The API key is a single static value loaded from the `DEALERSHIP_API_KEY` environment variable (default: `demo-key-12345`). This is intentionally simple — the goal is to test how doc generators render endpoints with mixed auth requirements, not to implement a real auth system.

## Data Flow: Selling a Car

A typical state-changing operation follows this path:

```
1. Client sends POST /cars/1/sell
   Headers: x-api-key: demo-key-12345

2. FastAPI dependency injection:
   a. verify_api_key() checks the header → 401 if invalid
   b. get_db() opens a SQLAlchemy session

3. Route handler (mark_car_sold):
   a. db.get(Car, 1) → loads the car or raises 404
   b. Guard: car.is_sold → 400 "already sold"
   c. Guard: car.status == IN_SERVICE → 409 "in service"
   d. Guard: car.status == RESERVED → 400 "reserved"
   e. Mutate: car.is_sold = True, car.status = SOLD, car.sold_at = now
   f. db.commit() → writes to SQLite
   g. db.refresh(car) → reloads with DB-generated values

4. FastAPI serialization:
   a. CarResponse schema validates the ORM object (from_attributes=True)
   b. JSON response with 200 status
```

## Error Handling

The API uses FastAPI's `HTTPException` for all error responses. Status codes are chosen to match HTTP semantics:

| Code | Meaning | Example |
|------|---------|---------|
| 400 | Bad request / business rule violation | Selling an already-sold car |
| 401 | Missing or invalid API key | No `x-api-key` header |
| 404 | Resource not found | Car ID doesn't exist |
| 409 | Conflict with current state | Duplicate VIN, selling a car in service |
| 422 | Validation failure | Invalid file type, missing required field |

FastAPI automatically generates 422 responses for Pydantic validation failures with detailed error locations (`["body", "price"]`).

## Static File Serving

Uploaded car photos are saved to the `uploads/` directory and served via FastAPI's `StaticFiles` mount at `/uploads/`. The car's `photo_url` field stores the relative path (e.g., `/uploads/1_a3f2b1c4.jpg`).

The `uploads/` directory is `.gitignore`d since it contains user-generated content that shouldn't be version controlled.
