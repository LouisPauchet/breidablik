import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.awards import AwardCategorySuggestion, AwardCycle
from app.models.duty import Duty
from app.models.event import Event
from app.models.notification import Notification
from app.models.shopping import ShoppingItem, ShoppingList
from app.models.user import User
from app.services.duty_status import resolve_current_assignee
from app.services.push import send_push_to_user
from app.timeutils import today


async def _broadcast_to_active_users(
    session: AsyncSession, kind: str, title: str, body: str, url: str
) -> None:
    result = await session.execute(select(User.id).where(User.is_active.is_(True)))
    recipient_ids = list(result.scalars())
    if not recipient_ids:
        return

    for recipient_id in recipient_ids:
        session.add(Notification(user_id=recipient_id, kind=kind, title=title, body=body, url=url))
    await session.commit()

    for recipient_id in recipient_ids:
        await send_push_to_user(session, recipient_id, {"title": title, "body": body, "url": url})


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


async def notify_award_suggestion_window_open(session: AsyncSession, cycle: AwardCycle) -> None:
    await _broadcast_to_active_users(
        session,
        kind="award_suggest_open",
        title="Suggest this month's award category",
        body="Pick a title and emoji for this month's community award.",
        url="/",
    )


async def notify_award_voting_window_open(
    session: AsyncSession, cycle: AwardCycle, drawn: AwardCategorySuggestion
) -> None:
    await _broadcast_to_active_users(
        session,
        kind="award_vote_open",
        title=f"Vote now: {drawn.emoji} {drawn.title}",
        body="This month's community award category has been drawn — cast your vote!",
        url="/",
    )


async def notify_award_results_decided(session: AsyncSession, cycle: AwardCycle) -> None:
    winner_ids = [uid for uid in (cycle.duty_master_winner_id, cycle.community_award_winner_id) if uid]
    names_by_id: dict[uuid.UUID, str] = {}
    if winner_ids:
        result = await session.execute(select(User.id, User.display_name).where(User.id.in_(winner_ids)))
        names_by_id = dict(result.all())

    if cycle.duty_master_winner_id:
        duty_master_line = f"Duty Master: {names_by_id.get(cycle.duty_master_winner_id, 'Someone')}"
    else:
        duty_master_line = "No Duty Master this month."

    if cycle.community_award_winner_id:
        emoji = cycle.drawn_suggestion.emoji if cycle.drawn_suggestion else ""
        title = cycle.drawn_suggestion.title if cycle.drawn_suggestion else "Community award"
        winner_name = names_by_id.get(cycle.community_award_winner_id, "Someone")
        community_line = f"{emoji} {title}: {winner_name}"
    else:
        community_line = "No community award this month."

    await _broadcast_to_active_users(
        session,
        kind="award_results",
        title="This month's awards are in!",
        body=f"{duty_master_line} · {community_line}",
        url="/",
    )
