import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.config import get_settings
from app.db import get_session
from app.models.notification import Notification, PushSubscription
from app.models.user import User
from app.schemas.notification import NotificationOut, PushSubscriptionCreate

router = APIRouter(
    prefix="/api/notifications", tags=["notifications"], dependencies=[Depends(current_active_user)]
)


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    return {"public_key": get_settings().vapid_public_key}


@router.post("/push-subscriptions", status_code=201)
async def subscribe(
    data: PushSubscriptionCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PushSubscription).where(PushSubscription.endpoint == data.endpoint)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        session.add(
            PushSubscription(
                user_id=user.id,
                endpoint=data.endpoint,
                p256dh=data.keys.p256dh,
                auth=data.keys.auth,
            )
        )
    else:
        existing.user_id = user.id
        existing.p256dh = data.keys.p256dh
        existing.auth = data.keys.auth
    await session.commit()
    return {"ok": True}


@router.delete("/push-subscriptions")
async def unsubscribe(
    endpoint: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PushSubscription).where(
            PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is not None:
        await session.delete(subscription)
        await session.commit()
    return {"ok": True}


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    return list(result.scalars())


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=404, detail="NOTIFICATION_NOT_FOUND")
    notification.is_read = True
    await session.commit()
    return notification
