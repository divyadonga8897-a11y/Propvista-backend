import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.services.real_estate_service import real_estate_service
from app.schemas.schemas import FloorResponse, FloorUpdate

router = APIRouter(prefix="/floors", tags=["Floors"])


@router.get("/{floor_id}", response_model=FloorResponse)
async def get_floor(floor_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get floor by ID."""
    floor = await real_estate_service.get_floor_by_id(db, floor_id)
    return floor


@router.put("/{floor_id}", response_model=FloorResponse)
async def update_floor(
    floor_id: uuid.UUID,
    obj_in: FloorUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Rename or update a floor."""
    floor = await real_estate_service.update_floor(db, floor_id, obj_in)
    return floor


@router.delete("/{floor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_floor(floor_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Admin: Delete a floor."""
    await real_estate_service.delete_floor(db, floor_id)
