import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent

db_path = BASE_DIR / "support.db"

schema_path = BASE_DIR / "schema.sql"
seed_path = BASE_DIR / "seed.sql"

conn = sqlite3.connect(db_path)

cursor = conn.cursor()

with open(schema_path, "r", encoding="utf-8") as f:
    cursor.executescript(f.read())

with open(seed_path, "r", encoding="utf-8") as f:
    cursor.executescript(f.read())

conn.commit()
conn.close()

print("Database created successfully!")