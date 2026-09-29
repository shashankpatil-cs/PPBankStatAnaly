import uuid

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt

from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    get_current_user,
)
from app.config import settings
from app.database import users_collection, transactions_collection, statements_collection
from app.services.s3_service import delete_user_folder
from app.schemas import UserCreate, Token, RefreshRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate):
    existing = await users_collection.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    await users_collection.insert_one(
        {
            "_id": user_id,
            "email": payload.email,
            "name": payload.name,
            "hashed_password": hash_password(payload.password),
        }
    )
    access_token = create_access_token({"sub": user_id})
    refresh_token = create_refresh_token({"sub": user_id})
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_collection.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token({"sub": user["_id"]})
    refresh_token = create_refresh_token({"sub": user["_id"]})
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest):
    token = payload.refresh_token
    try:
        jwt_payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = jwt_payload.get("sub")
        token_type = jwt_payload.get("type")
        if not user_id or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await users_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_access = create_access_token({"sub": user_id})
    new_refresh = create_refresh_token({"sub": user_id})
    return Token(access_token=new_access, refresh_token=new_refresh)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(current_user: dict = Depends(get_current_user)):
    user_id = current_user["_id"]
    
    # Delete all associated S3 files in a background thread so we don't block the async loop
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, delete_user_folder, user_id)
    
    await transactions_collection.delete_many({"user_id": user_id})
    await statements_collection.delete_many({"user_id": user_id})
    await users_collection.delete_one({"_id": user_id})
