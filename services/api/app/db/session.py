from app.core.config import settings
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
redis_client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
