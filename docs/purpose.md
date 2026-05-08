# Purpose and Design Goals

## Why This Project Exists

The Car Dealership API is a reference implementation of a multi-resource REST API. It was built to serve as a realistic test bed for API documentation generators — specifically to exercise edge cases in tools like Mintlify, Redocly, and Swagger UI that simpler CRUD examples don't reach.

Rather than a toy "todo list" API, this project models a domain with enough complexity to surface real-world documentation challenges: nested resources, state machines, bulk operations, file uploads, and mixed authentication requirements.

## Design Goals

### 1. Cover the OpenAPI Surface Area

The API was deliberately designed to include patterns that stress-test OpenAPI consumers:

- **Generic pagination wrappers** — `PaginatedResponse[T]` is a generic Pydantic model that wraps different item types. Doc generators must resolve the generic and display the concrete `items` schema for each endpoint.
- **Enum parameters everywhere** — Query parameters, request body fields, and response fields all use string enums (`CarStatus`, `ServiceType`, `SortOrder`, `CarSortField`). Generators need to render the allowed values and ideally link to a shared enum definition.
- **3-level nested routes** — The service record endpoints live at `/dealerships/{dealership_id}/cars/{car_id}/services`. Many doc generators assume at most two path parameters.
- **Mixed content types** — Most endpoints accept `application/json`, but the photo upload endpoint uses `multipart/form-data`. The generated docs should switch the request body UI accordingly.
- **Selective authentication** — Write endpoints require an `x-api-key` header; read endpoints are public. Generators should render a lock icon and header requirement only where needed.
- **Multiple error responses** — Individual endpoints declare different HTTP status codes (400, 404, 409, 422) with distinct descriptions. Generators should display all of them, not just the happy path.

### 2. Model a Realistic Domain

The dealership domain has enough moving parts to feel real without being overwhelming:

- **Two core entities** (Dealership, Car) with a one-to-many relationship
- **One nested entity** (ServiceRecord) that creates a three-level hierarchy
- **A state machine** (Car status: available → reserved → sold, with an `in_service` detour)
- **Business rules** (can't sell a reserved car, can't transfer a sold car, completing the last service returns a car to available)
- **Computed aggregations** (dealership stats: inventory value, average days to sell, most common make)

This makes the API useful beyond documentation testing — it works as a teaching example for REST API design patterns.

### 3. Stay Zero-Config

The API uses SQLite with automatic table creation. There are no migrations to run, no database server to install, no environment variables to set (the API key has a default). Clone, `pip install`, and `uvicorn` — that's it.

This matters for a demo project. If someone needs to debug why their Mintlify configuration isn't rendering an endpoint correctly, they shouldn't also be debugging database connectivity.

## What This Project Is Not

- **Not production software.** There's no rate limiting, no request logging, no CORS configuration, no connection pooling, and the authentication is a single static API key.
- **Not a framework template.** The entire app lives in four files. There's no router splitting, no dependency injection container, no middleware stack. This is intentional — the goal is readability, not scalability.
- **Not an ORM tutorial.** The SQLAlchemy usage is straightforward and doesn't demonstrate advanced patterns like hybrid properties, polymorphic inheritance, or async sessions.

## Endpoint Design Decisions

### Why PATCH instead of PUT?

All update endpoints use `PATCH` with `exclude_unset=True` on the Pydantic model. This gives true partial updates — the caller only sends the fields they want to change, and omitted fields remain untouched. `PUT` would require the caller to send the complete object every time, which is more error-prone for a demo where people are testing individual fields.

### Why separate `/sell`, `/reserve`, `/unreserve` endpoints?

These could be modeled as `PATCH /cars/{id}` with `{"status": "sold"}`. But explicit action endpoints make the state machine visible in the API surface. A doc generator should render them as distinct operations with their own descriptions and error responses, which is a better stress test than a generic update.

### Why a flat `/cars/{id}` alongside nested `/dealerships/{id}/cars`?

The nested path is used for creating and listing cars within a dealership. The flat path is used for operations on a specific car (update, sell, transfer) where the dealership context is already implied by the car's ID. This mixed nesting is common in real APIs and tests whether doc generators can group endpoints sensibly across different path prefixes.

### Why `/cars/compare` uses POST?

The compare endpoint accepts a list of car IDs. While this could be a GET with repeated query parameters (`?id=1&id=2&id=3`), using POST with a JSON body is cleaner and avoids URL length limits. It also tests whether doc generators correctly render a POST endpoint that doesn't create a resource — a common source of confusion in auto-generated docs.
