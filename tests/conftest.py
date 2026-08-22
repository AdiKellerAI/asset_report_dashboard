import os

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.db import Base, make_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/asset_report_dashboard_test",
)


def _alembic_config():
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _migrated_db():
    command.upgrade(_alembic_config(), "head")
    yield
    command.downgrade(_alembic_config(), "base")


@pytest.fixture
def db_session():
    engine = make_engine(TEST_DATABASE_URL)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.rollback()
        table_names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        session.execute(text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"))
        session.commit()
        session.close()
        engine.dispose()
