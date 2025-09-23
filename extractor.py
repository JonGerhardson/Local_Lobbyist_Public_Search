import os
import pandas as pd
from bs4 import BeautifulSoup
import re

def clean_currency(text):
    """Cleans currency strings by removing '$' and commas, converting to float."""
    if text is None or text.strip() == '':
        return 0.0
    try:
        return float(text.replace('$', '').replace(',', '').strip())
    except (ValueError, AttributeError):
        return 0.0

def parse_date_range(date_string):
    """Parses a date range string into start and end dates."""
    try:
        start_str, end_str = [d.strip() for d in date_string.split('-')]
        start_date = pd.to_datetime(start_str, format='%m/%d/%Y').strftime('%Y-%m-%d')
        end_date = pd.to_datetime(end_str, format='%m/%d/%Y').strftime('%Y-%m-%d')
        return start_date, end_date
    except (ValueError, IndexError):
        return None, None

def safe_get_text(soup_obj, tag, element_id):
    """Safely gets text from a BeautifulSoup object by tag and ID."""
    element = soup_obj.find(tag, id=element_id)
    return element.get_text(strip=True) if element else ""

def format_date(date_string):
    """Safely parses and formats a date string, returning None if invalid."""
    if date_string is None or not date_string.strip():
        return None
    date_val = pd.to_datetime(date_string, errors='coerce')
    return None if pd.isna(date_val) else date_val.strftime('%Y-%m-%d')

def parse_met_expenses(table, disclosure_id, lobbyist_name=None):
    """Parses Meals, Entertainment, and Travel expense tables."""
    expenses = []
    if table and "No meals, travel, or entertainment expenses" not in table.get_text():
        rows = table.find_all('tr')
        if len(rows) > 1:
            for row in rows[1:]:
                cols = row.find_all('td')
                if "Total amount" in row.get_text() or len(cols) < 5:
                    continue
                
                has_lobbyist_col = len(cols) == 6
                
                expense_record = {
                    'disclosure_id': disclosure_id,
                    'lobbyist_name': cols[1].get_text(strip=True) if has_lobbyist_col else (lobbyist_name or "N/A"),
                    'date': format_date(cols[0].get_text(strip=True)),
                    'event_type': cols[2].get_text(strip=True) if has_lobbyist_col else cols[1].get_text(strip=True),
                    'payee_vendor': cols[3].get_text(strip=True) if has_lobbyist_col else cols[2].get_text(strip=True),
                    'attendees': cols[4].get_text(strip=True) if has_lobbyist_col else cols[3].get_text(strip=True),
                    'amount': clean_currency(cols[5].get_text(strip=True)) if has_lobbyist_col else clean_currency(cols[4].get_text(strip=True)),
                }
                expenses.append(expense_record)
    return expenses

def parse_operating_expenses(soup, disclosure_id):
    """Parses Operating Expense tables."""
    operating_expenses = []
    table = soup.find('table', id=re.compile(r'grdvOperatingExpenses'))
    if table and "No operating expenses were filed" not in table.get_text():
        rows = table.find_all('tr')
        for row in rows[1:]: # Skip header
            cols = row.find_all('td')
            if "Total operating expenses" in row.get_text() or len(cols) < 4:
                continue
            operating_expenses.append({
                'disclosure_id': disclosure_id,
                'date': format_date(cols[0].get_text(strip=True)),
                'recipient': cols[1].get_text(strip=True),
                'type_of_expense': cols[2].get_text(strip=True),
                'amount': clean_currency(cols[3].get_text(strip=True)),
            })
    return operating_expenses

def parse_additional_expenses(soup, disclosure_id):
    """Parses Additional Expense tables."""
    additional_expenses = []
    tables = soup.find_all('table', id=re.compile(r'grdvAdditionalExpenses'))
    for table in tables:
        if "No additional expenses were filed" in table.get_text():
            continue
        rows = table.find_all('tr')
        for row in rows[1:]: # Skip header
            cols = row.find_all('td')
            if "Total additional expenses" in row.get_text() or len(cols) < 6:
                continue
            additional_expenses.append({
                'disclosure_id': disclosure_id,
                'date': format_date(cols[0].get_text(strip=True)),
                'lobbyist_name': cols[1].get_text(strip=True),
                'recipient_name': cols[2].get_text(strip=True),
                'type_of_expense': cols[3].get_text(strip=True),
                'description': cols[4].get_text(strip=True),
                'amount': clean_currency(cols[5].get_text(strip=True)),
            })
    return additional_expenses

def parse_lobbyist_report(soup, disclosure_id):
    """Parses a lobbyist report and extracts relevant information."""
    employer_name = safe_get_text(soup, 'span', 'ContentPlaceHolder1_LRegistrationInfoReview1_lblLobbyistCompany')
    first_name = safe_get_text(soup, 'span', 'ContentPlaceHolder1_LRegistrationInfoReview1_lblLobbyistFirstName')
    last_name = safe_get_text(soup, 'span', 'ContentPlaceHolder1_LRegistrationInfoReview1_lblLobbyistLastName')
    
    filer_is_individual = bool(first_name and last_name)
    
    lobbyist_info = {
        'disclosure_id': disclosure_id,
        'first_name': first_name or employer_name, 'last_name': last_name, 'employer_name': employer_name,
        'is_incidental': bool(soup.find('span', id='ContentPlaceHolder1_LRegistrationInfoReview1_lblIncidental')),
    }
    
    activities = []
    activity_tables = soup.find_all('table', id=lambda x: x and 'grdvActivitiesNew' in x)

    for table in activity_tables:
        current_lobbyist = f"{first_name} {last_name}".strip() if filer_is_individual else employer_name
        current_client = employer_name
        
        lobbyist_header_td = table.find_previous('td', text=re.compile(r'^\s*Lobbyist:'))
        if lobbyist_header_td:
            lobbyist_name_td = lobbyist_header_td.find_next_sibling('td')
            if lobbyist_name_td:
                current_lobbyist = lobbyist_name_td.get_text(strip=True)

        client_header_td = table.find_previous('td', text=re.compile(r'^\s*Client:\s*'))
        client_header_strong = table.find_previous('strong', text=re.compile(r'^\s*Client:\s*'))
        
        if client_header_td:
            client_name_td = client_header_td.find_next_sibling('td')
            if client_name_td:
                current_client = client_name_td.get_text(strip=True)
        elif client_header_strong:
            client_name_span = client_header_strong.find_next_sibling('span')
            if client_name_span:
                current_client = client_name_span.get_text(strip=True)
        
        rows = table.find_all('tr')
        if len(rows) > 1:
            for row in rows[1:]:
                cols = row.find_all('td')
                if "Total amount" in row.get_text() or len(cols) < 6: continue
                
                activities.append({
                    'disclosure_id': disclosure_id, 'individual_lobbyist_name': current_lobbyist,
                    'client_name': current_client, 'house_senate': cols[0].get_text(strip=True),
                    'bill_or_agency': cols[1].get_text(strip=True), 'bill_title': cols[2].get_text(strip=True),
                    'agent_position': cols[3].get_text(strip=True), 'amount': clean_currency(cols[4].get_text(strip=True)),
                    'business_association': cols[5].get_text(strip=True),
                })
    
    # --- EXPENSE BLOCKS ---
    met_expenses = []
    expense_tables = soup.find_all('table', id=re.compile(r'grdvMETExpenses'))
    for table in expense_tables:
        lobbyist_name_element = table.find_previous('span', id=re.compile(r'lblLobbyistName'))
        lobbyist_name = lobbyist_name_element.get_text(strip=True).replace("Lobbyist: ", "") if lobbyist_name_element else f"{first_name} {last_name}".strip()
        met_expenses.extend(parse_met_expenses(table, disclosure_id, lobbyist_name))
    
    operating_expenses = parse_operating_expenses(soup, disclosure_id)
    additional_expenses = parse_additional_expenses(soup, disclosure_id)

    # --- CONTRIBUTIONS BLOCK ---
    contributions = []
    contributions_table = soup.find('table', id=re.compile(r'grdvCampaignContribution'))
    if contributions_table and "No campaign contributions were filed" not in contributions_table.get_text():
        rows = contributions_table.find_all('tr')
        if len(rows) > 1:
            for row in rows[1:]:
                cols = row.find_all('td')
                if "Total contributions" in row.get_text() or len(cols) < 4: continue
                contributions.append({
                    'disclosure_id': disclosure_id,
                    'date': format_date(cols[0].get_text(strip=True)),
                    'recipient_name': cols[1].get_text(strip=True), 'office_sought': cols[2].get_text(strip=True),
                    'amount': clean_currency(cols[3].get_text(strip=True)),
                })
    
    return lobbyist_info, activities, met_expenses, operating_expenses, additional_expenses, contributions

def parse_client_report(soup, disclosure_id):
    """Parses a client report and extracts relevant information."""
    client_name = safe_get_text(soup, 'span', 'ContentPlaceHolder1_CRegistrationInfoReview1_lblClientCompany')
    officer_first = safe_get_text(soup, 'span', 'ContentPlaceHolder1_CRegistrationInfoReview1_lblClientAuthorizingOfficerFirstName')
    officer_last = safe_get_text(soup, 'span', 'ContentPlaceHolder1_CRegistrationInfoReview1_lblClientAuthorizingOfficerLastName')
    client_info = {
        'disclosure_id': disclosure_id, 'client_name': client_name,
        'auth_officer_name': f"{officer_first} {officer_last}".strip(),
        'business_interest': safe_get_text(soup, 'span', 'ContentPlaceHolder1_CRegistrationInfoReview1_lblBusinessInterest'),
    }
    compensations = []
    comp_table = soup.find('table', id='ContentPlaceHolder1_DisclosureReviewDetail1_grdvSalaryPaid')
    if comp_table:
        rows = comp_table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all('td')
            if "Total" in row.get_text() or len(cols) < 2: continue
            compensations.append({
                'disclosure_id': disclosure_id, 'payee_name': cols[0].get_text(strip=True),
                'amount': clean_currency(cols[1].get_text(strip=True)),
            })

    # --- EXPENSE BLOCKS FOR CLIENT REPORT ---
    met_expenses = []
    expenses_table = soup.find('table', id=re.compile(r'grdvMETExpenses'))
    met_expenses.extend(parse_met_expenses(expenses_table, disclosure_id))
    
    operating_expenses = parse_operating_expenses(soup, disclosure_id)
    additional_expenses = parse_additional_expenses(soup, disclosure_id)

    return client_info, compensations, met_expenses, operating_expenses, additional_expenses

def main():
    """Main function to process HTML files and generate CSVs."""
    html_dir = 'html_files'
    if not os.path.exists(html_dir):
        print(f"Error: Directory '{html_dir}' not found.")
        return
        
    all_files = [f for f in os.listdir(html_dir) if f.endswith('.html')]
    total_files = len(all_files)
    
    skipped_files_log = []
    disclosure_reports_list = []
    lobbyists_list = []
    clients_list = []
    compensations_list = []
    lobbying_activities_list = []
    met_expenses_list = []
    operating_expenses_list = []
    additional_expenses_list = []
    contributions_list = []
    
    processed_count, skipped_bad_filename, skipped_no_header, skipped_other_error = 0, 0, 0, 0

    print(f"Found {total_files} HTML files to process...")
    for i, filename in enumerate(all_files):
        print(f"Processing file {i+1}/{total_files}: {filename}", end='\r')
        filepath = os.path.join(html_dir, filename)
        
        disclosure_id = None
        match = re.search(r'sysvalue=(.+)\.html', filename)
        if match:
            disclosure_id = match.group(1).replace('%2f', '/')
        else:
            disclosure_id = os.path.splitext(filename)[0]
            
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            
        header_element = soup.find('span', id='ContentPlaceHolder1_lblDisclosureHeader')
        
        if not header_element:
            skipped_no_header += 1
            skipped_files_log.append(f"{filename} (Reason: Invalid Content / No Header)")
            continue
            
        try:
            header_text = header_element.get_text(strip=True)
            report_type = "Lobbyist" if "Lobbyist" in header_text else "Client"
            period_str = safe_get_text(soup, 'span', 'ContentPlaceHolder1_lblYear')
            start_date, end_date = parse_date_range(period_str)
            disclosure_reports_list.append({
                'disclosure_id': disclosure_id, 'report_type': report_type,
                'period_start_date': start_date, 'period_end_date': end_date
            })
            if "Lobbyist" in report_type:
                lobbyist_info, activities, met_expenses, operating_expenses, additional_expenses, contributions = parse_lobbyist_report(soup, disclosure_id)
                lobbyists_list.append(lobbyist_info)
                lobbying_activities_list.extend(activities)
                met_expenses_list.extend(met_expenses)
                operating_expenses_list.extend(operating_expenses)
                additional_expenses_list.extend(additional_expenses)
                contributions_list.extend(contributions)
            else: # Client report
                client_info, compensations, met_expenses, operating_expenses, additional_expenses = parse_client_report(soup, disclosure_id)
                clients_list.append(client_info)
                compensations_list.extend(compensations)
                met_expenses_list.extend(met_expenses)
                operating_expenses_list.extend(operating_expenses)
                additional_expenses_list.extend(additional_expenses)
            processed_count += 1
        except Exception as e:
            skipped_other_error += 1
            skipped_files_log.append(f"{filename} (Reason: Parsing Error - {e})")

    print("\n\n--- 📊 Processing Summary ---")
    print(f"Total files found:       {total_files}")
    print(f"Successfully processed:    {processed_count}")
    print(f"Skipped (bad filename):    {skipped_bad_filename}")
    print(f"Skipped (no header/empty): {skipped_no_header}")
    print(f"Skipped (other errors):    {skipped_other_error}")
    print("-----------------------------\n")

    with open('skipped_files.txt', 'w') as f:
        for item in skipped_files_log:
            f.write(f"{item}\n")
    print(f"List of {len(skipped_files_log)} skipped files saved to 'skipped_files.txt'")

    df_reports = pd.DataFrame(disclosure_reports_list)
    df_lobbyists = pd.DataFrame(lobbyists_list).drop_duplicates(subset=['disclosure_id']) if lobbyists_list else pd.DataFrame()
    df_clients = pd.DataFrame(clients_list).drop_duplicates(subset=['disclosure_id']) if clients_list else pd.DataFrame()
    df_compensations = pd.DataFrame(compensations_list)
    df_activities = pd.DataFrame(lobbying_activities_list)
    df_met_expenses = pd.DataFrame(met_expenses_list)
    df_operating_expenses = pd.DataFrame(operating_expenses_list)
    df_additional_expenses = pd.DataFrame(additional_expenses_list)
    df_contributions = pd.DataFrame(contributions_list)

    output_dir = 'output_csvs'
    if not os.path.exists(output_dir): 
        os.makedirs(output_dir)
    
    df_reports.to_csv(os.path.join(output_dir, 'disclosure_reports.csv'), index=False)
    if not df_lobbyists.empty: df_lobbyists.to_csv(os.path.join(output_dir, 'lobbyists.csv'), index=False)
    if not df_clients.empty: df_clients.to_csv(os.path.join(output_dir, 'clients.csv'), index=False)
    if not df_compensations.empty: df_compensations.to_csv(os.path.join(output_dir, 'compensations.csv'), index=False)
    if not df_activities.empty: df_activities.to_csv(os.path.join(output_dir, 'lobbying_activities.csv'), index=False)
    if not df_met_expenses.empty: df_met_expenses.to_csv(os.path.join(output_dir, 'met_expenses.csv'), index=False)
    if not df_operating_expenses.empty: df_operating_expenses.to_csv(os.path.join(output_dir, 'operating_expenses.csv'), index=False)
    if not df_additional_expenses.empty: df_additional_expenses.to_csv(os.path.join(output_dir, 'additional_expenses.csv'), index=False)
    if not df_contributions.empty: df_contributions.to_csv(os.path.join(output_dir, 'contributions.csv'), index=False)

    print(f"Successfully created CSV files in the '{output_dir}' directory.")
if __name__ == '__main__':
    main()


