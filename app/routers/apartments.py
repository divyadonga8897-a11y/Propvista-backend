import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.services.real_estate_service import real_estate_service
from app.schemas.schemas import ApartmentCreate, ApartmentUpdate, ApartmentResponse, FloorResponse, ApartmentDetailResponse, DashboardStats, ApartmentGalleryImageResponse, ApartmentGalleryImageCreate
from app.utils.logging import logger

router = APIRouter(prefix="/apartments", tags=["Apartments"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard stats for apartments, floors, flats and status counts."""
    stats = await real_estate_service.get_dashboard_stats(db)
    return stats


@router.get("/", response_model=List[ApartmentResponse])
async def list_apartments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    city_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all apartment communities, optionally filter by city/search/status."""
    apartments = await real_estate_service.get_apartments(
        db, skip=skip, limit=limit, city_id=city_id, search=search, status=status
    )
    return apartments


@router.get("/{apartment_id}", response_model=ApartmentDetailResponse)
async def get_apartment(apartment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single apartment with all its floors and flats."""
    apartment = await real_estate_service.get_apartment_by_id(db, apartment_id)
    return apartment


@router.post("/", response_model=ApartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_apartment(obj_in: ApartmentCreate, db: AsyncSession = Depends(get_db)):
    """Admin: Create a new apartment community."""
    apartment = await real_estate_service.create_apartment(db, obj_in)
    return apartment


@router.put("/{apartment_id}", response_model=ApartmentResponse)
async def update_apartment(apartment_id: uuid.UUID, obj_in: ApartmentUpdate, db: AsyncSession = Depends(get_db)):
    """Admin: Update apartment details."""
    apartment = await real_estate_service.update_apartment(db, apartment_id, obj_in)
    return apartment


@router.delete("/{apartment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_apartment(apartment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Admin: Delete an apartment."""
    await real_estate_service.delete_apartment(db, apartment_id)


@router.patch("/{apartment_id}/activate", response_model=ApartmentResponse)
async def activate_apartment(apartment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Admin: Activate an apartment community."""
    return await real_estate_service.set_apartment_active(db, apartment_id, is_active=True)


@router.patch("/{apartment_id}/deactivate", response_model=ApartmentResponse)
async def deactivate_apartment(apartment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Admin: Deactivate an apartment community."""
    return await real_estate_service.set_apartment_active(db, apartment_id, is_active=False)


@router.get("/{apartment_id}/gallery", response_model=List[ApartmentGalleryImageResponse])
async def get_apartment_gallery(apartment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get gallery images for an apartment."""
    return await real_estate_service.get_apartment_gallery(db, apartment_id)


@router.post("/{apartment_id}/gallery", response_model=ApartmentGalleryImageResponse, status_code=status.HTTP_201_CREATED)
async def add_apartment_gallery_image(
    apartment_id: uuid.UUID,
    obj_in: ApartmentGalleryImageCreate,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Add an image to the apartment gallery."""
    return await real_estate_service.add_apartment_gallery_image(db, apartment_id, obj_in)


@router.delete("/{apartment_id}/gallery/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_apartment_gallery_image(
    apartment_id: uuid.UUID,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Delete a gallery image."""
    await real_estate_service.delete_apartment_gallery_image(db, apartment_id, image_id)


@router.get("/{apartment_id}/floors", response_model=List[FloorResponse])
async def get_apartment_floors(apartment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all floors for a specific apartment."""
    floors = await real_estate_service.get_floors_by_apartment(db, apartment_id)
    return floors


@router.post("/{apartment_id}/floors", response_model=FloorResponse, status_code=status.HTTP_201_CREATED)
async def create_floor(
    apartment_id: uuid.UUID,
    floor_number: int,
    floor_name: Optional[str] = None,
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Add a new floor to an apartment."""
    floor = await real_estate_service.create_floor(db, apartment_id, floor_number, floor_name, description)
    return floor
