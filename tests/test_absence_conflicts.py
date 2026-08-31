import uuid
from datetime import date

from app.services.absences import is_user_away, load_active_absences_by_user
from app.models.absence import Absence

ALICE = uuid.uuid4()
BOB = uuid.uuid4()


def test_is_user_away_within_range():
    absences_by_user = {
        ALICE: [Absence(user_id=ALICE, start_date=date(2026, 9, 1), end_date=date(2026, 9, 10))]
    }
    assert is_user_away(absences_by_user, ALICE, date(2026, 9, 1)) is True
    assert is_user_away(absences_by_user, ALICE, date(2026, 9, 5)) is True
    assert is_user_away(absences_by_user, ALICE, date(2026, 9, 10)) is True


def test_is_user_away_outside_range():
    absences_by_user = {
        ALICE: [Absence(user_id=ALICE, start_date=date(2026, 9, 1), end_date=date(2026, 9, 10))]
    }
    assert is_user_away(absences_by_user, ALICE, date(2026, 8, 31)) is False
    assert is_user_away(absences_by_user, ALICE, date(2026, 9, 11)) is False


def test_is_user_away_no_absences_for_user():
    absences_by_user = {ALICE: [Absence(user_id=ALICE, start_date=date(2026, 9, 1), end_date=date(2026, 9, 10))]}
    assert is_user_away(absences_by_user, BOB, date(2026, 9, 5)) is False


def test_is_user_away_unaffected_by_other_users_absences():
    absences_by_user = {
        ALICE: [Absence(user_id=ALICE, start_date=date(2026, 9, 1), end_date=date(2026, 9, 10))],
        BOB: [],
    }
    assert is_user_away(absences_by_user, BOB, date(2026, 9, 5)) is False


async def test_load_active_absences_by_user_groups_by_user(test_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        session.add_all(
            [
                Absence(user_id=ALICE, start_date=date(2026, 9, 1), end_date=date(2026, 9, 5)),
                Absence(user_id=ALICE, start_date=date(2026, 10, 1), end_date=date(2026, 10, 5)),
                Absence(user_id=BOB, start_date=date(2026, 9, 1), end_date=date(2026, 9, 5)),
            ]
        )
        await session.commit()

        by_user = await load_active_absences_by_user(session, [ALICE, BOB])
        assert len(by_user[ALICE]) == 2
        assert len(by_user[BOB]) == 1


async def test_load_active_absences_by_user_empty_input_returns_empty(test_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        assert await load_active_absences_by_user(session, []) == {}
