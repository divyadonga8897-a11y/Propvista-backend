import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.services.real_estate_service import real_estate_service
from app.schemas.schemas import CityResponse

router = APIRouter(prefix="/cities", tags=["Cities"])


@router.get("/", response_model=List[CityResponse])
async def list_cities(db: AsyncSession = Depends(get_db)):
    """List all available cities."""
    cities = await real_estate_service.get_cities(db)
    return cities


@router.get("/{city_id}")
async def get_city(city_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get city details with its apartment communities."""
    city = await real_estate_service.get_city_by_id(db, city_id)
    return city
