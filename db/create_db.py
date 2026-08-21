import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from state_graph.common.store import StateStore

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

StateStore(db_path)

print("Database created successfully!")