"""Admin-only member management. Registration is deliberately not public (closed household
app) — an admin adds each member's account here, reusing UserManager.create() rather than
hand-rolling password hashing/validation.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi_users.exceptions import UserAlreadyExists

from app.auth.backend import current_superuser
from app.auth.users import UserManager, get_user_manager
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_superuser)])


@router.post("/users", response_model=UserRead, status_code=201)
async def create_member(
    data: UserCreate,
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        return await user_manager.create(data, safe=False)
    except UserAlreadyExists as exc:
        raise HTTPException(status_code=400, detail="USER_ALREADY_EXISTS") from exc
