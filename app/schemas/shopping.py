import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShoppingItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    list_id: uuid.UUID
    name: str
    quantity: str | None
    is_checked: bool
    added_by_id: uuid.UUID
    checked_by_id: uuid.UUID | None
    checked_at: datetime | None
    created_at: datetime


class ShoppingListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner_user_id: uuid.UUID | None
    duty_id: uuid.UUID | None
    created_by_id: uuid.UUID
    created_at: datetime
    items: list[ShoppingItemOut]


class ShoppingListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_private: bool = False
    duty_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_duty_only_if_shared(self) -> "ShoppingListCreate":
        if self.is_private and self.duty_id is not None:
            raise ValueError("a private list can't be linked to a duty")
        return self


class ShoppingItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    quantity: str | None = Field(default=None, max_length=50)
