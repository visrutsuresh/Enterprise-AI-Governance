import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy import Column, String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()
SECRET = os.getenv("AUTH_SECRET", "")
if not SECRET:
    raise RuntimeError("AUTH_SECRET missing from .env")

# reuse the app's DATABASE_URL but through the async driver fastapi-users needs
ASYNC_DB_URL = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://")


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    # reviewer (admin-created) | admin (seeded). No open signup.
    role = Column(String, nullable=False, default="reviewer")


engine = create_async_engine(ASYNC_DB_URL)
session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_user_table():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_user_db():
    async with session_maker() as session:
        yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


cookie_transport = CookieTransport(cookie_name="governance", cookie_max_age=60 * 60 * 24 * 7, cookie_secure=False)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=60 * 60 * 24 * 7)


auth_backend = AuthenticationBackend(name="cookie", transport=cookie_transport, get_strategy=get_jwt_strategy)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])
current_user = fastapi_users.current_user(active=True)


def require_reviewer(user: User = Depends(current_user)) -> User:
    if user.role not in ("reviewer", "admin"):
        raise HTTPException(status_code=403, detail="reviewers only")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin only")
    return user
