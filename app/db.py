from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import Config


class Base(DeclarativeBase):
    pass


def make_engine(database_url=None):
    return create_engine(database_url or Config.DATABASE_URL)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine)
