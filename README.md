# Car Dealership API

A comprehensive REST API for managing car dealerships, vehicle inventory, and service records. Built with FastAPI and SQLite.

## Quick Start

```bash
# Clone and set up
git clone https://github.com/gmiggan/car-dealership-api.git
cd car-dealership-api

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --port 8111
```

Open [http://localhost:8111/docs](http://localhost:8111/docs) for the interactive Swagger UI.

## Authentication

Write operations require an API key passed via the `x-api-key` header. The default key for development is `demo-key-12345`. Override it by setting the `DEALERSHIP_API_KEY` environment variable:

```bash
export DEALERSHIP_API_KEY="your-secret-key"
```

Read-only endpoints (listings, search, health check) are public.

## API Overview

| Group | Endpoints | Description |
|-------|-----------|-------------|
| **System** | 1 | Health check with DB status |
| **Dealerships** | 6 | CRUD + aggregated stats |
| **Cars** | 12 | CRUD, bulk import, reserve/sell workflow, transfer, photo upload, comparison |
| **Service Records** | 6 | CRUD with completion workflow (nested under dealerships and cars) |
| **Search** | 1 | Global search across dealerships and cars with relevance scoring |

**Total: 28 endpoints**

## Key Features

- **Pagination** — All list endpoints return paginated responses with `total`, `has_more`, `limit`, and `offset` metadata.
- **Sorting & Filtering** — Car listings support sorting by price, year, mileage, or creation date, with filters for make, color, price range, year range, mileage, and status.
- **Bulk Operations** — Add up to 50 cars in a single request with per-item error reporting.
- **Status Workflow** — Cars move through `available` → `reserved` → `sold` (or `in_service` during maintenance).
- **Service History** — Full service record tracking with mechanic assignment and completion workflow.
- **File Upload** — Multipart photo upload for car listings (JPEG, PNG, WebP).
- **VIN Uniqueness** — Optional VIN field with database-level uniqueness enforcement.
- **Cross-Dealership Transfer** — Move cars between dealerships while preserving history.
- **Car Comparison** — Compare 2–5 cars side-by-side with computed price/mileage/year ranges.

## Example Requests

### Create a dealership

```bash
curl -X POST http://localhost:8111/dealerships \
  -H "Content-Type: application/json" \
  -H "x-api-key: demo-key-12345" \
  -d '{
    "name": "Miggan Motors",
    "address": "123 Main St, Dublin",
    "phone": "01-555-1234",
    "email": "info@miggan.ie",
    "website": "https://miggan.ie"
  }'
```

### Bulk add cars

```bash
curl -X POST http://localhost:8111/dealerships/1/cars/bulk \
  -H "Content-Type: application/json" \
  -H "x-api-key: demo-key-12345" \
  -d '{
    "cars": [
      {"make": "BMW", "model": "M3", "year": 2024, "price": 75000, "color": "Alpine White"},
      {"make": "Toyota", "model": "Supra", "year": 2023, "price": 55000, "color": "Red"}
    ]
  }'
```

### Search

```bash
curl "http://localhost:8111/search?q=BMW&result_type=car"
```

### Get dealership stats

```bash
curl http://localhost:8111/dealerships/1/stats
```

## Project Structure

```
car-dealership-api/
├── main.py            # FastAPI application and route definitions
├── models.py          # SQLAlchemy ORM models (Dealership, Car, ServiceRecord)
├── schemas.py         # Pydantic request/response schemas and enums
├── database.py        # Database engine and session configuration
├── requirements.txt   # Python dependencies
└── docs/
    ├── purpose.md     # Project purpose and design goals
    └── architecture.md # Technical architecture overview
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ORM | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (mapped columns) |
| Validation | [Pydantic v2](https://docs.pydantic.dev/) |
| Database | SQLite (file-based, zero config) |
| Server | [Uvicorn](https://www.uvicorn.org/) |

## OpenAPI Spec

The auto-generated OpenAPI 3.1 spec is available at:

```
GET http://localhost:8111/openapi.json
```

## License

MIT
