from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.utils.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def sync_db_sequences():
    """
    Ensures PostgreSQL primary key sequences match the MAX(id) of their respective tables.
    Prevents 'duplicate key value violates unique constraint' errors when tables were seeded
    or imported with explicit IDs.
    """
    from sqlalchemy import text
    tables = [
        "search_history", "places", "hidden_gems", "place_relations",
        "travel_tips", "ai_context", "user_feedback", "itineraries",
        "itinerary_versions", "local_contributions", "raw_scrapes"
    ]
    with engine.connect() as conn:
        for tbl in tables:
            try:
                seq_name = conn.execute(text(f"SELECT pg_get_serial_sequence('{tbl}', 'id')")).scalar()
                if seq_name:
                    max_id = conn.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {tbl}")).scalar()
                    next_val = max(max_id, 1)
                    is_called = True if max_id > 0 else False
                    conn.execute(text(f"SELECT setval('{seq_name}', {next_val}, {is_called})"))
                    conn.commit()
            except Exception:
                pass
