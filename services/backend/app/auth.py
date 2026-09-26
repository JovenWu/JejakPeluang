from datetime import datetime
from os import environ
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.db import BaseUserDatabase
from fastapi_users.password import PasswordHelper
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.auth import AccessToken, User
from app.security import AUTH_COOKIE_NAME

SECRET = environ.get('AUTH_SECRET', 'jp-dev-auth-secret-change-me')
password_helper = PasswordHelper(PasswordHash((Argon2Hasher(),)))


class UserDatabase(BaseUserDatabase[User, UUID]):
    """fastapi-users user adapter over the sync SQLAlchemy Session."""

    def __init__(self, session: Session):
        self.session = session

    async def get(self, id: UUID) -> User | None:
        return self.session.get(User, id)

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(func.lower(User.email) == func.lower(email))
        return self.session.execute(statement).unique().scalar_one_or_none()

    async def create(self, create_dict: dict[str, Any]) -> User:
        user = User(**create_dict)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def update(self, user: User, update_dict: dict[str, Any]) -> User:
        for key, value in update_dict.items():
            setattr(user, key, value)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        self.session.delete(user)
        self.session.commit()


class AccessTokenDatabase:
    """AccessTokenDatabase protocol impl over the sync SQLAlchemy Session."""

    def __init__(self, session: Session):
        self.session = session

    async def get_by_token(self, token: str,
        max_age: datetime | None = None) -> AccessToken | None:
        statement = select(AccessToken).where(AccessToken.token == token)
        if max_age is not None:
            statement = statement.where(AccessToken.created_at >= max_age)
        return self.session.execute(statement).scalar_one_or_none()

    async def create(self, create_dict: dict[str, Any]) -> AccessToken:
        access_token = AccessToken(**create_dict)
        self.session.add(access_token)
        self.session.commit()
        self.session.refresh(access_token)
        return access_token

    async def update(self, access_token: AccessToken,
        update_dict: dict[str, Any]) -> AccessToken:
        for key, value in update_dict.items():
            setattr(access_token, key, value)
        self.session.add(access_token)
        self.session.commit()
        self.session.refresh(access_token)
        return access_token

    async def delete(self, access_token: AccessToken) -> None:
        self.session.delete(access_token)
        self.session.commit()


def get_user_db(session: Session = Depends(get_session)):
    yield UserDatabase(session)


def get_access_token_db(session: Session = Depends(get_session)):
    yield AccessTokenDatabase(session)


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET


def get_user_manager(user_db: UserDatabase = Depends(get_user_db)):
    yield UserManager(user_db, password_helper)


cookie_transport = CookieTransport(cookie_name=AUTH_COOKIE_NAME,
    cookie_secure=environ.get('COOKIE_SECURE', 'false').lower() == 'true',
    cookie_samesite='lax', cookie_httponly=True)


def get_database_strategy(
    token_db: AccessTokenDatabase = Depends(get_access_token_db),
) -> DatabaseStrategy:
    return DatabaseStrategy(token_db)


auth_backend = AuthenticationBackend(name='cookie', transport=cookie_transport,
    get_strategy=get_database_strategy)

fastapi_users = FastAPIUsers[User, UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
current_user_token = fastapi_users.authenticator.current_user_token(active=True)


def require_moderator(user: User = Depends(current_active_user)) -> User:
    if user.role != 'moderator':
        raise HTTPException(status_code=403, detail='Not a moderator')
    return user
