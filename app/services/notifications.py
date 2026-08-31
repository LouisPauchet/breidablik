import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.duty import Duty
from app.models.notification import Notification
from app.models.shopping import ShoppingItem, ShoppingList
from app.services.push import send_push_to_user
from app.services.rotation import (
    compute_period_index,
    overrides_by_period_index,
    resolve_assignee_for_period,
    sorted_assignees,
)
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

    ordered = sorted_assignees(duty.assignees)
    if not ordered:
        return

    period_index = compute_period_index(duty, today())
    overrides_by_period = overrides_by_period_index(duty.overrides)
    on_duty_user_id = resolve_assignee_for_period(ordered, overrides_by_period, period_index)

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
