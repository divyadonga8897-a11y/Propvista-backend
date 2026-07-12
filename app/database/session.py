from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create async engine optimized for high-latency cloud database connections.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=15,
    max_overflow=25,
    pool_recycle=300,  # Recycle connections after 5 mins to cleanly handle idle firewall drops
    pool_pre_ping=False,  # Disable pre-ping to save 1s+ database roundtrip on every API call
    echo=False,
    connect_args={
        "timeout": 30,
        "command_timeout": 30
    }
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
