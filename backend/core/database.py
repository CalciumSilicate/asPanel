# backend/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from backend.core.constants import SQLALCHEMY_DATABASE_URL, DATABASE_CONNECT_ARGS

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=DATABASE_CONNECT_ARGS
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
