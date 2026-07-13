import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Detect if running in a serverless environment (Vercel)
IS_SERVERLESS = os.environ.get("VERCEL") == "1" or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None

# Use NullPool in serverless to avoid persistent connections that get killed between invocations.
# Use standard pool locally for performance.
_pool_class = NullPool if IS_SERVERLESS else None

_engine_kwargs = dict(
    echo=False,
    pool_pre_ping=True,
    connect_args={
        "timeout": 5,
        "command_timeout": 5,
        "ssl": "require",  # Supabase requires SSL
        "statement_cache_size": 0,  # Disable prepared statement caching for PgBouncer compatibility
    }
)

if IS_SERVERLESS:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 300,
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs
)

# AsyncSessionLocal class
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to retrieve database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
