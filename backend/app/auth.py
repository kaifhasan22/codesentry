from datetime import datetime, timedelta, timezone
import re

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("dummy-authentication-password")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return False
    try:
        return password_hash.verify(password, hashed)
    except (ValueError, TypeError, UnknownHashError):
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expires}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        if len(token) > 4096:
            raise ValueError()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"require_exp": True, "require_sub": True})
        subject = payload.get("sub")
        if not isinstance(subject, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", subject):
            raise ValueError()
        user_id = int(subject)
        if user_id > 2**31 - 1:
            raise ValueError()
    except (JWTError, ValueError, TypeError, OverflowError):
        raise credentials_error

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise credentials_error
    return user
