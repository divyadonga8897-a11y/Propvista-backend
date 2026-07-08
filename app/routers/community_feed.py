import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import CommunityFeedPost, CommunityFeedComment, CommunityFeedLike
from app.schemas.schemas import CommunityFeedPostCreate, CommunityFeedPostResponse, CommunityFeedCommentCreate, CommunityFeedCommentResponse

from app.core.dependencies import verify_resident_access

router = APIRouter(prefix="/community-feed", tags=["Community Feed"])

@router.get("/{apartment_id}", response_model=List[CommunityFeedPostResponse])
async def get_feed(
    apartment_id: uuid.UUID,
    current_user: UserClaims = Depends(verify_resident_access),
    db: AsyncSession = Depends(get_db)
):
    query = select(CommunityFeedPost).where(CommunityFeedPost.apartment_id == apartment_id).order_by(
        desc(CommunityFeedPost.is_pinned), desc(CommunityFeedPost.created_at)
    )
    result = await db.execute(query)
    posts = result.scalars().all()
    return posts

@router.post("/", response_model=CommunityFeedPostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    apartment_id: uuid.UUID,
    post: CommunityFeedPostCreate,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    new_post = CommunityFeedPost(
        apartment_id=apartment_id,
        user_id=uuid.UUID(current_user.user_id),
        **post.model_dump()
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)
    return new_post

@router.post("/{post_id}/like")
async def toggle_like(
    post_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = uuid.UUID(current_user.user_id)
    query = select(CommunityFeedLike).where(
        CommunityFeedLike.post_id == post_id,
        CommunityFeedLike.user_id == user_id
    )
    result = await db.execute(query)
    like = result.scalar_one_or_none()
    
    post_query = select(CommunityFeedPost).where(CommunityFeedPost.id == post_id)
    post_result = await db.execute(post_query)
    post = post_result.scalar_one_or_none()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
        
    if like:
        await db.delete(like)
        post.likes_count = max(0, post.likes_count - 1)
        action = "unliked"
    else:
        new_like = CommunityFeedLike(post_id=post_id, user_id=user_id)
        db.add(new_like)
        post.likes_count += 1
        action = "liked"
        
    await db.commit()
    return {"status": action, "likes_count": post.likes_count}

@router.post("/{post_id}/comment", response_model=CommunityFeedCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: uuid.UUID,
    comment: CommunityFeedCommentCreate,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_comment = CommunityFeedComment(
        post_id=post_id,
        user_id=uuid.UUID(current_user.user_id),
        content=comment.content
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    return new_comment

@router.get("/{post_id}/comments", response_model=List[CommunityFeedCommentResponse])
async def get_comments(
    post_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(CommunityFeedComment).where(CommunityFeedComment.post_id == post_id).order_by(CommunityFeedComment.created_at)
    result = await db.execute(query)
    return result.scalars().all()
