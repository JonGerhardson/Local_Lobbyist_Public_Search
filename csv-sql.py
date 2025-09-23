import os
import sqlite3
import pandas as pd

DB_FILE = "lobbying_data.db"
CSV_DIR = "output_csvs"

# Updated and complete SQL schema definition
SCHEMA = """
CREATE TABLE IF NOT EXISTS disclosure_reports (
    disclosure_id TEXT PRIMARY KEY,
    report_type TEXT,
    period_start_date DATE,
    period_end_date DATE
);

CREATE TABLE IF NOT EXISTS lobbyists (
    lobbyist_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id TEXT,
    first_name TEXT,
    last_name TEXT,
    employer_name TEXT,
    is_incidental BOOLEAN
);

CREATE TABLE IF NOT EXISTS clients (
    client_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id TEXT,
    client_name TEXT,
    auth_officer_name TEXT,
    business_interest TEXT
);

CREATE TABLE IF NOT EXISTS compensations (
    compensation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id TEXT,
    payee_name TEXT,
    amount REAL
);

CREATE TABLE IF NOT EXISTS lobbying_activities (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id TEXT,
    individual_lobbyist_name TEXT,
    client_name TEXT,
    house_senate TEXT,
    bill_or_agency TEXT,
    bill_title TEXT,
    agent_position TEXT,
    amount REAL,
    business_association TEXT
);

CREATE TABLE IF NOT EXISTS met_expenses (
    met_expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id TEXT,
    lobbyist_name TEXT,
    date DATE,
    event_type TEXT,
    payee_vendor TEXT,
    attendees TEXT,
    amount REAL
);

CREATE TABLE IF NOT EXISTS operating_expenses (
    operating_expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id TEXT,
    date DATE,
    recipient TEXT,
    type_of_expense TEXT,
    amount REAL
);

CREATE TABLE IF NOT EXISTS additional_expenses (
    additional_expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id TEXT,
    date DATE,
    lobbyist_name TEXT,
    recipient_name TEXT,
    type_of_expense TEXT,
    description TEXT,
    amount REAL
);

CREATE TABLE IF NOT EXISTS contributions (
    contribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
    disclosure_id TEXT,
    date DATE,
    recipient_name TEXT,
    office_sought TEXT,
    amount REAL
);
"""

def create_database():
    """Removes the old database file and creates a new one with the specified schema."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Removed old database file: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Database '{DB_FILE}' created successfully with new schema.")

def import_csvs_to_db():
    """Imports data from CSV files in the specified directory into the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    # Updated map to include all CSV files
    csv_to_table_map = {
        'disclosure_reports.csv': 'disclosure_reports',
        'lobbyists.csv': 'lobbyists',
        'clients.csv': 'clients',
        'compensations.csv': 'compensations',
        'lobbying_activities.csv': 'lobbying_activities',
        'met_expenses.csv': 'met_expenses',
        'operating_expenses.csv': 'operating_expenses',
        'additional_expenses.csv': 'additional_expenses',
        'contributions.csv': 'contributions'
    }
    print("\nStarting import of CSV files...")
    for csv_file, table_name in csv_to_table_map.items():
        file_path = os.path.join(CSV_DIR, csv_file)
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                # Ensure date columns are handled correctly if they exist
                for col in ['date', 'period_start_date', 'period_end_date']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
                df.to_sql(table_name, conn, if_exists='append', index=False)
                print(f"  ✅ Imported {len(df)} rows into '{table_name}'")
            except Exception as e:
                print(f"  ❌ Failed to import {csv_file}. Error: {e}")
        else:
            print(f"  ℹ️  Skipping '{csv_file}' as it was not found.")
    conn.close()
    print("\nImport process complete.")

if __name__ == '__main__':
    create_database()
    import_csvs_to_db()

