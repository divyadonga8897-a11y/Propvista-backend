"""
vehicles.py - Vehicle registration & management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import Vehicle, Resident

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])

# --- Schemas ---

class VehicleOut(BaseModel):
    id: str
    resident_id: str
    vehicle_type: str         # Car | Bike
    vehicle_number: str
    parking_slot: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    color: Optional[str] = None

class RegisterVehicleRequest(BaseModel):
    vehicle_type: str         # Car | Bike
    vehicle_number: str
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    color: Optional[str] = None

class AssignParkingRequest(BaseModel):
    parking_slot: str

# --- Endpoints ---

@router.get(
    "/",
    response_model=List[VehicleOut],
    summary="List vehicles",
    description="Residents see their own registered vehicles. Admins see all.",
)
async def list_vehicles(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Vehicle).options(joinedload(Vehicle.resident))
    
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
        resident = res_profile.scalar_one_or_none()
        if not resident:
            return []
        query = query.where(Vehicle.resident_id == resident.id)
        
    res = await db.execute(query)
    vehicles = res.scalars().all()
    
    return [
        VehicleOut(
            id=str(v.id),
            resident_id=str(v.resident_id) if v.resident_id else "",
            vehicle_type=v.vehicle_type,
            vehicle_number=v.vehicle_number,
            parking_slot=v.parking_slot,
            vehicle_make=v.vehicle_make,
            vehicle_model=v.vehicle_model,
            color=v.color
        )
        for v in vehicles
    ]


@router.post(
    "/",
    response_model=VehicleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a vehicle (Resident)",
)
async def register_vehicle(
    body: RegisterVehicleRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
    resident = res_profile.scalar_one_or_none()
    if not resident:
        raise HTTPException(status_code=400, detail="Only active residents can register vehicles.")
        
    vehicle = Vehicle(
        flat_id=resident.flat_id,
        resident_id=resident.id,
        vehicle_type=body.vehicle_type,
        vehicle_number=body.vehicle_number,
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        color=body.color
    )
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    
    return VehicleOut(
        id=str(vehicle.id),
        resident_id=str(vehicle.resident_id),
        vehicle_type=vehicle.vehicle_type,
        vehicle_number=vehicle.vehicle_number,
        parking_slot=vehicle.parking_slot,
        vehicle_make=vehicle.vehicle_make,
        vehicle_model=vehicle.vehicle_model,
        color=vehicle.color
    )


@router.put(
    "/{vehicle_id}/parking",
    response_model=VehicleOut,
    summary="Assign parking slot (Admin)",
)
async def assign_parking(
    vehicle_id: str,
    body: AssignParkingRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    vid = uuid.UUID(vehicle_id)
    vehicle = await db.get(Vehicle, vid)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
        
    vehicle.parking_slot = body.parking_slot
    await db.commit()
    await db.refresh(vehicle)
    
    return VehicleOut(
        id=str(vehicle.id),
        resident_id=str(vehicle.resident_id) if vehicle.resident_id else "",
        vehicle_type=vehicle.vehicle_type,
        vehicle_number=vehicle.vehicle_number,
        parking_slot=vehicle.parking_slot,
        vehicle_make=vehicle.vehicle_make,
        vehicle_model=vehicle.vehicle_model,
        color=vehicle.color
    )


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete vehicle registration (Resident/Admin)",
)
async def delete_vehicle(
    vehicle_id: str,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    vid = uuid.UUID(vehicle_id)
    vehicle = await db.get(Vehicle, vid, options=[joinedload(Vehicle.resident)])
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
        
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        if not vehicle.resident or vehicle.resident.user_id != uid:
            raise HTTPException(status_code=403, detail="Not authorized to delete this vehicle.")
            
    await db.delete(vehicle)
    await db.commit()
    return None
