import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.schemas import UnitCreate, UnitUpdate, UnitResponse, UnitDetailResponse, UnitImageResponse
from app.services.real_estate_service import real_estate_service
from app.services.supabase_storage import storage_service
from app.core.roles import require_admin
from app.core.auth import UserClaims

router = APIRouter(prefix="/units", tags=["units"])

@router.get("", response_model=List[UnitDetailResponse])
async def list_units(
    project_id: Optional[uuid.UUID] = None,
    city: Optional[str] = None,
    bhk_type: Optional[str] = None,
    facing_direction: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    status: Optional[str] = None,
    listing_type: Optional[str] = Query(None, description="Filter by transaction type: 'buy' or 'rent'"),
    sort_by: Optional[str] = "newest",
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Search and filter apartment units based on price range, location, BHK config, direction, and availability."""
    return await real_estate_service.get_units(
        db=db,
        skip=skip,
        limit=limit,
        project_id=project_id,
        city=city,
        bhk_type=bhk_type,
        facing_direction=facing_direction,
        min_price=min_price,
        max_price=max_price,
        status=status,
        listing_type=listing_type,
        sort_by=sort_by
    )

@router.get("/{unit_id}", response_model=UnitDetailResponse)
async def get_unit(unit_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve specifications and images for a specific apartment unit."""
    return await real_estate_service.get_unit_by_id(db, unit_id)

@router.post("/floors/{floor_id}", response_model=UnitDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_unit(
    floor_id: uuid.UUID,
    unit_in: UnitCreate,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Add a new unit to a floor. Accessible only by Administrators."""
    unit = await real_estate_service.create_unit(db, floor_id, unit_in)
    return await real_estate_service.get_unit_by_id(db, unit.id)

@router.put("/{unit_id}", response_model=UnitDetailResponse)
async def update_unit(
    unit_id: uuid.UUID,
    unit_in: UnitUpdate,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Edit details and specifications of a unit. Accessible only by Administrators."""
    return await real_estate_service.update_unit(db, unit_id, unit_in)

@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(
    unit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Delete a unit. Accessible only by Administrators."""
    await real_estate_service.delete_unit(db, unit_id)

@router.post("/{unit_id}/images", response_model=UnitImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_unit_image(
    unit_id: uuid.UUID,
    file: UploadFile = File(...),
    display_order: int = 0,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Upload an image for a unit to Supabase Storage. Accessible only by Administrators."""
    file_bytes = await file.read()
    image_url = await storage_service.upload_file(
        bucket="unit-images",
        file_bytes=file_bytes,
        original_filename=file.filename,
        content_type=file.content_type
    )
    return await real_estate_service.add_unit_image(db, unit_id, image_url, display_order)

@router.put("/{unit_id}/status", response_model=UnitDetailResponse)
async def update_unit_status(
    unit_id: uuid.UUID,
    status: str = Query(..., description="Availability status: Available, Held, Booked, Sold, Rented"),
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Update status of a unit (e.g. mark as Booked or Rented). Accessible only by Administrators."""
    unit_update = UnitUpdate(status=status)
    return await real_estate_service.update_unit(db, unit_id, unit_update)
