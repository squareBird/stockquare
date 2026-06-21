"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class Watchlist(Base):
    """User watchlist entries."""

    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(6), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )


class Strategy(Base):
    """Auto-trading strategy definition.

    The composite `config` (rule indicators / ai / sizing) is stored as a
    single JSON column so the schema stays stable as new indicator kinds are
    added (see backend STRATEGY.md §7).
    """

    __tablename__ = "strategy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    strategy_type: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    side_policy: Mapped[str] = mapped_column(String(16), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )


class StrategySignal(Base):
    """A single evaluation outcome for a strategy (buy/sell/hold)."""

    __tablename__ = "strategy_signal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("strategy.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
