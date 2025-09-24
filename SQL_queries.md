# SQL Query Reference Guide: Massachusetts Lobbying Database Analysis

This guide compiles key SQL queries from our conversation for analyzing the lobbying database (`lobbying_data.db`). The database includes tables such as `compensations`, `clients`, `disclosure_reports`, `lobbying_activities`, `contributions`, `met_expenses`, `lobbyists`, and `elected_officials` (added via CSV import).

Queries are grouped by category for easy reference. Each includes:
- **Title**: A descriptive name.
- **SQL**: The full query code.
- **Description**: What it does and expected results.
- **Notes**: Any assumptions, filters, or prerequisites (e.g., requires `elected_officials` table).

Run these in SQLite (e.g., via `sqlite3 lobbying_data.db`). Assumes standard schema from the conversation; adjust table/column names if needed. Queries use CTEs (Common Table Expressions) for complex logic and `printf` for formatted output.

## 1. Firm and Client Spending Analysis

### Top 10 Highest-Paid Lobbying Firms
**SQL**:
```sql
SELECT
  payee_name,
  SUM(amount) AS total_compensation_received
FROM compensations
GROUP BY payee_name
ORDER BY total_compensation_received DESC
LIMIT 10;
```
**Description**: Ranks payees (firms/individuals) by total compensation received. Results: List of top 10 payees with aggregated amounts.
**Notes**: Focuses on `compensations` table.

### Top 10 Clients by Spending
**SQL**:
```sql
SELECT
  c.client_name,
  c.business_interest,
  SUM(comp.amount) AS total_spent
FROM clients c
JOIN disclosure_reports dr ON c.disclosure_id = dr.disclosure_id
JOIN compensations comp ON dr.disclosure_id = comp.disclosure_id
GROUP BY c.client_name
ORDER BY total_spent DESC
LIMIT 10;
```
**Description**: Ranks clients by total lobbying expenditures, including business interest. Results: Top 10 clients with name, interest, and total spent.
**Notes**: Joins `clients`, `disclosure_reports`, and `compensations`.

## 2. Bill Analysis

These queries filter for bills (`WHERE house_senate LIKE '%Bill%'`) and often join with `clients` on `client_name`. They include top 3 business interests (ranked by activity count) with stance breakdowns.

### Most Lobbied Bills (Basic: Activity Count, Support/Oppose)
**SQL**:
```sql
SELECT
  bill_or_agency,
  bill_title,
  COUNT(activity_id) AS lobbying_activity_count,
  SUM(CASE WHEN agent_position = 'Support' THEN 1 ELSE 0 END) AS support_count,
  SUM(CASE WHEN agent_position = 'Oppose' THEN 1 ELSE 0 END) AS oppose_count
FROM lobbying_activities
WHERE house_senate LIKE '%Bill%'
GROUP BY bill_or_agency, bill_title
ORDER BY lobbying_activity_count DESC
LIMIT 15;
```
**Description**: Ranks bills by total lobbying activities, with support/oppose breakdown. Results: Top 15 bills with counts.
**Notes**: Basic version; excludes agencies.

### Most Lobbied Bills with Top 3 Business Interests (Raw Counts), House/Senate, and Status
**SQL**:
```sql
WITH RankedInterests AS (
  SELECT
    la.house_senate,
    la.bill_or_agency,
    la.bill_title,
    c.business_interest,
    printf('%s (%d Support / %d Oppose)', c.business_interest,
      SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END),
      SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END)) AS interest_summary,
    ROW_NUMBER() OVER(PARTITION BY la.house_senate, la.bill_or_agency, la.bill_title ORDER BY COUNT(la.activity_id) DESC) AS rn
  FROM lobbying_activities AS la
  JOIN clients AS c ON la.client_name = c.client_name
  WHERE la.house_senate LIKE '%Bill%' AND c.business_interest IS NOT NULL
  GROUP BY la.house_senate, la.bill_or_agency, la.bill_title, c.business_interest
),
TopThreeInterests AS (
  SELECT house_senate, bill_or_agency, bill_title, GROUP_CONCAT(interest_summary, '; ') AS top_interests_breakdown
  FROM RankedInterests WHERE rn <= 3
  GROUP BY house_senate, bill_or_agency, bill_title
)
SELECT
  la.house_senate,
  la.bill_or_agency,
  la.bill_title,
  la.status,
  COUNT(la.activity_id) AS total_lobbying_activity,
  SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END) AS total_support,
  SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END) AS total_oppose,
  tti.top_interests_breakdown
FROM lobbying_activities AS la
LEFT JOIN TopThreeInterests AS tti ON la.house_senate = tti.house_senate AND la.bill_or_agency = tti.bill_or_agency AND la.bill_title = tti.bill_title
WHERE la.house_senate LIKE '%Bill%'
GROUP BY la.house_senate, la.bill_or_agency, la.bill_title, la.status
ORDER BY total_lobbying_activity DESC
LIMIT 15;
```
**Description**: Ranks bills by activity count, adds chamber (`house_senate`), status, and top 3 interests with raw support/oppose counts. Results: Top 15 bills with full details.
**Notes**: Use raw counts (not %). For House/Senate only, change `WHERE` to `= 'House Bill'` or `= 'Senate Bill'`.

### Most Supported Bills (Raw Count, Filtered: Support > Oppose)
**SQL** (All bills; adapt for House/Senate by changing WHERE):
```sql
WITH RankedInterests AS (
  SELECT
    la.house_senate, la.bill_or_agency, la.bill_title, c.business_interest,
    printf('%s (%d Support / %d Oppose)', c.business_interest,
      SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END),
      SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END)) AS interest_summary,
    ROW_NUMBER() OVER(PARTITION BY la.house_senate, la.bill_or_agency, la.bill_title ORDER BY COUNT(la.activity_id) DESC) AS rn
  FROM lobbying_activities AS la JOIN clients AS c ON la.client_name = c.client_name
  WHERE la.house_senate LIKE '%Bill%' AND c.business_interest IS NOT NULL
  GROUP BY la.house_senate, la.bill_or_agency, la.bill_title, c.business_interest
),
TopThreeInterests AS (
  SELECT house_senate, bill_or_agency, bill_title, GROUP_CONCAT(interest_summary, '; ') AS top_interests_breakdown
  FROM RankedInterests WHERE rn <= 3 GROUP BY house_senate, bill_or_agency, bill_title
)
SELECT
  la.house_senate, la.bill_or_agency, la.bill_title, la.status,
  SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END) AS support_count,
  SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END) AS oppose_count,
  SUM(CASE WHEN la.agent_position = 'Neutral' THEN 1 ELSE 0 END) AS neutral_count,
  tti.top_interests_breakdown
FROM lobbying_activities AS la
LEFT JOIN TopThreeInterests AS tti ON la.house_senate = tti.house_senate AND la.bill_or_agency = tti.bill_or_agency AND la.bill_title = tti.bill_title
WHERE la.house_senate LIKE '%Bill%'
GROUP BY la.house_senate, la.bill_or_agency, la.bill_title, la.status
HAVING support_count > oppose_count
ORDER BY support_count DESC
LIMIT 15;
```
**Description**: Ranks by support count, filtered for support > oppose. Includes chamber, status, neutral count, top 3 interests (raw counts). Results: Top 15 "loved" bills.
**Notes**: For House/Senate: Replace `WHERE la.house_senate LIKE '%Bill%'` with `= 'House Bill'` or `= 'Senate Bill'`, and add to GROUP BY/HAVING.

### Most Opposed Bills (Raw Count, Filtered: Oppose > Support)
**SQL** (Similar structure to above; change HAVING to `oppose_count > support_count` and ORDER BY `oppose_count DESC`):
- Use the same template as "Most Supported", but filter `HAVING SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END) > SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END)` and ORDER BY oppose_count DESC.
**Description**: Ranks by oppose count, filtered for oppose > support. Results: Top 15 "hated" bills.
**Notes**: Same adaptations for House/Senate.

### Most Neutral ("Meh") Bills (Raw Count, Filtered: Neutral > Support + Oppose)
**SQL** (Similar; change HAVING to neutral > support + oppose, ORDER BY neutral_count DESC):
- Template as above, but `HAVING SUM(CASE WHEN la.agent_position = 'Neutral' THEN 1 ELSE 0 END) > (SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END) + SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END))`.
**Description**: Ranks by neutral count, filtered for neutral dominant. Results: Top 15 non-controversial bills.
**Notes**: Same for House/Senate.

### Most Divisive Bills (Closest Support/Oppose Ratio, House/Senate Separate)
**House Version**:
```sql
WITH RankedInterests AS (
  SELECT la.house_senate, la.bill_or_agency, la.bill_title, c.business_interest,
    printf('%s (%d Support / %d Oppose)', c.business_interest,
      SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END),
      SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END)) AS interest_summary,
    ROW_NUMBER() OVER(PARTITION BY la.house_senate, la.bill_or_agency, la.bill_title ORDER BY COUNT(la.activity_id) DESC) AS rn
  FROM lobbying_activities AS la JOIN clients AS c ON la.client_name = c.client_name
  WHERE la.house_senate = 'House Bill' AND c.business_interest IS NOT NULL
  GROUP BY la.house_senate, la.bill_or_agency, la.bill_title, c.business_interest
),
TopThreeInterests AS (
  SELECT house_senate, bill_or_agency, bill_title, GROUP_CONCAT(interest_summary, '; ') AS top_interests_breakdown
  FROM RankedInterests WHERE rn <= 3 GROUP BY house_senate, bill_or_agency, bill_title
)
SELECT
  la.house_senate, la.bill_or_agency, la.bill_title, la.status,
  SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END) AS support_count,
  SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END) AS oppose_count,
  tti.top_interests_breakdown
FROM lobbying_activities AS la
LEFT JOIN TopThreeInterests AS tti ON la.house_senate = tti.house_senate AND la.bill_or_agency = tti.bill_or_agency AND la.bill_title = tti.bill_title
WHERE la.house_senate = 'House Bill'
GROUP BY la.house_senate, la.bill_or_agency, la.bill_title, la.status
HAVING support_count > 0 AND oppose_count > 0 AND (support_count + oppose_count) >= 10
ORDER BY ABS(CAST(support_count AS REAL) / oppose_count - 1) ASC
LIMIT 10;
```
**Senate Version**: Change `WHERE la.house_senate = 'House Bill'` to `'Senate Bill'` throughout.
**Description**: Ranks bills by ratio closest to 1:1 (most balanced support/oppose), with min 10 activities. Includes top 3 interests (raw counts). Results: Top 10 divisive bills per chamber.
**Notes**: Raw counts in breakdown; totals may not match top 3 due to other industries.

### View All Industries for a Specific Bill (Verification Query)
**SQL** (Example for House Bill 86):
```sql
SELECT
  c.business_interest,
  SUM(CASE WHEN la.agent_position = 'Support' THEN 1 ELSE 0 END) AS support_count,
  SUM(CASE WHEN la.agent_position = 'Oppose' THEN 1 ELSE 0 END) AS oppose_count,
  COUNT(la.activity_id) AS total_activities
FROM lobbying_activities AS la
JOIN clients AS c ON la.client_name = c.client_name
WHERE la.bill_or_agency = '86' AND la.house_senate = 'House Bill'
GROUP BY c.business_interest
ORDER BY total_activities DESC;
```
**Description**: Lists all industries for one bill with raw counts. Results: Full breakdown to verify totals.
**Notes**: Replace `'86'` and `'House Bill'` as needed.

## 3. Campaign Contributions Analysis

### Total and Count of Contributions per Official (Top 15)
**SQL**:
```sql
SELECT
  eo.full_name, eo.title, eo.party,
  COUNT(c.contribution_id) AS number_of_contributions,
  printf("$%,.2f", SUM(c.amount)) AS total_contributions_amount
FROM contributions AS c
JOIN elected_officials AS eo ON c.recipient_name LIKE '%' || eo.full_name || '%'
GROUP BY eo.full_name, eo.title, eo.party
ORDER BY SUM(c.amount) DESC
LIMIT 15;
```
**Description**: Ranks officials by total contributions received, with count. Results: Top 15 with name, title, party, count, and formatted total.
**Notes**: Requires `elected_officials` table; uses fuzzy name matching.

## 4. Meals, Entertainment, and Travel Expenses (MET) Analysis

Requires `elected_officials` table for accurate matching (via `LIKE '%' || full_name || '%'`) on `attendees`.

### Expenses with Elected Officials (Per-Official Cost, Top 25)
**SQL**:
Note: per-official cost only counts people appearing in the elected_officials table, not all attendees for the reported expense. Should be used for ballparking things at most,. 
```sql
WITH expense_official_counts AS (
  SELECT me.met_expense_id, COUNT(eo.full_name) AS official_count
  FROM met_expenses AS me
  JOIN elected_officials AS eo ON me.attendees LIKE '%' || eo.full_name || '%'
  GROUP BY me.met_expense_id
)
SELECT
  eo.full_name AS official_name, eo.title,
  me.attendees, me.amount AS total_expense, eoc.official_count,
  printf("$%.2f", me.amount / eoc.official_count) AS cost_per_official,
  dr.report_type,
  COALESCE(l.first_name || ' ' || l.last_name, c.client_name) AS reporting_entity
FROM met_expenses AS me
JOIN elected_officials AS eo ON me.attendees LIKE '%' || eo.full_name || '%'
JOIN expense_official_counts AS eoc ON me.met_expense_id = eoc.met_expense_id
JOIN disclosure_reports AS dr ON me.disclosure_id = dr.disclosure_id
LEFT JOIN lobbyists AS l ON dr.disclosure_id = l.disclosure_id AND dr.report_type IN ('Lobbyist', 'Lobbyist Entity')
LEFT JOIN clients AS c ON dr.disclosure_id = c.disclosure_id AND dr.report_type = 'Client'
ORDER BY (me.amount / eoc.official_count) DESC
LIMIT 25;
```
**Description**: Finds MET expenses mentioning officials, divides cost by # of officials per event, ranks by per-official cost. Includes verification (`attendees`), filer details. Results: Top 25 events with per-person costs.
**Notes**: Handles group events; uses CTE for counts.

### Officials Attending the Most Events (Top 15)
**SQL**:
```sql
SELECT
  eo.full_name, eo.title, eo.district,
  COUNT(me.met_expense_id) AS event_count
FROM met_expenses AS me
JOIN elected_officials AS eo ON me.attendees LIKE '%' || eo.full_name || '%'
GROUP BY eo.full_name, eo.title, eo.district
ORDER BY event_count DESC
LIMIT 15;
```
**Description**: Ranks officials by # of MET events attended. Results: Top 15 with counts.
**Notes**: Frequency-based.

### Detailed Reports for Top 15 Most Frequent Attendees
**SQL**:
```sql
WITH top_officials AS (
  SELECT eo.full_name
  FROM met_expenses AS me JOIN elected_officials AS eo ON me.attendees LIKE '%' || eo.full_name || '%'
  GROUP BY eo.full_name ORDER BY COUNT(me.met_expense_id) DESC LIMIT 15
)
SELECT
  dr.disclosure_id, eo.full_name AS official_name, me.date, me.payee_vendor,
  printf("$%.2f", me.amount) AS amount, me.attendees,
  COALESCE(l.first_name || ' ' || l.last_name, c.client_name) AS reporting_entity
FROM met_expenses AS me
JOIN elected_officials AS eo ON me.attendees LIKE '%' || eo.full_name || '%'
JOIN top_officials ON eo.full_name = top_officials.full_name
JOIN disclosure_reports AS dr ON me.disclosure_id = dr.disclosure_id
LEFT JOIN lobbyists AS l ON dr.disclosure_id = l.disclosure_id AND dr.report_type IN ('Lobbyist', 'Lobbyist Entity')
LEFT JOIN clients AS c ON dr.disclosure_id = c.disclosure_id AND dr.report_type = 'Client'
ORDER BY eo.full_name, me.date;
```
**Description**: Lists all MET expenses for top 15 frequent attendees, chronologically. Results: Detailed unaggregated list.
**Notes**: Uses CTE for top officials.

### Revised MET Query (Handles NULL Lobbyist Names, with Filer)
**SQL**:
```sql
SELECT
  dr.report_type,
  COALESCE(l.first_name || ' ' || l.last_name, c.client_name) AS reporting_entity,
  me.lobbyist_name, me.attendees, me.amount
FROM met_expenses AS me
JOIN disclosure_reports AS dr ON me.disclosure_id = dr.disclosure_id
LEFT JOIN lobbyists AS l ON dr.disclosure_id = l.disclosure_id AND dr.report_type IN ('Lobbyist', 'Lobbyist Entity')
LEFT JOIN clients AS c ON dr.disclosure_id = c.disclosure_id AND dr.report_type = 'Client'
WHERE me.attendees LIKE '%Rep.%' OR me.attendees LIKE '%Sen.%'
ORDER BY me.amount DESC
LIMIT 20;
```
**Description**: Shows MET expenses with legislators (keyword match), including filer (client/firm) for NULL `lobbyist_name`. Results: Top 20 by amount.
**Notes**: Older keyword version; prefer official name matching above.

