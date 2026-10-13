from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401
from app.auth import routers as auth_routers
from app.core.config import settings
from app.departments import routers as department_routers
from app.dependencies.database import engine
from app.employees import routers as employees_routers
from app.health.router import router as health_router
from app.job_titles import routers as job_title_routers
from app.roles import routers as role_routers
from app.users import routers as user_routers


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title="HR Management App",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    description="Application to manage human resources for a company from 30 to 80 employees",
    version="1.0.0",
    contact={"name": "E.Tomcini", "email": "tomcinieolian@gmail.com"},
    openapi_tags=[
        *user_routers.openapi_tags,
        *role_routers.openapi_tags,
        *job_title_routers.openapi_tags,
        *department_routers.openapi_tags,
        *employees_routers.openapi_tags,
        *auth_routers.openapi_tags,
    ],
)
app.include_router(user_routers.router)
app.include_router(role_routers.router)
app.include_router(job_title_routers.router)
app.include_router(department_routers.router)
app.include_router(employees_routers.router)
app.include_router(auth_routers.router)
app.include_router(health_router)
