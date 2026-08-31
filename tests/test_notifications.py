import uuid
from datetime import date
from types import SimpleNamespace

from pywebpush import WebPushException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.services.push as push_module
from app.models.duty import Duty, DutyAssignee
from app.models.notification import Notification, PushSubscription
from app.models.shopping import ShoppingItem, ShoppingList
from app.services.notifications import notify_shopping_item_added
from app.services.push import send_push_to_user

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def _session(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)()


async def test_private_list_never_notifies(test_engine):
    async with _session(test_engine) as session:
        shopping_list = ShoppingList(name="Mine", owner_user_id=ALICE, created_by_id=ALICE)
        session.add(shopping_list)
        await session.flush()
        item = ShoppingItem(list_id=shopping_list.id, name="Milk", added_by_id=ALICE)
        session.add(item)
        await session.commit()

        await notify_shopping_item_added(session, shopping_list, item, adder_id=ALICE)

        result = await session.execute(select(Notification))
        assert list(result.scalars()) == []


async def test_shared_list_without_duty_never_notifies(test_engine):
    async with _session(test_engine) as session:
        shopping_list = ShoppingList(name="Household", owner_user_id=None, duty_id=None, created_by_id=ALICE)
        session.add(shopping_list)
        await session.flush()
        item = ShoppingItem(list_id=shopping_list.id, name="Milk", added_by_id=ALICE)
        session.add(item)
        await session.commit()

        await notify_shopping_item_added(session, shopping_list, item, adder_id=ALICE)

        result = await session.execute(select(Notification))
        assert list(result.scalars()) == []


async def test_shared_list_with_duty_notifies_on_duty_person_not_adder(test_engine):
    async with _session(test_engine) as session:
        duty = Duty(
            title="Shopping",
            start_date=date.today(),
            task_interval_days=7,
            rotation_interval_days=7,
            created_by_id=ALICE,
        )
        session.add(duty)
        await session.flush()
        session.add(DutyAssignee(duty_id=duty.id, user_id=BOB, order_index=0))

        shopping_list = ShoppingList(
            name="Household", owner_user_id=None, duty_id=duty.id, created_by_id=ALICE
        )
        session.add(shopping_list)
        await session.flush()
        item = ShoppingItem(list_id=shopping_list.id, name="Milk", added_by_id=ALICE)
        session.add(item)
        await session.commit()

        await notify_shopping_item_added(session, shopping_list, item, adder_id=ALICE)

        result = await session.execute(select(Notification))
        notifications = list(result.scalars())
        assert len(notifications) == 1
        assert notifications[0].user_id == BOB
        assert "Milk" in notifications[0].body


async def test_skip_self_when_adder_is_on_duty(test_engine):
    async with _session(test_engine) as session:
        duty = Duty(
            title="Shopping",
            start_date=date.today(),
            task_interval_days=7,
            rotation_interval_days=7,
            created_by_id=BOB,
        )
        session.add(duty)
        await session.flush()
        session.add(DutyAssignee(duty_id=duty.id, user_id=BOB, order_index=0))

        shopping_list = ShoppingList(
            name="Household", owner_user_id=None, duty_id=duty.id, created_by_id=BOB
        )
        session.add(shopping_list)
        await session.flush()
        item = ShoppingItem(list_id=shopping_list.id, name="Eggs", added_by_id=BOB)
        session.add(item)
        await session.commit()

        # Bob is both the adder and the on-duty person -> no notification.
        await notify_shopping_item_added(session, shopping_list, item, adder_id=BOB)

        result = await session.execute(select(Notification))
        assert list(result.scalars()) == []


async def test_send_push_noop_without_vapid_configured(test_engine, monkeypatch):
    fake_settings = SimpleNamespace(vapid_private_key="", vapid_claim_email="mailto:test@example.com")
    monkeypatch.setattr(push_module, "get_settings", lambda: fake_settings)

    called = False

    def fake_webpush(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(push_module, "webpush", fake_webpush)

    async with _session(test_engine) as session:
        session.add(PushSubscription(user_id=ALICE, endpoint="https://example.com/ep1", p256dh="p", auth="a"))
        await session.commit()
        await send_push_to_user(session, ALICE, {"title": "hi"})

    assert called is False


async def test_send_push_prunes_subscription_on_410(test_engine, monkeypatch):
    fake_settings = SimpleNamespace(vapid_private_key="fake-key", vapid_claim_email="mailto:test@example.com")
    monkeypatch.setattr(push_module, "get_settings", lambda: fake_settings)

    def raise_gone(*args, **kwargs):
        raise WebPushException("gone", response=SimpleNamespace(status_code=410))

    monkeypatch.setattr(push_module, "webpush", raise_gone)

    async with _session(test_engine) as session:
        sub = PushSubscription(user_id=ALICE, endpoint="https://example.com/ep2", p256dh="p", auth="a")
        session.add(sub)
        await session.commit()
        sub_id = sub.id

        await send_push_to_user(session, ALICE, {"title": "hi"})

        result = await session.execute(select(PushSubscription).where(PushSubscription.id == sub_id))
        assert result.scalar_one_or_none() is None


async def test_send_push_keeps_subscription_on_other_errors(test_engine, monkeypatch):
    fake_settings = SimpleNamespace(vapid_private_key="fake-key", vapid_claim_email="mailto:test@example.com")
    monkeypatch.setattr(push_module, "get_settings", lambda: fake_settings)

    def raise_server_error(*args, **kwargs):
        raise WebPushException("server error", response=SimpleNamespace(status_code=500))

    monkeypatch.setattr(push_module, "webpush", raise_server_error)

    async with _session(test_engine) as session:
        sub = PushSubscription(user_id=ALICE, endpoint="https://example.com/ep3", p256dh="p", auth="a")
        session.add(sub)
        await session.commit()
        sub_id = sub.id

        # Must not raise — push sending is best-effort.
        await send_push_to_user(session, ALICE, {"title": "hi"})

        result = await session.execute(select(PushSubscription).where(PushSubscription.id == sub_id))
        assert result.scalar_one_or_none() is not None
