"""Web Push sending. Best-effort by design: a failed push must never fail the request that
triggered it (e.g. adding a shopping list item) — the in-app Notification row written
alongside it is the reliable fallback, since push delivery itself can't be guaranteed (no
VAPID configured, an expired subscription, a browser that doesn't support it, iOS Safari
without the PWA installed to the home screen, ...).
"""

import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.models.notification import PushSubscription

logger = logging.getLogger(__name__)


def _send_sync(subscription: PushSubscription, payload: dict) -> None:
    settings = get_settings()
    webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        },
        data=json.dumps(payload),
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_claim_email},
    )


async def send_push_to_user(session: AsyncSession, user_id, payload: dict) -> None:
    settings = get_settings()
    if not settings.vapid_private_key:
        return

    result = await session.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))
    subscriptions = list(result.scalars())

    for subscription in subscriptions:
        try:
            await run_in_threadpool(_send_sync, subscription, payload)
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in (404, 410):
                await session.delete(subscription)
                await session.commit()
            else:
                logger.warning("Push send failed for subscription %s: %s", subscription.id, exc)
