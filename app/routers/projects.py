import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, UploadFile, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDetailResponse, AmenityCreate, AmenityResponse, NearbyPlaceCreate, NearbyPlaceResponse
from app.services.real_estate_service import real_estate_service
from app.services.supabase_storage import storage_service
from app.core.roles import require_admin, require_any_user
from app.core.auth import UserClaims

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    city: Optional[str] = None,
    search: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = "newest",
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all real estate projects with search, filtering, and sorting."""
    return await real_estate_service.get_projects(
        db=db, skip=skip, limit=limit, city=city, search=search, status=status, sort_by=sort_by
    )

@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve project details, including blocks, floors, units, amenities, and nearby locations."""
    return await real_estate_service.get_project_by_id(db, project_id)

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    auto_generate_blocks: int = Query(0, description="Auto-generate this many blocks with floors & units"),
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Create a new property project. Accessible only by Administrators. Can auto-generate floor/unit hierarchy."""
    return await real_estate_service.create_project(db, project_in, auto_generate_blocks)

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Edit project configuration. Accessible only by Administrators."""
    return await real_estate_service.update_project(db, project_id, project_in)

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Delete a project and its hierarchy. Accessible only by Administrators."""
    await real_estate_service.delete_project(db, project_id)

@router.post("/{project_id}/cover-image", response_model=ProjectResponse)
async def upload_cover_image(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Upload a project cover image to Supabase Storage and link it to the project."""
    file_bytes = await file.read()
    cover_url = await storage_service.upload_file(
        bucket="property-images",
        file_bytes=file_bytes,
        original_filename=file.filename,
        content_type=file.content_type
    )
    
    project_update = ProjectUpdate(cover_image=cover_url)
    return await real_estate_service.update_project(db, project_id, project_update)

@router.post("/{project_id}/amenities", response_model=AmenityResponse, status_code=status.HTTP_201_CREATED)
async def add_project_amenity(
    project_id: uuid.UUID,
    amenity_in: AmenityCreate,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Add a new amenity to a project. Accessible only by Administrators."""
    return await real_estate_service.add_amenity(db, project_id, amenity_in)

@router.post("/{project_id}/nearby", response_model=NearbyPlaceResponse, status_code=status.HTTP_201_CREATED)
async def add_project_nearby_place(
    project_id: uuid.UUID,
    place_in: NearbyPlaceCreate,
    db: AsyncSession = Depends(get_db),
    admin: UserClaims = Depends(require_admin)
):
    """Add a nearby place/landmark. Accessible only by Administrators."""
    return await real_estate_service.add_nearby_place(db, project_id, place_in)
