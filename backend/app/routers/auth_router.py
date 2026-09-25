import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends

from app.auth import hash_password, verify_password, create_access_token, create_refresh_token, store_refresh_token, verify_refresh_token_in_redis, revoke_refresh_token
from app.database import users_collection
from app.schemas import UserCreate, Token, RefreshRequest
from jose import JWTError, jwt
from app.config import settings

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
    await store_refresh_token(user_id, refresh_token)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_collection.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token({"sub": user["_id"]})
    refresh_token = create_refresh_token({"sub": user["_id"]})
    await store_refresh_token(user["_id"], refresh_token)
    return Token(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest):
    token = payload.refresh_token
    try:
        jwt_payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = jwt_payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    stored_user_id = await verify_refresh_token_in_redis(token)
    if not stored_user_id or stored_user_id != user_id:
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
    
    await revoke_refresh_token(token)
    
    new_access = create_access_token({"sub": user_id})
    new_refresh = create_refresh_token({"sub": user_id})
    await store_refresh_token(user_id, new_refresh)
    
    return Token(access_token=new_access, refresh_token=new_refresh)
