import uuid
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import DateTime, Date, Float, ForeignKey, Integer, Numeric, String, Text, func, Boolean, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base_class import Base


class City(Base):
    __tablename__ = "cities"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="India")
    apartments: Mapped[List["Apartment"]] = relationship("Apartment", back_populates="city", cascade="all, delete-orphan")


class Apartment(Base):
    __tablename__ = "apartments"
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    cover_image: Mapped[Optional[str]] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(50), default="Ready to Move")
    total_floors: Mapped[int] = mapped_column(Integer, default=1)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255))
    contact_number: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    builder_name: Mapped[Optional[str]] = mapped_column(String(255))
    construction_status: Mapped[str] = mapped_column(String(100), default="Completed")
    possession_status: Mapped[str] = mapped_column(String(100), default="Ready to Move")
    construction_progress: Mapped[int] = mapped_column(Integer, default=100)
    estimated_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    amenities: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    city: Mapped["City"] = relationship("City", back_populates="apartments")
    floors: Mapped[List["Floor"]] = relationship("Floor", back_populates="apartment", cascade="all, delete-orphan")
    gallery_images: Mapped[List["ApartmentGalleryImage"]] = relationship("ApartmentGalleryImage", back_populates="apartment", cascade="all, delete-orphan")
    complaints: Mapped[List["Complaint"]] = relationship("Complaint", back_populates="apartment", cascade="all, delete-orphan")
    announcements: Mapped[List["Announcement"]] = relationship("Announcement", back_populates="apartment", cascade="all, delete-orphan")
    facility_bookings: Mapped[List["FacilityBooking"]] = relationship("FacilityBooking", back_populates="apartment", cascade="all, delete-orphan")
    residents: Mapped[List["Resident"]] = relationship("Resident", back_populates="apartment", cascade="all, delete-orphan")
    community_rules: Mapped[List["CommunityRule"]] = relationship("CommunityRule", back_populates="apartment", cascade="all, delete-orphan")


class ApartmentGalleryImage(Base):
    __tablename__ = "apartment_gallery_images"
    apartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(String(255))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    apartment: Mapped["Apartment"] = relationship("Apartment", back_populates="gallery_images")


class Floor(Base):
    __tablename__ = "floors"
    apartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False)
    floor_name: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    apartment: Mapped["Apartment"] = relationship("Apartment", back_populates="floors")
    flats: Mapped[List["Flat"]] = relationship("Flat", back_populates="floor", cascade="all, delete-orphan")


class Flat(Base):
    __tablename__ = "flats"
    floor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"), nullable=False, index=True)
    apartment_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=True, index=True)
    flat_number: Mapped[str] = mapped_column(String(50), nullable=False)
    flat_type: Mapped[str] = mapped_column(String(20), nullable=False)
    area_sqft: Mapped[float] = mapped_column(Float, nullable=False)
    facing_direction: Mapped[str] = mapped_column(String(50), nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, default=1)
    bathrooms: Mapped[int] = mapped_column(Integer, default=1)
    balconies: Mapped[int] = mapped_column(Integer, default=0)
    parking_slots: Mapped[int] = mapped_column(Integer, default=0)
    hall: Mapped[int] = mapped_column(Integer, default=1)
    kitchen: Mapped[int] = mapped_column(Integer, default=1)
    dining: Mapped[int] = mapped_column(Integer, default=0)
    price_buy: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    price_rent: Mapped[Optional[float]] = mapped_column(Numeric(15, 2))
    maintenance_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="Available", index=True)
    short_description: Mapped[Optional[str]] = mapped_column(Text)
    long_description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    floor: Mapped["Floor"] = relationship("Floor", back_populates="flats")
    images: Mapped[List["FlatImage"]] = relationship("FlatImage", back_populates="flat", cascade="all, delete-orphan")
    wishlisted_by: Mapped[List["Wishlist"]] = relationship("Wishlist", back_populates="flat", cascade="all, delete-orphan")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="flat", cascade="all, delete-orphan")
    maintenance_records: Mapped[List["Maintenance"]] = relationship("Maintenance", back_populates="flat", cascade="all, delete-orphan")
    visitors: Mapped[List["Visitor"]] = relationship("Visitor", back_populates="flat", cascade="all, delete-orphan")
    vehicles: Mapped[List["Vehicle"]] = relationship("Vehicle", back_populates="flat", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="flat", cascade="all, delete-orphan")
    residents: Mapped[List["Resident"]] = relationship("Resident", back_populates="flat", cascade="all, delete-orphan")
    maintenance_bills: Mapped[List["MaintenanceBill"]] = relationship("MaintenanceBill", back_populates="flat", cascade="all, delete-orphan")
    rent_records: Mapped[List["RentRecord"]] = relationship("RentRecord", back_populates="flat", cascade="all, delete-orphan")

    @property
    def floor_name(self) -> Optional[str]:
        return self.floor.floor_name if self.floor else None

    @property
    def apartment_name(self) -> Optional[str]:
        return self.floor.apartment.name if (self.floor and self.floor.apartment) else None


class FlatImage(Base):
    __tablename__ = "flat_images"
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    image_type: Mapped[Optional[str]] = mapped_column(String(100))
    caption: Mapped[Optional[str]] = mapped_column(String(255))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    flat: Mapped["Flat"] = relationship("Flat", back_populates="images")


class Wishlist(Base):
    __tablename__ = "wishlists"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    flat: Mapped["Flat"] = relationship("Flat", back_populates="wishlisted_by")


class User(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(50), default="Customer")
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="user", cascade="all, delete-orphan")
    maintenance_records: Mapped[List["Maintenance"]] = relationship("Maintenance", back_populates="user", cascade="all, delete-orphan")
    complaints: Mapped[List["Complaint"]] = relationship("Complaint", back_populates="user", cascade="all, delete-orphan")
    facility_bookings: Mapped[List["FacilityBooking"]] = relationship("FacilityBooking", back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    resident_profile: Mapped[Optional["Resident"]] = relationship("Resident", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Booking(Base):
    __tablename__ = "bookings"
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_type: Mapped[str] = mapped_column(String(50))
    amount_paid: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="Pending", index=True)
    hold_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    flat: Mapped["Flat"] = relationship("Flat", back_populates="bookings")
    user: Mapped["User"] = relationship("User", back_populates="bookings")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="booking", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="booking", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payment_type: Mapped[str] = mapped_column(String(100), default="Advance Booking")
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    booking: Mapped["Booking"] = relationship("Booking", back_populates="payments")


class Maintenance(Base):
    __tablename__ = "maintenance"
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    due_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="Unpaid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    flat: Mapped["Flat"] = relationship("Flat", back_populates="maintenance_records")
    user: Mapped["User"] = relationship("User", back_populates="maintenance_records")


class Complaint(Base):
    __tablename__ = "complaints"
    apartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resident_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("residents.id", ondelete="SET NULL"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(100), default="Other")
    priority: Mapped[str] = mapped_column(String(20), default="Medium")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Open")
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    apartment: Mapped["Apartment"] = relationship("Apartment", back_populates="complaints")
    user: Mapped["User"] = relationship("User", back_populates="complaints")
    resident: Mapped[Optional["Resident"]] = relationship("Resident", back_populates="complaints")


class Announcement(Base):
    __tablename__ = "announcements"
    apartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    announcement_type: Mapped[str] = mapped_column(String(50), default="General")
    publish_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    apartment: Mapped["Apartment"] = relationship("Apartment", back_populates="announcements")


class Visitor(Base):
    __tablename__ = "visitors"
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    resident_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("residents.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    purpose: Mapped[Optional[str]] = mapped_column(String(255))
    visit_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    visit_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="Pending")
    qr_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_in: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    check_out: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    flat: Mapped["Flat"] = relationship("Flat", back_populates="visitors")
    resident: Mapped[Optional["Resident"]] = relationship("Resident", back_populates="visitors")


class Vehicle(Base):
    __tablename__ = "vehicles"
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    resident_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("residents.id", ondelete="SET NULL"), nullable=True, index=True)
    vehicle_number: Mapped[str] = mapped_column(String(50), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(50))
    vehicle_make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parking_slot: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    flat: Mapped["Flat"] = relationship("Flat", back_populates="vehicles")
    resident: Mapped[Optional["Resident"]] = relationship("Resident", back_populates="vehicles")


class Document(Base):
    __tablename__ = "documents"
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    flat: Mapped["Flat"] = relationship("Flat", back_populates="documents")
    booking: Mapped[Optional["Booking"]] = relationship("Booking", back_populates="documents")


class Notification(Base):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user: Mapped["User"] = relationship("User", back_populates="notifications")


class FacilityBooking(Base):
    __tablename__ = "facility_bookings"
    apartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resident_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("residents.id", ondelete="SET NULL"), nullable=True, index=True)
    facility_name: Mapped[str] = mapped_column(String(100), nullable=False)
    booking_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    booking_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    duration_hours: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    apartment: Mapped["Apartment"] = relationship("Apartment", back_populates="facility_bookings")
    user: Mapped["User"] = relationship("User", back_populates="facility_bookings")
    resident: Mapped[Optional["Resident"]] = relationship("Resident", back_populates="facility_bookings")


# =============================================================
# STAGE 4  NEW MODELS
# =============================================================

class Resident(Base):
    __tablename__ = "residents"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    apartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("floors.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True)
    resident_type: Mapped[str] = mapped_column(String(20), nullable=False)
    move_in_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Active")
    agreement_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    emergency_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user: Mapped["User"] = relationship("User", back_populates="resident_profile")
    apartment: Mapped["Apartment"] = relationship("Apartment", back_populates="residents")
    floor: Mapped["Floor"] = relationship("Floor")
    flat: Mapped["Flat"] = relationship("Flat", back_populates="residents")
    complaints: Mapped[List["Complaint"]] = relationship("Complaint", back_populates="resident")
    visitors: Mapped[List["Visitor"]] = relationship("Visitor", back_populates="resident")
    vehicles: Mapped[List["Vehicle"]] = relationship("Vehicle", back_populates="resident")
    facility_bookings: Mapped[List["FacilityBooking"]] = relationship("FacilityBooking", back_populates="resident")
    maintenance_bills: Mapped[List["MaintenanceBill"]] = relationship("MaintenanceBill", back_populates="resident")
    rent_records: Mapped[List["RentRecord"]] = relationship("RentRecord", back_populates="resident")


class MaintenanceBill(Base):
    __tablename__ = "maintenance_bills"
    resident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("residents.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    late_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    payment_status: Mapped[str] = mapped_column(String(20), default="Pending")
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    resident: Mapped["Resident"] = relationship("Resident", back_populates="maintenance_bills")
    flat: Mapped["Flat"] = relationship("Flat", back_populates="maintenance_bills")


class RentRecord(Base):
    __tablename__ = "rent_records"
    resident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("residents.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="Pending")
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    resident: Mapped["Resident"] = relationship("Resident", back_populates="rent_records")
    flat: Mapped["Flat"] = relationship("Flat", back_populates="rent_records")


class CommunityRule(Base):
    __tablename__ = "community_rules"
    apartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="General")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    apartment: Mapped["Apartment"] = relationship("Apartment", back_populates="community_rules")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    user: Mapped["User"] = relationship("User")

class SiteVisit(Base):
    __tablename__ = "site_visits"
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    apartment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apartments.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("flats.id", ondelete="SET NULL"), nullable=True, index=True)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    visit_time: Mapped[str] = mapped_column(String(50), nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="Pending") # Pending, Approved, Rejected, Rescheduled
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    customer: Mapped["User"] = relationship("User")
    apartment: Mapped["Apartment"] = relationship("Apartment")
    flat: Mapped["Flat"] = relationship("Flat")


class ResidentAccessRequest(Base):
    __tablename__ = "resident_access_requests"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    flat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flats.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="Pending") # Pending, Approved, Rejected
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approval_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    customer: Mapped["User"] = relationship("User")
    booking: Mapped["Booking"] = relationship("Booking")
    flat: Mapped["Flat"] = relationship("Flat")
    document: Mapped["Document"] = relationship("Document")
