
# Massachusetts Lobbying Database Project

This project scrapes, processes, and enriches lobbying disclosure reports from the Massachusetts Secretary of the Commonwealth's website. The final output is a queryable SQLite database that can be used for more complex analysis then can be easily done through the state's web app.

The process is broken down into four main steps, executed by separate Python scripts:

* **Scrape HTML Files (hobby_lobby.py)**: Downloads the raw HTML disclosure reports from the web.

* **Extract Data (extractor.py)**: Parses the downloaded HTML files and extracts the lobbying data into a set of clean CSV files.

* **Create Database (csvsql.py)**: Imports the data from all the generated CSV files into a structured SQLite database.

* **Enrich Bill Data (get_bills.py)**: Connects to the LegiScan API to fetch the latest legislative status for bills in the database and updates the records accordingly.

**Dependencies**

Python 3

A valid LegiScan API key (free) 

Required Python libraries. Install with pip if you don't already have them installed. Pip is a package installer for python. If you need to install pip follow the instructions at https://pypi.org/project/pip/

```
pip install pandas requests beautifulsoup4 tqdm selenium webdriver-manager

```

Clone this repo into your working directory. It is reccomended to create a new working directory for each seperate year you create a database for.

```
git clone [https://github.com/JonGerhardson/Local_Lobbyist_Public_Search/](https://github.com/JonGerhardson/Local_Lobbyist_Public_Search/)

```

# Step-by-Step Guide

**❗❗❗** If you just want to build the .db you can skip this step and download a copy of my html files HERE \[TK ADD ZIP LINK HERE\] for disclosure reports from the first 6 months of 2025.

## Step 0: Extract Disclosure Report URLs from the MA Lobbyist Website

This first step involves manually gathering the starting URLs for every lobbyist and client for a given year.

**Step 0.1: Search for Lobbyists and Lobbying Entities**

Navigate to the Lobbyist Public Search page at https://www.sec.ma.us/lobbyistpublicsearch/

Set the search criteria as follows:

* **Select registration year**: Choose your target year. You can only search one year at a time.

* **Enter name**: Leave this field blank.

* **Select lobbyist type**: **Lobbyist or Lobbying Entity**

* **Select results per page**: **View all results**

* **Click Search**. This might take a couple minutes to load. The reason for changing lobbyist type from all is to prevent problems with it loading all clients and lobbyist at once.

<img width="862" height="662" alt="image" src="https://github.com/user-attachments/assets/a00f96ac-7904-4632-ad47-209191f254da" />

**Step 0.2: Save the Lobbyist Search Results**

Once the results page loads, right-click anywhere on the page and select “Save As…” or “Save Page As…”.
Save the file with a clear name, such as `lobbyist_results_2024.html`.

**Step 0.3: Search for Clients**

Go back to the search page.
Keep the same year, but change the **Select lobbyist type** to **Client**.
Click Search.

**Step 0.4: Save the Client Search Results**

Save the results page just as before, using a name like `client_results_2024.html`.

**Step 0.5: Convert HTML to CSV using htmlcsv.py**

You will now run the provided Python script twice.
First, for lobbyists:

* Open `htmlcsv.py` and change the `input_html_file` variable to `'lobbyist_results_2024.html'`.

* Change the `output_csv_file` to `'lobbyist_urls_2024.csv'`.

* Run the script from your terminal: `python htmlcsv.py`
  Second, for clients:

* In `htmlcsv.py`, change `input_html_file` to `'client_results_2024.html'`.

* Change `output_csv_file` to `'client_urls_2024.csv'`.

* Run the script again: ````python htmlcsv.py````

**Step 0.6: Combine the URLs**

Create a new, blank CSV file and name it `input_urls.csv`.
Open `lobbyist_urls_2024.csv` and `client_urls_2024.csv`.
Copy the contents of both files (including the header from one of them) into `input_urls_2024.csv`.
Alternatively on macOS or Linux you can run this command in your terminal to do the same thing:

```
{ head -n 1 lobbyist_urls_2024.csv; tail -n +2 lobbyist_urls_2024.csv; tail -n +2 client_urls_2024.csv; } > input_urls.csv

```

This single file now contains all the starting points for the web scraper. The urls from the search results point to summary pages, but we need the CompleDisclosure pages that are linked to within those summary pages. 

**Step 0.7 Scrape CompleteDisclosure.aspx urls**
Make sure that input_urls.csv is in the top level directory for this project and run 
```python get_disclosure_urls.py```

This might take a few hours to run so it's a good time to take a break. It will output a urls.csv file that we will use in the next step to download the html content of the disclosure reports. 


**Why not use the data on the summary pages directly?**
State law requires all lobbyists and their clients to submit disclosure reports twice a year, (once for the period of January 1 to June 30, and again for July 1 toDecember 31).This project uses only these files to create a database of lobbying activit and these are, as I understand it the primary source material, or at least contain identical information to those sources. 

 The summary pages seem to be created using info from the disclosure reports and registration reports, and display data for the whole year rather than each 6 month reporting period. In theory this sounds good, but in practice I had difficulty deduplicating data using this approach. (Tip: If you wind up with a .db that shows a tiny trade group spent billions more than the entire market value of that industry on lobbying in the last six months you fucked up somewhere.) There are also Registration records, which have the date the lobbyist/client registered, contact info, and other data deemed out of scope for this project. 
 
## Step 1: Scrape HTML Files from the Web


Take a look at your urls.txt file from the previous step. There should be a few thousand pages listed, and they should look like this: 
https://www.sec.ma.us/publiclobbyistsearch/CompleteDisclosure.aspx/sysvalue=[long random string] 

```
python urlsscrape.py

```
This should go a little faster than the previous step, but will take a while too. The scraper is set to block images, javascript, and css, only grabbing the html content which speeds things up and saves bandwith but expect about 30 minutes minuimum for this step, ptobably closer to an hour. 

## Step 2: Extract Data from HTML to CSVs

This step uses `extractor.py` to parse all the saved HTML files from the `html_files` directory and extract the data into a collection of CSV files inside the `output_csvs` folder. 

```
python extractor.py

```
Once it is complete you should have the following files in the output folder:
lobbying_activities.csv  
met_expenses.csv            
lobbyists.csv
operating_expenses.csv   
clients.csv                 
expenses.csv
disclosure_reports.csv   
campaign_contributions.csv  
additional_expenses.csv
compensations.csv        
contributions.csv

Each csv will have a column "disclosure_id" mapped to the uuid from its URL. For example, in campaign_contributions.csv you might see:
```
v_mjLQ41YVqm2bof1TANC_F5a7okEZ8LtZpHF44JY5OFbHIlI4gKEJVd1FDAJSZz,2025-03-19,Maura Healey,Governor,200.0
```
To find who gave $200 to Maura Healy on March 19, ctrl+f the string inside lobbyists.csv. In the next step we will join these seperate files into a single database by matching these strings accross each csv file. 

## Step 3: Create SQLite Database from CSVs

This step takes all the CSV files from the `output_csvs` directory and loads them into a structured SQLite database file named `lobbying_data.db`.

Run the `csvsql.py` script. If `lobbying_data.db` already exists, it will be deleted and a new one will be created.

```
python csvsql.py

```

## Step 4: Enrich with Bill Status from LegiScan

This final step uses the `get_bills.py` script to add legislative status and other details to the `lobbying_activities` table in your new database.

**Setup**: Open `get_bills.py` and replace `'YOUR_API_KEY'` with your actual LegiScan API key. You can get a free API key with 30,000 requests per month from Legiscan here https://legiscan.com/legiscan 

**Usage**: The script requires a legislative year as an argument.

**Fetch Missing Data Only (Standard Mode)**:
If you're adding Legiscan data for the first time this will get the Legiscan ID and bill status for every bill in your dataset. If you add new data, or if something got borked and there's null values in any of the legiscape data, it will only only fetch data for bills that haven't been processed before to avoid using up all your API credits. 

```
python get_bills.py 2025

```

**Update All Bill Data**:
Use the `--update_all` flag to refresh the status for every bill for a given year. This is useful for keeping the current year's data up to date with the outcomes of bills. Probably not useful in most cases for data from past years. 

```
python get_bills.py 2025 --update_all

```

# Data Dictionary

This section describes the tables and columns in the `lobbying_data.db` SQLite database.


**disclosure_reports**
Stores the top-level information for each submitted disclosure report.

```disclosure_id```: Primary Key: The unique identifier for the report.

```report_type```: The type of report (e.g., "Lobbyist", "Client", "Lobbyist Entity").

```period_start_date```: The start date of the reporting period.

```period_end_date```: The end date of the reporting period.

**lobbyists**
Contains information about individual lobbyists or lobbying entities.

```lobbyist_id```: Primary Key: A unique ID for each lobbyist record.

```disclosure_id```: Foreign Key: Links to the disclosure_reports table.

```first_name```: The first name of the individual lobbyist or the name of the lobbying entity.

```last_name```: The last name of the individual lobbyist.

```employer_name```: The name of the lobbyist's employer.

```is_incidental```: A boolean flag indicating if the lobbyist is an incidental lobbyist.

**clients**
Stores details about the clients who hire lobbyists.

```client_id```: Primary Key: A unique ID for each client record.

```disclosure_id```: Foreign Key: Links to the disclosure_reports table.

```client_name```: The name of the client company or organization.

```auth_officer_name```: The name of the client's authorizing officer.

```business_interest```: The industry or sector of the client.

**compensations**
Details the payments made to lobbyists or lobbying firms.

```compensation_id```: Primary Key: A unique ID for each compensation record.

```disclosure_id```: Foreign Key: Links to the disclosure_reports table.

```payee_name```: The name of the lobbyist or firm that received the payment.

```amount```: The total compensation amount.

**lobbying_activities**
The central table detailing specific lobbying actions on bills or with agencies.

```activity_id```: Primary Key: A unique ID for each lobbying activity.

```disclosure_id```: Foreign Key: Links to the disclosure_reports table.

```individual_lobbyist_name```: The name of the lobbyist who performed the activity.

```client_name```: The name of the client on whose behalf the activity was performed.

```house_senate```: The legislative body targeted (e.g., "House Bill", "Senate Bill", "Executive").

```bill_or_agency```: The bill number or the name of the executive agency lobbied.

```bill_title```: The official title of the legislation.

```agent_position```: The stance taken by the lobbyist (e.g., "Support", "Oppose").

```amount```: The monetary amount associated with this specific activity.

```business_association```: Any declared direct business association related to the lobbying.

```legiscan_bill_id```: Foreign Key: The unique identifier from the LegiScan API for the bill.

```status```: The current legislative status of the bill (e.g., "Introduced", "Passed").

**contributions**
Records political campaign contributions made by the lobbyist or entity.

```contribution_id```: Primary Key: A unique ID for each contribution.

```disclosure_id```: Foreign Key: Links to the disclosure_reports table.

```date```: The date the contribution was made.

```recipient_name```: The name of the political candidate or committee that received the funds.

```office_sought```: The political office the recipient was seeking.

```amount```: The amount of the contribution.

**met_expenses**
Details expenses related to meals, entertainment, and travel.

```met_expense_id```: Primary Key: A unique ID for each expense.

```disclosure_id```: Foreign Key: Links to the disclosure_reports table.

```lobbyist_name```: The name of the lobbyist associated with the expense.

```date```: The date of the expense.

```event_type```: The category of the expense (e.g., "Meal", "Travel").

```payee_vendor```: The business or person who was paid.

```attendees```: A list of individuals who attended the event.

```amount```: The amount of the expense.

**operating_expenses**
Records general operating costs associated with lobbying.

```operating_expense_id```: Primary Key: A unique ID for each expense.

```disclosure_id```: Foreign Key: Links to the disclosure_reports table.

```date```: The date of the expense.

```recipient```: The name of the person or entity paid.

```expense_type```: The category of the operating expense (e.g., "Office supplies").

```amount```: The amount of the expense.

**additional_expenses**
Captures any other miscellaneous expenses not covered in other categories.

```additional_expense_id```: Primary Key: A unique ID for each expense.

```disclosure_id```: Foreign Key: Links to the disclosure_reports table.

```date_from```: The start date for the expense period.

```date_to```: The end date for the expense period.

```lobbyist_name```: The name of the lobbyist associated with the expense.

```recipient```: The name of the person or entity paid.

```purpose```: A description of the purpose of the expense.

```amount```: The amount of the expense.
