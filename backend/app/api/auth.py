from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.services.auth_service import AuthService
from app.core.security import decode_token
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

security = HTTPBearer()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    """
    auth_service = AuthService(db)
    user = await auth_service.register(user_data)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    """
    token = credentials.credentials
    token_data = decode_token(token)
    user_id = token_data.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return user


# Guest user for development (no auth required)
_guest_user_cache = None


async def get_guest_user(db: AsyncSession = Depends(get_db)) -> User:
    """
    Return a guest user for development. Creates a default user if none exists.
    This bypasses authentication for easier testing.
    """
    global _guest_user_cache
    if _guest_user_cache is not None:
        return _guest_user_cache

    auth_service = AuthService(db)

    # Try to get or create default user
    user = await auth_service.get_user_by_id(1)
    if user is None:
        # Create default guest user
        from app.schemas.user import UserCreate
        try:
            user = await auth_service.register(UserCreate(
                email="guest@example.com",
                password="guest123456",
                name="Guest User"
            ))
        except Exception:
            # User might already exist due to race condition
            user = await auth_service.get_user_by_email("guest@example.com")

    _guest_user_cache = user
    return user


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password to get access token.
    """
    auth_service = AuthService(db)
    token = await auth_service.login(login_data)
    return token


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user.
    """
    return current_user
