import uuid
import random
import string
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import Referral, Resident
from app.schemas.schemas import ReferralCreate, ReferralResponse

router = APIRouter(prefix="/referrals", tags=["Referrals"])

def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

@router.post("/generate", response_model=ReferralResponse, status_code=status.HTTP_201_CREATED)
async def generate_referral(
    referral: ReferralCreate,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = uuid.UUID(current_user.user_id)
    
    res_query = select(Resident).where(Resident.user_id == user_id)
    res_result = await db.execute(res_query)
    resident = res_result.scalar_one_or_none()
    
    if not resident:
        raise HTTPException(status_code=403, detail="Only residents can generate referrals")
        
    code = generate_referral_code()
    link = f"https://propvista.ai/register?ref={code}"
    
    new_referral = Referral(
        referrer_resident_id=resident.id,
        apartment_id=resident.apartment_id,
        referral_code=code,
        referral_link=link,
        **referral.model_dump()
    )
    db.add(new_referral)
    await db.commit()
    await db.refresh(new_referral)
    return new_referral

@router.get("/my", response_model=List[ReferralResponse])
async def get_my_referrals(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = uuid.UUID(current_user.user_id)
    
    res_query = select(Resident).where(Resident.user_id == user_id)
    res_result = await db.execute(res_query)
    resident = res_result.scalar_one_or_none()
    
    if not resident:
        raise HTTPException(status_code=403, detail="Only residents can view referrals")
        
    query = select(Referral).where(Referral.referrer_resident_id == resident.id)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/", response_model=List[ReferralResponse])
async def get_all_referrals(
    apartment_id: uuid.UUID = None,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(Referral)
    if apartment_id:
        query = query.where(Referral.apartment_id == apartment_id)
        
    result = await db.execute(query)
    return result.scalars().all()
