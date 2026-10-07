"""
db/database.py
--------------
SQLite engine, session factory, and Base declarative.
The DB file lives at data/safevision.db (relative to the backend working dir).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = os.path.join("data", "safevision.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + threads
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    os.makedirs("data", exist_ok=True)
    from db import models  # noqa: F401 – registers models with Base
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
