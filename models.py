import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class CarStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"
    IN_SERVICE = "in_service"


class ServiceType(str, enum.Enum):
    OIL_CHANGE = "oil_change"
    TIRE_ROTATION = "tire_rotation"
    BRAKE_INSPECTION = "brake_inspection"
    FULL_INSPECTION = "full_inspection"
    ENGINE_REPAIR = "engine_repair"
    BODY_WORK = "body_work"
    DETAILING = "detailing"
    OTHER = "other"


class Dealership(Base):
    __tablename__ = "dealerships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(300), nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cars: Mapped[list["Car"]] = relationship(back_populates="dealership", cascade="all, delete-orphan")


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dealership_id: Mapped[int] = mapped_column(ForeignKey("dealerships.id"))
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    color: Mapped[str] = mapped_column(String(50))
    mileage: Mapped[int] = mapped_column(Integer, default=0)
    vin: Mapped[str | None] = mapped_column(String(17), unique=True, nullable=True)
    status: Mapped[CarStatus] = mapped_column(Enum(CarStatus), default=CarStatus.AVAILABLE)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_sold: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    dealership: Mapped["Dealership"] = relationship(back_populates="cars")
    service_records: Mapped[list["ServiceRecord"]] = relationship(back_populates="car", cascade="all, delete-orphan")


class ServiceRecord(Base):
    __tablename__ = "service_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"))
    service_type: Mapped[ServiceType] = mapped_column(Enum(ServiceType))
    description: Mapped[str] = mapped_column(Text)
    cost: Mapped[float] = mapped_column(Float)
    mechanic_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mileage_at_service: Mapped[int] = mapped_column(Integer)
    service_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    car: Mapped["Car"] = relationship(back_populates="service_records")
