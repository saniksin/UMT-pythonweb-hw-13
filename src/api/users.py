from fastapi import APIRouter, Depends, File, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import config
from src.database.db import get_db
from src.database.models import User
from src.schemas import UserResponse
from src.services.auth import get_current_admin_user, get_current_user
from src.services.cache import invalidate_user
from src.services.upload_file import UploadFileService
from src.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])
limiter = Limiter(key_func=get_remote_address)


@router.get(
    "/me",
    response_model=UserResponse,
    description="Get the currently authenticated user. Rate limit: 10 req/min.",
)
@limiter.limit("10/minute")
async def me(request: Request, user: User = Depends(get_current_user)):
    """Return the currently authenticated user (served from the Redis cache).

    :param request: The incoming request (required by the rate limiter).
    :type request: Request
    :param user: The authenticated user (injected by ``get_current_user``).
    :type user: User
    :return: The authenticated user.
    :rtype: User
    """
    return user


@router.patch("/avatar", response_model=UserResponse)
async def update_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new avatar to Cloudinary and persist its URL.

    Only administrators may change the default avatar — regular users get a
    ``403 Forbidden``. The cached copy of the user is invalidated so the new
    avatar is visible immediately.

    :param file: The uploaded image.
    :type file: UploadFile
    :param user: The authenticated administrator (injected dependency).
    :type user: User
    :param db: The database session (injected dependency).
    :type db: AsyncSession
    :return: The updated user.
    :rtype: User
    """
    avatar_url = UploadFileService(
        config.CLD_NAME, config.CLD_API_KEY, config.CLD_API_SECRET
    ).upload_file(file, user.username)

    user_service = UserService(db)
    updated_user = await user_service.update_avatar_url(user.email, avatar_url)
    await invalidate_user(user.username)
    return updated_user
