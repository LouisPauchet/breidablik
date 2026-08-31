import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.backend import current_active_user
from app.db import get_session
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(current_active_user)])


def _build_task_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        is_done=task.is_done,
        done_by_id=task.done_by_id,
        done_at=task.done_at,
        created_by_id=task.created_by_id,
        created_at=task.created_at,
        assignee_user_ids=[a.user_id for a in task.assignees],
    )


async def _load_task_or_404(session: AsyncSession, task_id: uuid.UUID) -> Task:
    result = await session.execute(
        select(Task).options(selectinload(Task.assignees)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="TASK_NOT_FOUND")
    return task


@router.get("", response_model=list[TaskOut])
async def list_tasks(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Task)
        .options(selectinload(Task.assignees))
        .order_by(Task.is_done.asc(), Task.due_date.asc().nullslast())
    )
    tasks = result.scalars().unique().all()
    return [_build_task_out(t) for t in tasks]


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    data: TaskCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    task = Task(
        title=data.title,
        description=data.description,
        due_date=data.due_date,
        created_by_id=user.id,
    )
    session.add(task)
    await session.flush()

    for user_id in data.assignee_user_ids:
        session.add(TaskAssignee(task_id=task.id, user_id=user_id))
    await session.commit()

    return _build_task_out(await _load_task_or_404(session, task.id))


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID, data: TaskUpdate, session: AsyncSession = Depends(get_session)
):
    task = await _load_task_or_404(session, task_id)

    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.due_date is not None:
        task.due_date = data.due_date

    if data.assignee_user_ids is not None:
        await session.execute(delete(TaskAssignee).where(TaskAssignee.task_id == task_id))
        await session.flush()
        for user_id in data.assignee_user_ids:
            session.add(TaskAssignee(task_id=task_id, user_id=user_id))
        await session.commit()
        # A raw bulk delete()/add() doesn't refresh the already-loaded `assignees`
        # collection on `task` — re-querying in the same session would just hand back the
        # same cached (pre-update) object from the identity map, not the new rows.
        await session.refresh(task, attribute_names=["assignees"])
    else:
        await session.commit()

    return _build_task_out(task)


@router.post("/{task_id}/toggle-done", response_model=TaskOut)
async def toggle_task_done(
    task_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    task = await _load_task_or_404(session, task_id)
    task.is_done = not task.is_done
    task.done_by_id = user.id if task.is_done else None
    task.done_at = datetime.now(timezone.utc) if task.is_done else None
    await session.commit()
    return _build_task_out(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    task = await _load_task_or_404(session, task_id)
    await session.delete(task)
    await session.commit()
