from pydantic import BaseModel
from typing import Optional, List, Any
import uuid
from datetime import datetime


class CustomerSummary(BaseModel):
    id: uuid.UUID
    email: str
    full_name: Optional[str] = None

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
    created_at: datetime

    # Nested relationship objects (populated by selectinload in service)
    customer: Optional[CustomerSummary] = None
    flat: Optional[FlatSummary] = None
    document: Optional[DocumentSummary] = None

    class Config:
        from_attributes = True


class ResidentAccessApproval(BaseModel):
    remarks: Optional[str] = None


class ResidentAccessRejection(BaseModel):
    remarks: str
