from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.database import get_db

if TYPE_CHECKING:
    from app.job_titles import models

from app.job_titles.schemas import JobTitleCreate, JobTitleResponse, JobTitleUpdate
from app.job_titles.services import (
    create_db_job_title,
    delete_db_job_title,
    get_db_job_title_by_id,
    get_db_job_titles,
    update_db_job_title,
)

openapi_tags = [
    {"name": "Job Titles", "description": "Endpoints to manage Job titles."}
]

router = APIRouter(
    prefix="/api/v1/job_titles",
    tags=["Job Titles"],
)


@router.get(
    "/",
    response_model=list[JobTitleResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all Job titles or only name filtered ones",
)
async def get_job_titles(
    db: Annotated[AsyncSession, Depends(get_db)],
    name: str | None = None,
) -> list[models.JobTitle]:
    return await get_db_job_titles(db, name)


@router.get(
    "/{job_title_id}",
    response_model=JobTitleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a Job title by ID",
)
async def get_job_title(
    job_title_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.JobTitle:
    return await get_db_job_title_by_id(db, job_title_id)


@router.post(
    "/",
    response_model=JobTitleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_title(
    job_title_data: JobTitleCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> models.JobTitle:
    return await create_db_job_title(db, job_title_data)


@router.patch(
    "/{job_title_id}",
    response_model=JobTitleResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Job title partialy through PATCH",
)
async def update_job_title(
    job_title_id: int,
    job_title_data: JobTitleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> models.JobTitle:
    return await update_db_job_title(db, job_title_id, job_title_data)


@router.delete(
    "/{job_title_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_job_title(
    job_title_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    return await delete_db_job_title(db, job_title_id)
