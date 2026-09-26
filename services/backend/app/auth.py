from datetime import datetime
from os import environ
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, exceptions
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
ACCESS_TOKEN_TTL_SECONDS = int(
    environ.get('ACCESS_TOKEN_TTL_SECONDS', str(8 * 3600)))
password_helper = PasswordHelper(PasswordHash((Argon2Hasher(),)))


class UserDatabase(BaseUserDatabase[User, UUID]):
    """fastapi-users user adapter over the sync SQLAlchemy Session.

    The stock fastapi-users-db-sqlalchemy adapter needs AsyncSession; we keep
    the app's sync Session and run every blocking call in the threadpool so
    the event loop is never stalled.
    """

    def __init__(self, session: Session):
        self.session = session

    def _fetch_user(self, statement) -> User | None:
        return self.session.execute(statement).unique().scalar_one_or_none()

    def _create(self, create_dict: dict[str, Any]) -> User:
        user = User(**create_dict)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def _update(self, user: User, update_dict: dict[str, Any]) -> User:
        for key, value in update_dict.items():
            setattr(user, key, value)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def _delete(self, user: User) -> None:
        self.session.delete(user)
        self.session.commit()

    async def get(self, id: UUID) -> User | None:
        return await run_in_threadpool(self.session.get, User, id)

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(func.lower(User.email) == func.lower(email))
        return await run_in_threadpool(self._fetch_user, statement)

    async def create(self, create_dict: dict[str, Any]) -> User:
        return await run_in_threadpool(self._create, create_dict)

    async def update(self, user: User, update_dict: dict[str, Any]) -> User:
        return await run_in_threadpool(self._update, user, update_dict)

    async def delete(self, user: User) -> None:
        await run_in_threadpool(self._delete, user)


class AccessTokenDatabase:
    """AccessTokenDatabase protocol impl over the sync SQLAlchemy Session.

    Same offload pattern as UserDatabase: blocking session work runs in the
    threadpool, only the request-scoped Session object is shared per request.
    """

    def __init__(self, session: Session):
        self.session = session

    def _get_by_token(self, token: str,
        max_age: datetime | None = None) -> AccessToken | None:
        statement = select(AccessToken).where(AccessToken.token == token)
        if max_age is not None:
            statement = statement.where(AccessToken.created_at >= max_age)
        return self.session.execute(statement).scalar_one_or_none()

    def _create(self, create_dict: dict[str, Any]) -> AccessToken:
        access_token = AccessToken(**create_dict)
        self.session.add(access_token)
        self.session.commit()
        self.session.refresh(access_token)
        return access_token

    def _update(self, access_token: AccessToken,
        update_dict: dict[str, Any]) -> AccessToken:
        for key, value in update_dict.items():
            setattr(access_token, key, value)
        self.session.add(access_token)
        self.session.commit()
        self.session.refresh(access_token)
        return access_token

    def _delete(self, access_token: AccessToken) -> None:
        self.session.delete(access_token)
        self.session.commit()

    async def get_by_token(self, token: str,
        max_age: datetime | None = None) -> AccessToken | None:
        return await run_in_threadpool(self._get_by_token, token, max_age)

    async def create(self, create_dict: dict[str, Any]) -> AccessToken:
        return await run_in_threadpool(self._create, create_dict)

    async def update(self, access_token: AccessToken,
        update_dict: dict[str, Any]) -> AccessToken:
        return await run_in_threadpool(self._update, access_token, update_dict)

    async def delete(self, access_token: AccessToken) -> None:
        await run_in_threadpool(self._delete, access_token)


def get_user_db(session: Session = Depends(get_session)):
    yield UserDatabase(session)


def get_access_token_db(session: Session = Depends(get_session)):
    yield AccessTokenDatabase(session)


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    """Argon2id hashing is CPU-bound; authenticate() offloads it to threads."""

    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def authenticate(self, credentials: OAuth2PasswordRequestForm) -> User | None:
        try:
            user = await self.get_by_email(credentials.username)
        except exceptions.UserNotExists:
            # Hash anyway to blunt timing attacks, off the event loop.
            await run_in_threadpool(self.password_helper.hash,
                credentials.password)
            return None
        verified, updated_hash = await run_in_threadpool(
            self.password_helper.verify_and_update,
            credentials.password, user.hashed_password)
        if not verified:
            return None
        if updated_hash is not None:
            await self.user_db.update(user, {'hashed_password': updated_hash})
        return user


def get_user_manager(user_db: UserDatabase = Depends(get_user_db)):
    yield UserManager(user_db, password_helper)


cookie_transport = CookieTransport(cookie_name=AUTH_COOKIE_NAME,
    cookie_secure=environ.get('COOKIE_SECURE', 'false').lower() == 'true',
    cookie_samesite='lax', cookie_httponly=True)


def get_database_strategy(
    token_db: AccessTokenDatabase = Depends(get_access_token_db),
) -> DatabaseStrategy:
    return DatabaseStrategy(token_db,
        lifetime_seconds=ACCESS_TOKEN_TTL_SECONDS)


auth_backend = AuthenticationBackend(name='cookie', transport=cookie_transport,
    get_strategy=get_database_strategy)

fastapi_users = FastAPIUsers[User, UUID](get_user_manager, [auth_backend])
current_active_user = fastapi_users.current_user(active=True)
current_user_token = fastapi_users.authenticator.current_user_token(active=True)


def require_moderator(user: User = Depends(current_active_user)) -> User:
    if user.role != 'moderator':
        raise HTTPException(status_code=403, detail='Not a moderator')
    return user
