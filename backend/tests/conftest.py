"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Set env vars before Settings() is instantiated anywhere.
os.environ.setdefault("KIS_APP_KEY", "test-app-key")
os.environ.setdefault("KIS_APP_SECRET", "test-app-secret")
os.environ.setdefault("KIS_ACCOUNT_NO", "12345678")
os.environ.setdefault("KIS_ACCOUNT_PRODUCT_CODE", "01")
os.environ.setdefault("KIS_ACCOUNT_MODE", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
# Pop any ambient CORS_ORIGINS so Settings-default tests are deterministic.
os.environ.pop("CORS_ORIGINS", None)

from app.api.deps import get_db_session, get_kis_client  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.main import create_app  # noqa: E402


class FakeKISClient:
    """Programmable KIS client stub for tests."""

    def __init__(self) -> None:
        self.inquire_stock_price = AsyncMock()
        self.inquire_balance = AsyncMock()
        self.inquire_account_summary = AsyncMock()
        self.inquire_index = AsyncMock()
        self.search_info = AsyncMock()
        self.token_manager = _FakeTokenManager()

    async def close(self) -> None:  # pragma: no cover - not exercised
        return None


class _FakeTokenManager:
    def __init__(self) -> None:
        self.state: Any = None
        self.refresh = AsyncMock(side_effect=self._refresh)
        self.revoke = AsyncMock(side_effect=self._revoke)

    async def _refresh(self) -> None:
        from datetime import UTC, datetime, timedelta

        from app.kis.models import TokenState

        self.state = TokenState(
            access_token="test-token",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

    async def _revoke(self) -> None:
        self.state = None


@pytest.fixture
def fake_kis_client() -> FakeKISClient:
    return FakeKISClient()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def app_client(
    fake_kis_client: FakeKISClient,
    db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    def _override_kis():
        return fake_kis_client

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_kis_client] = _override_kis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _patch_init_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Skip init_db side-effects during app creation in tests."""
    from app import main as main_module

    async def _noop() -> None:
        return None

    monkeypatch.setattr(main_module, "init_db", _noop)
    yield
