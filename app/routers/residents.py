"""
residents.py - Resident profile and property management endpoints.
Resident-specific operations after flat purchase/rental.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import date
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import Resident, Flat, Apartment, Floor, User

router = APIRouter(prefix="/residents", tags=["Residents"])

class ResidentOut(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: Optional[str] = None
    flat_id: str
    flat_number: str
    apartment_name: str
    floor_number: int
    resident_type: str       # Owner | Tenant
    move_in_date: Optional[str] = None
    status: str
    agreement_number: Optional[str] = None

class ResidentListResponse(BaseModel):
    residents: List[ResidentOut]
    total: int

class MyPropertyOut(BaseModel):
    flat_id: str
    flat_number: str
    flat_type: str
    apartment_name: str
    floor_number: int
    area_sqft: float
    facing_direction: str
    resident_type: str
    move_in_date: Optional[str] = None
    maintenance_fee: float
    agreement_number: Optional[str] = None
    status: str
    owner_name: Optional[str] = None

class ResidentUpdateStatus(BaseModel):
    status: str

@router.get(
    "/",
    response_model=ResidentListResponse,
    summary="List all residents (Admin)",
    description="Returns all residents across all apartments. Requires Admin role.",
)
async def list_residents(
    apartment_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(Resident).options(
        joinedload(Resident.user),
        joinedload(Resident.flat),
        joinedload(Resident.apartment),
        joinedload(Resident.floor)
    )
    if apartment_id:
        query = query.where(Resident.apartment_id == uuid.UUID(apartment_id))
    
    total_query = select(func.count(Resident.id))
    if apartment_id:
        total_query = total_query.where(Resident.apartment_id == uuid.UUID(apartment_id))
        
    total_res = await db.execute(total_query)
    total = total_res.scalar() or 0
    
    query = query.limit(page_size).offset((page - 1) * page_size)
    res = await db.execute(query)
    db_residents = res.scalars().all()
    
    output = []
    for r in db_residents:
        output.append(ResidentOut(
            id=str(r.id),
            user_id=str(r.user_id),
            email=r.user.email if r.user else "",
            full_name=getattr(r.user, 'full_name', r.user.email),
            flat_id=str(r.flat_id),
            flat_number=r.flat.flat_number if r.flat else "",
            apartment_name=r.apartment.name if r.apartment else "",
            floor_number=r.floor.floor_number if r.floor else 0,
            resident_type=r.resident_type,
            move_in_date=str(r.move_in_date) if r.move_in_date else None,
            status=r.status,
            agreement_number=r.agreement_number
        ))
        
    return ResidentListResponse(residents=output, total=total)


@router.get(
    "/me/profile",
    response_model=ResidentOut,
    summary="Get current resident profile",
)
async def get_my_profile(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    query = select(Resident).where(Resident.user_id == uid).options(
        joinedload(Resident.user),
        joinedload(Resident.flat),
        joinedload(Resident.apartment),
        joinedload(Resident.floor)
    )
    res = await db.execute(query)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resident profile not found for this user."
        )
    return ResidentOut(
        id=str(r.id),
        user_id=str(r.user_id),
        email=r.user.email if r.user else "",
        full_name=getattr(r.user, 'full_name', r.user.email),
        flat_id=str(r.flat_id),
        flat_number=r.flat.flat_number if r.flat else "",
        apartment_name=r.apartment.name if r.apartment else "",
        floor_number=r.floor.floor_number if r.floor else 0,
        resident_type=r.resident_type,
        move_in_date=str(r.move_in_date) if r.move_in_date else None,
        status=r.status,
        agreement_number=r.agreement_number
    )


@router.get(
    "/me/property",
    response_model=MyPropertyOut,
    summary="Get my property details (Resident)",
)
async def get_my_property(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    query = select(Resident).where(Resident.user_id == uid).options(
        joinedload(Resident.flat),
        joinedload(Resident.apartment),
        joinedload(Resident.floor)
    )
    res = await db.execute(query)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No confirmed property profile found for this user."
        )
    flat = r.flat
    return MyPropertyOut(
        flat_id=str(r.flat_id),
        flat_number=flat.flat_number,
        flat_type=flat.flat_type,
        apartment_name=r.apartment.name,
        floor_number=r.floor.floor_number,
        area_sqft=flat.area_sqft,
        facing_direction=flat.facing_direction,
        resident_type=r.resident_type,
        move_in_date=str(r.move_in_date) if r.move_in_date else None,
        maintenance_fee=float(flat.maintenance_fee or 0),
        agreement_number=r.agreement_number,
        status=r.status,
        owner_name=r.apartment.owner_name
    )


@router.get(
    "/{user_id}",
    response_model=ResidentOut,
    summary="Get resident by user ID (Admin)",
)
async def get_resident(
    user_id: str,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(user_id)
    query = select(Resident).where(Resident.user_id == uid).options(
        joinedload(Resident.user),
        joinedload(Resident.flat),
        joinedload(Resident.apartment),
        joinedload(Resident.floor)
    )
    res = await db.execute(query)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    return ResidentOut(
        id=str(r.id),
        user_id=str(r.user_id),
        email=r.user.email if r.user else "",
        full_name=getattr(r.user, 'full_name', r.user.email),
        flat_id=str(r.flat_id),
        flat_number=r.flat.flat_number if r.flat else "",
        apartment_name=r.apartment.name if r.apartment else "",
        floor_number=r.floor.floor_number if r.floor else 0,
        resident_type=r.resident_type,
        move_in_date=str(r.move_in_date) if r.move_in_date else None,
        status=r.status,
        agreement_number=r.agreement_number
    )


@router.put(
    "/{resident_id}/status",
    summary="Update resident status (Admin)"
)
async def update_resident_status(
    resident_id: str,
    body: ResidentUpdateStatus,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    rid = uuid.UUID(resident_id)
    query = select(Resident).where(Resident.id == rid)
    res = await db.execute(query)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Resident not found")
    r.status = body.status
    await db.commit()
    return {"status": "success", "message": f"Resident status updated to {body.status}"}


# Alias routes to match Stage 4 resident API surface
resident_router = APIRouter(prefix="/resident", tags=["Resident"])

@resident_router.get(
    "/profile",
    response_model=ResidentOut,
    summary="Get current resident profile",
)
async def get_resident_profile_alias(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_my_profile(current_user=current_user, db=db)


@resident_router.get(
    "/property",
    response_model=MyPropertyOut,
    summary="Get my property details (Resident)",
)
async def get_my_property_alias(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_my_property(current_user=current_user, db=db)
