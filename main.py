import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Car, CarStatus, Dealership, ServiceRecord, ServiceType
from schemas import (
    BulkCarCreate,
    BulkCarResponse,
    CarCreate,
    CarResponse,
    CarSortField,
    CarUpdate,
    CarWithServices,
    CompareRequest,
    CompareResponse,
    DealershipCreate,
    DealershipResponse,
    DealershipStats,
    DealershipUpdate,
    DealershipWithCars,
    HealthResponse,
    PaginatedResponse,
    SearchResponse,
    SearchResult,
    SearchResultType,
    ServiceRecordCreate,
    ServiceRecordResponse,
    ServiceRecordUpdate,
    SortOrder,
    TransferCarRequest,
)

Base.metadata.create_all(bind=engine)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="Car Dealership API",
    version="2.0.0",
    description="A comprehensive API for managing car dealerships, inventory, and service records.",
    contact={"name": "API Support", "email": "api@cardealership.example"},
    license_info={"name": "MIT"},
)

API_KEY = os.environ.get("DEALERSHIP_API_KEY", "demo-key-12345")


def verify_api_key(x_api_key: str = Header(..., description="API key for authentication")):
    if x_api_key != API_KEY:
        raise HTTPException(401, "Invalid API key")
    return x_api_key


# ── Health ───────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        db_connected=True,
        total_dealerships=db.query(func.count(Dealership.id)).scalar(),
        total_cars=db.query(func.count(Car.id)).scalar(),
    )


# ── Dealership CRUD ──────────────────────────────────────────────


@app.post(
    "/dealerships",
    response_model=DealershipResponse,
    status_code=201,
    tags=["Dealerships"],
    summary="Create a new dealership",
    responses={409: {"description": "Dealership with this name already exists"}},
)
def create_dealership(
    body: DealershipCreate,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    existing = db.query(Dealership).filter(Dealership.name == body.name).first()
    if existing:
        raise HTTPException(409, f"Dealership '{body.name}' already exists")
    dealership = Dealership(**body.model_dump())
    db.add(dealership)
    db.commit()
    db.refresh(dealership)
    return dealership


@app.get(
    "/dealerships",
    response_model=PaginatedResponse[DealershipResponse],
    tags=["Dealerships"],
    summary="List dealerships with pagination and filters",
)
def list_dealerships(
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    min_rating: float | None = Query(None, ge=0, le=5, description="Minimum rating filter"),
    name: str | None = Query(None, description="Search by name (partial match)"),
    db: Session = Depends(get_db),
):
    query = db.query(Dealership)
    if is_active is not None:
        query = query.filter(Dealership.is_active == is_active)
    if min_rating is not None:
        query = query.filter(Dealership.rating >= min_rating)
    if name:
        query = query.filter(Dealership.name.ilike(f"%{name}%"))
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset, has_more=(offset + limit) < total)


@app.get(
    "/dealerships/{dealership_id}",
    response_model=DealershipWithCars,
    tags=["Dealerships"],
    summary="Get a dealership with its car inventory",
    responses={404: {"description": "Dealership not found"}},
)
def get_dealership(dealership_id: int, db: Session = Depends(get_db)):
    dealership = db.get(Dealership, dealership_id)
    if not dealership:
        raise HTTPException(404, "Dealership not found")
    return dealership


@app.patch(
    "/dealerships/{dealership_id}",
    response_model=DealershipResponse,
    tags=["Dealerships"],
    summary="Partially update a dealership",
)
def update_dealership(
    dealership_id: int,
    body: DealershipUpdate,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    dealership = db.get(Dealership, dealership_id)
    if not dealership:
        raise HTTPException(404, "Dealership not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(dealership, key, value)
    db.commit()
    db.refresh(dealership)
    return dealership


@app.delete("/dealerships/{dealership_id}", status_code=204, tags=["Dealerships"])
def delete_dealership(
    dealership_id: int,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    dealership = db.get(Dealership, dealership_id)
    if not dealership:
        raise HTTPException(404, "Dealership not found")
    db.delete(dealership)
    db.commit()


@app.get(
    "/dealerships/{dealership_id}/stats",
    response_model=DealershipStats,
    tags=["Dealerships"],
    summary="Get aggregated statistics for a dealership",
)
def get_dealership_stats(dealership_id: int, db: Session = Depends(get_db)):
    dealership = db.get(Dealership, dealership_id)
    if not dealership:
        raise HTTPException(404, "Dealership not found")

    cars = db.query(Car).filter(Car.dealership_id == dealership_id).all()
    sold_cars = [c for c in cars if c.status == CarStatus.SOLD]
    available = [c for c in cars if c.status == CarStatus.AVAILABLE]
    reserved = [c for c in cars if c.status == CarStatus.RESERVED]
    in_service = [c for c in cars if c.status == CarStatus.IN_SERVICE]

    days_to_sell = []
    for c in sold_cars:
        if c.sold_at:
            days_to_sell.append((c.sold_at - c.created_at).days)

    makes = [c.make for c in cars]
    most_common_make = max(set(makes), key=makes.count) if makes else None

    services = db.query(ServiceRecord).join(Car).filter(Car.dealership_id == dealership_id).all()

    return DealershipStats(
        dealership_id=dealership_id,
        dealership_name=dealership.name,
        total_cars=len(cars),
        available_cars=len(available),
        reserved_cars=len(reserved),
        sold_cars=len(sold_cars),
        in_service_cars=len(in_service),
        total_inventory_value=sum(c.price for c in available),
        total_sales_revenue=sum(c.price for c in sold_cars),
        average_car_price=sum(c.price for c in cars) / len(cars) if cars else 0,
        average_days_to_sell=sum(days_to_sell) / len(days_to_sell) if days_to_sell else None,
        most_common_make=most_common_make,
        service_records_count=len(services),
        total_service_revenue=sum(s.cost for s in services),
    )


# ── Car CRUD ─────────────────────────────────────────────────────


@app.post(
    "/dealerships/{dealership_id}/cars",
    response_model=CarResponse,
    status_code=201,
    tags=["Cars"],
    summary="Add a car to a dealership",
    responses={
        404: {"description": "Dealership not found"},
        409: {"description": "Car with this VIN already exists"},
    },
)
def add_car(
    dealership_id: int,
    body: CarCreate,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    if not db.get(Dealership, dealership_id):
        raise HTTPException(404, "Dealership not found")
    if body.vin:
        existing = db.query(Car).filter(Car.vin == body.vin).first()
        if existing:
            raise HTTPException(409, f"Car with VIN {body.vin} already exists")
    car = Car(dealership_id=dealership_id, **body.model_dump())
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


@app.post(
    "/dealerships/{dealership_id}/cars/bulk",
    response_model=BulkCarResponse,
    status_code=201,
    tags=["Cars"],
    summary="Add multiple cars to a dealership at once",
)
def bulk_add_cars(
    dealership_id: int,
    body: BulkCarCreate,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    if not db.get(Dealership, dealership_id):
        raise HTTPException(404, "Dealership not found")
    created = []
    failed = []
    for i, car_data in enumerate(body.cars):
        try:
            if car_data.vin:
                existing = db.query(Car).filter(Car.vin == car_data.vin).first()
                if existing:
                    raise ValueError(f"Duplicate VIN: {car_data.vin}")
            car = Car(dealership_id=dealership_id, **car_data.model_dump())
            db.add(car)
            db.flush()
            created.append(car)
        except Exception as e:
            failed.append({"index": i, "error": str(e), "data": car_data.model_dump()})
    db.commit()
    for car in created:
        db.refresh(car)
    return BulkCarResponse(created=created, failed=failed, total_created=len(created), total_failed=len(failed))


@app.get(
    "/dealerships/{dealership_id}/cars",
    response_model=PaginatedResponse[CarResponse],
    tags=["Cars"],
    summary="List cars with sorting, filtering, and pagination",
)
def list_cars(
    dealership_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: CarStatus | None = Query(None, description="Filter by car status"),
    is_sold: bool | None = Query(None, description="Filter by sold state"),
    make: str | None = Query(None, description="Filter by make (partial match)"),
    color: str | None = Query(None, description="Filter by color"),
    min_price: float | None = Query(None, ge=0, description="Minimum price"),
    max_price: float | None = Query(None, ge=0, description="Maximum price"),
    min_year: int | None = Query(None, ge=1900, description="Minimum model year"),
    max_year: int | None = Query(None, le=2030, description="Maximum model year"),
    max_mileage: int | None = Query(None, ge=0, description="Maximum mileage"),
    sort_by: CarSortField = Query(CarSortField.CREATED_AT, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort direction"),
    db: Session = Depends(get_db),
):
    if not db.get(Dealership, dealership_id):
        raise HTTPException(404, "Dealership not found")

    query = db.query(Car).filter(Car.dealership_id == dealership_id)

    if status is not None:
        query = query.filter(Car.status == status)
    if is_sold is not None:
        query = query.filter(Car.is_sold == is_sold)
    if make:
        query = query.filter(Car.make.ilike(f"%{make}%"))
    if color:
        query = query.filter(Car.color.ilike(f"%{color}%"))
    if min_price is not None:
        query = query.filter(Car.price >= min_price)
    if max_price is not None:
        query = query.filter(Car.price <= max_price)
    if min_year is not None:
        query = query.filter(Car.year >= min_year)
    if max_year is not None:
        query = query.filter(Car.year <= max_year)
    if max_mileage is not None:
        query = query.filter(Car.mileage <= max_mileage)

    sort_column = getattr(Car, sort_by.value)
    if sort_order == SortOrder.DESC:
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset, has_more=(offset + limit) < total)


@app.get(
    "/cars/{car_id}",
    response_model=CarWithServices,
    tags=["Cars"],
    summary="Get a car with its full service history",
)
def get_car(car_id: int, db: Session = Depends(get_db)):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    return car


@app.patch("/cars/{car_id}", response_model=CarResponse, tags=["Cars"])
def update_car(
    car_id: int,
    body: CarUpdate,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(car, key, value)
    db.commit()
    db.refresh(car)
    return car


@app.post(
    "/cars/{car_id}/sell",
    response_model=CarResponse,
    tags=["Cars"],
    summary="Mark a car as sold",
    responses={
        400: {"description": "Car is already sold"},
        409: {"description": "Car is currently in service"},
    },
)
def mark_car_sold(
    car_id: int,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    if car.is_sold:
        raise HTTPException(400, "Car is already sold")
    if car.status == CarStatus.IN_SERVICE:
        raise HTTPException(409, "Cannot sell a car that is currently in service")
    if car.status == CarStatus.RESERVED:
        raise HTTPException(400, "Car is currently reserved — unreserve it first")
    car.is_sold = True
    car.status = CarStatus.SOLD
    car.sold_at = datetime.utcnow()
    db.commit()
    db.refresh(car)
    return car


@app.post(
    "/cars/{car_id}/reserve",
    response_model=CarResponse,
    tags=["Cars"],
    summary="Reserve a car for a customer",
    responses={400: {"description": "Car is not available for reservation"}},
)
def reserve_car(
    car_id: int,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    if car.status != CarStatus.AVAILABLE:
        raise HTTPException(400, f"Car cannot be reserved (current status: {car.status.value})")
    car.status = CarStatus.RESERVED
    db.commit()
    db.refresh(car)
    return car


@app.post(
    "/cars/{car_id}/unreserve",
    response_model=CarResponse,
    tags=["Cars"],
    summary="Release a reservation on a car",
    responses={400: {"description": "Car is not currently reserved"}},
)
def unreserve_car(
    car_id: int,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    if car.status != CarStatus.RESERVED:
        raise HTTPException(400, "Car is not currently reserved")
    car.status = CarStatus.AVAILABLE
    db.commit()
    db.refresh(car)
    return car


@app.post(
    "/cars/{car_id}/transfer",
    response_model=CarResponse,
    tags=["Cars"],
    summary="Transfer a car to a different dealership",
    responses={
        400: {"description": "Car cannot be transferred in current state"},
        404: {"description": "Car or target dealership not found"},
    },
)
def transfer_car(
    car_id: int,
    body: TransferCarRequest,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    if car.is_sold:
        raise HTTPException(400, "Cannot transfer a sold car")
    target = db.get(Dealership, body.target_dealership_id)
    if not target:
        raise HTTPException(404, "Target dealership not found")
    if car.dealership_id == body.target_dealership_id:
        raise HTTPException(400, "Car is already at this dealership")
    car.dealership_id = body.target_dealership_id
    db.commit()
    db.refresh(car)
    return car


@app.post(
    "/cars/{car_id}/photo",
    response_model=CarResponse,
    tags=["Cars"],
    summary="Upload a photo for a car",
    responses={422: {"description": "Invalid file type"}},
)
def upload_car_photo(
    car_id: int,
    file: UploadFile = File(..., description="Image file (JPEG, PNG, or WebP)"),
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(422, f"File type {file.content_type} not allowed. Use JPEG, PNG, or WebP.")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "jpg"
    filename = f"{car_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    car.photo_url = f"/uploads/{filename}"
    db.commit()
    db.refresh(car)
    return car


@app.delete("/cars/{car_id}", status_code=204, tags=["Cars"])
def delete_car(
    car_id: int,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    db.delete(car)
    db.commit()


@app.post(
    "/cars/compare",
    response_model=CompareResponse,
    tags=["Cars"],
    summary="Compare multiple cars side by side",
)
def compare_cars(body: CompareRequest, db: Session = Depends(get_db)):
    cars = db.query(Car).filter(Car.id.in_(body.car_ids)).all()
    if len(cars) < 2:
        raise HTTPException(400, "Need at least 2 valid car IDs to compare")

    prices = [c.price for c in cars]
    mileages = [c.mileage for c in cars]
    years = [c.year for c in cars]

    return CompareResponse(
        cars=cars,
        price_range={"min": min(prices), "max": max(prices), "spread": max(prices) - min(prices)},
        mileage_range={"min": min(mileages), "max": max(mileages), "spread": max(mileages) - min(mileages)},
        year_range={"min": min(years), "max": max(years), "spread": max(years) - min(years)},
    )


# ── Service Records (3-level nesting) ───────────────────────────


@app.post(
    "/dealerships/{dealership_id}/cars/{car_id}/services",
    response_model=ServiceRecordResponse,
    status_code=201,
    tags=["Service Records"],
    summary="Create a service record for a car at a dealership",
    responses={400: {"description": "Car does not belong to this dealership"}},
)
def create_service_record(
    dealership_id: int,
    car_id: int,
    body: ServiceRecordCreate,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    if car.dealership_id != dealership_id:
        raise HTTPException(400, "Car does not belong to this dealership")
    record = ServiceRecord(car_id=car_id, **body.model_dump())
    car.status = CarStatus.IN_SERVICE
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get(
    "/dealerships/{dealership_id}/cars/{car_id}/services",
    response_model=list[ServiceRecordResponse],
    tags=["Service Records"],
    summary="List all service records for a car",
)
def list_service_records(
    dealership_id: int,
    car_id: int,
    service_type: ServiceType | None = Query(None, description="Filter by service type"),
    is_completed: bool | None = Query(None, description="Filter by completion status"),
    db: Session = Depends(get_db),
):
    car = db.get(Car, car_id)
    if not car:
        raise HTTPException(404, "Car not found")
    if car.dealership_id != dealership_id:
        raise HTTPException(400, "Car does not belong to this dealership")

    query = db.query(ServiceRecord).filter(ServiceRecord.car_id == car_id)
    if service_type is not None:
        query = query.filter(ServiceRecord.service_type == service_type)
    if is_completed is not None:
        query = query.filter(ServiceRecord.is_completed == is_completed)
    return query.order_by(ServiceRecord.service_date.desc()).all()


@app.get(
    "/services/{service_id}",
    response_model=ServiceRecordResponse,
    tags=["Service Records"],
    summary="Get a single service record by ID",
)
def get_service_record(service_id: int, db: Session = Depends(get_db)):
    record = db.get(ServiceRecord, service_id)
    if not record:
        raise HTTPException(404, "Service record not found")
    return record


@app.patch(
    "/services/{service_id}",
    response_model=ServiceRecordResponse,
    tags=["Service Records"],
)
def update_service_record(
    service_id: int,
    body: ServiceRecordUpdate,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    record = db.get(ServiceRecord, service_id)
    if not record:
        raise HTTPException(404, "Service record not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


@app.post(
    "/services/{service_id}/complete",
    response_model=ServiceRecordResponse,
    tags=["Service Records"],
    summary="Mark a service as completed and return the car to available status",
    responses={400: {"description": "Service is already completed"}},
)
def complete_service(
    service_id: int,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    record = db.get(ServiceRecord, service_id)
    if not record:
        raise HTTPException(404, "Service record not found")
    if record.is_completed:
        raise HTTPException(400, "Service is already completed")
    record.is_completed = True
    record.completed_at = datetime.utcnow()

    car = db.get(Car, record.car_id)
    open_services = (
        db.query(ServiceRecord)
        .filter(ServiceRecord.car_id == car.id, ServiceRecord.is_completed == False, ServiceRecord.id != service_id)
        .count()
    )
    if open_services == 0:
        car.status = CarStatus.AVAILABLE

    db.commit()
    db.refresh(record)
    return record


@app.delete("/services/{service_id}", status_code=204, tags=["Service Records"])
def delete_service_record(
    service_id: int,
    db: Session = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    record = db.get(ServiceRecord, service_id)
    if not record:
        raise HTTPException(404, "Service record not found")
    db.delete(record)
    db.commit()


# ── Search ───────────────────────────────────────────────────────


@app.get(
    "/search",
    response_model=SearchResponse,
    tags=["Search"],
    summary="Search across dealerships and cars",
)
def global_search(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    result_type: SearchResultType | None = Query(None, description="Limit to a specific result type"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    results: list[SearchResult] = []

    if result_type is None or result_type == SearchResultType.DEALERSHIP:
        dealerships = (
            db.query(Dealership)
            .filter(or_(Dealership.name.ilike(f"%{q}%"), Dealership.address.ilike(f"%{q}%")))
            .limit(limit)
            .all()
        )
        for d in dealerships:
            score = 1.0 if q.lower() in d.name.lower() else 0.5
            results.append(
                SearchResult(
                    result_type=SearchResultType.DEALERSHIP,
                    id=d.id,
                    name=d.name,
                    detail=d.address,
                    score=score,
                )
            )

    if result_type is None or result_type == SearchResultType.CAR:
        cars = (
            db.query(Car)
            .filter(
                or_(
                    Car.make.ilike(f"%{q}%"),
                    Car.model.ilike(f"%{q}%"),
                    Car.color.ilike(f"%{q}%"),
                    Car.vin.ilike(f"%{q}%"),
                )
            )
            .limit(limit)
            .all()
        )
        for c in cars:
            score = 1.0 if q.lower() in c.make.lower() else 0.7
            results.append(
                SearchResult(
                    result_type=SearchResultType.CAR,
                    id=c.id,
                    name=f"{c.year} {c.make} {c.model}",
                    detail=f"{c.color} - ${c.price:,.0f}",
                    score=score,
                )
            )

    results.sort(key=lambda r: r.score, reverse=True)
    return SearchResponse(query=q, total_results=len(results), results=results[:limit])


# ── Static files for uploads ─────────────────────────────────────

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
