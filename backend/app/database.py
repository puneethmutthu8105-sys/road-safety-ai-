from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
import os

# Use SQLite for local dev if PostgreSQL is not configured / unavailable
_db_url = settings.DATABASE_URL
if "postgresql" in _db_url and not os.environ.get("DATABASE_URL"):
    _db_url = "sqlite+aiosqlite:///./roadsafety.db"

_engine_kwargs = {"echo": settings.DEBUG}
if "postgresql" in _db_url:
    _engine_kwargs.update({"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20})
else:
    # SQLite does not support pool_size / max_overflow
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(_db_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup (dev). Use Alembic in production."""
    async with engine.begin() as conn:
        from app.models import user, accident, traffic, road_condition, emergency, ambulance  # noqa
        await conn.run_sync(Base.metadata.create_all)
