import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.services.ai.groq_service import groq_service
from app.services.ai.prompt_manager import prompt_manager
from app.services.ai.db_search_engine import db_search_engine
from app.models.models import Flat, Complaint

router = APIRouter(prefix="/ai", tags=["AI Intelligence Layer"])

# --- Schemas ---

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    apartment_id: Optional[str] = None
    flat_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    model: str
    tokens_used: int

class SearchRequest(BaseModel):
    query: str

class ComplaintAnalysisRequest(BaseModel):
    description: str

class ComplaintAnalysisResponse(BaseModel):
    category: str
    priority: str
    title: str
    summary: str

class AnnouncementGenerationRequest(BaseModel):
    topic: str

class AnnouncementGenerationResponse(BaseModel):
    title: str
    content: str
    announcement_type: str

# --- Endpoints ---

@router.post("/chat", response_model=ChatResponse)
async def chat_bot(
    body: ChatRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """General AI chat routing logic. Extracts filters or fetches resident details dynamically."""
    last_msg = body.messages[-1].content
    user_id = uuid.UUID(current_user.user_id)
    
    # 1. Resident Specific Context Routing
    if current_user.role == "Resident":
        ctx = await db_search_engine.get_resident_context(db, user_id)
        prompts = prompt_manager.get_resident_assistant_prompt(last_msg, ctx)
        res = await groq_service.get_chat_completion(prompts)
        return ChatResponse(reply=res["reply"], model=groq_service.model, tokens_used=res["tokens"])

    # 2. Admin Context Routing
    elif current_user.role == "Admin":
        metrics = await db_search_engine.get_admin_metrics(db)
        prompts = prompt_manager.get_admin_assistant_prompt(last_msg, metrics)
        res = await groq_service.get_chat_completion(prompts)
        return ChatResponse(reply=res["reply"], model=groq_service.model, tokens_used=res["tokens"])

    # 3. Customer Property Discovery AI / Natural Language Flat Filters
    else:
        # Extract filters
        extract_prompts = prompt_manager.get_filter_extraction_prompt(last_msg)
        extract_res = await groq_service.get_chat_completion(extract_prompts, response_format={"type": "json_object"})
        
        try:
            filters = json.loads(extract_res["reply"])
            flats = await db_search_engine.extract_filters_and_search_flats(db, filters)
            
            if not flats:
                reply = "I couldn't find any available flats matching your criteria in the database."
            else:
                flat_list = "\n".join([
                    f"- Flat {f.flat_number} ({f.flat_type}, facing {f.facing_direction}, price: Buy: ₹{f.price_buy or 0}/Rent: ₹{f.price_rent or 0})" 
                    for f in flats
                ])
                reply = f"Here are the matching available flats I found:\n{flat_list}"
        except Exception:
            reply = "I encountered an error trying to search the database. Let me help you with general queries instead."
            
        return ChatResponse(reply=reply, model=groq_service.model, tokens_used=extract_res["tokens"])


@router.post("/search")
async def global_ai_search(
    body: SearchRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Global search across flats, residents, complaints and documents."""
    results = await db_search_engine.global_search(db, body.query)
    return {"results": results, "count": len(results)}


@router.post("/resident", response_model=ChatResponse)
async def resident_ai_assistant(
    body: ChatRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Strict resident dashboard AI assistant helper."""
    user_id = uuid.UUID(current_user.user_id)
    ctx = await db_search_engine.get_resident_context(db, user_id)
    last_msg = body.messages[-1].content
    prompts = prompt_manager.get_resident_assistant_prompt(last_msg, ctx)
    res = await groq_service.get_chat_completion(prompts)
    return ChatResponse(reply=res["reply"], model=groq_service.model, tokens_used=res["tokens"])


@router.post("/admin", response_model=ChatResponse)
async def admin_ai_assistant(
    body: ChatRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin portal dashboard reporting metrics assistant."""
    metrics = await db_search_engine.get_admin_metrics(db)
    last_msg = body.messages[-1].content
    prompts = prompt_manager.get_admin_assistant_prompt(last_msg, metrics)
    res = await groq_service.get_chat_completion(prompts)
    return ChatResponse(reply=res["reply"], model=groq_service.model, tokens_used=res["tokens"])


@router.post("/complaint", response_model=ComplaintAnalysisResponse)
async def analyze_complaint(
    body: ComplaintAnalysisRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Automatically categorizes and formats raw complaint text."""
    prompts = prompt_manager.get_complaint_classifier_prompt(body.description)
    res = await groq_service.get_chat_completion(prompts, response_format={"type": "json_object"})
    try:
        data = json.loads(res["reply"])
        return ComplaintAnalysisResponse(
            category=data.get("category", "Other"),
            priority=data.get("priority", "Medium"),
            title=data.get("title", "Service Ticket Request"),
            summary=data.get("summary", body.description)
        )
    except Exception:
        return ComplaintAnalysisResponse(
            category="Other",
            priority="Medium",
            title="Service Ticket",
            summary=body.description
        )


@router.post("/announcement", response_model=AnnouncementGenerationResponse)
async def generate_announcement_template(
    body: AnnouncementGenerationRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Generates announcement copy and notices professionally."""
    prompts = prompt_manager.get_announcement_generator_prompt(body.topic)
    res = await groq_service.get_chat_completion(prompts, response_format={"type": "json_object"})
    try:
        data = json.loads(res["reply"])
        return AnnouncementGenerationResponse(
            title=data.get("title", "Water Shutdown Notice"),
            content=data.get("content", ""),
            announcement_type=data.get("announcement_type", "General")
        )
    except Exception:
        return AnnouncementGenerationResponse(
            title="Community Bulletin",
            content=body.topic,
            announcement_type="General"
        )
