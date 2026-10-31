import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


async def log_audit(
    session: AsyncSession, actor: User, action: str, target: User | None = None, **detail
) -> None:
    """Stage an audit entry on the caller's session. Deliberately doesn't commit: the entry
    must share the transaction of the action it records, so a failed action leaves no trace.
    """
    session.add(
        AuditLog(
            actor_id=actor.id,
            target_user_id=target.id if target else None,
            action=action,
            detail=json.dumps(detail) if detail else None,
        )
    )
    await session.flush()
