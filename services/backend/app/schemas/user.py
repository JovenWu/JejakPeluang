from uuid import UUID
from fastapi_users.schemas import BaseUser


class UserRead(BaseUser[UUID]):
    role: str
