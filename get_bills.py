# Save this as get_bills.py
import pandas as pd
import requests
import argparse
import sqlite3
from tqdm import tqdm

# --- Configuration ---
# IMPORTANT: Replace with your actual LegiScan API key
API_KEY = 'YOUR_API_KEY_HERE' 
BASE_URL = 'https://api.legiscan.com/'
STATE = 'MA'
DB_FILE = "lobbying_data.db"

def get_session_id_for_year(api_key, state, target_year):
    """
    Gets the session_id for a given state and year, accounting for multi-year sessions.
    """
    if api_key == 'YOUR_API_KEY':
        print("Error: Please replace 'YOUR_API_KEY' with your actual LegiScan API key.")
        return None
    
    params = {'key': api_key, 'op': 'getSessionList', 'state': state}
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == 'OK':
            for session in data['sessions']:
                if (target_year >= session['year_start'] and 
                    target_year <= session['year_end'] and 
                    session['special'] == 0):
                    print(f"Found session for {target_year}: {session['session_name']} (ID: {session['session_id']})")
                    return session['session_id']
            print(f"Error: No regular session found covering the year {target_year}.")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
    return None

def create_bill_id_map(api_key, session_id):
    """Creates a mapping from bill_number to bill_id for a given session."""
    params = {'key': api_key, 'op': 'getMasterList', 'id': session_id}
    bill_map = {}
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'OK':
            masterlist = data.get('masterlist', {})
            for item in masterlist.values():
                if 'number' in item and 'bill_id' in item:
                    bill_map[item['number']] = item['bill_id']
            print(f"Created a lookup map with {len(bill_map)} bills.")
            return bill_map
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
    return None

def get_bill_details(api_key, bill_id):
    """Retrieves detailed information for a single bill_id."""
    params = {'key': api_key, 'op': 'getBill', 'id': bill_id}
    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'OK' and 'bill' in data:
            bill = data['bill']
            status_map = {0: 'Prefiled', 1: 'Introduced', 2: 'Engrossed', 3: 'Enrolled', 4: 'Passed', 5: 'Vetoed', 6: 'Failed'}
            return {
                'legiscan_bill_id': bill.get('bill_id'),
                'status': status_map.get(bill.get('status'), 'Unknown'),
                'last_action_date': bill.get('last_action_date'),
                'last_action': bill.get('last_action'),
                'title': bill.get('title')
            }
    except requests.exceptions.RequestException:
        return None
    return None

def fetch_and_update_bills(year):
    """
    Main function to fetch bill data from LegiScan API and update the SQLite database.
    """
    session_id = get_session_id_for_year(API_KEY, STATE, year)
    if not session_id:
        return

    conn = sqlite3.connect(DB_FILE)
    
    try:
        # 1. Get unique bills from the DB that haven't been updated yet
        print("\nQuerying database for bills to update...")
        query = """
            SELECT DISTINCT house_senate, bill_or_agency 
            FROM lobbying_activities 
            WHERE legiscan_bill_id IS NULL AND house_senate LIKE '%Bill%'
        """
        df_bills_to_fetch = pd.read_sql_query(query, conn)
        print(f"Found {len(df_bills_to_fetch)} unique bills needing LegiScan data.")
        
        if df_bills_to_fetch.empty:
            print("No new bills to update.")
            return

        # 2. Create the master list of all bills for the session
        bill_id_map = create_bill_id_map(API_KEY, session_id)
        if not bill_id_map:
            return

        # 3. Fetch details for each unique bill and cache them
        bill_details_cache = {}
        print("\nFetching details for each unique bill from LegiScan API...")
        for _, row in tqdm(df_bills_to_fetch.iterrows(), total=df_bills_to_fetch.shape[0]):
            bill_prefix = 'H' if 'House' in row['house_senate'] else 'S'
            full_bill_number = f"{bill_prefix}{row['bill_or_agency']}"
            
            bill_id = bill_id_map.get(full_bill_number)
            if bill_id:
                details = get_bill_details(API_KEY, bill_id)
                if details:
                    bill_details_cache[(row['house_senate'], row['bill_or_agency'])] = details

        # 4. Update the database with the cached details
        print("\nUpdating the database...")
        cursor = conn.cursor()
        update_count = 0
        for (house_senate, bill_or_agency), details in tqdm(bill_details_cache.items(), desc="Updating records"):
            update_query = """
                UPDATE lobbying_activities
                SET legiscan_bill_id = ?,
                    status = ?
                WHERE house_senate = ? AND bill_or_agency = ?
            """
            params = (
                details['legiscan_bill_id'],
                details['status'],
                house_senate,
                bill_or_agency
            )
            cursor.execute(update_query, params)
            update_count += cursor.rowcount
            
        conn.commit()
        print(f"\nSuccess! Updated {update_count} records in the 'lobbying_activities' table.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enrich lobbying activity data in the SQLite database with bill details from the LegiScan API.')
    parser.add_argument('year', type=int, help='The legislative year to query (e.g., 2025).')
    args = parser.parse_args()
    
    fetch_and_update_bills(args.year)

