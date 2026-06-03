from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db

router = APIRouter(tags=["utils"])


@router.get("/healthchecker")
async def healthchecker(db: AsyncSession = Depends(get_db)):
    """Check database connectivity by running a trivial ``SELECT 1``.

    :param db: The database session (injected dependency).
    :type db: AsyncSession
    :raises HTTPException: 500 if the database is misconfigured or unreachable.
    :return: A welcome message when the database responds.
    :rtype: dict
    """
    try:
        result = await db.execute(text("SELECT 1"))
        result = result.scalar_one_or_none()
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database is not configured correctly",
            )
        return {"message": "Welcome to Contacts API!"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error connecting to the database",
        )
