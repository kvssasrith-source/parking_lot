'A small script to view the database tables.'
from database import get_db

def inspect_database():
    conn = get_db()
    try:
        tables = [list(r.values())[0] for r in conn.execute("SHOW TABLES").fetchall()]
        print("=" * 75)
        print("                 SMART PARKING DATABASE INSPECTION (MySQL)          ")
        print("=" * 75)

        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM `{table}`").fetchone()[0]
            col_rows = conn.execute(f"DESCRIBE `{table}`").fetchall()
            col_names = [c["Field"] for c in col_rows]
            
            print(f"\n[TABLE] {table.upper()} -- Total Rows: {count}")
            print(f"Columns ({len(col_names)}): {', '.join(col_names)}")

            # Show sample rows if table has data
            if count > 0:
                rows = conn.execute(f"SELECT * FROM `{table}` LIMIT 5").fetchall()
                print("Data preview (up to 5 rows):")
                for i, r in enumerate(rows, 1):
                    row_dict = {k: v for k, v in r.items() if k != "password_hash"}
                    print(f"  {i}. {row_dict}")
            else:
                print("  (Empty table - 0 rows)")

        print("\n" + "=" * 75)
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_database()
