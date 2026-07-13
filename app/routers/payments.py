import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.core.auth import get_current_user, get_or_create_db_user, UserClaims
from app.services.booking_service import booking_service
from app.schemas.schemas import CompleteLocalPaymentRequest, PaymentResponse, DocumentResponse

router = APIRouter(prefix="/payments", tags=["Payments"])
documents_router = APIRouter(prefix="/documents", tags=["Documents"])




@router.post("/complete-local")
async def complete_local_payment(
    body: CompleteLocalPaymentRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Bypasses third party payment gateways and executes local payment & booking completion."""
    await get_or_create_db_user(db, current_user)
    user_id = uuid.UUID(current_user.user_id)
    return await booking_service.complete_payment_local(
        db, user_id, body.booking_id, body.amount, body.payment_type
    )


@router.get("/history", response_model=List[PaymentResponse])
async def get_payment_history(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List payment transaction logs."""
    if current_user.role == "Admin":
        return await booking_service.get_payments(db)
    else:
        user_id = uuid.UUID(current_user.user_id)
        return await booking_service.get_payments(db, user_id)


# Direct document fetching endpoints mapping Stage 3 specification
@router.get("/documents", response_model=List[DocumentResponse], tags=["Documents"])
async def list_user_documents(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all legal generated agreements and receipts for user."""
    user_id = uuid.UUID(current_user.user_id)
    return await booking_service.get_documents(db, user_id)


@documents_router.get("/", response_model=List[DocumentResponse], tags=["Documents"])
async def list_documents(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = uuid.UUID(current_user.user_id)
    return await booking_service.get_documents(db, user_id)


from fastapi import Response
import httpx
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.models.models import Document

@documents_router.get("/{document_id}/view", tags=["Documents"])
async def view_document(
    document_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Securely view document PDF inline in browser, verifying ownership."""
    user_id = uuid.UUID(current_user.user_id)
    
    query = select(Document).options(joinedload(Document.booking)).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    if current_user.role != "Admin":
        if not doc.booking or doc.booking.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this document."
            )
            
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(doc.file_url, timeout=5.0)
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail="Document file not found in storage.")
            pdf_bytes = resp.content
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to retrieve document file from storage.")
        
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline"
        }
    )


@documents_router.get("/{document_id}/download", tags=["Documents"])
async def download_document(
    document_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Securely download document PDF, verifying ownership."""
    user_id = uuid.UUID(current_user.user_id)
    
    query = select(Document).options(joinedload(Document.booking)).where(Document.id == document_id)
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    if current_user.role != "Admin":
        if not doc.booking or doc.booking.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this document."
            )
            
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(doc.file_url, timeout=5.0)
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail="Document file not found in storage.")
            pdf_bytes = resp.content
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to retrieve document file from storage.")
        
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{doc.name.replace(' ', '_')}.pdf\""
        }
    )
