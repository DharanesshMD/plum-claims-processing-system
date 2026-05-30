"""Database setup — SQLAlchemy async with SQLite."""


import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import get_settings


class Base(DeclarativeBase):
    pass


class ClaimRecord(Base):
    __tablename__ = "claims"

    claim_id = Column(String, primary_key=True)
    member_id = Column(String, nullable=False, index=True)
    claim_category = Column(String, nullable=False)
    claimed_amount = Column(Float, nullable=False)
    decision = Column(String, nullable=True)
    approved_amount = Column(Float, nullable=True)
    confidence_score = Column(Float, default=0.0)
    explanation = Column(Text, default="")
    full_response_json = Column(Text, nullable=False)  # Full ClaimDecision as JSON
    created_at = Column(DateTime, default=datetime.utcnow)


# Sync engine for simplicity (SQLite doesn't benefit much from async)
_engine = None
_SessionLocal = None


def get_engine(database_url: str = None):
    global _engine
    if _engine is None:
        import sqlite3
        from pathlib import Path
        from sqlalchemy import event

        if database_url is None:
            database_url = get_settings().database_url

        # Convert async SQLite URL to sync URL for SQLAlchemy
        # Strip +aiosqlite prefix and any query params for the engine URL
        sync_url = database_url
        if sync_url.startswith("sqlite+aiosqlite:///"):
            sync_url = sync_url.replace("sqlite+aiosqlite:///", "sqlite:///")

        # Strip query params from the SQLAlchemy URL (e.g. ?nolock=1)
        # We'll pass these directly to sqlite3 via URI mode
        base_url = sync_url.split("?")[0]

        # Extract the file path from the URL (handles both relative and absolute paths)
        # sqlite:////absolute/path -> /absolute/path
        # sqlite:///./relative -> ./relative
        if base_url.startswith("sqlite:////"):
            db_path = base_url[len("sqlite:///"):]   # keep leading /
        elif base_url.startswith("sqlite:///"):
            db_path = base_url[len("sqlite:///"):]   # relative path
        else:
            db_path = base_url[len("sqlite:"):]

        # Ensure the parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Build the SQLite URI with nolock=1 to bypass GCS FUSE locking issues
        sqlite_uri = f"file:{db_path}?nolock=1"

        def _creator():
            return sqlite3.connect(sqlite_uri, uri=True, check_same_thread=False, timeout=30)

        _engine = create_engine("sqlite://", creator=_creator, echo=False)

        # Set GCS-FUSE-safe pragmas on every new connection:
        # - journal_mode=MEMORY: no journal file written to disk, no lock files
        # - synchronous=OFF: no fsync() calls that block on network filesystems
        # This makes SQLite safe on GCS FUSE which doesn't support fcntl() locks
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=MEMORY")
            cursor.execute("PRAGMA synchronous=OFF")
            cursor.close()

        Base.metadata.create_all(_engine)
    return _engine


def get_session(database_url: str = None) -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(database_url)
        _SessionLocal = sessionmaker(bind=engine)
    return _SessionLocal()


def save_claim(decision_dict: dict, database_url: str = None):
    """Save a claim decision to the database."""
    session = get_session(database_url)
    try:
        record = ClaimRecord(
            claim_id=decision_dict["claim_id"],
            member_id=decision_dict.get("_member_id", ""),
            claim_category=decision_dict.get("_claim_category", ""),
            claimed_amount=decision_dict.get("_claimed_amount", 0),
            decision=decision_dict.get("decision"),
            approved_amount=decision_dict.get("approved_amount"),
            confidence_score=decision_dict.get("confidence_score", 0),
            explanation=decision_dict.get("explanation", ""),
            full_response_json=json.dumps(decision_dict, default=str),
        )
        session.merge(record)  # Use merge to handle re-runs
        session.commit()
    finally:
        session.close()


def get_claim(claim_id: str, database_url: str = None) -> dict | None:
    """Retrieve a claim decision from the database."""
    session = get_session(database_url)
    try:
        record = session.query(ClaimRecord).filter_by(claim_id=claim_id).first()
        if record:
            return json.loads(record.full_response_json)
        return None
    finally:
        session.close()


def list_claims(database_url: str = None) -> list[dict]:
    """List all claims."""
    session = get_session(database_url)
    try:
        records = session.query(ClaimRecord).order_by(ClaimRecord.created_at.desc()).all()
        return [
            {
                "claim_id": r.claim_id,
                "member_id": r.member_id,
                "claim_category": r.claim_category,
                "claimed_amount": r.claimed_amount,
                "decision": r.decision,
                "approved_amount": r.approved_amount,
                "confidence_score": r.confidence_score,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
    finally:
        session.close()
