import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Callable

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-test-secret")

from backend.auth.password import hash_password  # noqa: E402
from backend.db.models import Org, User  # noqa: E402
from backend.db.session import get_engine, get_sessionmaker  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def temp_user(db: AsyncSession) -> AsyncIterator[User]:
    user = User(
        email=f"test-{uuid.uuid4().hex[:10]}@gatewise.test",
        name="Test User",
        password_hash=hash_password("Test@12345"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    user_id = user.id
    try:
        yield user
    finally:
        await db.rollback()
        await db.execute(delete(User).where(User.id == user_id))
        await db.commit()


def _make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with _make_client() as c:
        yield c


@pytest.fixture
async def make_client() -> AsyncIterator[Callable[[], AsyncClient]]:
    created: list[AsyncClient] = []

    def factory() -> AsyncClient:
        c = _make_client()
        created.append(c)
        return c

    yield factory
    for c in created:
        await c.aclose()


async def _sweep_test_rows() -> None:
    async with get_sessionmaker()() as session:
        await session.execute(delete(User).where(User.email.like("test-%@gatewise.test")))
        await session.execute(delete(Org).where(Org.slug.like("test-%")))
        await session.commit()
    await get_engine().dispose()


def _is_controller(config: pytest.Config) -> bool:
    return not hasattr(config, "workerinput")


def pytest_sessionstart(session: pytest.Session) -> None:
    if _is_controller(session.config):
        asyncio.run(_sweep_test_rows())


def pytest_sessionfinish(session: pytest.Session) -> None:
    if _is_controller(session.config):
        asyncio.run(_sweep_test_rows())


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engine() -> AsyncIterator[None]:
    yield
    await get_engine().dispose()
