import os
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.sql import func
import uuid


class Base(DeclarativeBase):
    pass


class URL(Base):
    __tablename__ = "urls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_url = Column(Text, nullable=False)
    short_code = Column(String(10), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(255), nullable=True)
    metadata = Column(JSONB, default={})


class ClickEvent(Base):
    __tablename__ = "click_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id = Column(UUID(as_uuid=True), nullable=False)
    short_code = Column(String(10), nullable=False)
    clicked_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    referer = Column(Text, nullable=True)
    country = Column(String(2), nullable=True)
    city = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)
    browser = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)
    metadata = Column(JSONB, default={})


class URLAnalytics(Base):
    __tablename__ = "url_analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url_id = Column(UUID(as_uuid=True), nullable=False)
    short_code = Column(String(10), nullable=False)
    date = Column(Date, nullable=False)
    total_clicks = Column(Integer, default=0)
    unique_clicks = Column(Integer, default=0)
    top_countries = Column(JSONB, default=[])
    top_devices = Column(JSONB, default=[])
    top_browsers = Column(JSONB, default=[])
    top_referers = Column(JSONB, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_async_engine(
            database_url,
            echo=os.getenv("LOG_LEVEL") == "DEBUG",
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def health_check(self) -> bool:
        try:
            async with self.get_session() as session:
                await session.execute("SELECT 1")
                return True
        except Exception:
            return False

    async def close(self):
        await self.engine.dispose()


_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        _db_manager = DatabaseManager(database_url)
    return _db_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    db_manager = get_database_manager()
    async with db_manager.get_session() as session:
        yield session
