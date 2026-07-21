from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def ensure_schema_compatibility() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "published_records" in table_names:
        columns = {column["name"] for column in inspector.get_columns("published_records")}
        if "content_locks" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE published_records ADD COLUMN content_locks JSON DEFAULT '{}'"))
        if "content_candidates" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE published_records ADD COLUMN content_candidates JSON DEFAULT '{}'")
                )

    if "destinations" in table_names:
        columns = {column["name"] for column in inspector.get_columns("destinations")}
        if "review_status" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE destinations ADD COLUMN review_status VARCHAR NOT NULL DEFAULT 'approved'"
                    )
                )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
