from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_URL = "sqlite:///storages/asPanel.db"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

try:
    result = session.execute(text("SELECT id, name, data_source_ids FROM server_link_groups LIMIT 1"))
    for row in result:
        print(f"Row: {row}")
    print("Query successful.")
except Exception as e:
    print(f"Query failed: {e}")
finally:
    session.close()
