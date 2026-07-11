from datetime import datetime
import uuid
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator

# -------------------------------------------------------------
# City Schemas
# -------------------------------------------------------------
class CityBase(BaseModel):
    name: str = Field(..., max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: str = Field("India", max_length=100)

class CityCreate(CityBase):
    pass

class CityResponse(CityBase):
    id: uuid.UUID

    class Config:
        from_attributes = True

# -------------------------------------------------------------
# Apartment Gallery Image Schemas
# -------------------------------------------------------------
class ApartmentGalleryImageCreate(BaseModel):
    image_url: str
    caption: Optional[str] = None
    display_order: int = 0

class ApartmentGalleryImageResponse(ApartmentGalleryImageCreate):
    id: uuid.UUID
    apartment_id: uuid.UUID

    class Config:
        from_attributes = True

# -------------------------------------------------------------
# Flat Image Schemas
# -------------------------------------------------------------
class FlatImageBase(BaseModel):
    image_url: str
    image_type: Optional[str] = None   # front_view, living_room, master_bedroom, etc.
    caption: Optional[str] = None
    display_order: int = 0

class FlatImageCreate(FlatImageBase):
    pass

class FlatImageResponse(FlatImageBase):
    id: uuid.UUID
    flat_id: uuid.UUID

    class Config:
        from_attributes = True

# -------------------------------------------------------------
# Flat Schemas
# -------------------------------------------------------------
class FlatBase(BaseModel):
    flat_number: str = Field(..., max_length=50)
    flat_type: str = Field(..., max_length=20)   # Studio, 1BHK, 2BHK, 3BHK, 4BHK
    area_sqft: float
    facing_direction: str = Field(..., max_length=50)
    bedrooms: int = 1
    bathrooms: int = 1
    balconies: int = 0
    parking_slots: int = 0
    hall: int = 1
    kitchen: int = 1
    dining: int = 0
    price_buy: Optional[float] = None
    price_rent: Optional[float] = None
    maintenance_fee: float = 0.0
    status: str = "Available"   # Available, Held, Sold, Rented, Reserved
    short_description: Optional[str] = None
    long_description: Optional[str] = None

class FlatCreate(FlatBase):
    pass

class FlatUpdate(BaseModel):
    flat_number: Optional[str] = None
    flat_type: Optional[str] = None
    area_sqft: Optional[float] = None
    facing_direction: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    balconies: Optional[int] = None
    parking_slots: Optional[int] = None
    hall: Optional[int] = None
    kitchen: Optional[int] = None
    dining: Optional[int] = None
    price_buy: Optional[float] = None
    price_rent: Optional[float] = None
    maintenance_fee: Optional[float] = None
    status: Optional[str] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None

class FlatStatusUpdate(BaseModel):
    status: str   # Available, Held, Sold, Rented, Reserved

class FlatDuplicateRequest(BaseModel):
    target_floor_id: uuid.UUID
    new_flat_number: str

class FlatMoveRequest(BaseModel):
    target_floor_id: uuid.UUID

class FlatResponse(FlatBase):
    id: uuid.UUID
    floor_id: uuid.UUID
    apartment_id: Optional[uuid.UUID] = None
    created_at: datetime
    images: List[FlatImageResponse] = []

    class Config:
        from_attributes = True

# -------------------------------------------------------------
# Floor Schemas
# -------------------------------------------------------------
class FloorBase(BaseModel):
    floor_number: int
    floor_name: Optional[str] = None
    description: Optional[str] = None

class FloorCreate(FloorBase):
    pass

class FloorUpdate(BaseModel):
    floor_number: Optional[int] = None
    floor_name: Optional[str] = None
    description: Optional[str] = None

class FloorResponse(FloorBase):
    id: uuid.UUID
    apartment_id: uuid.UUID

    class Config:
        from_attributes = True

# -------------------------------------------------------------
# Apartment Schemas
# -------------------------------------------------------------
class ApartmentBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    address: str
    cover_image: Optional[str] = None
    status: str = "Ready to Move"
    total_floors: int = 1
    owner_name: Optional[str] = Field(None, max_length=255)
    # Stage 2 fields
    contact_number: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    builder_name: Optional[str] = None
    construction_status: str = "Completed"
    possession_status: str = "Ready to Move"
    # amenities is stored as a JSON string in the DB; accept both list and raw string
    amenities: Optional[List[str]] = None
    is_active: bool = True

    @field_validator("amenities", mode="before")
    @classmethod
    def parse_amenities(cls, v):
        """Accept a JSON string, a list, or None for the amenities field."""
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return [str(parsed)]
            except (json.JSONDecodeError, TypeError):
                # Comma-separated fallback
                return [item.strip() for item in v.split(",") if item.strip()]
        return v

class ApartmentCreate(ApartmentBase):
    city_id: uuid.UUID

class ApartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    cover_image: Optional[str] = None
    status: Optional[str] = None
    total_floors: Optional[int] = None
    owner_name: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    builder_name: Optional[str] = None
    construction_status: Optional[str] = None
    possession_status: Optional[str] = None
    amenities: Optional[List[str]] = None

    @field_validator("amenities", mode="before")
    @classmethod
    def parse_amenities(cls, v):
        """Accept a JSON string, a list, or None for the amenities field."""
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
                return [str(parsed)]
            except (json.JSONDecodeError, TypeError):
                return [item.strip() for item in v.split(",") if item.strip()]
        return v
    is_active: Optional[bool] = None

class ApartmentResponse(ApartmentBase):
    id: uuid.UUID
    city_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

# -------------------------------------------------------------
# Detail / nested response models
# -------------------------------------------------------------
class FlatDetailResponse(FlatResponse):
    floor_number: int
    apartment_name: str
    apartment_id: uuid.UUID
    city_name: str

    class Config:
        from_attributes = True

class FloorDetailResponse(FloorResponse):
    flats: List[FlatResponse] = []

    class Config:
        from_attributes = True

class ApartmentDetailResponse(ApartmentResponse):
    floors: List[FloorDetailResponse] = []
    city: CityResponse
    gallery_images: List[ApartmentGalleryImageResponse] = []

    class Config:
        from_attributes = True

# -------------------------------------------------------------
# Dashboard Stats Schema
# -------------------------------------------------------------
class DashboardStats(BaseModel):
    total_apartments: int
    active_apartments: int
    total_floors: int
    total_flats: int
    available_flats: int
    held_flats: int
    sold_flats: int
    rented_flats: int
    reserved_flats: int

# -------------------------------------------------------------
# Wishlist Schemas
# -------------------------------------------------------------
class WishlistCreate(BaseModel):
    flat_id: uuid.UUID

class WishlistResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    flat_id: uuid.UUID
    created_at: datetime
    flat: FlatResponse

    class Config:
        from_attributes = True


# -------------------------------------------------------------
# Booking & Payment Schemas (Stage 3)
# -------------------------------------------------------------
class BookingCreate(BaseModel):
    flat_id: uuid.UUID
    booking_type: str  # BUY or RENT

class BookingHold(BaseModel):
    flat_id: uuid.UUID

class DocumentResponse(BaseModel):
    id: uuid.UUID
    flat_id: uuid.UUID
    booking_id: Optional[uuid.UUID] = None
    name: str
    file_url: str
    doc_type: str
    created_at: datetime
    apartment_name: Optional[str] = None
    floor_name: Optional[str] = None
    flat_number: Optional[str] = None
    booking_type: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True

class PaymentResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    user_id: uuid.UUID
    transaction_id: Optional[str] = None
    amount: float
    status: str
    payment_method: Optional[str] = None
    payment_type: str
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    payment_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class UserBriefResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    full_name: Optional[str] = None

    class Config:
        from_attributes = True

class BookingResponse(BaseModel):
    id: uuid.UUID
    flat_id: uuid.UUID
    user_id: uuid.UUID
    booking_type: str
    amount_paid: float
    status: str
    hold_expiry: Optional[datetime] = None
    created_at: datetime
    flat: Optional[FlatResponse] = None
    user: Optional[UserBriefResponse] = None
    payments: List[PaymentResponse] = []
    documents: List[DocumentResponse] = []

    class Config:
        from_attributes = True

class CreateOrderRequest(BaseModel):
    booking_id: uuid.UUID
    amount: float
    payment_type: str = "Advance Booking"

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class CompleteLocalPaymentRequest(BaseModel):
    booking_id: uuid.UUID
    amount: float
    payment_type: str = "Advance Booking"


