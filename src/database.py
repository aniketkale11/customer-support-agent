"""
Database Module for Customer Support Resolution Agent.

This module initializes a local SQLite database (`support.db`) from our 4 CSV files:
1. mock_orders.csv     -> 'orders' table
2. returns.csv         -> 'returns' table
3. refunds.csv         -> 'refunds' table
4. support_tickets.csv -> 'tickets' table

It uses Python's built-in `sqlite3` and `csv` modules (standard library), 
which is fast, reliable, and has zero external dependencies.
"""

import csv
import sqlite3
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "support.db"


def get_db_connection():
    """
    Creates and returns a connection to the SQLite database.
    row_factory = sqlite3.Row allows accessing columns by name like a dictionary.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn: sqlite3.Connection):
    """
    Creates the 4 relational tables with appropriate schema and primary keys.
    """
    cursor = conn.cursor()

    # 1. Orders table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            order_date TEXT NOT NULL,
            order_total REAL NOT NULL,
            order_status TEXT NOT NULL,
            payment_id TEXT NOT NULL,
            payment_status TEXT NOT NULL
        )
        """
    )

    # 2. Returns table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS returns (
            return_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            return_requested_date TEXT,
            return_received_date TEXT,
            return_reason TEXT,
            return_status TEXT NOT NULL,
            item_condition TEXT,
            inspection_result TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        )
        """
    )

    # 3. Refunds table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS refunds (
            refund_id TEXT PRIMARY KEY,
            return_id TEXT,
            order_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            requested_amount REAL NOT NULL,
            approved_amount REAL DEFAULT 0.0,
            refund_status TEXT NOT NULL,
            eligibility_status TEXT NOT NULL,
            approval_status TEXT NOT NULL,
            payment_id TEXT,
            provider_transaction_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            notes TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (order_id),
            FOREIGN KEY (return_id) REFERENCES returns (return_id)
        )
        """
    )

    # 4. Support Tickets table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            order_id TEXT,
            return_id TEXT,
            refund_id TEXT,
            category TEXT,
            customer_message TEXT NOT NULL,
            priority TEXT,
            ticket_status TEXT NOT NULL,
            resolution_summary TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        )
        """
    )

    conn.commit()


def populate_table_from_csv(conn: sqlite3.Connection, csv_path: Path, table_name: str):
    """
    Reads a CSV file using Python's standard csv.DictReader and inserts rows into the table.
    """
    if not csv_path.exists():
        print(f"Warning: CSV file not found: {csv_path}")
        return

    cursor = conn.cursor()
    # Clear existing data in the table to allow clean reloads
    cursor.execute(f"DELETE FROM {table_name}")

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]

    if not rows:
        print(f"No rows found in {csv_path.name}")
        return

    columns = list(rows[0].keys())
    placeholders = ", ".join(["?" for _ in columns])
    column_names = ", ".join(columns)
    sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

    # Prepare values for batch insert
    values = [[row[col] if row[col] != "" else None for col in columns] for row in rows]
    cursor.executemany(sql, values)
    conn.commit()
    print(f" Successfully inserted {len(values)} rows into '{table_name}'")


def init_db(force: bool = False):
    """
    Initializes the database schema and loads CSV records.
    """
    if DB_PATH.exists() and not force:
        print(f"Database already exists at {DB_PATH}. Use force=True to re-populate.")
        return

    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    create_tables(conn)

    populate_table_from_csv(conn, DATA_DIR / "mock_orders.csv", "orders")
    populate_table_from_csv(conn, DATA_DIR / "returns.csv", "returns")
    populate_table_from_csv(conn, DATA_DIR / "refunds.csv", "refunds")
    populate_table_from_csv(conn, DATA_DIR / "support_tickets.csv", "tickets")

    conn.close()
    print(f"Database initialization complete: {DB_PATH}")


def query_db(query: str, params: tuple = ()) -> list[dict]:
    """
    Executes a SELECT SQL query with safe parameters and returns results as Python dicts.
    
    Example:
        orders = query_db("SELECT * FROM orders WHERE customer_id = ?", ("CUST001",))
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def execute_db(statement: str, params: tuple = ()) -> int:
    """
    Executes an INSERT, UPDATE, or DELETE SQL statement and commits the transaction.
    Returns the number of rows affected.
    
    Example:
        rows_affected = execute_db("UPDATE refunds SET refund_status = ? WHERE refund_id = ?", ("COMPLETED", "REF3001"))
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(statement, params)
        conn.commit()
        return cursor.rowcount


if __name__ == "__main__":
    # Test initialization
    init_db(force=True)

    print("\n--- TEST 1: Retrieve single order details ---")
    orders = query_db("SELECT * FROM orders WHERE order_id = ?", ("ORD1001",))
    print(orders)

    print("\n--- TEST 2: Join order with return & refund status ---")
    query = """
    SELECT 
        o.order_id,
        o.customer_id,
        o.product_name,
        o.order_total,
        r.return_status,
        r.inspection_result,
        ref.refund_status,
        ref.approved_amount
    FROM orders o
    LEFT JOIN returns r ON o.order_id = r.order_id
    LEFT JOIN refunds ref ON o.order_id = ref.order_id
    WHERE o.order_id = ?
    """
    joined = query_db(query, ("ORD1001",))
    print(joined)
