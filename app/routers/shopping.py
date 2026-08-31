import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.shopping import ShoppingItem, ShoppingList
from app.models.user import User
from app.schemas.shopping import ShoppingItemCreate, ShoppingItemOut, ShoppingListCreate, ShoppingListOut
from app.services.notifications import notify_shopping_item_added

router = APIRouter(prefix="/api/shopping", tags=["shopping"], dependencies=[Depends(current_active_user)])


def _visible_to(user_id: uuid.UUID):
    return or_(ShoppingList.owner_user_id.is_(None), ShoppingList.owner_user_id == user_id)


async def _load_list_or_404(session: AsyncSession, list_id: uuid.UUID, user: User) -> ShoppingList:
    result = await session.execute(
        select(ShoppingList).options(selectinload(ShoppingList.items)).where(ShoppingList.id == list_id)
    )
    shopping_list = result.scalar_one_or_none()
    if shopping_list is None:
        raise HTTPException(status_code=404, detail="LIST_NOT_FOUND")
    if shopping_list.owner_user_id is not None and shopping_list.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="NOT_YOUR_LIST")
    return shopping_list


async def _load_item_or_404(session: AsyncSession, item_id: uuid.UUID, user: User) -> ShoppingItem:
    result = await session.execute(
        select(ShoppingItem).options(selectinload(ShoppingItem.list)).where(ShoppingItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="ITEM_NOT_FOUND")
    if item.list.owner_user_id is not None and item.list.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="NOT_YOUR_LIST")
    return item


@router.get("/lists", response_model=list[ShoppingListOut])
async def list_shopping_lists(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(ShoppingList)
        .options(selectinload(ShoppingList.items))
        .where(_visible_to(user.id))
        .order_by(ShoppingList.created_at)
    )
    return list(result.scalars().unique())


@router.post("/lists", response_model=ShoppingListOut, status_code=201)
async def create_shopping_list(
    data: ShoppingListCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    shopping_list = ShoppingList(
        name=data.name,
        owner_user_id=user.id if data.is_private else None,
        duty_id=data.duty_id,
        created_by_id=user.id,
    )
    session.add(shopping_list)
    await session.commit()
    await session.refresh(shopping_list, attribute_names=["items"])
    return shopping_list


@router.get("/lists/{list_id}", response_model=ShoppingListOut)
async def get_shopping_list(
    list_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    return await _load_list_or_404(session, list_id, user)


@router.delete("/lists/{list_id}", status_code=204)
async def delete_shopping_list(
    list_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    shopping_list = await _load_list_or_404(session, list_id, user)
    await session.delete(shopping_list)
    await session.commit()


@router.post("/lists/{list_id}/items", response_model=ShoppingItemOut, status_code=201)
async def add_item(
    list_id: uuid.UUID,
    data: ShoppingItemCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    shopping_list = await _load_list_or_404(session, list_id, user)
    item = ShoppingItem(
        list_id=shopping_list.id, name=data.name, quantity=data.quantity, added_by_id=user.id
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    await notify_shopping_item_added(session, shopping_list, item, adder_id=user.id)

    return item


@router.patch("/items/{item_id}/toggle-checked", response_model=ShoppingItemOut)
async def toggle_item_checked(
    item_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    item = await _load_item_or_404(session, item_id, user)
    item.is_checked = not item.is_checked
    item.checked_by_id = user.id if item.is_checked else None
    item.checked_at = datetime.now(timezone.utc) if item.is_checked else None
    await session.commit()
    return item


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    item = await _load_item_or_404(session, item_id, user)
    await session.delete(item)
    await session.commit()
