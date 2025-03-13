import requests
from datetime import date, datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import base64

# Jira Credentials
JIRA_URL = "https://cwcyprus-sales.atlassian.net"
JIRA_EMAIL = "webadmin@cwcyprus.com"
with open("JiraToken.txt", "r") as file:
    JIRA_API_TOKEN = file.read().strip()

# Jira Project and API Endpoint
JIRA_PROJECT_KEY = "SALES"
TRANSITIONS = {
    "Follow-up": 45
}

auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()

# Google Sheets API Setup
GOOGLE_SHEETS_CREDENTIALS_FILE = "credentials.json"
GOOGLE_SHEET_NAME = "Jira Sales API"
GOOGLE_SHEET_TAB_NAME = "Sheet1"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Basic {auth}"
}

def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    return client

def read_google_sheet(client):
    sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB_NAME)
    data = sheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    return df

def formate_date(date):
    parsed_date = datetime.strptime(date, "%m/%d/%Y")
    return parsed_date.strftime("%Y-%m-%d")

# Function to create an issue in Jira
def create_jira_issues(df):
    bulk_issue_data = {
        "issueUpdates": []
    }

    for _, row in df.iterrows():
        last_date = formate_date(row['Last Transaction Date'])
        days_diff = (date.today() - datetime.strptime(last_date, "%Y-%m-%d").date()).days
        if days_diff < 90:
            continue
        print(f"Days since last transaction: {days_diff}")

        summary = row['Customer Name']
        transaction_amount = row['Last Transaction Amount']
        email = row['Email']
        sms = row['SMS']
    
        issue_payload = {
            "fields": {
                "issuetype": {"id": 10003}, # Task issue hardcoded
                "project": {"key": JIRA_PROJECT_KEY},
                "summary": str(summary),
                "customfield_10050": str(last_date),
                "customfield_10037": float(transaction_amount),
                "customfield_10039": str(email),
                "customfield_10049": str(sms),
            }
        }

        bulk_issue_data["issueUpdates"].append(issue_payload)
    # print(json.dumps(bulk_issue_data, indent=4))

    response = requests.post(f"{JIRA_URL}/rest/api/3/issue/bulk", headers=HEADERS, json=bulk_issue_data)
    
    if response.status_code == 201:
        print(f"Issues created: {len(bulk_issue_data["issueUpdates"])}")
    else:
        print(f"Failed to create issue: {response.text}")

    keys = [issue['key'] for issue in response.json()['issues']]
    print(keys)
    return keys

def get_transitions(key):
    response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{key}/transitions", headers=HEADERS)

    if response.status_code == 200:
        print(f"Transitions for issue {key}:")
        print(response.json())
    else:
        print(f"Failed to get transitions: {response.text}")


def transition_to_needs_follow_up(transition, keys):
    transition_payload = {
        "transition": {"id": transition}
    }

    for key in keys:
        response = requests.post(f"{JIRA_URL}/rest/api/3/issue/{key}/transitions", json=transition_payload, headers=HEADERS)

        if response.status_code == 204:
            print(f"Issue {key} moved to 'Needs Follow Up'")
        else:
            print(f"Failed to transition issue: {response.text}")

def search_issues():
    params = {
        "jql": "project = 'SALES' AND status = 'Needs Follow-up'"
    }
    response = requests.get(f"{JIRA_URL}/rest/api/2/search/jql", params=params, headers=HEADERS)

    if response.status_code == 200:
        print(f"Found: {response.json()}")
        return response.json()["issues"]
    else:
        print(f"Failed to search issues: {response.text}")

    return ""

def get_issue(id):
    response = requests.get(f"{JIRA_URL}/rest/api/3/issue/{id}", headers=HEADERS)

    if response.status_code == 200:
        print(f"Found issue {id}")
        return response.json()["fields"]["summary"]
    else:
        print(f"Failed to get issue: {response.text}")

    return ""


def main():
    df = read_google_sheet(authenticate_google_sheets()) # read google sheet
    keys = create_jira_issues(df) # create jira issues in bulk
    transition_to_needs_follow_up(TRANSITIONS.get("Follow-up", 0), keys) # transition issues to 'Needs Follow-up'

    #print all issues in status 'Needs Follow-up'
    issues = search_issues()
    for issue in issues:
        print(get_issue(issue["id"]))
    

if __name__ == "__main__":
    main()
