from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────


class CarStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"
    IN_SERVICE = "in_service"


class ServiceType(str, Enum):
    OIL_CHANGE = "oil_change"
    TIRE_ROTATION = "tire_rotation"
    BRAKE_INSPECTION = "brake_inspection"
    FULL_INSPECTION = "full_inspection"
    ENGINE_REPAIR = "engine_repair"
    BODY_WORK = "body_work"
    DETAILING = "detailing"
    OTHER = "other"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class CarSortField(str, Enum):
    PRICE = "price"
    YEAR = "year"
    MILEAGE = "mileage"
    CREATED_AT = "created_at"
    MAKE = "make"


class SearchResultType(str, Enum):
    DEALERSHIP = "dealership"
    CAR = "car"


# ── Pagination ───────────────────────────────────────────────────

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    has_more: bool


# ── Dealership Schemas ───────────────────────────────────────────


class DealershipCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, examples=["Miggan Motors"])
    address: str = Field(..., max_length=500, examples=["123 Main St, Dublin"])
    phone: str = Field(..., max_length=20, examples=["01-555-1234"])
    email: str | None = Field(None, max_length=200, examples=["info@migganmotors.ie"])
    website: str | None = Field(None, max_length=300, examples=["https://migganmotors.ie"])


class DealershipUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    address: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=20)
    email: str | None = None
    website: str | None = None
    rating: float | None = Field(None, ge=0, le=5)
    is_active: bool | None = None


class DealershipResponse(BaseModel):
    id: int
    name: str
    address: str
    phone: str
    email: str | None
    website: str | None
    rating: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DealershipStats(BaseModel):
    dealership_id: int
    dealership_name: str
    total_cars: int
    available_cars: int
    reserved_cars: int
    sold_cars: int
    in_service_cars: int
    total_inventory_value: float
    total_sales_revenue: float
    average_car_price: float
    average_days_to_sell: float | None
    most_common_make: str | None
    service_records_count: int
    total_service_revenue: float


# ── Car Schemas ──────────────────────────────────────────────────


class CarCreate(BaseModel):
    make: str = Field(..., min_length=1, max_length=100, examples=["BMW"])
    model: str = Field(..., min_length=1, max_length=100, examples=["M3"])
    year: int = Field(..., ge=1900, le=2030, examples=[2024])
    price: float = Field(..., gt=0, examples=[75000.00])
    color: str = Field(..., max_length=50, examples=["Alpine White"])
    mileage: int = Field(0, ge=0, examples=[1200])
    vin: str | None = Field(None, min_length=17, max_length=17, examples=["WBA5A5C55FD123456"])
    status: CarStatus = CarStatus.AVAILABLE
    description: str | None = Field(None, max_length=2000)


class CarUpdate(BaseModel):
    make: str | None = Field(None, min_length=1, max_length=100)
    model: str | None = Field(None, min_length=1, max_length=100)
    year: int | None = Field(None, ge=1900, le=2030)
    price: float | None = Field(None, gt=0)
    color: str | None = Field(None, max_length=50)
    mileage: int | None = Field(None, ge=0)
    vin: str | None = Field(None, min_length=17, max_length=17)
    status: CarStatus | None = None
    description: str | None = None


class CarResponse(BaseModel):
    id: int
    dealership_id: int
    make: str
    model: str
    year: int
    price: float
    color: str
    mileage: int
    vin: str | None
    status: CarStatus
    description: str | None
    photo_url: str | None
    is_sold: bool
    created_at: datetime
    updated_at: datetime
    sold_at: datetime | None

    model_config = {"from_attributes": True}


class CarWithServices(CarResponse):
    service_records: list["ServiceRecordResponse"] = []


class BulkCarCreate(BaseModel):
    cars: list[CarCreate] = Field(..., min_length=1, max_length=50)


class BulkCarResponse(BaseModel):
    created: list[CarResponse]
    failed: list[dict]
    total_created: int
    total_failed: int


class TransferCarRequest(BaseModel):
    target_dealership_id: int


# ── Service Record Schemas ───────────────────────────────────────


class ServiceRecordCreate(BaseModel):
    service_type: ServiceType
    description: str = Field(..., min_length=1, max_length=2000, examples=["Routine oil change and filter replacement"])
    cost: float = Field(..., ge=0, examples=[89.99])
    mechanic_name: str | None = Field(None, max_length=200, examples=["John Murphy"])
    mileage_at_service: int = Field(..., ge=0, examples=[15000])


class ServiceRecordUpdate(BaseModel):
    description: str | None = Field(None, min_length=1, max_length=2000)
    cost: float | None = Field(None, ge=0)
    mechanic_name: str | None = None


class ServiceRecordResponse(BaseModel):
    id: int
    car_id: int
    service_type: ServiceType
    description: str
    cost: float
    mechanic_name: str | None
    mileage_at_service: int
    service_date: datetime
    completed_at: datetime | None
    is_completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Composite Schemas ────────────────────────────────────────────


class DealershipWithCars(DealershipResponse):
    cars: list[CarResponse] = []


class SearchResult(BaseModel):
    result_type: SearchResultType
    id: int
    name: str
    detail: str
    score: float


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[SearchResult]


class HealthResponse(BaseModel):
    status: str
    version: str
    db_connected: bool
    total_dealerships: int
    total_cars: int


class CompareRequest(BaseModel):
    car_ids: list[int] = Field(..., min_length=2, max_length=5)


class CompareResponse(BaseModel):
    cars: list[CarResponse]
    price_range: dict
    mileage_range: dict
    year_range: dict
