import json
import logging
from typing import List
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.models.models import Apartment, Flat, Floor, City, Resident, Complaint, Announcement, Visitor, Vehicle, FacilityBooking, Document, CommunityRule
import uuid

logger = logging.getLogger("app.ai_search")

class DatabaseSearchEngine:
    async def extract_filters_and_search_flats(self, db: AsyncSession, structured_filters: dict) -> List[Flat]:
        """Convert structured filters into DB queries to get matching flats."""
        query = select(Flat).options(joinedload(Flat.floor).joinedload(Floor.apartment))
        conditions = []

        # 1. Flat Type Filter (Studio, 1BHK, 2BHK, 3BHK, etc.)
        flat_type = structured_filters.get("flat_type")
        if flat_type and flat_type.lower() != "any":
            conditions.append(Flat.flat_type.like(f"%{flat_type}%"))

        # 2. Facing Direction Filter (East, West, etc.)
        facing = structured_filters.get("facing_direction")
        if facing and facing.lower() != "any":
            conditions.append(Flat.facing_direction.like(f"%{facing}%"))

        # 3. Budget Filter
        max_budget = structured_filters.get("max_budget")
        if max_budget:
            try:
                budget_val = float(max_budget)
                conditions.append(or_(
                    Flat.price_buy <= budget_val,
                    Flat.price_rent <= budget_val
                ))
            except ValueError:
                pass

        # 4. Rent vs Buy Selection
        listing_type = structured_filters.get("listing_type")
        if listing_type:
            if listing_type.upper() == "RENT":
                conditions.append(Flat.price_rent.isnot(None))
            elif listing_type.upper() == "BUY":
                conditions.append(Flat.price_buy.isnot(None))

        # 5. Parking slots
        has_parking = structured_filters.get("has_parking")
        if has_parking is True:
            conditions.append(Flat.parking_slots > 0)

        # 6. Floor level
        floor_num = structured_filters.get("floor_number")
        if floor_num is not None:
            try:
                floor_val = int(floor_num)
                # Link floor
                query = query.join(Flat.floor).where(Floor.floor_number == floor_val)
            except ValueError:
                pass

        # 7. Apartment Community Filter
        apartment_id = structured_filters.get("apartment_id")
        if apartment_id:
            try:
                conditions.append(Flat.apartment_id == uuid.UUID(apartment_id))
            except Exception:
                pass
                
        # Status Filter (default to Available to keep database valid)
        conditions.append(Flat.status == "Available")

        if conditions:
            query = query.where(and_(*conditions))

        res = await db.execute(query)
        return list(res.scalars().all())

    async def get_resident_context(self, db: AsyncSession, user_id: uuid.UUID) -> dict:
        """Fetch all contextual data belonging strictly to the resident user."""
        res_profile = await db.execute(
            select(Resident)
            .where(Resident.user_id == user_id)
            .options(
                joinedload(Resident.flat),
                joinedload(Resident.apartment),
                joinedload(Resident.floor)
            )
        )
        resident = res_profile.scalar_one_or_none()
        if not resident:
            return {}

        # Fetch resident's announcements, complaints, visitors, vehicles, bookings, rules, documents
        announcements_res = await db.execute(select(Announcement).where(Announcement.apartment_id == resident.apartment_id))
        announcements = announcements_res.scalars().all()

        complaints_res = await db.execute(select(Complaint).where(Complaint.resident_id == resident.id))
        complaints = complaints_res.scalars().all()

        visitors_res = await db.execute(select(Visitor).where(Visitor.resident_id == resident.id))
        visitors = visitors_res.scalars().all()

        vehicles_res = await db.execute(select(Vehicle).where(Vehicle.resident_id == resident.id))
        vehicles = vehicles_res.scalars().all()

        bookings_res = await db.execute(select(FacilityBooking).where(FacilityBooking.resident_id == resident.id))
        bookings = bookings_res.scalars().all()

        rules_res = await db.execute(select(CommunityRule).where(CommunityRule.apartment_id == resident.apartment_id))
        rules = rules_res.scalars().all()

        documents_res = await db.execute(select(Document).where(Document.flat_id == resident.flat_id))
        documents = documents_res.scalars().all()

        return {
            "profile": {
                "id": str(resident.id),
                "resident_type": resident.resident_type,
                "apartment_name": resident.apartment.name,
                "flat_number": resident.flat.flat_number,
                "floor_number": resident.floor.floor_number,
                "move_in_date": str(resident.move_in_date),
                "agreement_number": resident.agreement_number,
                "status": resident.status
            },
            "announcements": [{"title": a.title, "content": a.content, "type": a.announcement_type} for a in announcements],
            "complaints": [{"id": str(c.id), "title": c.title, "category": c.category, "status": c.status} for c in complaints],
            "visitors": [{"name": v.name, "date": str(v.visit_date), "status": v.approval_status} for v in visitors],
            "vehicles": [{"number": v.vehicle_number, "type": v.vehicle_type, "slot": v.parking_slot} for v in vehicles],
            "facility_bookings": [{"facility": fb.facility_name, "date": str(fb.booking_date), "status": fb.status} for fb in bookings],
            "rules": [{"title": r.title, "description": r.description} for r in rules],
            "documents": [{"name": d.name, "url": d.file_url} for d in documents]
        }

    async def get_admin_metrics(self, db: AsyncSession) -> dict:
        """Fetch general high-level analytics summary data for the admin assistant."""
        apts_cnt = await db.execute(select(func.count(Apartment.id)))
        flats_cnt = await db.execute(select(func.count(Flat.id)))
        avail_cnt = await db.execute(select(func.count(Flat.id)).where(Flat.status == "Available"))
        sold_cnt = await db.execute(select(func.count(Flat.id)).where(Flat.status == "Sold"))
        rented_cnt = await db.execute(select(func.count(Flat.id)).where(Flat.status == "Rented"))
        
        # complaints statistics
        complaints_res = await db.execute(select(Complaint).options(joinedload(Complaint.apartment)))
        complaints = complaints_res.scalars().all()
        
        return {
            "total_apartments": apts_cnt.scalar() or 0,
            "total_flats": flats_cnt.scalar() or 0,
            "available_flats": avail_cnt.scalar() or 0,
            "sold_flats": sold_cnt.scalar() or 0,
            "rented_flats": rented_cnt.scalar() or 0,
            "complaints": [{"title": c.title, "category": c.category, "status": c.status, "apartment": c.apartment.name if c.apartment else ""} for c in complaints]
        }

    async def global_search(self, db: AsyncSession, query_str: str) -> List[dict]:
        """Perform search across Flats, Residents, Complaints, and Documents."""
        results = []
        
        # 1. Search flats
        flats_res = await db.execute(select(Flat).where(Flat.flat_number.like(f"%{query_str}%")).limit(5))
        for f in flats_res.scalars().all():
            results.append({
                "type": "Flat",
                "title": f"Flat {f.flat_number}",
                "detail": f"Status: {f.status} • Area: {f.area_sqft} sqft",
                "link": f"/flat/{f.id}"
            })
            
        # 2. Search residents
        residents_res = await db.execute(
            select(Resident)
            .join(Resident.user)
            .where(or_(
                Resident.user.has(email=query_str),
                Resident.agreement_number.like(f"%{query_str}%")
            ))
            .options(joinedload(Resident.flat))
            .limit(5)
        )
        for r in residents_res.scalars().all():
            results.append({
                "type": "Resident",
                "title": f"Resident ({r.resident_type})",
                "detail": f"Agreement: {r.agreement_number} • Flat: {r.flat.flat_number if r.flat else 'N/A'}",
                "link": f"/dashboard/admin"
            })
            
        # 3. Search complaints
        complaints_res = await db.execute(select(Complaint).where(Complaint.title.like(f"%{query_str}%")).limit(5))
        for c in complaints_res.scalars().all():
            results.append({
                "type": "Complaint",
                "title": c.title,
                "detail": f"Status: {c.status} • Category: {c.category}",
                "link": f"/resident/complaints"
            })
            
        # 4. Search documents
        documents_res = await db.execute(select(Document).where(Document.name.like(f"%{query_str}%")).limit(5))
        for d in documents_res.scalars().all():
            results.append({
                "type": "Document",
                "title": d.name,
                "detail": f"Type: {d.doc_type}",
                "link": d.file_url
            })
            
        return results

db_search_engine = DatabaseSearchEngine()
