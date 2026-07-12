from pydantic import BaseModel
from typing import Optional, List, Any
import uuid
from datetime import datetime


class CustomerSummary(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class FlatSummary(BaseModel):
    id: uuid.UUID
    flat_number: str
    apartment_name: Optional[str] = None
    floor_name: Optional[str] = None
    flat_type: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    id: uuid.UUID
    name: str
    file_url: Optional[str] = None
    doc_type: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentSummary(BaseModel):
    id: uuid.UUID
    amount: float
    status: str
    payment_method: Optional[str] = None
    payment_type: str
    razorpay_payment_id: Optional[str] = None
    payment_date: datetime

    class Config:
        from_attributes = True


class BookingSummary(BaseModel):
    id: uuid.UUID
    booking_type: str
    amount_paid: float
    status: str
    created_at: datetime
    payments: Optional[List[PaymentSummary]] = None

    class Config:
        from_attributes = True


class ResidentAccessRequestCreate(BaseModel):
    booking_id: uuid.UUID
    flat_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None


class ResidentAccessRequestResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    booking_id: uuid.UUID
    flat_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    status: str
    remarks: Optional[str] = None
    approval_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

    # Nested relationship objects (populated by selectinload in service)
    customer: Optional[CustomerSummary] = None
    flat: Optional[FlatSummary] = None
    document: Optional[DocumentSummary] = None
    booking: Optional[BookingSummary] = None

    class Config:
        from_attributes = True


class ResidentAccessApproval(BaseModel):
    remarks: Optional[str] = None


class ResidentAccessRejection(BaseModel):
    remarks: str
