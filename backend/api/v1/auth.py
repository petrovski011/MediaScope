from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.users import User
from api.deps import get_current_user
from config import settings
from passlib.context import CryptContext
from jose import jwt

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash(password: str) -> str:
    return pwd_context.hash(password)


def _verify(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    token: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not _verify(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    return TokenResponse(
        access_token=_token(user),
        expires_in=settings.JWT_EXPIRE_HOURS * 3600,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        },
    )


@router.post("/refresh")
async def refresh(req: RefreshRequest):
    from jose import JWTError
    try:
        payload = jwt.decode(req.token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")

    new_payload = {
        "sub": payload["sub"],
        "role": payload["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
    }
    token = jwt.encode(new_payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return {"access_token": token, "expires_in": settings.JWT_EXPIRE_HOURS * 3600}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "last_login": current_user.last_login,
    }


@router.post("/register-admin")
async def register_first_admin(
    email: str,
    name: str,
    password: str,
    db: AsyncSession = Depends(get_db),
):
    """One-time setup — only works when no users exist."""
    count = (await db.execute(select(User))).scalars().first()
    if count is not None:
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    user = User(
        email=email,
        name=name,
        hashed_password=_hash(password),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role}
