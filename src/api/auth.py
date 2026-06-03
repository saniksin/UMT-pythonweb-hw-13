from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db
from src.schemas import (
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RequestEmail,
    Token,
    UserCreate,
    UserResponse,
)
from src.services.auth import (
    Hash,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_email_from_reset_token,
    get_email_from_token,
)
from src.services.cache import invalidate_user
from src.services.email import send_reset_password_email, send_verification_email
from src.services.users import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user account, send a verification email and return the
    public projection of the new user with HTTP 201."""
    user_service = UserService(db)

    if await user_service.get_user_by_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    if await user_service.get_user_by_username(body.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username already exists",
        )

    body.password = Hash().get_password_hash(body.password)
    new_user = await user_service.create_user(body)

    background_tasks.add_task(
        send_verification_email,
        new_user.email,
        new_user.username,
        str(request.base_url),
    )
    return new_user


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Verify credentials and issue a JWT access token."""
    user_service = UserService(db)
    user = await user_service.get_user_by_username(form_data.username)

    if user is None or not Hash().verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email address is not confirmed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = await create_access_token(data={"sub": user.username})
    refresh_token = await create_refresh_token(data={"sub": user.username})
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh_token", response_model=Token, status_code=status.HTTP_200_OK)
async def refresh_token(
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a fresh access/refresh token pair."""
    username = await decode_refresh_token(body.refresh_token)

    user_service = UserService(db)
    user = await user_service.get_user_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    access_token = await create_access_token(data={"sub": user.username})
    new_refresh_token = await create_refresh_token(data={"sub": user.username})
    return Token(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/confirmed_email/{token}")
async def confirmed_email(token: str, db: AsyncSession = Depends(get_db)):
    """Mark a user as confirmed when they follow the verification link."""
    email = await get_email_from_token(token)
    user_service = UserService(db)
    user = await user_service.get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification error",
        )
    if user.confirmed:
        return {"message": "Email already confirmed"}
    await user_service.confirmed_email(email)
    return {"message": "Email confirmed successfully"}


@router.post("/request_email", status_code=status.HTTP_200_OK)
async def request_email(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Re-send the verification email for the supplied address."""
    user_service = UserService(db)
    user = await user_service.get_user_by_email(body.email)

    if user and user.confirmed:
        return {"message": "Email already confirmed"}
    if user:
        background_tasks.add_task(
            send_verification_email,
            user.email,
            user.username,
            str(request.base_url),
        )
    return {"message": "Check your inbox to confirm your email"}


@router.post("/reset_password", status_code=status.HTTP_200_OK)
async def reset_password_request(
    body: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Start the password-reset flow by emailing a reset link/token.

    The response is intentionally identical whether or not the email exists,
    so the endpoint cannot be used to enumerate registered addresses.
    """
    user_service = UserService(db)
    user = await user_service.get_user_by_email(body.email)

    if user:
        background_tasks.add_task(
            send_reset_password_email,
            user.email,
            user.username,
            str(request.base_url),
        )
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset_password/confirm", status_code=status.HTTP_200_OK)
async def reset_password_confirm(
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Finish the password-reset flow: verify the token and set a new password."""
    email = await get_email_from_reset_token(body.token)

    user_service = UserService(db)
    user = await user_service.get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset error",
        )

    hashed_password = Hash().get_password_hash(body.new_password)
    await user_service.update_password(email, hashed_password)
    await invalidate_user(user.username)
    return {"message": "Password has been reset successfully"}
