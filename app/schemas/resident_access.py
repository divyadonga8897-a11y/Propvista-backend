from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime

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
    
    class Config:
        from_attributes = True

class ResidentAccessApproval(BaseModel):
    remarks: Optional[str] = None

class ResidentAccessRejection(BaseModel):
    remarks: str
