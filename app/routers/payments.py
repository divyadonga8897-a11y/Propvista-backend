import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.services.booking_service import booking_service
from app.schemas.schemas import CreateOrderRequest, VerifyPaymentRequest, PaymentResponse, DocumentResponse

router = APIRouter(prefix="/payments", tags=["Payments"])
documents_router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/create-order", status_code=status.HTTP_201_CREATED)
async def create_payment_order(
    body: CreateOrderRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate a Razorpay Order ID for standard checkout."""
    user_id = uuid.UUID(current_user.user_id)
    return await booking_service.create_payment_order(
        db, user_id, body.booking_id, body.amount, body.payment_type
    )


@router.post("/verify")
async def verify_payment(
    body: VerifyPaymentRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify Razorpay payment signature & activate property status / residency."""
    success = await booking_service.verify_payment(
        db, body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    )
    if not success:
        raise HTTPException(status_code=400, detail="Payment verification failed. Signature mismatch.")
    return {"status": "success", "verified": True}


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
