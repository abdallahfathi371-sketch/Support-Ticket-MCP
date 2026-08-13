from mcp_server.database import get_connection

c = get_connection()

print("DATABASE:")
print(c.execute("PRAGMA database_list").fetchall())

print("\nTABLES:")
print(c.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall())

c.close()