from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
if settings.database_url.startswith("sqlite:///") and ":memory:" not in settings.database_url:
    db_path = settings.database_url.removeprefix("sqlite:///")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Columns introduced after the first release. create_all only creates missing
# tables, so existing databases are upgraded here at startup. Defaults keep
# pre-existing accounts working: they were registered before email
# verification existed, so they count as verified.
_COLUMN_ADDITIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "users": (
        ("token_version", "INTEGER NOT NULL DEFAULT 0"),
        ("email_verified", "BOOLEAN NOT NULL DEFAULT 1"),
        ("two_factor_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
        ("totp_secret", "VARCHAR(64)"),
    ),
}


def run_light_migrations(target_engine=None) -> None:
    engine_to_use = target_engine or engine
    inspector = inspect(engine_to_use)
    with engine_to_use.begin() as connection:
        for table, columns in _COLUMN_ADDITIONS.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
