from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.job_titles.models import JobTitle

if TYPE_CHECKING:
    from app.job_titles.schemas import JobTitleCreate, JobTitleUpdate


async def get_job_title_by_name(
    db: AsyncSession,
    name: str,
) -> JobTitle | None:
    stmt = select(JobTitle).where(func.lower(JobTitle.name) == name.lower())

    return await db.scalar(stmt)


async def get_db_job_titles(
    db: AsyncSession,
    name: str | None = None,
) -> list[JobTitle]:
    stmt = select(JobTitle)

    if name is not None:
        stmt = stmt.where(JobTitle.name.ilike(f"%{name.strip()}%"))

    stmt = stmt.order_by(JobTitle.id)

    result = await db.scalars(stmt)

    return list(result.all())


async def get_db_job_title_by_id(
    db: AsyncSession,
    job_title_id: int,
) -> JobTitle:
    job_title = await db.get(JobTitle, job_title_id)

    if job_title is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job title not found",
        )

    return job_title


async def create_db_job_title(
    db: AsyncSession,
    job_title_data: JobTitleCreate,
) -> JobTitle:
    existing_job_title: JobTitle | None = await get_job_title_by_name(
        db=db,
        name=job_title_data.name,
    )

    if existing_job_title:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job title already exists.",
        )

    job_title = JobTitle(**job_title_data.model_dump())

    db.add(job_title)
    await db.commit()
    await db.refresh(job_title)

    return job_title


async def update_db_job_title(
    db: AsyncSession,
    job_title_id: int,
    job_title_data: JobTitleUpdate,
) -> JobTitle:

    job_title = await get_db_job_title_by_id(db=db, job_title_id=job_title_id)

    update_data = job_title_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        existing_job_title = await get_job_title_by_name(
            db=db,
            name=update_data["name"],
        )

        if existing_job_title is not None and existing_job_title.id != job_title.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A Job title with this name already exists.",
            )

    for field, value in update_data.items():
        setattr(job_title, field, value)

    await db.commit()
    await db.refresh(job_title)

    return job_title


async def delete_db_job_title(
    db: AsyncSession,
    job_title_id: int,
) -> None:
    job_title = await get_db_job_title_by_id(db=db, job_title_id=job_title_id)

    await db.delete(job_title)
    await db.commit()
