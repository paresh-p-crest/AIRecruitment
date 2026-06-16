import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "recruitment.db"
conn = sqlite3.connect(db)
print("DDL:", conn.execute("SELECT sql FROM sqlite_master WHERE name='match_results'").fetchone())
print("indexes:")
for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE tbl_name='match_results'"):
    print(" ", row)
