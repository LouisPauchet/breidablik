import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ShoppingList(Base):
    """owner_user_id NULL = shared/collective list; set = private to that user. duty_id
    (only meaningful when shared) links to the Duty whose current on-duty person gets
    notified when an item is added. The check constraint keeps private lists from ever
    carrying a duty — private lists never notify anyone.
    """

    __tablename__ = "shopping_list"
    __table_args__ = (
        CheckConstraint(
            "owner_user_id IS NULL OR duty_id IS NULL", name="ck_shopping_list_private_no_duty"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), default=None, index=True
    )
    duty_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("duty.id", ondelete="SET NULL"), default=None
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    items: Mapped[list["ShoppingItem"]] = relationship(
        back_populates="list", cascade="all, delete-orphan"
    )


class ShoppingItem(Base):
    __tablename__ = "shopping_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_list.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    quantity: Mapped[str | None] = mapped_column(String(50), default=None)

    is_checked: Mapped[bool] = mapped_column(default=False)
    added_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    checked_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), default=None)
    checked_at: Mapped[datetime | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    list: Mapped["ShoppingList"] = relationship(back_populates="items")
