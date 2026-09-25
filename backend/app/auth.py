"""
Minimal JWT-based auth so every transaction/statement is scoped to a user
(the task calls for "secure user-specific data access").
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
import uuid

from app.config import settings
from app.database import users_collection
from app.redis_client import redis_client

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.update({"jti": str(uuid.uuid4())})
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_refresh_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

async def store_refresh_token(user_id: str, token: str):
    await redis_client.setex(
        f"refresh_token:{token}",
        settings.jwt_refresh_expire_minutes * 60,
        user_id
    )

async def verify_refresh_token_in_redis(token: str) -> Optional[str]:
    return await redis_client.get(f"refresh_token:{token}")

async def revoke_refresh_token(token: str):
    await redis_client.delete(f"refresh_token:{token}")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await users_collection.find_one({"_id": user_id})
    if user is None:
        raise credentials_exception
    return user
