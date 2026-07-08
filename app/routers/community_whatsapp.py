import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import CommunityWhatsApp
from typing import List
from app.schemas.schemas import CommunityWhatsAppCreate, CommunityWhatsAppResponse
from app.core.dependencies import verify_resident_access

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Groups"])

@router.get("/{apartment_id}", response_model=List[CommunityWhatsAppResponse])
async def get_groups(
    apartment_id: uuid.UUID,
    current_user: UserClaims = Depends(verify_resident_access),
    db: AsyncSession = Depends(get_db)
):
    query = select(CommunityWhatsApp).where(CommunityWhatsApp.apartment_id == apartment_id)
    result = await db.execute(query)
    whatsapp = result.scalar_one_or_none()
    
    if not whatsapp:
        return []
        
    return [whatsapp]

@router.put("/{apartment_id}", response_model=CommunityWhatsAppResponse)
async def update_whatsapp_info(
    apartment_id: uuid.UUID,
    whatsapp_data: CommunityWhatsAppCreate,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(CommunityWhatsApp).where(CommunityWhatsApp.apartment_id == apartment_id)
    result = await db.execute(query)
    whatsapp = result.scalar_one_or_none()
    
    if whatsapp:
        whatsapp.group_name = whatsapp_data.group_name
        whatsapp.invite_link = whatsapp_data.invite_link
    else:
        whatsapp = CommunityWhatsApp(
            apartment_id=apartment_id,
            group_name=whatsapp_data.group_name,
            invite_link=whatsapp_data.invite_link
        )
        db.add(whatsapp)
        
    await db.commit()
    await db.refresh(whatsapp)
    return whatsapp
