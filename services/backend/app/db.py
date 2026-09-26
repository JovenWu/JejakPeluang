from functools import lru_cache
from os import environ
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


@lru_cache
def engine():
    return create_engine(environ['DATABASE_URL'], pool_pre_ping=True)


def get_session():
    with Session(engine()) as session:
        yield session
