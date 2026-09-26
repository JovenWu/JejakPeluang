from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.router.common import ErrorCode

from app.auth import (UserManager, auth_backend, current_active_user,
    current_user_token, get_database_strategy, get_user_manager)
from app.models.auth import User
from app.schemas.user import UserRead
from app.security import (RateLimiter, get_rate_limiter, login_attempt_key)

auth_router = APIRouter(tags=['auth'])
users_router = APIRouter(tags=['users'])


@auth_router.post('/login', status_code=204, response_class=Response,
    name='auth:cookie.login')
async def login(request: Request,
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
    strategy: DatabaseStrategy = Depends(get_database_strategy),
    limiter: RateLimiter = Depends(get_rate_limiter)):
    key = login_attempt_key(request, credentials.username)
    if not limiter.check(key, limit=5, window_seconds=60):
        raise HTTPException(status_code=429, detail='Too many login attempts')
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400,
            detail=ErrorCode.LOGIN_BAD_CREDENTIALS)
    response = await auth_backend.login(strategy, user)
    await user_manager.on_after_login(user, request, response)
    return response


@auth_router.post('/logout', status_code=204, response_class=Response,
    name='auth:cookie.logout')
async def logout(
    user_token: tuple[User, str] = Depends(current_user_token),
    strategy: DatabaseStrategy = Depends(get_database_strategy)):
    user, token = user_token
    return await auth_backend.logout(strategy, user, token)


@users_router.get('/me', response_model=UserRead, name='users:current_user')
async def me(user: User = Depends(current_active_user)):
    return UserRead.model_validate(user)
