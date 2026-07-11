import json
import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, update, and_, or_, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from app.models.models import (
    City, Apartment, ApartmentGalleryImage, Floor, Flat, FlatImage, Wishlist
)
from app.schemas.schemas import (
    ApartmentCreate, ApartmentUpdate,
    FloorCreate, FloorUpdate,
    FlatCreate, FlatUpdate,
    ApartmentGalleryImageCreate,
)
from app.core.exceptions import EntityNotFoundException, APIException
from app.utils.logging import logger


DIRECTIONS = ["North", "South", "East", "West", "North East", "North West", "South East", "South West"]

FLAT_IMAGES = [
    "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&auto=format&fit=crop&q=60",
    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&auto=format&fit=crop&q=60",
    "https://images.unsplash.com/photo-1484154218962-a197022b5858?w=800&auto=format&fit=crop&q=60",
    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800&auto=format&fit=crop&q=60",
    "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&auto=format&fit=crop&q=60",
    "https://images.unsplash.com/photo-1502672023488-70e25813eb80?w=800&auto=format&fit=crop&q=60",
    "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=800&auto=format&fit=crop&q=60",
    "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800&auto=format&fit=crop&q=60",
    "https://images.unsplash.com/photo-1484101403633-562f891dc89a?w=800&auto=format&fit=crop&q=60",
]

IMAGE_TYPES = [
    "front_view", "living_room", "master_bedroom",
    "bedroom", "kitchen", "bathroom", "balcony", "dining_room"
]

APARTMENT_DATA = [
    {
        "name": "PropVista Heights",
        "description": "A warm and vibrant residential community with spacious layouts and modern amenities, designed for comfortable family living in the heart of Nandyal.",
        "address": "Survey No. 45, Kurnool Road, Nandyal, Andhra Pradesh - 518501",
        "builder_name": "Sri Venkata Raju Constructions",
        "contact_number": "+91 94400 12345",
        "email": "propvista.heights@gmail.com",
        "latitude": 15.4775,
        "longitude": 78.4835,
        "construction_status": "Completed",
        "possession_status": "Ready to Move",
        "amenities": ["Lift", "Security", "Parking", "Power Backup", "CCTV", "Water Supply", "Garden"],
        "cover_image": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=800&auto=format&fit=crop&q=60",
        "total_floors": 5,
        "gallery": [
            "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=800&auto=format&fit=crop&q=60",
            "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&auto=format&fit=crop&q=60",
            "https://images.unsplash.com/photo-1605276374104-dee2a0ed3cd6?w=800&auto=format&fit=crop&q=60",
        ],
    },
    {
        "name": "Green Valley Residency",
        "description": "An eco-conscious residential township with lush green landscapes, rainwater harvesting, and solar-powered common areas nestled in the tranquil outskirts of Nandyal.",
        "address": "Plot No. 12, Green Valley Layout, Srinivasa Nagar, Nandyal, Andhra Pradesh - 518502",
        "builder_name": "Green Valley Builders Pvt Ltd",
        "contact_number": "+91 99890 56789",
        "email": "info@greenvalleynandyal.com",
        "latitude": 15.4890,
        "longitude": 78.4910,
        "construction_status": "Completed",
        "possession_status": "Ready to Move",
        "amenities": ["Lift", "Security", "Parking", "Gym", "Power Backup", "Children Play Area", "Garden", "Club House", "Swimming Pool", "CCTV", "Water Supply", "Community Hall"],
        "cover_image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&auto=format&fit=crop&q=60",
        "total_floors": 4,
        "gallery": [
            "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=800&auto=format&fit=crop&q=60",
            "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=800&auto=format&fit=crop&q=60",
            "https://images.unsplash.com/photo-1512918728675-ed5a9ecdebfd?w=800&auto=format&fit=crop&q=60",
        ],
    },
    {
        "name": "Skyline Residency",
        "description": "A premium high-rise luxury development offering panoramic views of Nandyal's skyline. Skyline Residency redefines urban living with world-class finishes and smart home integrations.",
        "address": "Opposite Bus Stand, Banaganapalle Road, Nandyal, Andhra Pradesh - 518503",
        "builder_name": "Skyline Group Developers",
        "contact_number": "+91 88800 99001",
        "email": "skyline.nandyal@propvista.in",
        "latitude": 15.4650,
        "longitude": 78.4790,
        "construction_status": "Under Construction",
        "possession_status": "Dec 2025",
        "amenities": ["Lift", "Security", "Parking", "Gym", "Power Backup", "Children Play Area", "Garden", "Club House", "CCTV", "Water Supply"],
        "cover_image": "https://images.unsplash.com/photo-1486325212027-8081e485255e?w=800&auto=format&fit=crop&q=60",
        "total_floors": 6,
        "gallery": [
            "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&auto=format&fit=crop&q=60",
            "https://images.unsplash.com/photo-1502672023488-70e25813eb80?w=800&auto=format&fit=crop&q=60",
            "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&auto=format&fit=crop&q=60",
        ],
    },
]


def _encode_amenities(amenities: Optional[List[str]]) -> Optional[str]:
    if amenities is None:
        return None
    return json.dumps(amenities)


def _decode_amenities(amenities_str: Optional[str]) -> Optional[List[str]]:
    if not amenities_str:
        return []
    try:
        return json.loads(amenities_str)
    except Exception:
        return []


def _flat_to_dict(f: Flat, fl: Optional[Floor] = None, apt: Optional[Apartment] = None, city: Optional[City] = None) -> Dict[str, Any]:
    """Convert a Flat ORM object to a dict with joined context."""
    if fl is None:
        fl = f.floor if hasattr(f, "floor") else None
    if apt is None and fl is not None:
        apt = fl.apartment if hasattr(fl, "apartment") else None
    if city is None and apt is not None:
        city = apt.city if hasattr(apt, "city") else None

    return {
        "id": f.id,
        "flat_number": f.flat_number,
        "flat_type": f.flat_type,
        "area_sqft": f.area_sqft,
        "facing_direction": f.facing_direction,
        "bedrooms": f.bedrooms,
        "bathrooms": f.bathrooms,
        "balconies": f.balconies,
        "parking_slots": f.parking_slots,
        "hall": f.hall,
        "kitchen": f.kitchen,
        "dining": f.dining,
        "price_buy": float(f.price_buy) if f.price_buy is not None else None,
        "price_rent": float(f.price_rent) if f.price_rent is not None else None,
        "maintenance_fee": float(f.maintenance_fee) if f.maintenance_fee is not None else 0.0,
        "status": f.status,
        "short_description": f.short_description,
        "long_description": f.long_description,
        "floor_id": f.floor_id,
        "apartment_id": f.apartment_id or (apt.id if apt else None),
        "floor_number": fl.floor_number if fl else 0,
        "floor_name": fl.floor_name if fl else None,
        "apartment_name": apt.name if apt else "",
        "city_name": city.name if city else "",
        "created_at": f.created_at,
        "images": [
            {
                "id": img.id,
                "image_url": img.image_url,
                "image_type": img.image_type,
                "caption": img.caption,
                "display_order": img.display_order,
            }
            for img in sorted(f.images, key=lambda x: x.display_order)
        ],
    }


class RealEstateService:

    # -------------------------------------------------------------
    # Seeding: Nandyal, AP — Stage 2 Full Data
    # -------------------------------------------------------------
    async def seed_stage_1_nandyal_data(self, db: AsyncSession) -> None:
        """
        Seeds the database with Nandyal city and three apartment communities.
        Each apartment has multiple floors with 8–9 flats per floor.
        Only runs if no data exists.
        """
        result = await db.execute(select(City).where(City.name == "Nandyal"))
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Seed data already exists. Skipping.")
            return

        logger.info("Seeding Stage 2 Nandyal data...")

        city = City(name="Nandyal", state="Andhra Pradesh", country="India")
        db.add(city)
        await db.flush()

        flat_types_per_floor = [
            ["2BHK", "2BHK", "3BHK", "2BHK", "3BHK", "2BHK", "2BHK", "3BHK"],
            ["2BHK", "3BHK", "2BHK", "2BHK", "3BHK", "2BHK", "3BHK", "2BHK"],
            ["3BHK", "2BHK", "2BHK", "3BHK", "2BHK", "3BHK", "2BHK", "2BHK"],
            ["2BHK", "2BHK", "3BHK", "3BHK", "2BHK", "2BHK", "3BHK", "2BHK"],
            ["3BHK", "3BHK", "2BHK", "2BHK", "2BHK", "3BHK", "2BHK", "3BHK"],
            ["2BHK", "3BHK", "3BHK", "2BHK", "3BHK", "2BHK", "2BHK", "3BHK"],
        ]
        statuses_cycle = ["Available", "Available", "Available", "Held", "Available", "Rented", "Available", "Sold"]

        for apt_idx, apt_data in enumerate(APARTMENT_DATA):
            apartment = Apartment(
                city_id=city.id,
                name=apt_data["name"],
                description=apt_data["description"],
                address=apt_data["address"],
                cover_image=apt_data["cover_image"],
                status="Ready to Move",
                total_floors=apt_data["total_floors"],
                owner_name=apt_data["builder_name"],
                builder_name=apt_data["builder_name"],
                contact_number=apt_data["contact_number"],
                email=apt_data["email"],
                latitude=apt_data["latitude"],
                longitude=apt_data["longitude"],
                construction_status=apt_data["construction_status"],
                possession_status=apt_data["possession_status"],
                amenities=_encode_amenities(apt_data["amenities"]),
                is_active=True,
            )
            db.add(apartment)
            await db.flush()

            # Gallery images
            for gal_idx, gal_url in enumerate(apt_data["gallery"]):
                gal_img = ApartmentGalleryImage(
                    apartment_id=apartment.id,
                    image_url=gal_url,
                    display_order=gal_idx + 1,
                )
                db.add(gal_img)

            floor_labels = {
                0: "Ground Floor", 1: "First Floor", 2: "Second Floor",
                3: "Third Floor", 4: "Fourth Floor", 5: "Fifth Floor",
            }

            for fl_idx in range(1, apt_data["total_floors"] + 1):
                floor = Floor(
                    apartment_id=apartment.id,
                    floor_number=fl_idx,
                    floor_name=floor_labels.get(fl_idx, f"Floor {fl_idx}"),
                    description=f"Floor {fl_idx} — {apt_data['name']}",
                )
                db.add(floor)
                await db.flush()

                bhk_list = flat_types_per_floor[(fl_idx - 1) % len(flat_types_per_floor)]

                for flat_idx in range(8):
                    flat_num = f"{fl_idx}{flat_idx + 1:02d}"
                    bhk = bhk_list[flat_idx]
                    is_2bhk = bhk == "2BHK"
                    direction = DIRECTIONS[(apt_idx * 8 + flat_idx) % len(DIRECTIONS)]
                    status = statuses_cycle[flat_idx % len(statuses_cycle)]

                    price_buy_base = 3500000 + (fl_idx * 100000) + (flat_idx * 50000) + (apt_idx * 200000)
                    price_rent_base = 8000 + (fl_idx * 500) + (flat_idx * 200) + (apt_idx * 1000)

                    flat = Flat(
                        floor_id=floor.id,
                        apartment_id=apartment.id,
                        flat_number=flat_num,
                        flat_type=bhk,
                        area_sqft=1050.0 if is_2bhk else 1450.0,
                        facing_direction=direction,
                        bedrooms=2 if is_2bhk else 3,
                        bathrooms=2,
                        balconies=1 if is_2bhk else 2,
                        parking_slots=1,
                        hall=1,
                        kitchen=1,
                        dining=0 if is_2bhk else 1,
                        price_buy=float(price_buy_base),
                        price_rent=float(price_rent_base),
                        maintenance_fee=2500.0 if is_2bhk else 3500.0,
                        status=status,
                        short_description=f"Spacious {bhk} flat on Floor {fl_idx} of {apt_data['name']} with {direction} facing.",
                        long_description=(
                            f"This {bhk} apartment at {apt_data['name']} offers a thoughtfully designed layout "
                            f"with {2 if is_2bhk else 3} bedrooms, 2 bathrooms, {'1 balcony' if is_2bhk else '2 balconies'}, "
                            f"1 parking slot, 1 hall, and 1 kitchen. Featuring {direction} facing windows, "
                            f"Italian marble flooring, modular kitchen, and premium bathroom fittings. "
                            f"Located in Nandyal, Andhra Pradesh."
                        ),
                    )
                    db.add(flat)
                    await db.flush()

                    # Add images per flat
                    img_start = flat_idx % len(FLAT_IMAGES)
                    img_count = min(3, len(FLAT_IMAGES))
                    for img_order in range(img_count):
                        img_url = FLAT_IMAGES[(img_start + img_order) % len(FLAT_IMAGES)]
                        img = FlatImage(
                            flat_id=flat.id,
                            image_url=img_url,
                            image_type=IMAGE_TYPES[img_order % len(IMAGE_TYPES)],
                            display_order=img_order + 1,
                        )
                        db.add(img)

        await db.commit()
        logger.info("Stage 2 seed data committed successfully.")

    # -------------------------------------------------------------
    # City
    # -------------------------------------------------------------
    async def get_cities(self, db: AsyncSession) -> List[City]:
        result = await db.execute(select(City))
        return list(result.scalars().all())

    async def get_city_by_id(self, db: AsyncSession, city_id: uuid.UUID) -> City:
        result = await db.execute(
            select(City).where(City.id == city_id).options(
                selectinload(City.apartments)
            )
        )
        city = result.scalar_one_or_none()
        if not city:
            raise EntityNotFoundException("City", str(city_id))
        return city

    # -------------------------------------------------------------
    # Dashboard Stats
    # -------------------------------------------------------------
    async def get_dashboard_stats(self, db: AsyncSession) -> Dict[str, int]:
        total_apartments = (await db.execute(select(func.count(Apartment.id)))).scalar_one()
        active_apartments = (await db.execute(select(func.count(Apartment.id)).where(Apartment.is_active == True))).scalar_one()
        total_floors = (await db.execute(select(func.count(Floor.id)))).scalar_one()
        total_flats = (await db.execute(select(func.count(Flat.id)))).scalar_one()

        status_counts: Dict[str, int] = {}
        for status in ["Available", "Held", "Sold", "Rented", "Reserved"]:
            stmt = select(func.count(Flat.id))
            if status == "Sold":
                stmt = stmt.where(Flat.status.in_(["Sold", "SOLD"]))
            elif status == "Rented":
                stmt = stmt.where(Flat.status.in_(["Rented", "RENTED"]))
            else:
                stmt = stmt.where(Flat.status == status)
            cnt = (await db.execute(stmt)).scalar_one()
            status_counts[status] = cnt

        return {
            "total_apartments": total_apartments,
            "active_apartments": active_apartments,
            "total_floors": total_floors,
            "total_flats": total_flats,
            "available_flats": status_counts.get("Available", 0),
            "held_flats": status_counts.get("Held", 0),
            "sold_flats": status_counts.get("Sold", 0),
            "rented_flats": status_counts.get("Rented", 0),
            "reserved_flats": status_counts.get("Reserved", 0),
        }

    async def get_apartment_stats(self, db: AsyncSession, apartment_id: uuid.UUID) -> Dict[str, int]:
        floor_ids_result = await db.execute(
            select(Floor.id).where(Floor.apartment_id == apartment_id)
        )
        floor_ids = [row[0] for row in floor_ids_result.fetchall()]
        total_flats = len(floor_ids)

        status_counts: Dict[str, int] = {}
        for status in ["Available", "Held", "Sold", "Rented", "Reserved"]:
            stmt = select(func.count(Flat.id)).where(Flat.floor_id.in_(floor_ids))
            if status == "Sold":
                stmt = stmt.where(Flat.status.in_(["Sold", "SOLD"]))
            elif status == "Rented":
                stmt = stmt.where(Flat.status.in_(["Rented", "RENTED"]))
            else:
                stmt = stmt.where(Flat.status == status)
            cnt = (await db.execute(stmt)).scalar_one()
            status_counts[status] = cnt

        total_flats_count = (await db.execute(
            select(func.count(Flat.id)).where(Flat.floor_id.in_(floor_ids))
        )).scalar_one()

        return {
            "total_floors": len(floor_ids),
            "total_flats": total_flats_count,
            "available_flats": status_counts.get("Available", 0),
            "held_flats": status_counts.get("Held", 0),
            "sold_flats": status_counts.get("Sold", 0),
            "rented_flats": status_counts.get("Rented", 0),
            "reserved_flats": status_counts.get("Reserved", 0),
        }

    # -------------------------------------------------------------
    # Apartment CRUD
    # -------------------------------------------------------------
    async def get_apartments(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        city_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        status: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Apartment]:
        """Fetch a list of apartments with optional filters.

        Args:
            db: Database session.
            skip: Number of records to skip for pagination.
            limit: Maximum number of records to return.
            city_id: Filter by city.
            search: Text search across name, description, and address.
            status: Filter by apartment status.
            is_active: Filter by active flag.
        """
        logger.debug(
            "Fetching apartments: skip=%s limit=%s city_id=%s search=%s status=%s is_active=%s",
            skip,
            limit,
            city_id,
            search,
            status,
            is_active,
        )
        try:
            query = select(Apartment)
            filters = []
            if city_id:
                filters.append(Apartment.city_id == city_id)
            if search:
                filters.append(
                    or_(
                        Apartment.name.ilike(f"%{search}%"),
                        Apartment.description.ilike(f"%{search}%"),
                        Apartment.address.ilike(f"%{search}%"),
                    )
                )
            if status:
                filters.append(Apartment.status == status)
            if is_active is not None:
                filters.append(Apartment.is_active == is_active)
            if filters:
                query = query.where(and_(*filters))
            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error("Error fetching apartments", exc_info=True)
            raise APIException(status_code=500, detail="Failed to fetch apartments.") from e

    async def get_apartment_by_id(self, db: AsyncSession, apartment_id: uuid.UUID) -> Apartment:
        query = select(Apartment).where(Apartment.id == apartment_id).options(
            selectinload(Apartment.city),
            selectinload(Apartment.gallery_images),
            selectinload(Apartment.floors).selectinload(Floor.flats).selectinload(Flat.images),
        )
        result = await db.execute(query)
        apt = result.scalar_one_or_none()
        if not apt:
            raise EntityNotFoundException("Apartment", str(apartment_id))
        return apt

    async def create_apartment(self, db: AsyncSession, obj_in: ApartmentCreate) -> Apartment:
        apartment = Apartment(
            city_id=obj_in.city_id,
            name=obj_in.name,
            description=obj_in.description,
            address=obj_in.address,
            cover_image=obj_in.cover_image,
            status=obj_in.status,
            total_floors=obj_in.total_floors,
            owner_name=obj_in.owner_name,
            contact_number=obj_in.contact_number,
            email=obj_in.email,
            latitude=obj_in.latitude,
            longitude=obj_in.longitude,
            builder_name=obj_in.builder_name,
            construction_status=obj_in.construction_status,
            possession_status=obj_in.possession_status,
            amenities=_encode_amenities(obj_in.amenities),
            is_active=obj_in.is_active,
        )
        db.add(apartment)
        await db.commit()
        await db.refresh(apartment)
        return apartment

    async def update_apartment(self, db: AsyncSession, apartment_id: uuid.UUID, obj_in: ApartmentUpdate) -> Apartment:
        apt = await self.get_apartment_by_id(db, apartment_id)
        update_data = obj_in.model_dump(exclude_unset=True)
        if "amenities" in update_data:
            update_data["amenities"] = _encode_amenities(update_data["amenities"])
        for key, value in update_data.items():
            setattr(apt, key, value)
        await db.commit()
        await db.refresh(apt)
        return apt

    async def delete_apartment(self, db: AsyncSession, apartment_id: uuid.UUID) -> None:
        apt = await self.get_apartment_by_id(db, apartment_id)
        await db.delete(apt)
        await db.commit()

    async def set_apartment_active(self, db: AsyncSession, apartment_id: uuid.UUID, is_active: bool) -> Apartment:
        apt = await self.get_apartment_by_id(db, apartment_id)
        apt.is_active = is_active
        await db.commit()
        await db.refresh(apt)
        return apt

    # -------------------------------------------------------------
    # Apartment Gallery Images
    # -------------------------------------------------------------
    async def get_apartment_gallery(self, db: AsyncSession, apartment_id: uuid.UUID) -> List[ApartmentGalleryImage]:
        result = await db.execute(
            select(ApartmentGalleryImage)
            .where(ApartmentGalleryImage.apartment_id == apartment_id)
            .order_by(asc(ApartmentGalleryImage.display_order))
        )
        return list(result.scalars().all())

    async def add_apartment_gallery_image(
        self, db: AsyncSession, apartment_id: uuid.UUID, obj_in: ApartmentGalleryImageCreate
    ) -> ApartmentGalleryImage:
        img = ApartmentGalleryImage(
            apartment_id=apartment_id,
            image_url=obj_in.image_url,
            caption=obj_in.caption,
            display_order=obj_in.display_order,
        )
        db.add(img)
        await db.commit()
        await db.refresh(img)
        return img

    async def delete_apartment_gallery_image(self, db: AsyncSession, apartment_id: uuid.UUID, image_id: uuid.UUID) -> None:
        result = await db.execute(
            select(ApartmentGalleryImage).where(
                and_(ApartmentGalleryImage.id == image_id, ApartmentGalleryImage.apartment_id == apartment_id)
            )
        )
        img = result.scalar_one_or_none()
        if not img:
            raise EntityNotFoundException("Gallery Image", str(image_id))
        await db.delete(img)
        await db.commit()

    # -------------------------------------------------------------
    # Floor CRUD
    # -------------------------------------------------------------
    async def get_floors_by_apartment(self, db: AsyncSession, apartment_id: uuid.UUID) -> List[Floor]:
        query = select(Floor).where(Floor.apartment_id == apartment_id).options(
            selectinload(Floor.flats).selectinload(Flat.images)
        ).order_by(asc(Floor.floor_number))
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_floor_by_id(self, db: AsyncSession, floor_id: uuid.UUID) -> Floor:
        result = await db.execute(
            select(Floor).where(Floor.id == floor_id).options(
                selectinload(Floor.flats).selectinload(Flat.images)
            )
        )
        floor = result.scalar_one_or_none()
        if not floor:
            raise EntityNotFoundException("Floor", str(floor_id))
        return floor

    async def create_floor(
        self, db: AsyncSession, apartment_id: uuid.UUID,
        floor_number: int, floor_name: Optional[str] = None, description: Optional[str] = None
    ) -> Floor:
        floor = Floor(
            apartment_id=apartment_id,
            floor_number=floor_number,
            floor_name=floor_name,
            description=description,
        )
        db.add(floor)
        await db.commit()
        await db.refresh(floor)
        return floor

    async def update_floor(self, db: AsyncSession, floor_id: uuid.UUID, obj_in: FloorUpdate) -> Floor:
        floor = await self.get_floor_by_id(db, floor_id)
        update_data = obj_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(floor, key, value)
        await db.commit()
        await db.refresh(floor)
        return floor

    async def delete_floor(self, db: AsyncSession, floor_id: uuid.UUID) -> None:
        floor = await self.get_floor_by_id(db, floor_id)
        await db.delete(floor)
        await db.commit()

    # -------------------------------------------------------------
    # Flat CRUD & Queries
    # -------------------------------------------------------------
    async def get_flats(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        apartment_id: Optional[uuid.UUID] = None,
        floor_id: Optional[uuid.UUID] = None,
        flat_type: Optional[str] = None,
        facing_direction: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        status: Optional[str] = None,
        listing_type: Optional[str] = None,
        sort_by: Optional[str] = None,
        bedrooms: Optional[int] = None,
        bathrooms: Optional[int] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        query = select(Flat).options(
            joinedload(Flat.images),
            joinedload(Flat.floor).joinedload(Floor.apartment).joinedload(Apartment.city)
        )
        filters = []
        if flat_type:
            filters.append(Flat.flat_type == flat_type)
        if facing_direction:
            filters.append(Flat.facing_direction == facing_direction)
        if status:
            filters.append(Flat.status == status)
        if floor_id:
            filters.append(Flat.floor_id == floor_id)
        if apartment_id:
            filters.append(Flat.apartment_id == apartment_id)
        if bedrooms is not None:
            filters.append(Flat.bedrooms == bedrooms)
        if bathrooms is not None:
            filters.append(Flat.bathrooms == bathrooms)
        if min_area:
            filters.append(Flat.area_sqft >= min_area)
        if max_area:
            filters.append(Flat.area_sqft <= max_area)

        if listing_type == "buy":
            filters.append(Flat.price_buy.is_not(None))
            if min_price:
                filters.append(Flat.price_buy >= min_price)
            if max_price:
                filters.append(Flat.price_buy <= max_price)
        elif listing_type == "rent":
            filters.append(Flat.price_rent.is_not(None))
            if min_price:
                filters.append(Flat.price_rent >= min_price)
            if max_price:
                filters.append(Flat.price_rent <= max_price)
        else:
            if min_price:
                filters.append(or_(Flat.price_buy >= min_price, Flat.price_rent >= min_price))
            if max_price:
                filters.append(or_(Flat.price_buy <= max_price, Flat.price_rent <= max_price))

        if filters:
            query = query.where(and_(*filters))

        if sort_by == "price_low":
            sort_col = Flat.price_rent if listing_type == "rent" else Flat.price_buy
            query = query.order_by(asc(sort_col))
        elif sort_by == "price_high":
            sort_col = Flat.price_rent if listing_type == "rent" else Flat.price_buy
            query = query.order_by(desc(sort_col))
        elif sort_by == "area":
            query = query.order_by(desc(Flat.area_sqft))
        elif sort_by == "floor":
            query = query.join(Floor).order_by(asc(Floor.floor_number))
        elif sort_by == "available":
            query = query.order_by(
                asc(Flat.status != "Available"),
                desc(Flat.created_at)
            )
        else:
            query = query.order_by(desc(Flat.created_at))

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        flats = result.unique().scalars().all()
        return [_flat_to_dict(f) for f in flats]

    async def get_flat_by_id(self, db: AsyncSession, flat_id: uuid.UUID) -> Dict[str, Any]:
        query = select(Flat).where(Flat.id == flat_id).options(
            joinedload(Flat.images),
            joinedload(Flat.floor).joinedload(Floor.apartment).joinedload(Apartment.city)
        )
        result = await db.execute(query)
        f = result.unique().scalar_one_or_none()
        if not f:
            raise EntityNotFoundException("Flat", str(flat_id))
        return _flat_to_dict(f)

    async def create_flat(self, db: AsyncSession, floor_id: uuid.UUID, obj_in: FlatCreate) -> Flat:
        # Get apartment_id from floor
        floor_result = await db.execute(select(Floor).where(Floor.id == floor_id))
        floor = floor_result.scalar_one_or_none()
        if not floor:
            raise EntityNotFoundException("Floor", str(floor_id))

        flat = Flat(
            floor_id=floor_id,
            apartment_id=floor.apartment_id,
            flat_number=obj_in.flat_number,
            flat_type=obj_in.flat_type,
            area_sqft=obj_in.area_sqft,
            facing_direction=obj_in.facing_direction,
            bedrooms=obj_in.bedrooms,
            bathrooms=obj_in.bathrooms,
            balconies=obj_in.balconies,
            parking_slots=obj_in.parking_slots,
            hall=obj_in.hall,
            kitchen=obj_in.kitchen,
            dining=obj_in.dining,
            price_buy=obj_in.price_buy,
            price_rent=obj_in.price_rent,
            maintenance_fee=obj_in.maintenance_fee,
            status=obj_in.status,
            short_description=obj_in.short_description,
            long_description=obj_in.long_description,
        )
        db.add(flat)
        await db.commit()
        await db.refresh(flat)
        return flat

    async def update_flat(self, db: AsyncSession, flat_id: uuid.UUID, obj_in: FlatUpdate) -> Dict[str, Any]:
        result = await db.execute(select(Flat).where(Flat.id == flat_id))
        flat = result.scalar_one_or_none()
        if not flat:
            raise EntityNotFoundException("Flat", str(flat_id))
        update_data = obj_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(flat, key, value)
        await db.commit()
        return await self.get_flat_by_id(db, flat_id)

    async def change_flat_status(self, db: AsyncSession, flat_id: uuid.UUID, new_status: str) -> Dict[str, Any]:
        result = await db.execute(select(Flat).where(Flat.id == flat_id))
        flat = result.scalar_one_or_none()
        if not flat:
            raise EntityNotFoundException("Flat", str(flat_id))
        flat.status = new_status
        await db.commit()
        return await self.get_flat_by_id(db, flat_id)

    async def duplicate_flat(
        self, db: AsyncSession, flat_id: uuid.UUID, target_floor_id: uuid.UUID, new_flat_number: str
    ) -> Flat:
        result = await db.execute(select(Flat).where(Flat.id == flat_id))
        flat = result.scalar_one_or_none()
        if not flat:
            raise EntityNotFoundException("Flat", str(flat_id))

        floor_result = await db.execute(select(Floor).where(Floor.id == target_floor_id))
        floor = floor_result.scalar_one_or_none()
        if not floor:
            raise EntityNotFoundException("Floor", str(target_floor_id))

        new_flat = Flat(
            floor_id=target_floor_id,
            apartment_id=floor.apartment_id,
            flat_number=new_flat_number,
            flat_type=flat.flat_type,
            area_sqft=flat.area_sqft,
            facing_direction=flat.facing_direction,
            bedrooms=flat.bedrooms,
            bathrooms=flat.bathrooms,
            balconies=flat.balconies,
            parking_slots=flat.parking_slots,
            hall=flat.hall,
            kitchen=flat.kitchen,
            dining=flat.dining,
            price_buy=flat.price_buy,
            price_rent=flat.price_rent,
            maintenance_fee=flat.maintenance_fee,
            status="Available",
            short_description=flat.short_description,
            long_description=flat.long_description,
        )
        db.add(new_flat)
        await db.commit()
        await db.refresh(new_flat)
        return new_flat

    async def move_flat(self, db: AsyncSession, flat_id: uuid.UUID, target_floor_id: uuid.UUID) -> Dict[str, Any]:
        result = await db.execute(select(Flat).where(Flat.id == flat_id))
        flat = result.scalar_one_or_none()
        if not flat:
            raise EntityNotFoundException("Flat", str(flat_id))

        floor_result = await db.execute(select(Floor).where(Floor.id == target_floor_id))
        floor = floor_result.scalar_one_or_none()
        if not floor:
            raise EntityNotFoundException("Floor", str(target_floor_id))

        flat.floor_id = target_floor_id
        flat.apartment_id = floor.apartment_id
        await db.commit()
        return await self.get_flat_by_id(db, flat_id)

    async def delete_flat(self, db: AsyncSession, flat_id: uuid.UUID) -> None:
        result = await db.execute(select(Flat).where(Flat.id == flat_id))
        flat = result.scalar_one_or_none()
        if not flat:
            raise EntityNotFoundException("Flat", str(flat_id))
        await db.delete(flat)
        await db.commit()

    # -------------------------------------------------------------
    # Flat Images
    # -------------------------------------------------------------
    async def add_flat_image(
        self, db: AsyncSession, flat_id: uuid.UUID, image_url: str,
        display_order: int = 0, image_type: Optional[str] = None, caption: Optional[str] = None
    ) -> FlatImage:
        img = FlatImage(
            flat_id=flat_id,
            image_url=image_url,
            image_type=image_type,
            caption=caption,
            display_order=display_order,
        )
        db.add(img)
        await db.commit()
        await db.refresh(img)
        return img

    async def delete_flat_image(self, db: AsyncSession, flat_id: uuid.UUID, image_id: uuid.UUID) -> None:
        result = await db.execute(
            select(FlatImage).where(
                and_(FlatImage.id == image_id, FlatImage.flat_id == flat_id)
            )
        )
        img = result.scalar_one_or_none()
        if not img:
            raise EntityNotFoundException("Flat Image", str(image_id))
        await db.delete(img)
        await db.commit()

    # -------------------------------------------------------------
    # Wishlist
    # -------------------------------------------------------------
    async def add_to_wishlist(self, db: AsyncSession, user_id: uuid.UUID, flat_id: uuid.UUID) -> Wishlist:
        query_flat = select(Flat).where(Flat.id == flat_id)
        res_flat = await db.execute(query_flat)
        if not res_flat.scalar_one_or_none():
            raise EntityNotFoundException("Flat", str(flat_id))

        query_wish = select(Wishlist).where(and_(Wishlist.user_id == user_id, Wishlist.flat_id == flat_id))
        res_wish = await db.execute(query_wish)
        existing = res_wish.scalar_one_or_none()
        if existing:
            return existing

        wish = Wishlist(user_id=user_id, flat_id=flat_id)
        db.add(wish)
        await db.commit()
        await db.refresh(wish)
        return wish

    async def remove_from_wishlist(self, db: AsyncSession, user_id: uuid.UUID, flat_id: uuid.UUID) -> None:
        query = delete(Wishlist).where(and_(Wishlist.user_id == user_id, Wishlist.flat_id == flat_id))
        await db.execute(query)
        await db.commit()

    async def get_user_wishlist(self, db: AsyncSession, user_id: uuid.UUID) -> List[Wishlist]:
        query = select(Wishlist).where(Wishlist.user_id == user_id).options(
            joinedload(Wishlist.flat).joinedload(Flat.images)
        )
        result = await db.execute(query)
        return list(result.scalars().all())


# Singleton
real_estate_service = RealEstateService()
