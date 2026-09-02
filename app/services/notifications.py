import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.duty import Duty
from app.models.event import Event
from app.models.notification import Notification
from app.models.shopping import ShoppingItem, ShoppingList
from app.models.user import User
from app.services.duty_status import resolve_current_assignee
from app.services.push import send_push_to_user
from app.timeutils import today


async def notify_shopping_item_added(
    session: AsyncSession, shopping_list: ShoppingList, item: ShoppingItem, adder_id: uuid.UUID
) -> None:
    """Notify whoever is currently on duty for the list's linked Duty, skipping the person
    who just added the item. Private lists and shared lists with no duty attached never
    notify anyone — see the CHECK constraint on ShoppingList for why the first case can't
    even happen by accident.
    """
    if shopping_list.owner_user_id is not None or shopping_list.duty_id is None:
        return

    result = await session.execute(
        select(Duty)
        .options(selectinload(Duty.assignees), selectinload(Duty.overrides))
        .where(Duty.id == shopping_list.duty_id)
    )
    duty = result.scalar_one_or_none()
    if duty is None:
        return

    on_duty_user_id = await resolve_current_assignee(session, duty, today())
    if on_duty_user_id is None:
        return

    if on_duty_user_id == adder_id:
        return

    notification = Notification(
        user_id=on_duty_user_id,
        kind="shopping_item_added",
        title="Shopping list updated",
        body=f'"{item.name}" was added to {shopping_list.name}',
        url="/shopping",
    )
    session.add(notification)
    await session.commit()

    await send_push_to_user(
        session,
        on_duty_user_id,
        {"title": notification.title, "body": notification.body, "url": notification.url},
    )


async def notify_event_created(session: AsyncSession, event: Event, creator: User) -> None:
    """A new event is relevant to the whole household, not just whoever's on duty — unlike
    notify_shopping_item_added above, this broadcasts to every other active member.
    """
    result = await session.execute(select(User).where(User.is_active.is_(True), User.id != creator.id))
    recipients = list(result.scalars())
    if not recipients:
        return

    title = "New event"
    body = f'"{event.title}" was added to the calendar'
    url = f"/events/{event.id}"

    for recipient in recipients:
        session.add(Notification(user_id=recipient.id, kind="event_created", title=title, body=body, url=url))
    await session.commit()

    for recipient in recipients:
        await send_push_to_user(session, recipient.id, {"title": title, "body": body, "url": url})


async def notify_admins_of_update(session: AsyncSession, version: str) -> None:
    """Called by the Passenger update script (scripts/passenger_update.py) after it swaps in
    a new release and runs migrations — lets admins know the deploy actually landed, since
    that script runs unattended (cron or a manual SSH invocation), not from a browser.
    """
    result = await session.execute(
        select(User).where(User.is_superuser.is_(True), User.is_active.is_(True))
    )
    admins = list(result.scalars())

    title = "Breidablik updated"
    body = f"The app was updated to v{version}."
    for admin in admins:
        session.add(Notification(user_id=admin.id, kind="app_updated", title=title, body=body, url="/profile"))
    await session.commit()

    for admin in admins:
        await send_push_to_user(session, admin.id, {"title": title, "body": body, "url": "/profile"})
