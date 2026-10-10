import asyncio

import app.models  # noqa: F401
from app.dependencies.database import AsyncSessionLocal, engine

from .permissions import seed_rbac


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db, db.begin():
            await seed_rbac(db)

        print("RBAC synchronization completed successfully.")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
