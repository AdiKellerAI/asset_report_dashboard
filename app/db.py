from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import Config


class Base(DeclarativeBase):
    pass


def make_engine(database_url=None):
    # Neon closes idle serverless connections after a few minutes; pre_ping
    # checks a pooled connection is alive before handing it out (transparent
    # reconnect instead of an OperationalError on the next request), and
    # pool_recycle proactively retires connections before Neon's own timeout.
    return create_engine(
        database_url or Config.DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=280,
    )


engine = make_engine()
SessionLocal = sessionmaker(bind=engine)
