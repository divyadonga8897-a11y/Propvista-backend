import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import EmergencyContact
from app.schemas.schemas import EmergencyContactCreate, EmergencyContactResponse

from app.core.dependencies import verify_resident_access

router = APIRouter(prefix="/emergency-contacts", tags=["Emergency Contacts"])

@router.get("/{apartment_id}", response_model=List[EmergencyContactResponse])
async def get_emergency_contacts(
    apartment_id: uuid.UUID,
    current_user: UserClaims = Depends(verify_resident_access),
    db: AsyncSession = Depends(get_db)
):
    query = select(EmergencyContact).where(
        EmergencyContact.apartment_id == apartment_id,
        EmergencyContact.is_active == True
    )
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=EmergencyContactResponse, status_code=status.HTTP_201_CREATED)
async def add_emergency_contact(
    apartment_id: uuid.UUID,
    contact: EmergencyContactCreate,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    new_contact = EmergencyContact(
        apartment_id=apartment_id,
        **contact.model_dump()
    )
    db.add(new_contact)
    await db.commit()
    await db.refresh(new_contact)
    return new_contact

@router.put("/{contact_id}", response_model=EmergencyContactResponse)
async def update_emergency_contact(
    contact_id: uuid.UUID,
    contact_update: EmergencyContactCreate,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(EmergencyContact).where(EmergencyContact.id == contact_id)
    result = await db.execute(query)
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    for key, value in contact_update.model_dump().items():
        setattr(contact, key, value)
        
    await db.commit()
    await db.refresh(contact)
    return contact

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_emergency_contact(
    contact_id: uuid.UUID,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(EmergencyContact).where(EmergencyContact.id == contact_id)
    result = await db.execute(query)
    contact = result.scalar_one_or_none()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    await db.delete(contact)
    await db.commit()
    return None
