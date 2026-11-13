"""
Interactive SQL Query Runner for support.db

Run this in your terminal:
    python explore_db.py

Then type any SQL query like:
    SELECT * FROM orders;
    SELECT * FROM returns WHERE return_status = 'RECEIVED';
    SELECT * FROM refunds;
Type 'exit' to quit.
"""

from src.database import query_db
import json

def main():
    print("=" * 60)
    print("🔍 Interactive SQLite Explorer for support.db")
    print("Tables available: orders, returns, refunds, tickets")
    print("Type 'exit' to quit.")
    print("=" * 60)

    while True:
        try:
            query = input("\nEnter SQL Query: ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            results = query_db(query)
            if not results:
                print(" Empty result (0 rows matched).")
            else:
                print(f" Returned {len(results)} row(s):")
                print(json.dumps(results, indent=2))
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
