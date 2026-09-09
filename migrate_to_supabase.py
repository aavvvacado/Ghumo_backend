import sys
import logging
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.utils.config import settings
from app.database.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("supabase_migration")

def migrate(target_db_url: str):
    local_db_url = settings.DATABASE_URL
    logger.info(f"Connecting to local database: {local_db_url}")
    local_engine = create_engine(local_db_url)
    LocalSession = sessionmaker(bind=local_engine)

    logger.info(f"Connecting to Supabase database...")
    supabase_engine = create_engine(target_db_url)
    SupabaseSession = sessionmaker(bind=supabase_engine)

    # 1. Create all schema tables on Supabase
    logger.info("Creating schema and tables on Supabase...")
    Base.metadata.create_all(bind=supabase_engine)
    logger.info("Schema creation complete.")

    local_session = LocalSession()
    supabase_session = SupabaseSession()

    try:
        # 2. Iterate through all defined model tables
        for table in Base.metadata.sorted_tables:
            table_name = table.name
            logger.info(f"Migrating table: {table_name}...")
            
            # Fetch all rows from local DB
            rows = local_session.execute(table.select()).fetchall()
            if not rows:
                logger.info(f"Table {table_name} is empty. Skipping.")
                continue

            # Convert rows to dicts
            row_dicts = [dict(row._mapping) for row in rows]
            logger.info(f"Found {len(row_dicts)} rows in local table '{table_name}'. Uploading to Supabase...")

            # Insert into Supabase
            supabase_session.execute(table.insert(), row_dicts)
            supabase_session.commit()
            logger.info(f"Successfully migrated {len(row_dicts)} rows for table '{table_name}'.")

        logger.info("MIGRATION COMPLETE! All local data is now stored in Supabase.")

    except Exception as e:
        supabase_session.rollback()
        logger.error(f"Migration failed: {e}")
        raise e
    finally:
        local_session.close()
        supabase_session.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        db_url = sys.argv[1]
    else:
        db_url = input("Enter your Supabase PostgreSQL Connection String (e.g. postgresql://postgres:password@db.dyssxffarwhctzpdjoul.supabase.co:5432/postgres): ").strip()
    
    migrate(db_url)
