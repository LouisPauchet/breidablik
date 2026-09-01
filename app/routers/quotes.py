"""A single quote of the day, shared by the wall dashboard (app/routers/dashboard.py) and the
in-app home screen — both just want today's pick from the same pool (app/services/quotes.py).
"""

from fastapi import APIRouter, Depends

from app.auth.backend import current_active_user
from app.schemas.quote import QuoteOut
from app.services.quotes import quote_of_the_day
from app.timeutils import today

router = APIRouter(
    prefix="/api/quote-of-the-day", tags=["quotes"], dependencies=[Depends(current_active_user)]
)


@router.get("", response_model=QuoteOut)
async def get_quote_of_the_day():
    return quote_of_the_day(today())
